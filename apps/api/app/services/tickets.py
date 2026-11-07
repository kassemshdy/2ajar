"""Support tickets created from the in-app "Report a bug" button.

Visibility rules:
* Reporters see their own tickets and public comments; they can reply (which reopens a resolved ticket).
* ``tickets.read`` sees every ticket including internal notes; ``tickets.manage`` can triage and comment.
* Anyone else gets 404 (no ticket enumeration).
Attachments are private and only served through the authorized ``/tickets/{id}/attachment`` endpoint, never
through the public ``/media`` route.
"""

import uuid
from collections.abc import Callable
from datetime import datetime

from fastapi import Request, UploadFile
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.authz.permissions import effective_permissions
from app.authz.policies import Principal
from app.core.config import Settings
from app.core.errors import Forbidden, NotFound, PayloadTooLarge, ValidationFailed
from app.core.events import EventRecorder
from app.core.security import utcnow
from app.domain.events import TicketCreated, TicketReplied
from app.models import Ticket, TicketComment, User
from app.models.enums import Permission, TicketPriority, TicketStatus
from app.schemas.tickets import (
    CommentCreate,
    CommentOut,
    PersonRef,
    TicketCreate,
    TicketOut,
    TicketSummary,
    TicketUpdate,
)
from app.services.audit import AuditTrail
from app.services.images import process_image
from app.storage import MediaNotFound, StorageBackend

Clock = Callable[[], datetime]
CLOSED_STATES = {TicketStatus.resolved, TicketStatus.closed}


def _is_staff_user(user: User | None) -> bool:
    return user is not None and Permission.tickets_read in effective_permissions(
        user.role, user.extra_permissions
    )


class TicketPresenter:
    """Shapes tickets for a given viewer: staff see e-mails and internal notes, reporters do not."""

    def __init__(self, viewer: Principal) -> None:
        self._staff = viewer.has(Permission.tickets_read)

    def person(self, user: User | None) -> PersonRef | None:
        if user is None:
            return None
        return PersonRef(id=user.id, name=user.full_name, email=user.email if self._staff else None)

    def summary(self, t: Ticket, comment_count: int | None = None) -> TicketSummary:
        reporter = self.person(t.reporter)
        assert reporter is not None
        visible = [c for c in t.comments if self._staff or not c.is_internal]
        return TicketSummary(
            id=t.id,
            number=t.number,
            title=t.title,
            category=t.category,
            status=t.status,
            priority=t.priority,
            reporter=reporter,
            assignee=self.person(t.assignee),
            comment_count=comment_count if comment_count is not None else len(visible),
            created_at=t.created_at,
            updated_at=t.updated_at,
        )

    def detail(self, t: Ticket) -> TicketOut:
        comments = [
            CommentOut(
                id=c.id,
                body=c.body,
                is_internal=c.is_internal,
                via=c.via,
                author=self.person(c.author),
                author_is_staff=_is_staff_user(c.author),
                created_at=c.created_at,
            )
            for c in t.comments
            if self._staff or not c.is_internal
        ]
        return TicketOut(
            **self.summary(t, len(comments)).model_dump(),
            description=t.description,
            page_url=t.page_url,
            context=t.context or {},
            has_attachment=t.attachment_key is not None,
            resolved_at=t.resolved_at,
            comments=comments,
        )


class TicketService:
    def __init__(
        self,
        session: AsyncSession,
        *,
        settings: Settings,
        storage: StorageBackend,
        events: EventRecorder,
        clock: Clock = utcnow,
    ) -> None:
        self._session = session
        self._settings = settings
        self._storage = storage
        self._events = events
        self._clock = clock
        self._audit = AuditTrail(session)

    # ---------- reporter side ----------

    async def create(self, p: Principal, data: TicketCreate, request: Request | None = None) -> Ticket:
        ticket = Ticket(
            reporter_user_id=p.user_id,
            category=data.category,
            title=data.title,
            description=data.description,
            page_url=data.page_url,
            context=data.context,
            status=TicketStatus.open,
            priority=TicketPriority.normal,
        )
        self._session.add(ticket)
        await self._session.flush()
        self._audit.record(p.user_id, "ticket.create", "ticket", ticket.id, request=request)
        await self._session.commit()
        loaded = await self._load(ticket.id)
        self._events.record(
            TicketCreated(
                number=loaded.number,
                title=loaded.title,
                category=loaded.category.value,
                reporter_name=loaded.reporter.full_name,
                page_url=loaded.page_url,
            )
        )
        return loaded

    async def attach(self, p: Principal, ticket_id: uuid.UUID, upload: UploadFile) -> Ticket:
        ticket = await self.get_visible(p, ticket_id)
        if ticket.reporter_user_id != p.user_id and not p.has(Permission.tickets_manage):
            raise Forbidden("Only the reporter can attach a screenshot")
        raw = await upload.read(self._settings.max_upload_bytes + 1)
        if len(raw) > self._settings.max_upload_bytes:
            raise PayloadTooLarge("Screenshots must be at most 8 MB")
        image = process_image(raw)  # same sniffing / EXIF stripping as listing photos
        key = f"tickets/{ticket.id}/{uuid.uuid4().hex}.webp"
        await self._storage.put(key, image.data, image.content_type)
        old = ticket.attachment_key
        ticket.attachment_key = key
        await self._session.commit()
        if old:
            await self._storage.delete(old)
        return await self._load(ticket.id)

    async def attachment(self, p: Principal, ticket_id: uuid.UUID) -> tuple[bytes, str]:
        ticket = await self.get_visible(p, ticket_id)
        if not ticket.attachment_key:
            raise NotFound("No attachment")
        try:
            return await self._storage.get(ticket.attachment_key)
        except MediaNotFound as exc:
            raise NotFound("No attachment") from exc

    async def list_mine(self, p: Principal, limit: int = 100) -> list[Ticket]:
        stmt = (
            select(Ticket)
            .where(Ticket.reporter_user_id == p.user_id)
            .order_by(Ticket.created_at.desc())
            .limit(limit)
        )
        return list((await self._session.scalars(stmt)).unique())

    # ---------- shared ----------

    async def get_visible(self, p: Principal, ticket_id: uuid.UUID) -> Ticket:
        ticket = await self._session.get(Ticket, ticket_id, populate_existing=True)
        if ticket is None or (ticket.reporter_user_id != p.user_id and not p.has(Permission.tickets_read)):
            raise NotFound("Ticket not found")
        return ticket

    async def get_by_number(self, p: Principal, number: int) -> Ticket:
        ticket_id = await self._session.scalar(select(Ticket.id).where(Ticket.number == number))
        if ticket_id is None:
            raise NotFound("Ticket not found")
        return await self.get_visible(p, ticket_id)

    async def comment(
        self,
        p: Principal,
        ticket_id: uuid.UUID,
        data: CommentCreate,
        *,
        via: str = "web",
        request: Request | None = None,
    ) -> Ticket:
        ticket = await self.get_visible(p, ticket_id)
        is_reporter = ticket.reporter_user_id == p.user_id
        is_manager = p.has(Permission.tickets_manage)
        if not (is_reporter or is_manager):
            raise Forbidden("You cannot comment on this ticket")
        if data.is_internal and not is_manager:
            raise Forbidden("Only staff can write internal notes")
        self._session.add(
            TicketComment(
                ticket_id=ticket.id,
                author_user_id=p.user_id,
                body=data.body,
                is_internal=data.is_internal,
                via=via,
            )
        )
        if is_reporter and not is_manager and ticket.status in CLOSED_STATES:
            ticket.status = TicketStatus.open  # a reply from the reporter reopens the conversation
            ticket.resolved_at = None
        ticket.updated_at = self._clock()
        await self._session.commit()
        loaded = await self._load(ticket.id)
        if not data.is_internal:
            self._events.record(
                TicketReplied(number=loaded.number, by_staff=is_manager and not is_reporter, via=via)
            )
        return loaded

    # ---------- staff side ----------

    async def search(
        self,
        *,
        status: TicketStatus | None = None,
        priority: TicketPriority | None = None,
        query: str | None = None,
        assignee_id: uuid.UUID | None = None,
        page: int = 1,
        page_size: int = 25,
    ) -> tuple[list[Ticket], int]:
        stmt = select(Ticket)
        if status:
            stmt = stmt.where(Ticket.status == status)
        if priority:
            stmt = stmt.where(Ticket.priority == priority)
        if assignee_id:
            stmt = stmt.where(Ticket.assignee_user_id == assignee_id)
        if query:
            like = f"%{query.strip().lower()}%"
            stmt = stmt.where(
                or_(func.lower(Ticket.title).like(like), func.lower(Ticket.description).like(like))
            )
        total = await self._session.scalar(select(func.count()).select_from(stmt.subquery())) or 0
        rows = await self._session.scalars(
            stmt.order_by(Ticket.created_at.desc()).offset((page - 1) * page_size).limit(page_size)
        )
        return list(rows.unique()), total

    async def update(
        self, p: Principal, ticket_id: uuid.UUID, data: TicketUpdate, request: Request | None = None
    ) -> Ticket:
        if not p.has(Permission.tickets_manage):
            raise Forbidden("You do not have permission to triage tickets")
        ticket = await self.get_visible(p, ticket_id)
        changes = data.model_dump(exclude_unset=True)
        if "assignee_user_id" in changes and changes["assignee_user_id"] is not None:
            assignee = await self._session.get(User, changes["assignee_user_id"])
            if assignee is None or not assignee.is_active or not _is_staff_user(assignee):
                raise ValidationFailed("Tickets can only be assigned to active staff members")
        for key, value in changes.items():
            if value is not None or key == "assignee_user_id":
                setattr(ticket, key, value)
        if "status" in changes:
            ticket.resolved_at = self._clock() if ticket.status in CLOSED_STATES else None
        self._audit.record(
            p.user_id,
            "ticket.update",
            "ticket",
            ticket.id,
            request=request,
            data={k: str(v) if v is not None else None for k, v in changes.items()},
        )
        await self._session.commit()
        return await self._load(ticket.id)

    async def stats(self) -> dict[str, int]:
        rows = await self._session.execute(select(Ticket.status, func.count()).group_by(Ticket.status))
        counts = {s.value: 0 for s in TicketStatus}
        counts.update({status.value: int(n) for status, n in rows.all()})
        return counts

    async def _load(self, ticket_id: uuid.UUID) -> Ticket:
        ticket = await self._session.get(Ticket, ticket_id, populate_existing=True)
        assert ticket is not None
        return ticket

import hashlib
import uuid
from datetime import UTC, datetime
from typing import Any

from fastapi import Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.ratelimit import client_ip
from app.models import AuditLog, ListingEvent
from app.models.enums import ListingEventType


def _hash(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def audit(
    session: AsyncSession,
    *,
    actor_id: uuid.UUID | None,
    action: str,
    resource_type: str,
    resource_id: uuid.UUID | None,
    data: dict[str, Any] | None = None,
    request: Request | None = None,
) -> None:
    session.add(
        AuditLog(
            actor_user_id=actor_id,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            data=data or {},
            ip_hash=_hash(client_ip(request)) if request else None,
        )
    )


def record_event(
    session: AsyncSession,
    *,
    listing_id: uuid.UUID,
    event_type: ListingEventType,
    user_id: uuid.UUID | None,
    request: Request | None,
) -> None:
    session_hash = None
    if request is not None:
        day = datetime.now(UTC).date().isoformat()
        ua = request.headers.get("user-agent", "")[:200]
        # Daily-rotating pseudonymous visitor hash: counts unique visitors without storing IPs.
        session_hash = _hash(f"{client_ip(request)}|{ua}|{day}")
    session.add(
        ListingEvent(listing_id=listing_id, event_type=event_type, user_id=user_id, session_hash=session_hash)
    )


class AuditTrail:
    """Session-bound convenience wrapper so services don't repeat audit plumbing."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    def record(
        self,
        actor_id: uuid.UUID | None,
        action: str,
        resource_type: str,
        resource_id: uuid.UUID | None,
        *,
        request: Request | None = None,
        data: dict[str, Any] | None = None,
    ) -> None:
        audit(
            self._session,
            actor_id=actor_id,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            data=data,
            request=request,
        )

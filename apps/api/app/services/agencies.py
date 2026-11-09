"""Agencies: the public agency page and staff verification (the "verified" badge)."""

import uuid
from collections.abc import Callable
from datetime import datetime, timedelta

from fastapi import Request
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.authz.policies import Principal
from app.core.config import Settings
from app.core.errors import NotFound
from app.core.security import utcnow
from app.models import Favorite, Lead, Listing, ListingEvent, Organization, OrganizationMember
from app.models.enums import ListingEventType
from app.repositories.listings import ListingSpecs
from app.schemas.admin import AdminAgencyOut
from app.schemas.listing import ListingStats
from app.services.audit import AuditTrail

AGENCY_PAGE_LIMIT = 60


class AgencyService:
    def __init__(
        self, session: AsyncSession, *, settings: Settings, clock: Callable[[], datetime] = utcnow
    ) -> None:
        self._session = session
        self._settings = settings
        self._now = clock()
        self._audit = AuditTrail(session)

    def _visible(self) -> object:
        return ListingSpecs.publicly_visible(self._now, self._settings.demo_mode)

    async def public_page(self, slug: str) -> tuple[Organization, list[Listing], int]:
        """The agency and its public listings (newest first). 404 for unknown agencies and, outside demo mode,
        for demo agencies, exactly like demo listings."""
        org = await self._session.scalar(select(Organization).where(Organization.slug == slug))
        if org is None or (org.is_demo and not self._settings.demo_mode):
            raise NotFound("Agency not found")
        listings = list(
            (
                await self._session.scalars(
                    select(Listing)
                    .where(Listing.organization_id == org.id, self._visible())  # type: ignore[arg-type]
                    .order_by(Listing.published_at.desc())
                    .limit(AGENCY_PAGE_LIMIT)
                )
            ).unique()
        )
        members = int(
            await self._session.scalar(
                select(func.count())
                .select_from(OrganizationMember)
                .where(OrganizationMember.organization_id == org.id)
            )
            or 0
        )
        return org, listings, members

    # ---------- staff ----------

    async def admin_list(self) -> list[AdminAgencyOut]:
        members = (
            select(OrganizationMember.organization_id, func.count().label("n"))
            .group_by(OrganizationMember.organization_id)
            .subquery()
        )
        live = (
            select(Listing.organization_id, func.count().label("n"))
            .where(self._visible())  # type: ignore[arg-type]
            .group_by(Listing.organization_id)
            .subquery()
        )
        rows = (
            await self._session.execute(
                select(Organization, func.coalesce(members.c.n, 0), func.coalesce(live.c.n, 0))
                .outerjoin(members, members.c.organization_id == Organization.id)
                .outerjoin(live, live.c.organization_id == Organization.id)
                .order_by(Organization.is_verified, func.coalesce(live.c.n, 0).desc(), Organization.name)
            )
        ).all()
        return [
            AdminAgencyOut(
                id=o.id,
                name=o.name,
                slug=o.slug,
                is_verified=o.is_verified,
                is_demo=o.is_demo,
                members=int(m),
                live_listings=int(n),
                created_at=o.created_at,
            )
            for o, m, n in rows
        ]

    async def set_verified(
        self, p: Principal, agency_id: uuid.UUID, verified: bool, request: Request | None = None
    ) -> AdminAgencyOut:
        org = await self._session.get(Organization, agency_id)
        if org is None:
            raise NotFound("Agency not found")
        if org.is_verified != verified:
            org.is_verified = verified
            self._audit.record(
                p.user_id,
                "agency.verify" if verified else "agency.unverify",
                "organization",
                org.id,
                request=request,
            )
            await self._session.commit()
        return next(a for a in await self.admin_list() if a.id == agency_id)

    # ---------- stats for whoever manages listings ----------

    async def listing_stats(self, listing_ids: list[uuid.UUID]) -> dict[uuid.UUID, ListingStats]:
        """Visitors, WhatsApp taps and leads in the last 30 days, plus total saves, per listing."""
        if not listing_ids:
            return {}
        since = self._now - timedelta(days=30)

        async def grouped(stmt: object) -> dict[uuid.UUID, int]:
            return {i: int(n) for i, n in (await self._session.execute(stmt)).all()}  # type: ignore[call-overload]

        def events(kind: ListingEventType, distinct_visitors: bool) -> object:
            n = func.count(func.distinct(ListingEvent.session_hash)) if distinct_visitors else func.count()
            return (
                select(ListingEvent.listing_id, n)
                .where(
                    ListingEvent.listing_id.in_(listing_ids),
                    ListingEvent.event_type == kind,
                    ListingEvent.created_at > since,
                )
                .group_by(ListingEvent.listing_id)
            )

        visitors = await grouped(events(ListingEventType.view, True))
        whatsapp = await grouped(events(ListingEventType.whatsapp_click, False))
        leads = await grouped(
            select(Lead.listing_id, func.count())
            .where(Lead.listing_id.in_(listing_ids), Lead.created_at > since)
            .group_by(Lead.listing_id)
        )
        saves = await grouped(
            select(Favorite.listing_id, func.count())
            .where(Favorite.listing_id.in_(listing_ids))
            .group_by(Favorite.listing_id)
        )
        return {
            i: ListingStats(
                visitors_30d=visitors.get(i, 0),
                whatsapp_30d=whatsapp.get(i, 0),
                leads_30d=leads.get(i, 0),
                saves=saves.get(i, 0),
            )
            for i in listing_ids
        }

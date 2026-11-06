"""Persistence for leads."""

import uuid
from datetime import datetime

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.authz.policies import Principal
from app.models import Lead, Listing
from app.repositories.listings import ListingSpecs


class LeadRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    def add(self, lead: Lead) -> None:
        self._session.add(lead)

    async def lock_contact(self, listing_id: uuid.UUID, phone_e164: str) -> None:
        """Serialize concurrent submissions for one listing+phone (transaction-scoped advisory lock).

        This makes dedupe race-free without a unique constraint, which could not express "within 24h".
        """
        await self._session.execute(
            text("SELECT pg_advisory_xact_lock(hashtextextended(:k, 0))"),
            {"k": f"lead:{listing_id}:{phone_e164}"},
        )

    async def recent_from(self, listing_id: uuid.UUID, phone_e164: str, since: datetime) -> Lead | None:
        stmt = (
            select(Lead)
            .where(Lead.listing_id == listing_id, Lead.phone_e164 == phone_e164, Lead.created_at > since)
            .order_by(Lead.created_at.desc())
            .limit(1)
        )
        return await self._session.scalar(stmt)

    async def inbox(
        self, p: Principal, listing_id: uuid.UUID | None = None, limit: int = 200
    ) -> list[tuple[Lead, Listing]]:
        """Leads on listings ``p`` may manage, most recent contact first.

        Orders by the NOT NULL ``last_contact_at`` column directly (no COALESCE) so the
        (listing_id, last_contact_at DESC) index can serve it.
        """
        stmt = (
            select(Lead, Listing)
            .join(Listing, Listing.id == Lead.listing_id)
            .where(ListingSpecs.manageable_by(p))
            .order_by(Lead.last_contact_at.desc())
            .limit(limit)
        )
        if listing_id is not None:
            stmt = stmt.where(Lead.listing_id == listing_id)
        rows = (await self._session.execute(stmt)).unique().all()
        return [(row[0], row[1]) for row in rows]

"""Persistence for listings (Repository pattern).

All SQL about listings lives here; services express *intent* ("search published listings", "load one I may
manage") and never build queries. The query shapes match the indexes added in migration 0002 — see
docs/DATABASE.md "Index strategy" for the measured plans.
"""

import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Literal

from sqlalchemy import ColumnElement, and_, false, func, or_, select, true
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import contains_eager

from app.authz.policies import ListingRef, Principal
from app.models import Lead, Listing, Location, Property
from app.models.enums import STAY_PERIODS, Furnished, ListingStatus, PropertyType, Stay, TransactionType

SortOrder = Literal["newest", "price_asc", "price_desc"]


@dataclass(frozen=True)
class SearchCriteria:
    """Validated public search filters. Prices are whole USD."""

    transaction_type: TransactionType | None = None
    location_path: str | None = None  # resolved from a slug by the caller (cached directory)
    price_min: int | None = None
    price_max: int | None = None
    bedrooms_min: int | None = None
    bathrooms_min: int | None = None
    furnished: Furnished | None = None
    property_type: PropertyType | None = None
    stay: Stay | None = None  # hours / nights / months: groups of price periods
    guests_min: int | None = None
    sort: SortOrder = "newest"
    page: int = 1
    page_size: int = 20


def as_ref(listing: Listing) -> ListingRef:
    """Project an ORM listing onto the minimal shape the authorization policies need."""
    return ListingRef(
        created_by_user_id=listing.created_by_user_id,
        organization_id=listing.organization_id,
        status=listing.status,
        expires_at=listing.expires_at,
        is_demo=listing.is_demo,
        is_rental=listing.transaction_type == TransactionType.rent,
    )


class ListingSpecs:
    """SQL counterparts of ``app.authz.policies`` (Specification pattern).

    Policies decide for one loaded object; these filter whole result sets in the database. The two must
    stay equivalent — tests exercise both sides with the same scenarios.
    """

    @staticmethod
    def publicly_visible(now: datetime, include_demo: bool) -> ColumnElement[bool]:
        return and_(
            Listing.status == ListingStatus.published,
            Listing.transaction_type == TransactionType.rent,
            or_(Listing.expires_at.is_(None), Listing.expires_at > now),
            true() if include_demo else Listing.is_demo.is_(False),
        )

    @staticmethod
    def manageable_by(p: Principal) -> ColumnElement[bool]:
        if p.is_admin:
            return true()
        conditions: list[ColumnElement[bool]] = [Listing.created_by_user_id == p.user_id]
        if p.admin_org_ids:
            conditions.append(Listing.organization_id.in_(p.admin_org_ids))
        return or_(*conditions) if conditions else false()


_ORDERINGS: dict[SortOrder, tuple[ColumnElement[Any], ...]] = {
    "newest": (Listing.published_at.desc(), Listing.id.asc()),
    "price_asc": (Listing.price_usd_cents.asc(), Listing.id.asc()),
    "price_desc": (Listing.price_usd_cents.desc(), Listing.id.asc()),
}


class ListingRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get(self, listing_id: uuid.UUID) -> Listing | None:
        # populate_existing: always reflect the latest committed state, even if the identity map has it.
        stmt = select(Listing).where(Listing.id == listing_id).execution_options(populate_existing=True)
        return await self._session.scalar(stmt)

    def add(self, *items: Property | Listing) -> None:
        self._session.add_all(items)

    async def flush(self) -> None:
        await self._session.flush()

    async def search(
        self, criteria: SearchCriteria, *, now: datetime, include_demo: bool
    ) -> tuple[list[Listing], int]:
        stmt = (
            select(Listing)
            .join(Listing.property)
            .join(Property.location)
            # Reuse the explicit joins for eager loading instead of joining the same tables twice.
            .options(contains_eager(Listing.property).contains_eager(Property.location))
            .where(ListingSpecs.publicly_visible(now, include_demo))
        )
        c = criteria
        if c.transaction_type:
            stmt = stmt.where(Listing.transaction_type == c.transaction_type)
        if c.location_path:
            # Materialized path + text_pattern_ops index => subtree query without recursion.
            stmt = stmt.where(
                or_(Location.path == c.location_path, Location.path.startswith(c.location_path + "/"))
            )
        if c.price_min is not None:
            stmt = stmt.where(Listing.price_usd_cents >= c.price_min * 100)
        if c.price_max is not None:
            stmt = stmt.where(Listing.price_usd_cents <= c.price_max * 100)
        if c.bedrooms_min is not None:
            stmt = stmt.where(Property.bedrooms >= c.bedrooms_min)
        if c.bathrooms_min is not None:
            stmt = stmt.where(Property.bathrooms >= c.bathrooms_min)
        if c.furnished:
            stmt = stmt.where(Property.furnished == c.furnished)
        if c.property_type:
            stmt = stmt.where(Property.property_type == c.property_type)
        if c.stay:
            stmt = stmt.where(Listing.price_period.in_(STAY_PERIODS[c.stay]))
        if c.guests_min is not None:
            stmt = stmt.where(Property.max_guests >= c.guests_min)

        total = await self._session.scalar(select(func.count()).select_from(stmt.order_by(None).subquery()))
        page = stmt.order_by(*_ORDERINGS[c.sort]).offset((c.page - 1) * c.page_size).limit(c.page_size)
        items = list((await self._session.scalars(page)).unique())
        return items, total or 0

    async def manageable_with_lead_counts(self, p: Principal, limit: int = 200) -> list[tuple[Listing, int]]:
        # Correlated count per returned row (uses ix_leads_listing_last_contact) instead of aggregating the
        # whole leads table: 80 ms -> 2 ms at 150k listings / 60k leads.
        lead_count = (
            select(func.count()).select_from(Lead).where(Lead.listing_id == Listing.id).scalar_subquery()
        )
        stmt = (
            select(Listing, lead_count)
            .where(ListingSpecs.manageable_by(p))
            .order_by(Listing.updated_at.desc())
            .limit(limit)
        )
        rows = (await self._session.execute(stmt)).unique().all()
        return [(row[0], int(row[1])) for row in rows]

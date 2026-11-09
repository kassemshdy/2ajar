"""Read-only queries behind the home-page rows (Airbnb-style discovery).

Every query starts from ``ListingSpecs.publicly_visible`` so a row can never show a draft, an expired, a demo
(outside demo mode) or a legacy sale listing. Queries return ids plus a metric, then load the listings in one
batch, so a row costs two or three queries whatever its length.
"""

import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import Float, and_, cast, func, literal, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from app.models import AreaProfile, Favorite, Listing, ListingEvent, Location, Property
from app.models.enums import STAY_PERIODS, ListingEventType, PricePeriod, Stay
from app.repositories.listings import ListingSpecs

KM_PER_DEGREE = 111.32
POPULAR_WINDOW_DAYS = 30
GREAT_VALUE_RATIO = 0.85  # at least 15 % below the area's median price per m²
GREAT_VALUE_MIN_PEERS = 3  # a median needs enough comparable listings to mean anything


@dataclass(frozen=True)
class Scored:
    listing: Listing
    value: float  # views, km or "fraction of the area median", depending on the row


@dataclass(frozen=True)
class AreaRank:
    profile: AreaProfile
    listing_count: int


class DiscoveryRepository:
    def __init__(self, session: AsyncSession, *, now: datetime, include_demo: bool) -> None:
        self._session = session
        self._now = now
        self._include_demo = include_demo

    def _visible(self) -> object:
        return ListingSpecs.publicly_visible(self._now, self._include_demo)

    async def _load(self, ids: list[uuid.UUID]) -> dict[uuid.UUID, Listing]:
        if not ids:
            return {}
        rows = await self._session.scalars(select(Listing).where(Listing.id.in_(ids)))
        return {x.id: x for x in rows.unique()}

    async def _scored(self, rows: list[tuple[uuid.UUID, Any]]) -> list[Scored]:
        loaded = await self._load([i for i, _ in rows])
        return [Scored(loaded[i], float(v)) for i, v in rows if i in loaded]

    async def most_viewed(self, limit: int) -> list[Scored]:
        """Listings with the most visitors in the last 30 days (only listings that have any)."""
        since = self._now - timedelta(days=POPULAR_WINDOW_DAYS)
        # Distinct daily visitor hashes, not raw hits: reloading a page can't push a listing up the row.
        views = func.count(func.distinct(ListingEvent.session_hash))
        stmt = (
            select(Listing.id, views)
            .join(ListingEvent, ListingEvent.listing_id == Listing.id)
            .where(
                self._visible(),  # type: ignore[arg-type]
                ListingEvent.event_type == ListingEventType.view,
                ListingEvent.created_at > since,
            )
            .group_by(Listing.id)
            .order_by(views.desc(), Listing.published_at.desc())
            .limit(limit)
        )
        return await self._scored([(i, v) for i, v in (await self._session.execute(stmt)).all()])

    async def great_value(self, limit: int) -> list[Scored]:
        """Monthly rentals priced well below the median price per m² of their own area.

        ``value`` is the listing's price per m² as a fraction of that median (0.7 = 30 % below).
        """
        per_sqm = cast(Listing.price_usd_cents, Float) / Property.area_sqm
        comparable = and_(
            self._visible(),  # type: ignore[arg-type]
            Listing.price_period == PricePeriod.monthly,
            Property.area_sqm > 0,
        )
        medians = (
            select(
                Property.location_id.label("location_id"),
                func.percentile_cont(0.5).within_group(per_sqm).label("median"),
            )
            .join(Listing.property)
            .where(comparable)
            .group_by(Property.location_id)
            .having(func.count() >= GREAT_VALUE_MIN_PEERS)
            .subquery()
        )
        ratio = per_sqm / medians.c.median
        stmt = (
            select(Listing.id, ratio)
            .join(Listing.property)
            .join(medians, medians.c.location_id == Property.location_id)
            .where(comparable, ratio <= GREAT_VALUE_RATIO)
            .order_by(ratio.asc(), Listing.id)
            .limit(limit)
        )
        return await self._scored([(i, v) for i, v in (await self._session.execute(stmt)).all()])

    async def nearby(
        self,
        lat: float,
        lng: float,
        limit: int,
        *,
        stay: Stay | None = None,
        exclude: uuid.UUID | None = None,
        max_km: float | None = None,
    ) -> list[Scored]:
        """Closest listings to a point (equirectangular distance: accurate to metres at Lebanon's scale).

        A property without its own coordinates uses its area's centre.
        """
        plat = cast(func.coalesce(Property.lat, Location.lat), Float)
        plng = cast(func.coalesce(Property.lng, Location.lng), Float)
        dx = (plng - literal(lng)) * func.cos(func.radians(literal(lat)))
        dy = plat - literal(lat)
        km = func.sqrt(dx * dx + dy * dy) * KM_PER_DEGREE
        stmt = (
            select(Listing.id, km)
            .join(Listing.property)
            .join(Property.location)
            .where(self._visible(), plat.is_not(None), plng.is_not(None))  # type: ignore[arg-type]
        )
        if stay:
            stmt = stmt.where(Listing.price_period.in_(STAY_PERIODS[stay]))
        if exclude:
            stmt = stmt.where(Listing.id != exclude)
        if max_km is not None:
            stmt = stmt.where(km <= max_km)
        stmt = stmt.order_by(km.asc(), Listing.published_at.desc()).limit(limit)
        return await self._scored([(i, v) for i, v in (await self._session.execute(stmt)).all()])

    async def top_areas(self, limit: int) -> list[AreaRank]:
        """Areas with curated profiles, best safety + quiet first, that have at least one public listing.

        Counts include listings in child areas (a district profile covers its neighbourhoods).
        """
        area_loc = aliased(Location)
        listing_loc = aliased(Location)
        listings = func.count(func.distinct(Listing.id))
        score = func.coalesce(AreaProfile.safety_score, 0) + func.coalesce(AreaProfile.quiet_score, 0)
        stmt = (
            select(AreaProfile, listings)
            .join(area_loc, area_loc.id == AreaProfile.location_id)
            .join(
                listing_loc,
                or_(listing_loc.path == area_loc.path, listing_loc.path.startswith(area_loc.path + "/")),
            )
            .join(Property, Property.location_id == listing_loc.id)
            .join(Listing, Listing.property_id == Property.id)
            .where(
                self._visible(),  # type: ignore[arg-type]
                or_(AreaProfile.safety_score.is_not(None), AreaProfile.quiet_score.is_not(None)),
            )
            .group_by(AreaProfile.id, area_loc.path)
            .order_by(score.desc(), listings.desc(), area_loc.path)
            .limit(limit)
        )
        if not self._include_demo:
            stmt = stmt.where(AreaProfile.is_demo.is_(False))
        rows = (await self._session.execute(stmt)).unique().all()
        return [AreaRank(profile, int(n)) for profile, n in rows]

    async def counts_by_location(self) -> dict[uuid.UUID, int]:
        """Number of public listings per location (the location a property is in, not its ancestors)."""
        stmt = (
            select(Property.location_id, func.count(Listing.id))
            .join(Listing, Listing.property_id == Property.id)
            .where(self._visible())  # type: ignore[arg-type]
            .group_by(Property.location_id)
        )
        return {loc: int(n) for loc, n in (await self._session.execute(stmt)).all()}

    # ---------- favorites ----------

    async def favorite_ids(self, user_id: uuid.UUID) -> list[uuid.UUID]:
        stmt = (
            select(Favorite.listing_id)
            .where(Favorite.user_id == user_id)
            .order_by(Favorite.created_at.desc())
        )
        return list((await self._session.scalars(stmt)).all())

    async def favorites(self, user_id: uuid.UUID, limit: int = 200) -> list[Listing]:
        """Saved listings that are still public, newest save first (a paused listing quietly drops out)."""
        stmt = (
            select(Listing)
            .join(Favorite, and_(Favorite.listing_id == Listing.id, Favorite.user_id == user_id))
            .where(self._visible())  # type: ignore[arg-type]
            .order_by(Favorite.created_at.desc())
            .limit(limit)
        )
        return list((await self._session.scalars(stmt)).unique())

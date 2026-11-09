"""Airbnb-style discovery: home-page rows, homes near a point, similar homes and favorites."""

import uuid
from collections.abc import Callable
from datetime import datetime

from fastapi import Request
from sqlalchemy import delete
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.authz.policies import Principal
from app.core.config import Settings
from app.core.security import utcnow
from app.models import Favorite, Listing
from app.models.enums import STAY_PERIODS, ListingEventType, LocationLevel, Stay
from app.repositories.discovery import DiscoveryRepository, Scored
from app.repositories.listings import SearchCriteria
from app.repositories.locations import LocationRecord
from app.schemas.discovery import AreaRow, DiscoverOut, NearbyListing, RankedArea, ValueListing, ViewedListing
from app.services.audit import record_event
from app.services.listings import ListingService
from app.services.presenters import ListingPresenter as present

ROW_SIZE = 12
AREA_ROWS = 4
AREA_ROW_MIN = 3  # a place needs a few homes before it gets its own row
NEARBY_MAX_KM = 40.0  # Lebanon is ~200 km long; beyond this "near you" stops being true


def _near(hits: list[Scored]) -> list[NearbyListing]:
    return [NearbyListing(listing=present.to_public(h.listing), distance_km=round(h.value, 1)) for h in hits]


def _stay_of(listing: Listing) -> Stay | None:
    return next((s for s, periods in STAY_PERIODS.items() if listing.price_period in periods), None)


class DiscoveryService:
    def __init__(
        self,
        session: AsyncSession,
        *,
        settings: Settings,
        listings: ListingService,
        clock: Callable[[], datetime] = utcnow,
    ) -> None:
        self._session = session
        self._listings = listings
        self._repo = DiscoveryRepository(session, now=clock(), include_demo=settings.demo_mode)

    async def _row(self, stay: Stay | None = None) -> list[Listing]:
        items, _ = await self._listings.search(SearchCriteria(stay=stay, page_size=ROW_SIZE), None)
        return items

    async def home(self) -> DiscoverOut:
        viewed = await self._repo.most_viewed(ROW_SIZE)
        value = await self._repo.great_value(ROW_SIZE)
        ranked = await self._repo.top_areas(8)
        by_area = await self._area_rows()
        return DiscoverOut(
            by_area=by_area,
            recent=[present.to_public(x) for x in await self._row()],
            nights=[present.to_public(x) for x in await self._row(Stay.nights)],
            hours=[present.to_public(x) for x in await self._row(Stay.hours)],
            most_viewed=[
                ViewedListing(listing=present.to_public(s.listing), visitors_30d=int(s.value)) for s in viewed
            ],
            great_value=[
                ValueListing(
                    listing=present.to_public(s.listing), below_area_median_pct=round((1 - s.value) * 100)
                )
                for s in value
            ],
            top_areas=[
                RankedArea(area=area, listing_count=r.listing_count)
                for r in ranked
                if (area := present.area(r.profile)) is not None
            ],
        )

    async def _area_rows(self) -> list[AreaRow]:
        """Rows per place, busiest first: neighbourhoods, or their district / city when homes are spread thin.

        A place qualifies with at least AREA_ROW_MIN public homes in it or below it. Rows never overlap: once
        "Beirut" has a row, "Hamra" (inside it) doesn't get another, and vice versa.
        """
        snapshot = await self._listings.locations.snapshot()
        totals: dict[uuid.UUID, int] = {}
        for location_id, n in (await self._repo.counts_by_location()).items():
            current = snapshot.by_id.get(location_id)
            while current is not None:  # a home counts for its area and every place above it
                totals[current.id] = totals.get(current.id, 0) + n
                current = snapshot.by_id.get(current.parent_id) if current.parent_id else None

        def eligible(rec: LocationRecord) -> bool:
            # Governorates are too broad ("Mount Lebanon"), except a city with no districts below it (Beirut).
            has_district = any(
                r.parent_id == rec.id and r.level == LocationLevel.district for r in snapshot.records
            )
            return rec.level != LocationLevel.governorate or not has_district

        candidates = sorted(
            (snapshot.by_id[i] for i, n in totals.items() if n >= AREA_ROW_MIN and i in snapshot.by_id),
            key=lambda r: (-totals[r.id], r.path),
        )
        picked: list[LocationRecord] = []
        for rec in candidates:
            overlaps = any(
                rec.path == p.path or rec.path.startswith(p.path + "/") or p.path.startswith(rec.path + "/")
                for p in picked
            )
            if eligible(rec) and not overlaps:
                picked.append(rec)
            if len(picked) == AREA_ROWS:
                break

        rows: list[AreaRow] = []
        for loc in picked:
            items, _ = await self._listings.search(SearchCriteria(page_size=ROW_SIZE), loc.slug)
            if not items:
                continue
            parent = snapshot.by_id.get(loc.parent_id) if loc.parent_id else None
            short = sum(1 for x in items if _stay_of(x) in (Stay.hours, Stay.nights))
            rows.append(
                AreaRow(
                    slug=loc.slug,
                    name_en=loc.name_en,
                    name_ar=loc.name_ar,
                    parent_en=parent.name_en if parent else None,
                    parent_ar=parent.name_ar if parent else None,
                    kind="stays" if short * 2 > len(items) else "homes",
                    listings=[present.to_public(x) for x in items],
                )
            )
        return rows

    async def nearby(self, lat: float, lng: float, stay: Stay | None, limit: int) -> list[NearbyListing]:
        hits = await self._repo.nearby(lat, lng, limit, stay=stay, max_km=NEARBY_MAX_KM)
        return [
            NearbyListing(listing=present.to_public(h.listing), distance_km=round(h.value, 1)) for h in hits
        ]

    async def similar(self, listing_id: uuid.UUID, limit: int) -> list[NearbyListing]:
        """Closest public homes rented for the same kind of stay (404 if the listing isn't public)."""
        base = await self._listings.get_public(listing_id)
        prop = base.property
        lat = prop.lat if prop.lat is not None else prop.location.lat
        lng = prop.lng if prop.lng is not None else prop.location.lng
        if lat is None or lng is None:
            return []
        hits = await self._repo.nearby(
            float(lat), float(lng), limit, stay=_stay_of(base), exclude=base.id, max_km=NEARBY_MAX_KM
        )
        return [
            NearbyListing(listing=present.to_public(h.listing), distance_km=round(h.value, 1)) for h in hits
        ]

    # ---------- favorites ----------

    async def favorite_ids(self, p: Principal) -> list[uuid.UUID]:
        return await self._repo.favorite_ids(p.user_id)

    async def favorites(self, p: Principal) -> list[Listing]:
        return await self._repo.favorites(p.user_id)

    async def save(self, p: Principal, listing_id: uuid.UUID, request: Request | None = None) -> None:
        """Idempotent. Only public listings can be saved (404 otherwise, like every private resource)."""
        await self._listings.get_public(listing_id)
        inserted = await self._session.scalar(
            insert(Favorite)
            .values(user_id=p.user_id, listing_id=listing_id)
            .on_conflict_do_nothing()
            .returning(Favorite.listing_id)
        )
        if inserted is not None:  # first save only: re-saving must not inflate the favorite count
            record_event(
                self._session,
                listing_id=listing_id,
                event_type=ListingEventType.favorite,
                user_id=p.user_id,
                request=request,
            )
        await self._session.commit()

    async def unsave(self, p: Principal, listing_id: uuid.UUID) -> None:
        await self._session.execute(
            delete(Favorite).where(Favorite.user_id == p.user_id, Favorite.listing_id == listing_id)
        )
        await self._session.commit()

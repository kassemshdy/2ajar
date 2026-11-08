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
from app.models.enums import STAY_PERIODS, ListingEventType, Stay
from app.repositories.discovery import DiscoveryRepository, Scored
from app.repositories.listings import SearchCriteria
from app.schemas.discovery import DiscoverOut, NearbyListing, RankedArea, ValueListing, ViewedListing
from app.services.audit import record_event
from app.services.listings import ListingService
from app.services.presenters import ListingPresenter as present

ROW_SIZE = 12
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
        return DiscoverOut(
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

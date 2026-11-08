"""Discovery (home-page rows, near me, similar homes) and favorites. Thin adapters over DiscoveryService.

Registered before the listings router so ``/listings/nearby`` is not captured by ``/listings/{listing_id}``.
"""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request, Response, status

from app.api.deps import PrincipalDep
from app.api.providers import DiscoveryDep
from app.core.ratelimit import rate_limit
from app.models.enums import Stay
from app.schemas.discovery import DiscoverOut, FavoriteIds, NearbyListing
from app.schemas.listing import ListingPublic
from app.services.presenters import ListingPresenter as present

router = APIRouter(tags=["discover"])

PUBLIC_CACHE = "public, max-age=30, stale-while-revalidate=120"


@router.get("/discover", response_model=DiscoverOut)
async def discover(service: DiscoveryDep, response: Response) -> DiscoverOut:
    response.headers["Cache-Control"] = PUBLIC_CACHE
    return await service.home()


@router.get(
    "/listings/nearby",
    response_model=list[NearbyListing],
    dependencies=[Depends(rate_limit("nearby", 120, 600))],
)
async def nearby(
    service: DiscoveryDep,
    lat: Annotated[float, Query(ge=-90, le=90)],
    lng: Annotated[float, Query(ge=-180, le=180)],
    stay: Stay | None = None,
    limit: Annotated[int, Query(ge=1, le=24)] = 12,
) -> list[NearbyListing]:
    # Coordinates are used for this query only: never stored or logged.
    return await service.nearby(lat, lng, stay, limit)


@router.get("/listings/{listing_id}/similar", response_model=list[NearbyListing])
async def similar(
    listing_id: uuid.UUID,
    service: DiscoveryDep,
    response: Response,
    limit: Annotated[int, Query(ge=1, le=12)] = 8,
) -> list[NearbyListing]:
    response.headers["Cache-Control"] = PUBLIC_CACHE
    return await service.similar(listing_id, limit)


# ---------- favorites (signed in) ----------


@router.get("/me/favorites", response_model=list[ListingPublic])
async def my_favorites(p: PrincipalDep, service: DiscoveryDep) -> list[ListingPublic]:
    return [present.to_public(x) for x in await service.favorites(p)]


@router.get("/me/favorites/ids", response_model=FavoriteIds)
async def my_favorite_ids(p: PrincipalDep, service: DiscoveryDep) -> FavoriteIds:
    return FavoriteIds(listing_ids=[str(i) for i in await service.favorite_ids(p)])


@router.put(
    "/me/favorites/{listing_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(rate_limit("favorite", 120, 600))],
)
async def save_favorite(
    listing_id: uuid.UUID, request: Request, p: PrincipalDep, service: DiscoveryDep
) -> None:
    await service.save(p, listing_id, request)


@router.delete("/me/favorites/{listing_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_favorite(listing_id: uuid.UUID, p: PrincipalDep, service: DiscoveryDep) -> None:
    await service.unsave(p, listing_id)

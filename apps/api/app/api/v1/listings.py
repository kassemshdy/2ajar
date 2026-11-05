import uuid
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, File, Query, Request, Response, UploadFile, status

from app.api.deps import OptionalPrincipal, OptionalUser, PrincipalDep, SessionDep
from app.authz.policies import can_manage_listing
from app.core.ratelimit import rate_limit
from app.models.enums import Furnished, PropertyType, TransactionType
from app.schemas.common import Page
from app.schemas.lead import LeadCreate, LeadReceipt
from app.schemas.listing import (
    ListingCreate,
    ListingPrivate,
    ListingPublic,
    ListingUpdate,
    MediaOut,
    WhatsAppHandoffOut,
)
from app.services import leads as lead_service
from app.services import listings as svc
from app.storage import get_storage

router = APIRouter(prefix="/listings", tags=["listings"])


@router.get("", response_model=Page[ListingPublic])
async def search(
    session: SessionDep,
    transaction_type: TransactionType | None = None,
    location: Annotated[str | None, Query(max_length=80)] = None,
    price_min: Annotated[int | None, Query(ge=0)] = None,
    price_max: Annotated[int | None, Query(ge=0)] = None,
    bedrooms_min: Annotated[int | None, Query(ge=0, le=20)] = None,
    bathrooms_min: Annotated[int | None, Query(ge=0, le=20)] = None,
    furnished: Furnished | None = None,
    property_type: PropertyType | None = None,
    sort: Literal["newest", "price_asc", "price_desc"] = "newest",
    page: Annotated[int, Query(ge=1, le=1000)] = 1,
    page_size: Annotated[int, Query(ge=1, le=50)] = 20,
) -> Page[ListingPublic]:
    params = svc.SearchParams(
        transaction_type=transaction_type,
        location=location,
        price_min=price_min,
        price_max=price_max,
        bedrooms_min=bedrooms_min,
        bathrooms_min=bathrooms_min,
        furnished=furnished,
        property_type=property_type,
        sort=sort,
        page=page,
        page_size=page_size,
    )
    items, total = await svc.search_listings(session, params)
    return Page(items=[svc.to_public(x) for x in items], total=total, page=page, page_size=page_size)


@router.post("", response_model=ListingPrivate, status_code=status.HTTP_201_CREATED)
async def create(
    data: ListingCreate, request: Request, p: PrincipalDep, session: SessionDep
) -> ListingPrivate:
    listing = await svc.create_listing(session, p, data, request)
    return svc.to_private(listing)


@router.get("/{listing_id}", response_model=ListingPublic | ListingPrivate)
async def detail(
    listing_id: uuid.UUID, p: OptionalPrincipal, session: SessionDep
) -> ListingPublic | ListingPrivate:
    listing = await svc.get_visible_listing(session, listing_id, p)
    if p is not None and can_manage_listing(p, svc.ref(listing)):
        return svc.to_private(listing)
    return svc.to_public(listing)


@router.patch("/{listing_id}", response_model=ListingPrivate)
async def update(
    listing_id: uuid.UUID, data: ListingUpdate, request: Request, p: PrincipalDep, session: SessionDep
) -> ListingPrivate:
    return svc.to_private(await svc.update_listing(session, p, listing_id, data, request))


@router.post("/{listing_id}/publish", response_model=ListingPrivate)
async def publish(
    listing_id: uuid.UUID, request: Request, p: PrincipalDep, session: SessionDep
) -> ListingPrivate:
    return svc.to_private(await svc.publish_listing(session, p, listing_id, request))


@router.post("/{listing_id}/pause", response_model=ListingPrivate)
async def pause(
    listing_id: uuid.UUID, request: Request, p: PrincipalDep, session: SessionDep
) -> ListingPrivate:
    return svc.to_private(await svc.pause_listing(session, p, listing_id, request))


@router.post("/{listing_id}/confirm", response_model=ListingPrivate)
async def confirm(
    listing_id: uuid.UUID, request: Request, p: PrincipalDep, session: SessionDep
) -> ListingPrivate:
    return svc.to_private(await svc.confirm_listing(session, p, listing_id, request))


@router.post(
    "/{listing_id}/media",
    response_model=MediaOut,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(rate_limit("upload", 120, 3600))],
)
async def upload_media(
    listing_id: uuid.UUID,
    request: Request,
    p: PrincipalDep,
    session: SessionDep,
    file: Annotated[UploadFile, File()],
) -> MediaOut:
    media = await svc.add_media(session, p, listing_id, file, request)
    return MediaOut(
        id=media.id, url=get_storage().url(media.storage_key), width=media.width, height=media.height
    )


@router.delete("/{listing_id}/media/{media_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_media(
    listing_id: uuid.UUID, media_id: uuid.UUID, request: Request, p: PrincipalDep, session: SessionDep
) -> Response:
    await svc.delete_media(session, p, listing_id, media_id, request)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post(
    "/{listing_id}/contact/whatsapp",
    response_model=WhatsAppHandoffOut,
    dependencies=[Depends(rate_limit("whatsapp", 30, 600))],
)
async def whatsapp(
    listing_id: uuid.UUID,
    request: Request,
    user: OptionalUser,
    session: SessionDep,
    locale: Literal["en", "ar"] = "en",
) -> WhatsAppHandoffOut:
    url = await svc.whatsapp_handoff(session, listing_id, user.id if user else None, locale, request)
    return WhatsAppHandoffOut(url=url)


@router.post(
    "/{listing_id}/view",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(rate_limit("view", 300, 600))],
)
async def view(listing_id: uuid.UUID, request: Request, user: OptionalUser, session: SessionDep) -> Response:
    await svc.record_view(session, listing_id, user.id if user else None, request)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post(
    "/{listing_id}/leads",
    response_model=LeadReceipt,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(rate_limit("lead", 10, 3600))],
)
async def create_lead(
    listing_id: uuid.UUID,
    data: LeadCreate,
    request: Request,
    response: Response,
    user: OptionalUser,
    session: SessionDep,
) -> LeadReceipt:
    lead, deduplicated = await lead_service.create_lead(
        session, listing_id, data, user.id if user else None, request
    )
    if deduplicated:
        response.status_code = status.HTTP_200_OK
    return LeadReceipt(id=lead.id, deduplicated=deduplicated)

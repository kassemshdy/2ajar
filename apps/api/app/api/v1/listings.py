"""Listing endpoints. Thin HTTP adapters: parse input, call one service method, present the result.

Business rules, authorization and notifications live in the services (see ``app.api.providers``).
"""

import uuid
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, File, Query, Request, Response, UploadFile, status
from fastapi.responses import PlainTextResponse

from app.api.deps import CurrentUser, OptionalPrincipal, OptionalUser, PrincipalDep, principal_of
from app.api.providers import (
    ContactServiceDep,
    ImporterDep,
    LeadServiceDep,
    ListingServiceDep,
    MediaServiceDep,
)
from app.core.ratelimit import rate_limit
from app.models.enums import Furnished, PropertyType, TransactionType
from app.repositories.listings import SearchCriteria
from app.schemas.common import Page
from app.schemas.lead import LeadCreate, LeadReceipt
from app.schemas.listing import (
    ImportResultOut,
    ImportRowOut,
    ListingCreate,
    ListingPrivate,
    ListingPublic,
    ListingUpdate,
    MediaOut,
    WhatsAppHandoffOut,
)
from app.services import import_csv
from app.services.presenters import ListingPresenter as present
from app.storage import media_url

router = APIRouter(prefix="/listings", tags=["listings"])


@router.get("", response_model=Page[ListingPublic])
async def search(
    service: ListingServiceDep,
    response: Response,
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
    criteria = SearchCriteria(
        transaction_type=transaction_type,
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
    items, total = await service.search(criteria, location_slug=location)
    # Public, anonymous data: let shared caches absorb bursts, while freshness stays within seconds.
    response.headers["Cache-Control"] = "public, max-age=15, stale-while-revalidate=60"
    return Page(items=[present.to_public(x) for x in items], total=total, page=page, page_size=page_size)


@router.post("", response_model=ListingPrivate, status_code=status.HTTP_201_CREATED)
async def create(
    data: ListingCreate, request: Request, p: PrincipalDep, service: ListingServiceDep
) -> ListingPrivate:
    return present.to_private(await service.create(p, data, request))


@router.get("/import/template", response_class=PlainTextResponse)
async def import_template() -> PlainTextResponse:
    return PlainTextResponse(
        import_csv.template_csv(),
        media_type="text/csv; charset=utf-8",
        headers={
            "Content-Disposition": 'attachment; filename="2ajar-listings-template.csv"',
            "Cache-Control": "public, max-age=86400",
        },
    )


@router.post(
    "/import", response_model=ImportResultOut, dependencies=[Depends(rate_limit("import", 30, 3600))]
)
async def import_listings(
    request: Request,
    user: CurrentUser,
    importer: ImporterDep,
    file: Annotated[UploadFile, File()],
    dry_run: bool = True,
) -> ImportResultOut:
    raw = await file.read(import_csv.MAX_BYTES + 1)
    results = await importer.run(
        principal_of(user), raw, dry_run=dry_run, actor_name=user.full_name, request=request
    )
    return ImportResultOut(
        dry_run=dry_run,
        total=len(results),
        valid=sum(1 for r in results if r.ok),
        created=sum(1 for r in results if r.listing_id),
        rows=[ImportRowOut.model_validate(r, from_attributes=True) for r in results],
    )


@router.get("/{listing_id}", response_model=ListingPublic | ListingPrivate)
async def detail(
    listing_id: uuid.UUID, p: OptionalPrincipal, service: ListingServiceDep
) -> ListingPublic | ListingPrivate:
    listing = await service.get_visible(listing_id, p)
    return present.to_private(listing) if service.can_manage(p, listing) else present.to_public(listing)


@router.patch("/{listing_id}", response_model=ListingPrivate)
async def update(
    listing_id: uuid.UUID, data: ListingUpdate, request: Request, p: PrincipalDep, service: ListingServiceDep
) -> ListingPrivate:
    return present.to_private(await service.update(p, listing_id, data, request))


@router.post("/{listing_id}/publish", response_model=ListingPrivate)
async def publish(
    listing_id: uuid.UUID, request: Request, p: PrincipalDep, service: ListingServiceDep
) -> ListingPrivate:
    return present.to_private(await service.publish(p, listing_id, request))


@router.post("/{listing_id}/pause", response_model=ListingPrivate)
async def pause(
    listing_id: uuid.UUID, request: Request, p: PrincipalDep, service: ListingServiceDep
) -> ListingPrivate:
    return present.to_private(await service.pause(p, listing_id, request))


@router.post("/{listing_id}/confirm", response_model=ListingPrivate)
async def confirm(
    listing_id: uuid.UUID, request: Request, p: PrincipalDep, service: ListingServiceDep
) -> ListingPrivate:
    return present.to_private(await service.confirm(p, listing_id, request))


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
    media_service: MediaServiceDep,
    file: Annotated[UploadFile, File()],
) -> MediaOut:
    media = await media_service.add(p, listing_id, file, request)
    return MediaOut(id=media.id, url=media_url(media.storage_key), width=media.width, height=media.height)


@router.delete("/{listing_id}/media/{media_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_media(
    listing_id: uuid.UUID,
    media_id: uuid.UUID,
    request: Request,
    p: PrincipalDep,
    media_service: MediaServiceDep,
) -> Response:
    await media_service.remove(p, listing_id, media_id, request)
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
    contact: ContactServiceDep,
    locale: Literal["en", "ar"] = "en",
) -> WhatsAppHandoffOut:
    url = await contact.whatsapp_link(listing_id, user.id if user else None, locale, request)
    return WhatsAppHandoffOut(url=url)


@router.post(
    "/{listing_id}/view",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(rate_limit("view", 300, 600))],
)
async def view(
    listing_id: uuid.UUID, request: Request, user: OptionalUser, contact: ContactServiceDep
) -> Response:
    await contact.record_view(listing_id, user.id if user else None, request)
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
    leads: LeadServiceDep,
) -> LeadReceipt:
    lead, deduplicated = await leads.submit(listing_id, data, user.id if user else None, request)
    if deduplicated:
        response.status_code = status.HTTP_200_OK
    return LeadReceipt(id=lead.id, deduplicated=deduplicated)

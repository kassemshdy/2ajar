"""Reference data, public configuration and "my" dashboard endpoints."""

import uuid
from typing import Annotated

from fastapi import APIRouter, Query, Response

from app.api.deps import PrincipalDep
from app.api.providers import (
    AgencyServiceDep,
    LeadServiceDep,
    ListingServiceDep,
    LocationDirectoryDep,
    SettingsDep,
)
from app.schemas.lead import LeadWithListing
from app.schemas.listing import ListingPrivate, LocationOut
from app.services.presenters import ListingPresenter

router = APIRouter()

# Reference data changes only on deploy; browsers and the web server may reuse it for a few minutes.
_REFERENCE_CACHE = "public, max-age=300, stale-while-revalidate=3600"


@router.get("/config", tags=["meta"])
async def public_config(settings: SettingsDep, response: Response) -> dict[str, object]:
    response.headers["Cache-Control"] = _REFERENCE_CACHE
    return {
        "consent_text_version": settings.consent_text_version,
        "demo_mode": settings.demo_mode,
        "max_upload_bytes": settings.max_upload_bytes,
        "max_media_per_listing": settings.max_media_per_listing,
    }


@router.get("/locations", response_model=list[LocationOut], tags=["locations"])
async def locations(directory: LocationDirectoryDep, response: Response) -> list[LocationOut]:
    response.headers["Cache-Control"] = _REFERENCE_CACHE
    return [LocationOut.model_validate(r, from_attributes=True) for r in await directory.all()]


@router.get("/me/listings", response_model=list[ListingPrivate], tags=["me"])
async def my_listings(
    p: PrincipalDep, service: ListingServiceDep, agencies: AgencyServiceDep
) -> list[ListingPrivate]:
    rows = await service.list_manageable(p)
    stats = await agencies.listing_stats([listing.id for listing, _ in rows])
    return [ListingPresenter.to_private(listing, n, stats=stats.get(listing.id)) for listing, n in rows]


@router.get("/me/leads", response_model=list[LeadWithListing], tags=["me"])
async def my_leads(
    p: PrincipalDep, leads: LeadServiceDep, listing_id: Annotated[uuid.UUID | None, Query()] = None
) -> list[LeadWithListing]:
    return [
        LeadWithListing(
            id=lead.id,
            listing_id=lead.listing_id,
            name=lead.name,
            phone_e164=lead.phone_e164,
            email=lead.email,
            message=lead.message,
            source=lead.source,
            status=lead.status,
            duplicate_count=lead.duplicate_count,
            consent_at=lead.consent_at,
            created_at=lead.created_at,
            last_contact_at=lead.last_contact_at,
            listing_title=listing.title_en or listing.title_ar,
        )
        for lead, listing in await leads.inbox(p, listing_id)
    ]

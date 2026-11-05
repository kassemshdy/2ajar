import uuid
from typing import Annotated

from fastapi import APIRouter, Query
from sqlalchemy import select

from app.api.deps import PrincipalDep, SessionDep
from app.core.config import get_settings
from app.models import Location
from app.schemas.lead import LeadWithListing
from app.schemas.listing import ListingPrivate, LocationOut
from app.services import leads as lead_service
from app.services import listings as svc

router = APIRouter()


@router.get("/config", tags=["meta"])
async def public_config() -> dict[str, object]:
    s = get_settings()
    return {
        "consent_text_version": s.consent_text_version,
        "demo_mode": s.demo_mode,
        "max_upload_bytes": s.max_upload_bytes,
        "max_media_per_listing": s.max_media_per_listing,
    }


@router.get("/locations", response_model=list[LocationOut], tags=["locations"])
async def locations(session: SessionDep) -> list[LocationOut]:
    rows = await session.scalars(select(Location).order_by(Location.path))
    return [LocationOut.model_validate(r) for r in rows]


@router.get("/me/listings", response_model=list[ListingPrivate], tags=["me"])
async def my_listings(p: PrincipalDep, session: SessionDep) -> list[ListingPrivate]:
    return [svc.to_private(listing, n) for listing, n in await svc.list_manageable(session, p)]


@router.get("/me/leads", response_model=list[LeadWithListing], tags=["me"])
async def my_leads(
    p: PrincipalDep, session: SessionDep, listing_id: Annotated[uuid.UUID | None, Query()] = None
) -> list[LeadWithListing]:
    rows = await lead_service.list_leads_for(session, p, listing_id)
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
        for lead, listing in rows
    ]

import uuid
from datetime import timedelta

from fastapi import Request
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.authz.policies import Principal
from app.core.config import get_settings
from app.core.errors import ValidationFailed
from app.core.phone import normalize_phone
from app.core.security import utcnow
from app.models import Lead, Listing
from app.models.enums import LeadSource, ListingEventType
from app.schemas.lead import LeadCreate
from app.services.audit import record_event
from app.services.listings import get_public_listing, manageable_clause

DEDUPE_WINDOW = timedelta(hours=24)


async def create_lead(
    session: AsyncSession,
    listing_id: uuid.UUID,
    data: LeadCreate,
    user_id: uuid.UUID | None,
    request: Request,
    source: LeadSource = LeadSource.web,
) -> tuple[Lead, bool]:
    """Returns (lead, deduplicated)."""
    listing = await get_public_listing(session, listing_id)
    phone = normalize_phone(data.phone)
    if phone is None:
        raise ValidationFailed("Invalid phone number", details=[{"loc": ["body", "phone"]}])
    if data.consent_text_version != get_settings().consent_text_version:
        raise ValidationFailed("Consent text is outdated, please reload the page")

    # Serialize concurrent submissions for the same listing+phone so dedupe is race-free.
    await session.execute(
        text("SELECT pg_advisory_xact_lock(hashtextextended(:k, 0))"), {"k": f"lead:{listing.id}:{phone}"}
    )
    now = utcnow()
    existing = await session.scalar(
        select(Lead)
        .where(Lead.listing_id == listing.id, Lead.phone_e164 == phone, Lead.created_at > now - DEDUPE_WINDOW)
        .order_by(Lead.created_at.desc())
        .limit(1)
    )
    if existing is not None:
        existing.duplicate_count += 1
        existing.last_contact_at = now
        if data.message and data.message != existing.message:
            combined = f"{existing.message}\n---\n{data.message}" if existing.message else data.message
            existing.message = combined[-4000:]
        await session.commit()
        return existing, True

    lead = Lead(
        listing_id=listing.id,
        seeker_user_id=user_id,
        name=data.name,
        phone_e164=phone,
        email=data.email.lower() if data.email else None,
        message=data.message,
        source=source,
        consent_at=now,
        consent_text_version=data.consent_text_version,
        last_contact_at=now,
    )
    session.add(lead)
    record_event(
        session, listing_id=listing.id, event_type=ListingEventType.lead, user_id=user_id, request=request
    )
    await session.commit()
    return lead, False


async def list_leads_for(
    session: AsyncSession, p: Principal, listing_id: uuid.UUID | None = None, limit: int = 200
) -> list[tuple[Lead, Listing]]:
    stmt = (
        select(Lead, Listing)
        .join(Listing, Listing.id == Lead.listing_id)
        .where(manageable_clause(p))
        .order_by(func.coalesce(Lead.last_contact_at, Lead.created_at).desc())
        .limit(limit)
    )
    if listing_id is not None:
        stmt = stmt.where(Lead.listing_id == listing_id)
    rows = (await session.execute(stmt)).unique().all()
    return [(r[0], r[1]) for r in rows]

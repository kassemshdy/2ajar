import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Literal
from urllib.parse import quote

from fastapi import Request, UploadFile
from sqlalchemy import ColumnElement, and_, false, func, or_, select, true
from sqlalchemy.ext.asyncio import AsyncSession

from app.authz.policies import (
    ListingRef,
    Principal,
    can_create_listing,
    can_manage_listing,
    can_view_listing,
    is_publicly_visible,
)
from app.core.config import get_settings
from app.core.errors import Conflict, Forbidden, NotFound, PayloadTooLarge, ValidationFailed
from app.core.phone import normalize_phone
from app.core.security import utcnow
from app.models import Lead, Listing, ListingMedia, Location, Property
from app.models.enums import (
    RESIDENTIAL_TYPES,
    Furnished,
    ListingEventType,
    ListingStatus,
    PricePeriod,
    PropertyType,
    TransactionType,
    UserRole,
)
from app.schemas.listing import (
    ListingCreate,
    ListingPrivate,
    ListingPublic,
    ListingUpdate,
    LocalizedText,
    LocationBrief,
    MediaOut,
    PropertyOut,
    PublisherOut,
)
from app.services.audit import audit, record_event
from app.services.images import process_image
from app.storage import get_storage

PROPERTY_FIELDS = ("bedrooms", "bathrooms", "area_sqm", "floor", "furnished", "property_type", "location_id")
LISTING_TEXT_FIELDS = ("title_en", "title_ar", "description_en", "description_ar")


def ref(listing: Listing) -> ListingRef:
    return ListingRef(
        created_by_user_id=listing.created_by_user_id,
        organization_id=listing.organization_id,
        status=listing.status,
        expires_at=listing.expires_at,
        is_demo=listing.is_demo,
    )


# ---------- SQL predicates (must mirror app.authz.policies) ----------


def public_clause(now: datetime, demo_mode: bool) -> ColumnElement[bool]:
    return and_(
        Listing.status == ListingStatus.published,
        or_(Listing.expires_at.is_(None), Listing.expires_at > now),
        true() if demo_mode else Listing.is_demo.is_(False),
    )


def manageable_clause(p: Principal) -> ColumnElement[bool]:
    if p.is_admin:
        return true()
    conds: list[ColumnElement[bool]] = [Listing.created_by_user_id == p.user_id]
    if p.admin_org_ids:
        conds.append(Listing.organization_id.in_(p.admin_org_ids))
    return or_(*conds) if conds else false()


# ---------- serialization ----------


def _publisher(listing: Listing) -> PublisherOut:
    if listing.organization is not None:
        return PublisherOut(
            type="broker", display_name=listing.organization.name, organization_name=listing.organization.name
        )
    creator = listing.created_by
    first_name = creator.full_name.split()[0] if creator.full_name else "Owner"
    kind: Literal["broker", "owner"] = "broker" if creator.role == UserRole.broker else "owner"
    return PublisherOut(type=kind, display_name=first_name, organization_name=None)


def to_public(listing: Listing) -> ListingPublic:
    storage = get_storage()
    prop = listing.property
    loc = prop.location
    return ListingPublic(
        id=listing.id,
        status=listing.status,
        transaction_type=listing.transaction_type,
        price_usd=listing.price_usd_cents // 100,
        price_period=listing.price_period,
        title=LocalizedText(en=listing.title_en, ar=listing.title_ar),
        description=LocalizedText(en=listing.description_en, ar=listing.description_ar),
        property=PropertyOut(
            property_type=prop.property_type,
            bedrooms=prop.bedrooms,
            bathrooms=prop.bathrooms,
            area_sqm=prop.area_sqm,
            floor=prop.floor,
            furnished=prop.furnished,
            amenities=list(prop.amenities or []),
        ),
        location=LocationBrief(slug=loc.slug, name_en=loc.name_en, name_ar=loc.name_ar, path=loc.path),
        media=[
            MediaOut(id=m.id, url=storage.url(m.storage_key), width=m.width, height=m.height)
            for m in listing.media
        ],
        publisher=_publisher(listing),
        published_at=listing.published_at,
        last_confirmed_at=listing.last_confirmed_at,
        is_demo=listing.is_demo,
    )


def to_private(listing: Listing, lead_count: int = 0) -> ListingPrivate:
    return ListingPrivate(
        **to_public(listing).model_dump(),
        contact_whatsapp=listing.contact_whatsapp_e164,
        expires_at=listing.expires_at,
        created_at=listing.created_at,
        updated_at=listing.updated_at,
        location_id=listing.property.location_id,
        lead_count=lead_count,
    )


# ---------- loading ----------


async def _load(session: AsyncSession, listing_id: uuid.UUID) -> Listing | None:
    return await session.scalar(
        select(Listing).where(Listing.id == listing_id).execution_options(populate_existing=True)
    )


async def get_visible_listing(
    session: AsyncSession, listing_id: uuid.UUID, principal: Principal | None
) -> Listing:
    listing = await _load(session, listing_id)
    s = get_settings()
    if listing is None or not can_view_listing(principal, ref(listing), utcnow(), s.demo_mode):
        raise NotFound("Listing not found")
    return listing


async def get_public_listing(session: AsyncSession, listing_id: uuid.UUID) -> Listing:
    listing = await _load(session, listing_id)
    if listing is None or not is_publicly_visible(ref(listing), utcnow(), get_settings().demo_mode):
        raise NotFound("Listing not found")
    return listing


async def get_manageable_listing(session: AsyncSession, listing_id: uuid.UUID, p: Principal) -> Listing:
    listing = await _load(session, listing_id)
    if listing is None or not can_manage_listing(p, ref(listing)):
        raise NotFound("Listing not found")
    return listing


async def _require_location(session: AsyncSession, location_id: uuid.UUID) -> None:
    if await session.get(Location, location_id) is None:
        raise ValidationFailed("Unknown location", details=[{"loc": ["body", "location_id"]}])


def _normalize_whatsapp(raw: str | None) -> str | None:
    if raw is None or raw == "":
        return None
    phone = normalize_phone(raw)
    if phone is None:
        raise ValidationFailed("Invalid WhatsApp number", details=[{"loc": ["body", "contact_whatsapp"]}])
    return phone


# ---------- commands ----------


async def create_listing(
    session: AsyncSession, p: Principal, data: ListingCreate, request: Request
) -> Listing:
    if not can_create_listing(p):
        raise Forbidden("Only owners and brokers can create listings")
    await _require_location(session, data.location_id)
    org_id = p.primary_org_id if p.role in (UserRole.broker, UserRole.platform_admin) else None
    prop = Property(
        owner_user_id=p.user_id,
        organization_id=org_id,
        location_id=data.location_id,
        property_type=data.property_type,
        bedrooms=data.bedrooms,
        bathrooms=data.bathrooms,
        area_sqm=data.area_sqm,
        floor=data.floor,
        furnished=data.furnished,
        amenities=[a.value for a in (data.amenities or [])],
    )
    session.add(prop)
    await session.flush()
    listing = Listing(
        property_id=prop.id,
        created_by_user_id=p.user_id,
        organization_id=org_id,
        transaction_type=data.transaction_type,
        price_usd_cents=data.price_usd * 100,
        price_period=data.price_period,
        status=ListingStatus.draft,
        title_en=data.title_en,
        title_ar=data.title_ar,
        description_en=data.description_en,
        description_ar=data.description_ar,
        contact_whatsapp_e164=_normalize_whatsapp(data.contact_whatsapp),
    )
    session.add(listing)
    await session.flush()
    audit(
        session,
        actor_id=p.user_id,
        action="listing.create",
        resource_type="listing",
        resource_id=listing.id,
        request=request,
    )
    await session.commit()
    loaded = await _load(session, listing.id)
    assert loaded is not None
    return loaded


async def update_listing(
    session: AsyncSession, p: Principal, listing_id: uuid.UUID, data: ListingUpdate, request: Request
) -> Listing:
    listing = await get_manageable_listing(session, listing_id, p)
    if listing.status == ListingStatus.archived:
        raise Conflict("Archived listings cannot be edited")
    changes = data.model_dump(exclude_unset=True)

    tx = changes.get("transaction_type", listing.transaction_type)
    period = changes.get("price_period", listing.price_period)
    if tx == TransactionType.rent and period == PricePeriod.total:
        raise ValidationFailed("Rent listings must be priced monthly or yearly")
    if tx == TransactionType.sale and period != PricePeriod.total:
        raise ValidationFailed("Sale listings must use price_period 'total'")

    if changes.get("location_id"):
        await _require_location(session, changes["location_id"])
    for key in PROPERTY_FIELDS:
        if key in changes and (changes[key] is not None or key not in ("property_type", "location_id")):
            setattr(listing.property, key, changes[key])
    if "amenities" in changes:
        listing.property.amenities = [
            a.value if hasattr(a, "value") else a for a in (changes["amenities"] or [])
        ]
    for key in LISTING_TEXT_FIELDS:
        if key in changes:
            setattr(listing, key, changes[key] or None)
    if changes.get("transaction_type"):
        listing.transaction_type = changes["transaction_type"]
    if changes.get("price_period"):
        listing.price_period = changes["price_period"]
    if changes.get("price_usd"):
        listing.price_usd_cents = changes["price_usd"] * 100
    if "contact_whatsapp" in changes:
        listing.contact_whatsapp_e164 = _normalize_whatsapp(changes["contact_whatsapp"])

    audit(
        session,
        actor_id=p.user_id,
        action="listing.update",
        resource_type="listing",
        resource_id=listing.id,
        data={"fields": sorted(changes)},
        request=request,
    )
    await session.commit()
    reloaded = await _load(session, listing.id)
    assert reloaded is not None
    return reloaded


def publish_problems(listing: Listing) -> list[str]:
    s = get_settings()
    problems = []
    if not (listing.title_en or listing.title_ar):
        problems.append("A title in English or Arabic is required")
    if not listing.contact_whatsapp_e164:
        problems.append("A WhatsApp contact number is required")
    if listing.property.property_type in RESIDENTIAL_TYPES and listing.property.bedrooms is None:
        problems.append("Number of bedrooms is required for residential properties")
    if s.publish_requires_media and not listing.media:
        problems.append("At least one photo is required")
    return problems


async def publish_listing(
    session: AsyncSession, p: Principal, listing_id: uuid.UUID, request: Request
) -> Listing:
    listing = await get_manageable_listing(session, listing_id, p)
    if listing.status not in (ListingStatus.draft, ListingStatus.paused, ListingStatus.published):
        raise Conflict(f"Cannot publish a listing with status '{listing.status.value}'")
    problems = publish_problems(listing)
    if problems:
        raise ValidationFailed(problems[0], details=problems)
    now = utcnow()
    # ADR-009: auto-publish in M1. M4 will route to pending_review when MODERATION_REQUIRED=true.
    listing.status = ListingStatus.published
    listing.published_at = listing.published_at or now
    listing.last_confirmed_at = now
    listing.expires_at = now + timedelta(days=get_settings().listing_ttl_days)
    audit(
        session,
        actor_id=p.user_id,
        action="listing.publish",
        resource_type="listing",
        resource_id=listing.id,
        request=request,
    )
    await session.commit()
    return listing


async def pause_listing(
    session: AsyncSession, p: Principal, listing_id: uuid.UUID, request: Request
) -> Listing:
    listing = await get_manageable_listing(session, listing_id, p)
    if listing.status != ListingStatus.published:
        raise Conflict("Only published listings can be paused")
    listing.status = ListingStatus.paused
    audit(
        session,
        actor_id=p.user_id,
        action="listing.pause",
        resource_type="listing",
        resource_id=listing.id,
        request=request,
    )
    await session.commit()
    return listing


async def confirm_listing(
    session: AsyncSession, p: Principal, listing_id: uuid.UUID, request: Request
) -> Listing:
    listing = await get_manageable_listing(session, listing_id, p)
    if listing.status != ListingStatus.published:
        raise Conflict("Only published listings can be confirmed")
    now = utcnow()
    listing.last_confirmed_at = now
    listing.expires_at = now + timedelta(days=get_settings().listing_ttl_days)
    audit(
        session,
        actor_id=p.user_id,
        action="listing.confirm",
        resource_type="listing",
        resource_id=listing.id,
        request=request,
    )
    await session.commit()
    return listing


# ---------- media ----------


async def add_media(
    session: AsyncSession, p: Principal, listing_id: uuid.UUID, upload: UploadFile, request: Request
) -> ListingMedia:
    s = get_settings()
    listing = await get_manageable_listing(session, listing_id, p)
    if len(listing.media) >= s.max_media_per_listing:
        raise Conflict(f"A listing can have at most {s.max_media_per_listing} photos")
    raw = await upload.read(s.max_upload_bytes + 1)
    if len(raw) > s.max_upload_bytes:
        raise PayloadTooLarge(f"Images must be at most {s.max_upload_bytes // (1024 * 1024)} MB")
    image = process_image(raw)
    key = f"listings/{listing.id}/{uuid.uuid4().hex}.webp"
    await get_storage().put(key, image.data, image.content_type)
    position = max((m.position for m in listing.media), default=-1) + 1
    media = ListingMedia(
        listing_id=listing.id,
        storage_key=key,
        content_type=image.content_type,
        width=image.width,
        height=image.height,
        byte_size=len(image.data),
        position=position,
    )
    session.add(media)
    audit(
        session,
        actor_id=p.user_id,
        action="listing.media_add",
        resource_type="listing",
        resource_id=listing.id,
        data={"key": key},
        request=request,
    )
    await session.commit()
    return media


async def delete_media(
    session: AsyncSession, p: Principal, listing_id: uuid.UUID, media_id: uuid.UUID, request: Request
) -> None:
    listing = await get_manageable_listing(session, listing_id, p)
    media = next((m for m in listing.media if m.id == media_id), None)
    if media is None:
        raise NotFound("Photo not found")
    key = media.storage_key
    listing.media.remove(media)
    audit(
        session,
        actor_id=p.user_id,
        action="listing.media_delete",
        resource_type="listing",
        resource_id=listing.id,
        data={"key": key},
        request=request,
    )
    await session.commit()
    await get_storage().delete(key)


# ---------- queries ----------


@dataclass
class SearchParams:
    transaction_type: TransactionType | None = None
    location: str | None = None
    price_min: int | None = None
    price_max: int | None = None
    bedrooms_min: int | None = None
    bathrooms_min: int | None = None
    furnished: Furnished | None = None
    property_type: PropertyType | None = None
    sort: Literal["newest", "price_asc", "price_desc"] = "newest"
    page: int = 1
    page_size: int = 20


async def search_listings(session: AsyncSession, params: SearchParams) -> tuple[list[Listing], int]:
    s = get_settings()
    stmt = (
        select(Listing)
        .join(Listing.property)
        .join(Property.location)
        .where(public_clause(utcnow(), s.demo_mode))
    )
    if params.transaction_type:
        stmt = stmt.where(Listing.transaction_type == params.transaction_type)
    if params.location:
        loc_path = await session.scalar(select(Location.path).where(Location.slug == params.location))
        if loc_path is None:
            return [], 0
        stmt = stmt.where(or_(Location.path == loc_path, Location.path.startswith(loc_path + "/")))
    if params.price_min is not None:
        stmt = stmt.where(Listing.price_usd_cents >= params.price_min * 100)
    if params.price_max is not None:
        stmt = stmt.where(Listing.price_usd_cents <= params.price_max * 100)
    if params.bedrooms_min is not None:
        stmt = stmt.where(Property.bedrooms >= params.bedrooms_min)
    if params.bathrooms_min is not None:
        stmt = stmt.where(Property.bathrooms >= params.bathrooms_min)
    if params.furnished:
        stmt = stmt.where(Property.furnished == params.furnished)
    if params.property_type:
        stmt = stmt.where(Property.property_type == params.property_type)

    total = await session.scalar(select(func.count()).select_from(stmt.order_by(None).subquery())) or 0
    order: dict[str, tuple[ColumnElement[Any], ...]] = {
        "newest": (Listing.published_at.desc(), Listing.id.asc()),
        "price_asc": (Listing.price_usd_cents.asc(), Listing.id.asc()),
        "price_desc": (Listing.price_usd_cents.desc(), Listing.id.asc()),
    }
    stmt = (
        stmt.order_by(*order[params.sort])
        .offset((params.page - 1) * params.page_size)
        .limit(params.page_size)
    )
    items: list[Listing] = list((await session.scalars(stmt)).unique())
    return items, total


async def list_manageable(session: AsyncSession, p: Principal) -> list[tuple[Listing, int]]:
    lead_counts = select(Lead.listing_id, func.count().label("n")).group_by(Lead.listing_id).subquery()
    stmt = (
        select(Listing, func.coalesce(lead_counts.c.n, 0))
        .outerjoin(lead_counts, lead_counts.c.listing_id == Listing.id)
        .where(manageable_clause(p))
        .order_by(Listing.updated_at.desc())
        .limit(200)
    )
    rows = (await session.execute(stmt)).unique().all()
    return [(row[0], int(row[1])) for row in rows]


# ---------- contact ----------


def whatsapp_url(listing: Listing, locale: str) -> str:
    assert listing.contact_whatsapp_e164
    web = get_settings().public_web_base_url.rstrip("/")
    lang = "ar" if locale == "ar" else "en"
    link = f"{web}/{lang}/listings/{listing.id}"
    title = (listing.title_ar or listing.title_en) if lang == "ar" else (listing.title_en or listing.title_ar)
    ref_code = str(listing.id)[:8].upper()
    if lang == "ar":
        text = f"مرحباً، أنا مهتم بهذا العقار على إيجار: {title}\n{link}\nالمرجع: {ref_code}"
    else:
        text = f"Hi, I'm interested in this property on 2ajar: {title}\n{link}\nRef: {ref_code}"
    digits = listing.contact_whatsapp_e164.lstrip("+")
    return f"https://wa.me/{digits}?text={quote(text)}"


async def whatsapp_handoff(
    session: AsyncSession, listing_id: uuid.UUID, user_id: uuid.UUID | None, locale: str, request: Request
) -> str:
    listing = await get_public_listing(session, listing_id)
    if not listing.contact_whatsapp_e164:
        raise NotFound("This listing has no WhatsApp contact")
    record_event(
        session,
        listing_id=listing.id,
        event_type=ListingEventType.whatsapp_click,
        user_id=user_id,
        request=request,
    )
    await session.commit()
    return whatsapp_url(listing, locale)


async def record_view(
    session: AsyncSession, listing_id: uuid.UUID, user_id: uuid.UUID | None, request: Request
) -> None:
    listing = await get_public_listing(session, listing_id)
    record_event(
        session, listing_id=listing.id, event_type=ListingEventType.view, user_id=user_id, request=request
    )
    await session.commit()

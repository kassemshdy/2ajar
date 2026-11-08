"""Listing use cases.

``ListingService`` is the single entry point for creating and changing listings. It depends on abstractions
that are injected (repository, cached location directory, publish policy, event recorder, clock), so each
collaborator can be replaced in tests or swapped later without editing this class (Dependency Inversion).

Authorization is checked here, not in routes, so every caller (HTTP, CSV import, future AI tools) gets the
same rules. Private resources the caller may not manage raise ``NotFound`` (ADR-010).
"""

import uuid
from collections.abc import Callable
from datetime import datetime, timedelta
from typing import Any

from fastapi import Request, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.authz.policies import (
    Principal,
    can_create_listing,
    can_manage_listing,
    can_view_listing,
    is_publicly_visible,
)
from app.core.config import Settings
from app.core.errors import Conflict, Forbidden, NotFound, PayloadTooLarge, ValidationFailed
from app.core.events import EventRecorder
from app.core.phone import normalize_phone
from app.core.security import utcnow
from app.domain.events import ListingCreated, ListingPublished, ListingSubmittedForReview
from app.models import Listing, ListingMedia, Property
from app.models.enums import ListingEventType, ListingStatus, PricePeriod, TransactionType, UserRole
from app.repositories.listings import ListingRepository, SearchCriteria, as_ref
from app.repositories.locations import LocationDirectory
from app.schemas.listing import LIVING_FIELDS, RENTALS_ONLY, ListingCreate, ListingUpdate
from app.services.audit import AuditTrail, record_event
from app.services.contact import WhatsAppLinkBuilder
from app.services.images import process_image
from app.services.presenters import ListingPresenter
from app.services.publishing import PublishPolicy, publish_policy_for
from app.storage import StorageBackend

Clock = Callable[[], datetime]

# Fields of ListingUpdate that live on the physical property rather than the advertisement.
_PROPERTY_FIELDS = ("bedrooms", "bathrooms", "area_sqm", "floor", "max_guests", "furnished")
_TEXT_FIELDS = ("title_en", "title_ar", "description_en", "description_ar")


def normalize_whatsapp(raw: str | None) -> str | None:
    """E.164 WhatsApp number, None when blank; ValidationFailed when present but invalid."""
    if not raw:
        return None
    phone = normalize_phone(raw)
    if phone is None:
        raise ValidationFailed("Invalid WhatsApp number", details=[{"loc": ["body", "contact_whatsapp"]}])
    return phone


def check_price_period(tx: TransactionType, period: PricePeriod) -> None:
    """Final check on the merged state of a listing (e.g. an old sale listing being edited)."""
    if tx == TransactionType.sale:
        raise ValidationFailed(RENTALS_ONLY)
    if period == PricePeriod.total:
        raise ValidationFailed("Choose a rental period: hourly, daily, nightly, weekly, monthly or yearly")


class ListingService:
    def __init__(
        self,
        session: AsyncSession,
        *,
        settings: Settings,
        events: EventRecorder,
        clock: Clock = utcnow,
        policy: PublishPolicy | None = None,
    ) -> None:
        self._session = session
        self._settings = settings
        self._events = events
        self._clock = clock
        self._policy = policy or publish_policy_for(settings)
        self.repo = ListingRepository(session)
        self.locations = LocationDirectory(session)
        self._audit = AuditTrail(session)

    # ---------- loading with authorization ----------

    async def get_visible(self, listing_id: uuid.UUID, p: Principal | None) -> Listing:
        listing = await self.repo.get(listing_id)
        if listing is None or not can_view_listing(
            p, as_ref(listing), self._clock(), self._settings.demo_mode
        ):
            raise NotFound("Listing not found")
        return listing

    async def get_public(self, listing_id: uuid.UUID) -> Listing:
        listing = await self.repo.get(listing_id)
        if listing is None or not is_publicly_visible(
            as_ref(listing), self._clock(), self._settings.demo_mode
        ):
            raise NotFound("Listing not found")
        return listing

    async def get_manageable(self, listing_id: uuid.UUID, p: Principal) -> Listing:
        listing = await self.repo.get(listing_id)
        if listing is None or not can_manage_listing(p, as_ref(listing)):
            raise NotFound("Listing not found")
        return listing

    def can_manage(self, p: Principal | None, listing: Listing) -> bool:
        return can_manage_listing(p, as_ref(listing))

    # ---------- queries ----------

    async def search(self, criteria: SearchCriteria, location_slug: str | None) -> tuple[list[Listing], int]:
        if location_slug:
            location = await self.locations.by_slug(location_slug)  # cached: no query per search
            if location is None:
                return [], 0
            criteria = SearchCriteria(**{**criteria.__dict__, "location_path": location.path})
        return await self.repo.search(criteria, now=self._clock(), include_demo=self._settings.demo_mode)

    async def list_manageable(self, p: Principal) -> list[tuple[Listing, int]]:
        return await self.repo.manageable_with_lead_counts(p)

    # ---------- commands ----------

    async def create(self, p: Principal, data: ListingCreate, request: Request | None = None) -> Listing:
        listing = await self.add_draft(p, data)
        self._audit.record(p.user_id, "listing.create", "listing", listing.id, request=request)
        await self._session.commit()
        loaded = await self.repo.get(listing.id)
        assert loaded is not None
        self._events.record(ListingCreated(ListingPresenter.snapshot(loaded)))
        return loaded

    async def add_draft(self, p: Principal, data: ListingCreate) -> Listing:
        """Validate and stage a draft property + listing without committing (used by bulk import too)."""
        if not can_create_listing(p):
            raise Forbidden("Only owners and brokers can create listings")
        await self._require_location(data.location_id)
        # Brokers publish on behalf of their agency (tenant); individual owners have no organization.
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
            max_guests=data.max_guests,
            furnished=data.furnished,
            amenities=[a.value for a in (data.amenities or [])],
            **{f: getattr(data, f) for f in LIVING_FIELDS if getattr(data, f) is not None},
        )
        self.repo.add(prop)
        await self.repo.flush()
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
            contact_whatsapp_e164=normalize_whatsapp(data.contact_whatsapp),
        )
        self.repo.add(listing)
        await self.repo.flush()
        return listing

    async def update(
        self, p: Principal, listing_id: uuid.UUID, data: ListingUpdate, request: Request | None = None
    ) -> Listing:
        listing = await self.get_manageable(listing_id, p)
        if listing.status == ListingStatus.archived:
            raise Conflict("Archived listings cannot be edited")
        changes: dict[str, Any] = data.model_dump(exclude_unset=True)
        check_price_period(
            changes.get("transaction_type") or listing.transaction_type,
            changes.get("price_period") or listing.price_period,
        )
        prop = listing.property
        if changes.get("location_id"):
            await self._require_location(changes["location_id"])
            prop.location_id = changes["location_id"]
        if changes.get("property_type"):
            prop.property_type = changes["property_type"]
        for key in _PROPERTY_FIELDS:
            if key in changes:  # explicit null clears the value
                setattr(prop, key, changes[key])
        for key in LIVING_FIELDS:
            if key in changes:  # explicit null clears the value; lists default to empty
                value = changes[key]
                setattr(
                    prop,
                    key,
                    value if value is not None or key not in ("highlights", "things_to_know") else [],
                )
        if "amenities" in changes:
            prop.amenities = [str(getattr(a, "value", a)) for a in (changes["amenities"] or [])]
        for key in _TEXT_FIELDS:
            if key in changes:
                setattr(listing, key, changes[key] or None)
        if changes.get("transaction_type"):
            listing.transaction_type = changes["transaction_type"]
        if changes.get("price_period"):
            listing.price_period = changes["price_period"]
        if changes.get("price_usd"):
            listing.price_usd_cents = changes["price_usd"] * 100
        if "contact_whatsapp" in changes:
            listing.contact_whatsapp_e164 = normalize_whatsapp(changes["contact_whatsapp"])

        self._audit.record(
            p.user_id,
            "listing.update",
            "listing",
            listing.id,
            request=request,
            data={"fields": sorted(changes)},
        )
        await self._session.commit()
        reloaded = await self.repo.get(listing.id)
        assert reloaded is not None
        return reloaded

    async def publish(self, p: Principal, listing_id: uuid.UUID, request: Request | None = None) -> Listing:
        listing = await self.get_manageable(listing_id, p)
        if listing.status not in (ListingStatus.draft, ListingStatus.paused, ListingStatus.published):
            raise Conflict(f"Cannot publish a listing with status '{listing.status.value}'")
        problems = self._policy.problems(listing)
        if problems:
            raise ValidationFailed(problems[0], details=problems)

        target = self._policy.target_status
        listing.status = target
        if target == ListingStatus.published:
            self._mark_fresh(listing)
            listing.published_at = listing.published_at or listing.last_confirmed_at
        self._audit.record(
            p.user_id,
            "listing.publish",
            "listing",
            listing.id,
            request=request,
            data={"status": target.value},
        )
        await self._session.commit()

        snapshot = ListingPresenter.snapshot(listing)
        if target == ListingStatus.published:
            self._events.record(ListingPublished(snapshot))
        else:
            self._events.record(ListingSubmittedForReview(snapshot))
        return listing

    async def pause(self, p: Principal, listing_id: uuid.UUID, request: Request | None = None) -> Listing:
        listing = await self.get_manageable(listing_id, p)
        if listing.status != ListingStatus.published:
            raise Conflict("Only published listings can be paused")
        listing.status = ListingStatus.paused
        self._audit.record(p.user_id, "listing.pause", "listing", listing.id, request=request)
        await self._session.commit()
        return listing

    async def confirm(self, p: Principal, listing_id: uuid.UUID, request: Request | None = None) -> Listing:
        """Publisher re-confirms availability: restarts the freshness window."""
        listing = await self.get_manageable(listing_id, p)
        if listing.status != ListingStatus.published:
            raise Conflict("Only published listings can be confirmed")
        self._mark_fresh(listing)
        self._audit.record(p.user_id, "listing.confirm", "listing", listing.id, request=request)
        await self._session.commit()
        return listing

    # ---------- helpers ----------

    def _mark_fresh(self, listing: Listing) -> None:
        now = self._clock()
        listing.last_confirmed_at = now
        listing.expires_at = now + timedelta(days=self._settings.listing_ttl_days)

    async def _require_location(self, location_id: uuid.UUID) -> None:
        if await self.locations.get(location_id) is None:
            raise ValidationFailed("Unknown location", details=[{"loc": ["body", "location_id"]}])


class ListingMediaService:
    """Photo upload/removal. Separate from ListingService: different collaborators (storage, imaging)."""

    def __init__(
        self, session: AsyncSession, *, settings: Settings, storage: StorageBackend, listings: ListingService
    ) -> None:
        self._session = session
        self._settings = settings
        self._storage = storage
        self._listings = listings
        self._audit = AuditTrail(session)

    async def add(
        self, p: Principal, listing_id: uuid.UUID, upload: UploadFile, request: Request | None = None
    ) -> ListingMedia:
        s = self._settings
        listing = await self._listings.get_manageable(listing_id, p)
        if len(listing.media) >= s.max_media_per_listing:
            raise Conflict(f"A listing can have at most {s.max_media_per_listing} photos")
        # Read at most limit+1 bytes: enough to detect oversize without buffering an arbitrarily large body.
        raw = await upload.read(s.max_upload_bytes + 1)
        if len(raw) > s.max_upload_bytes:
            raise PayloadTooLarge(f"Images must be at most {s.max_upload_bytes // (1024 * 1024)} MB")
        image = process_image(raw)
        key = f"listings/{listing.id}/{uuid.uuid4().hex}.webp"
        await self._storage.put(key, image.data, image.content_type)
        media = ListingMedia(
            listing_id=listing.id,
            storage_key=key,
            content_type=image.content_type,
            width=image.width,
            height=image.height,
            byte_size=len(image.data),
            position=max((m.position for m in listing.media), default=-1) + 1,
        )
        self._session.add(media)
        self._audit.record(
            p.user_id, "listing.media_add", "listing", listing.id, request=request, data={"key": key}
        )
        await self._session.commit()
        return media

    async def remove(
        self, p: Principal, listing_id: uuid.UUID, media_id: uuid.UUID, request: Request | None = None
    ) -> None:
        listing = await self._listings.get_manageable(listing_id, p)
        media = next((m for m in listing.media if m.id == media_id), None)
        if media is None:
            raise NotFound("Photo not found")
        key = media.storage_key
        listing.media.remove(media)
        self._audit.record(
            p.user_id, "listing.media_delete", "listing", listing.id, request=request, data={"key": key}
        )
        await self._session.commit()
        # Delete the file after the row: a failure leaves an orphan file, never a row without its file.
        await self._storage.delete(key)


class ContactService:
    """Visitor-side interactions with a public listing: WhatsApp hand-off and view tracking."""

    def __init__(self, session: AsyncSession, *, settings: Settings, listings: ListingService) -> None:
        self._session = session
        self._listings = listings
        self._links = WhatsAppLinkBuilder(settings.public_web_base_url)

    async def whatsapp_link(
        self, listing_id: uuid.UUID, user_id: uuid.UUID | None, locale: str, request: Request | None
    ) -> str:
        listing = await self._listings.get_public(listing_id)
        if not listing.contact_whatsapp_e164:
            raise NotFound("This listing has no WhatsApp contact")
        record_event(
            self._session,
            listing_id=listing.id,
            event_type=ListingEventType.whatsapp_click,
            user_id=user_id,
            request=request,
        )
        await self._session.commit()
        return self._links.build(listing, locale)

    async def record_view(
        self, listing_id: uuid.UUID, user_id: uuid.UUID | None, request: Request | None
    ) -> None:
        listing = await self._listings.get_public(listing_id)
        record_event(
            self._session,
            listing_id=listing.id,
            event_type=ListingEventType.view,
            user_id=user_id,
            request=request,
        )
        await self._session.commit()

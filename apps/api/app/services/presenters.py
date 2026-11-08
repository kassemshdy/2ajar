"""Map ORM listings to API response models (DTO assembly).

Keeping this mapping out of routes and services means the wire format can evolve (or gain a v2) without
touching business rules, and guarantees one consistent rule for what is public. Notably the publisher's
WhatsApp number only ever appears in ``to_private``.
"""

from typing import Any, Literal

from app.domain.events import ListingSnapshot
from app.models import AreaProfile, Listing
from app.models.enums import UserRole
from app.schemas.listing import (
    LIVING_FIELDS,
    AreaProfileOut,
    ListingPrivate,
    ListingPublic,
    LivingFactorsOut,
    LocalizedText,
    LocationBrief,
    MediaOut,
    PropertyOut,
    PublisherOut,
)
from app.storage import media_url


class ListingPresenter:
    @staticmethod
    def publisher(listing: Listing) -> PublisherOut:
        if listing.organization is not None:
            name = listing.organization.name
            return PublisherOut(type="broker", display_name=name, organization_name=name)
        creator = listing.created_by
        # First name only: individual owners' full names are not public.
        first_name = creator.full_name.split()[0] if creator.full_name.split() else "Owner"
        kind: Literal["broker", "owner"] = "broker" if creator.role == UserRole.broker else "owner"
        return PublisherOut(type=kind, display_name=first_name, organization_name=None)

    @staticmethod
    def living(prop: Any) -> LivingFactorsOut:
        return LivingFactorsOut(
            **{f: getattr(prop, f) for f in LIVING_FIELDS if getattr(prop, f) is not None}
        )

    @staticmethod
    def area(profile: AreaProfile | None) -> AreaProfileOut | None:
        if profile is None:
            return None
        loc = profile.location
        return AreaProfileOut(
            location_slug=loc.slug,
            location_name_en=loc.name_en,
            location_name_ar=loc.name_ar,
            safety_score=profile.safety_score,
            theft_reports_12m=profile.theft_reports_12m,
            quiet_score=profile.quiet_score,
            noise_notes_en=profile.noise_notes_en,
            noise_notes_ar=profile.noise_notes_ar,
            garbage_collection=profile.garbage_collection,
            flood_risk=profile.flood_risk,
            summary_en=profile.summary_en,
            summary_ar=profile.summary_ar,
            source_note=profile.source_note,
            is_demo=profile.is_demo,
            updated_at=profile.updated_at,
        )

    @classmethod
    def to_public(cls, listing: Listing, area: AreaProfile | None = None) -> ListingPublic:
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
                max_guests=prop.max_guests,
                furnished=prop.furnished,
                amenities=list(prop.amenities or []),
                living=cls.living(prop),
            ),
            location=LocationBrief(slug=loc.slug, name_en=loc.name_en, name_ar=loc.name_ar, path=loc.path),
            media=[
                MediaOut(id=m.id, url=media_url(m.storage_key), width=m.width, height=m.height)
                for m in listing.media
            ],
            publisher=cls.publisher(listing),
            area=cls.area(area),
            published_at=listing.published_at,
            last_confirmed_at=listing.last_confirmed_at,
            is_demo=listing.is_demo,
        )

    @classmethod
    def to_private(
        cls, listing: Listing, lead_count: int = 0, area: AreaProfile | None = None
    ) -> ListingPrivate:
        return ListingPrivate(
            **cls.to_public(listing, area).model_dump(),
            contact_whatsapp=listing.contact_whatsapp_e164,
            expires_at=listing.expires_at,
            created_at=listing.created_at,
            updated_at=listing.updated_at,
            location_id=listing.property.location_id,
            lead_count=lead_count,
        )

    @staticmethod
    def snapshot(listing: Listing) -> ListingSnapshot:
        return ListingSnapshot(
            listing_id=listing.id,
            title=listing.title_en or listing.title_ar,
            price_usd=listing.price_usd_cents // 100,
            price_period=listing.price_period.value,
            area_name=listing.property.location.name_en,
            is_demo=listing.is_demo,
        )

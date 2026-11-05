"""Map ORM listings to API response models (DTO assembly).

Keeping this mapping out of routes and services means the wire format can evolve (or gain a v2) without
touching business rules, and guarantees one consistent rule for what is public. Notably the publisher's
WhatsApp number only ever appears in ``to_private``.
"""

from typing import Literal

from app.domain.events import ListingSnapshot
from app.models import Listing
from app.models.enums import UserRole
from app.schemas.listing import (
    ListingPrivate,
    ListingPublic,
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

    @classmethod
    def to_public(cls, listing: Listing) -> ListingPublic:
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
                MediaOut(id=m.id, url=media_url(m.storage_key), width=m.width, height=m.height)
                for m in listing.media
            ],
            publisher=cls.publisher(listing),
            published_at=listing.published_at,
            last_confirmed_at=listing.last_confirmed_at,
            is_demo=listing.is_demo,
        )

    @classmethod
    def to_private(cls, listing: Listing, lead_count: int = 0) -> ListingPrivate:
        return ListingPrivate(
            **cls.to_public(listing).model_dump(),
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

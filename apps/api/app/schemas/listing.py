import uuid
from datetime import datetime
from typing import Literal

from pydantic import Field, model_validator

from app.models.enums import (
    Amenity,
    Furnished,
    ListingStatus,
    LocationLevel,
    PricePeriod,
    PropertyType,
    TransactionType,
)
from app.schemas.common import APIModel

MAX_PRICE_USD = 100_000_000


class LocationOut(APIModel):
    id: uuid.UUID
    parent_id: uuid.UUID | None
    level: LocationLevel
    slug: str
    name_en: str
    name_ar: str
    path: str


class _ListingFields(APIModel):
    title_en: str | None = Field(default=None, max_length=140)
    title_ar: str | None = Field(default=None, max_length=140)
    description_en: str | None = Field(default=None, max_length=5000)
    description_ar: str | None = Field(default=None, max_length=5000)
    contact_whatsapp: str | None = Field(default=None, max_length=32)
    bedrooms: int | None = Field(default=None, ge=0, le=20)
    bathrooms: int | None = Field(default=None, ge=0, le=20)
    area_sqm: int | None = Field(default=None, ge=1, le=100_000)
    floor: int | None = Field(default=None, ge=-5, le=100)
    furnished: Furnished | None = None
    amenities: list[Amenity] | None = Field(default=None, max_length=len(Amenity))


def _check_period(tx: TransactionType | None, period: PricePeriod | None) -> None:
    if tx is None or period is None:
        return
    if tx == TransactionType.rent and period == PricePeriod.total:
        raise ValueError("Rent listings must be priced monthly or yearly")
    if tx == TransactionType.sale and period != PricePeriod.total:
        raise ValueError("Sale listings must use price_period 'total'")


class ListingCreate(_ListingFields):
    transaction_type: TransactionType
    property_type: PropertyType
    location_id: uuid.UUID
    price_usd: int = Field(gt=0, le=MAX_PRICE_USD)
    price_period: PricePeriod

    @model_validator(mode="after")
    def _validate(self) -> "ListingCreate":
        _check_period(self.transaction_type, self.price_period)
        return self


class ListingUpdate(_ListingFields):
    transaction_type: TransactionType | None = None
    property_type: PropertyType | None = None
    location_id: uuid.UUID | None = None
    price_usd: int | None = Field(default=None, gt=0, le=MAX_PRICE_USD)
    price_period: PricePeriod | None = None


class LocalizedText(APIModel):
    en: str | None
    ar: str | None


class PropertyOut(APIModel):
    property_type: PropertyType
    bedrooms: int | None
    bathrooms: int | None
    area_sqm: int | None
    floor: int | None
    furnished: Furnished | None
    amenities: list[str]


class LocationBrief(APIModel):
    slug: str
    name_en: str
    name_ar: str
    path: str


class MediaOut(APIModel):
    id: uuid.UUID
    url: str
    width: int
    height: int


class PublisherOut(APIModel):
    type: Literal["broker", "owner"]
    display_name: str
    organization_name: str | None


class ListingPublic(APIModel):
    id: uuid.UUID
    status: ListingStatus
    transaction_type: TransactionType
    price_usd: int
    price_period: PricePeriod
    title: LocalizedText
    description: LocalizedText
    property: PropertyOut
    location: LocationBrief
    media: list[MediaOut]
    publisher: PublisherOut
    published_at: datetime | None
    last_confirmed_at: datetime | None
    is_demo: bool


class ListingPrivate(ListingPublic):
    """Returned to people who can manage the listing."""

    contact_whatsapp: str | None
    expires_at: datetime | None
    created_at: datetime
    updated_at: datetime
    location_id: uuid.UUID
    lead_count: int = 0


class WhatsAppHandoffOut(APIModel):
    url: str


class ImportRowOut(APIModel):
    row: int
    ok: bool
    listing_id: uuid.UUID | None
    title: str | None
    errors: list[str]


class ImportResultOut(APIModel):
    dry_run: bool
    total: int
    valid: int
    created: int
    rows: list[ImportRowOut]

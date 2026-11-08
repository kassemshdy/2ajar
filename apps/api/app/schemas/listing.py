import uuid
from datetime import datetime
from typing import Literal

from pydantic import Field, field_validator, model_validator

from app.models.enums import (
    Amenity,
    ElectricitySupply,
    FloodRisk,
    Furnished,
    GarbageCollection,
    ListingStatus,
    LocationLevel,
    PricePeriod,
    PropertyType,
    Sewage,
    SummerComfort,
    TransactionType,
    WaterSource,
    WinterComfort,
)
from app.schemas.common import APIModel

MAX_PRICE_USD = 100_000_000
MAX_POINTS = 6  # highlights / things to know, like short bullet lists on a rental page
MAX_POINT_LENGTH = 100


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
    # Living factors, reported by the publisher
    electricity_supply: ElectricitySupply | None = None
    generator_amps: int | None = Field(default=None, ge=1, le=100)
    electricity_usd_month: int | None = Field(default=None, ge=0, le=5000)
    water_source: WaterSource | None = None
    water_usd_month: int | None = Field(default=None, ge=0, le=2000)
    sewage: Sewage | None = None
    parking_spots: int | None = Field(default=None, ge=0, le=20)
    solar_ready: bool | None = None
    elevator_backup: bool | None = None
    winter_comfort: WinterComfort | None = None
    summer_comfort: SummerComfort | None = None
    highlights: list[str] | None = Field(default=None, max_length=MAX_POINTS)
    things_to_know: list[str] | None = Field(default=None, max_length=MAX_POINTS)

    @field_validator("highlights", "things_to_know")
    @classmethod
    def _clean_points(cls, v: list[str] | None) -> list[str] | None:
        if v is None:
            return None
        cleaned = [p.strip() for p in v if p and p.strip()]
        if any(len(p) > MAX_POINT_LENGTH for p in cleaned):
            raise ValueError(f"Each point must be at most {MAX_POINT_LENGTH} characters")
        return cleaned


LIVING_FIELDS = (
    "electricity_supply",
    "generator_amps",
    "electricity_usd_month",
    "water_source",
    "water_usd_month",
    "sewage",
    "parking_spots",
    "solar_ready",
    "elevator_backup",
    "winter_comfort",
    "summer_comfort",
    "highlights",
    "things_to_know",
)


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


class LivingFactorsOut(APIModel):
    """Publisher-reported running costs and comfort. Shown as 'reported by the publisher'."""

    electricity_supply: ElectricitySupply | None = None
    generator_amps: int | None = None
    electricity_usd_month: int | None = None
    water_source: WaterSource | None = None
    water_usd_month: int | None = None
    sewage: Sewage | None = None
    parking_spots: int | None = None
    solar_ready: bool | None = None
    elevator_backup: bool | None = None
    winter_comfort: WinterComfort | None = None
    summer_comfort: SummerComfort | None = None
    highlights: list[str] = []
    things_to_know: list[str] = []


class AreaProfileOut(APIModel):
    """Staff-curated neighbourhood facts for the listing's area."""

    location_slug: str
    location_name_en: str
    location_name_ar: str
    safety_score: int | None
    theft_reports_12m: int | None
    quiet_score: int | None
    noise_notes_en: str | None
    noise_notes_ar: str | None
    garbage_collection: GarbageCollection | None
    flood_risk: FloodRisk | None
    summary_en: str | None
    summary_ar: str | None
    source_note: str | None
    is_demo: bool
    updated_at: datetime


class AreaProfileIn(APIModel):
    safety_score: int | None = Field(default=None, ge=1, le=5)
    theft_reports_12m: int | None = Field(default=None, ge=0, le=100_000)
    quiet_score: int | None = Field(default=None, ge=1, le=5)
    noise_notes_en: str | None = Field(default=None, max_length=300)
    noise_notes_ar: str | None = Field(default=None, max_length=300)
    garbage_collection: GarbageCollection | None = None
    flood_risk: FloodRisk | None = None
    summary_en: str | None = Field(default=None, max_length=2000)
    summary_ar: str | None = Field(default=None, max_length=2000)
    source_note: str | None = Field(default=None, max_length=300)


class PropertyOut(APIModel):
    property_type: PropertyType
    bedrooms: int | None
    bathrooms: int | None
    area_sqm: int | None
    floor: int | None
    furnished: Furnished | None
    amenities: list[str]
    living: LivingFactorsOut = LivingFactorsOut()


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
    area: AreaProfileOut | None = None  # filled on detail pages and smart-search results
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

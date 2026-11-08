"""Request/response models for the plain-text smart search."""

import uuid
from typing import Literal

from pydantic import Field

from app.models.enums import Furnished, PropertyType, Stay
from app.schemas.common import APIModel
from app.schemas.listing import ListingPublic

MAX_QUERY_LENGTH = 300


class AskRequest(APIModel):
    query: str = Field(min_length=1, max_length=MAX_QUERY_LENGTH)
    locale: Literal["en", "ar"] = "en"


class UnderstoodPreference(APIModel):
    key: str
    label_en: str
    label_ar: str


class Understood(APIModel):
    """What the parser extracted. The web turns these into editable filter chips."""

    stay: Stay | None
    guests_min: int | None
    property_type: PropertyType | None
    location_slug: str | None
    location_name_en: str | None
    location_name_ar: str | None
    price_min: int | None
    price_max: int | None
    bedrooms_min: int | None
    bathrooms_min: int | None
    furnished: Furnished | None
    parking_spots: int | None
    preferences: list[UnderstoodPreference]
    sort: Literal["newest", "price_asc", "price_desc"]


class ReasonOut(APIModel):
    key: str
    label_en: str
    label_ar: str
    status: Literal["match", "miss", "unknown"]
    source: Literal["filter", "listing", "area"]


class RelaxationOut(APIModel):
    key: str
    label_en: str
    label_ar: str


class AskHit(APIModel):
    listing: ListingPublic
    score: int
    reasons: list[ReasonOut]


class AskResponse(APIModel):
    query_id: uuid.UUID | None
    understood: Understood
    summary_en: str
    summary_ar: str
    clarification_en: str | None
    clarification_ar: str | None
    relaxed: list[RelaxationOut]
    results: list[AskHit]
    total: int


class Suggestion(APIModel):
    """A predefined example prompt shown as a chip under the search box."""

    id: str
    text_en: str
    text_ar: str

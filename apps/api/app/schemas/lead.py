import uuid
from datetime import datetime

from pydantic import EmailStr, Field, StrictBool, field_validator

from app.models.enums import LeadSource, LeadStatus
from app.schemas.common import APIModel


class LeadCreate(APIModel):
    name: str = Field(min_length=2, max_length=100)
    phone: str = Field(min_length=6, max_length=32)
    email: EmailStr | None = None
    message: str | None = Field(default=None, max_length=1000)
    consent: StrictBool  # no coercion: "yes"/1 must not count as consent
    consent_text_version: str = Field(min_length=1, max_length=40)

    @field_validator("consent")
    @classmethod
    def _consent_required(cls, v: bool) -> bool:
        if v is not True:
            raise ValueError("Explicit consent is required to share your contact details")
        return v


class LeadOut(APIModel):
    id: uuid.UUID
    listing_id: uuid.UUID
    name: str
    phone_e164: str
    email: str | None
    message: str | None
    source: LeadSource
    status: LeadStatus
    duplicate_count: int
    consent_at: datetime
    created_at: datetime
    last_contact_at: datetime


class LeadReceipt(APIModel):
    """What the person submitting a lead gets back (no internal fields)."""

    id: uuid.UUID
    deduplicated: bool


class LeadWithListing(LeadOut):
    listing_title: str | None

"""Domain events: immutable facts about things that already happened.

Events carry plain data snapshots (never ORM objects), so subscribers can run after the request's database
session is closed and cannot accidentally lazy-load or mutate persistent state.
"""

import uuid
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class DomainEvent:
    """Marker base class for everything published on the event bus."""


@dataclass(frozen=True, slots=True)
class ListingSnapshot:
    listing_id: uuid.UUID
    title: str | None
    price_usd: int
    price_period: str
    area_name: str
    is_demo: bool


@dataclass(frozen=True, slots=True)
class UserRegistered(DomainEvent):
    full_name: str
    role: str
    organization_name: str | None


@dataclass(frozen=True, slots=True)
class ListingCreated(DomainEvent):
    listing: ListingSnapshot


@dataclass(frozen=True, slots=True)
class ListingPublished(DomainEvent):
    listing: ListingSnapshot


@dataclass(frozen=True, slots=True)
class ListingSubmittedForReview(DomainEvent):
    listing: ListingSnapshot


@dataclass(frozen=True, slots=True)
class LeadReceived(DomainEvent):
    listing_id: uuid.UUID
    listing_title: str | None
    source: str
    phone_e164: str


@dataclass(frozen=True, slots=True)
class ListingsImported(DomainEvent):
    created: int
    actor_name: str

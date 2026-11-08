"""Neighbourhood facts curated by 2ajar staff, and the log of plain-text searches.

Area facts (safety, theft reports, noise, garbage collection, flooding) can't come from publishers, who
have an interest in flattering answers, and must never be invented by the search engine. Staff enter them
per location with a source note and a date. The UI shows both, so visitors can judge how fresh they are.
"""

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    SmallInteger,
    String,
    Text,
    false,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, Timestamps, UUIDPk
from app.models.enums import FloodRisk, GarbageCollection
from app.models.location import Location
from app.models.types import enum_type


class AreaProfile(UUIDPk, Timestamps, Base):
    __tablename__ = "area_profiles"
    __table_args__ = (
        CheckConstraint("safety_score BETWEEN 1 AND 5", name="safety_score_range"),
        CheckConstraint("quiet_score BETWEEN 1 AND 5", name="quiet_score_range"),
        CheckConstraint("theft_reports_12m >= 0", name="theft_reports_non_negative"),
    )

    location_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("locations.id", ondelete="CASCADE"), unique=True
    )
    safety_score: Mapped[int | None] = mapped_column(SmallInteger)  # 1 (unsafe) .. 5 (very safe)
    theft_reports_12m: Mapped[int | None] = mapped_column(
        Integer
    )  # reported thefts/break-ins, last 12 months
    quiet_score: Mapped[int | None] = mapped_column(SmallInteger)  # 1 (very noisy) .. 5 (very quiet)
    noise_notes_en: Mapped[str | None] = mapped_column(String(300))  # e.g. "street dogs at night behind X"
    noise_notes_ar: Mapped[str | None] = mapped_column(String(300))
    garbage_collection: Mapped[GarbageCollection | None] = mapped_column(
        enum_type(GarbageCollection, "garbage_collection")
    )
    flood_risk: Mapped[FloodRisk | None] = mapped_column(enum_type(FloodRisk, "flood_risk"))
    summary_en: Mapped[str | None] = mapped_column(Text)
    summary_ar: Mapped[str | None] = mapped_column(Text)
    source_note: Mapped[str | None] = mapped_column(String(300))  # where the data comes from
    is_demo: Mapped[bool] = mapped_column(Boolean, default=False, server_default=false())
    updated_by_user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))

    location: Mapped[Location] = relationship(lazy="joined")


class SearchQuery(UUIDPk, Base):
    """One plain-text search: what was asked, what we understood and how many results (quality metrics)."""

    __tablename__ = "search_queries"
    __table_args__ = (Index("ix_search_queries_created", text("created_at DESC")),)

    query: Mapped[str] = mapped_column(String(300))
    locale: Mapped[str] = mapped_column(String(5))
    parsed: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict, server_default="{}")
    result_count: Mapped[int] = mapped_column(Integer, default=0)
    clarification: Mapped[bool] = mapped_column(Boolean, default=False, server_default=false())
    latency_ms: Mapped[int] = mapped_column(Integer, default=0)
    user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Favorite(Base):
    """A listing a signed-in user saved (the heart). One row per user and listing, so saving is idempotent."""

    __tablename__ = "favorites"

    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    listing_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("listings.id", ondelete="CASCADE"), primary_key=True, index=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

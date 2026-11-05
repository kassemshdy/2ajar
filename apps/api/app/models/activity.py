import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, Timestamps, UUIDPk
from app.models.enums import LeadSource, LeadStatus, ListingEventType
from app.models.types import enum_type


class Lead(UUIDPk, Timestamps, Base):
    __tablename__ = "leads"
    __table_args__ = (
        Index("ix_leads_listing_created", "listing_id", "created_at"),
        Index("ix_leads_dedupe", "listing_id", "phone_e164", "created_at"),
    )

    listing_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("listings.id", ondelete="CASCADE"))
    seeker_user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), index=True
    )
    name: Mapped[str] = mapped_column(String(100))
    phone_e164: Mapped[str] = mapped_column(String(20))
    email: Mapped[str | None] = mapped_column(String(254))
    message: Mapped[str | None] = mapped_column(Text)
    source: Mapped[LeadSource] = mapped_column(enum_type(LeadSource, "lead_source"))
    status: Mapped[LeadStatus] = mapped_column(enum_type(LeadStatus, "lead_status"), default=LeadStatus.new)
    consent_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    consent_text_version: Mapped[str] = mapped_column(String(40))
    duplicate_count: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    last_contact_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class ListingEvent(UUIDPk, Base):
    __tablename__ = "listing_events"
    __table_args__ = (Index("ix_listing_events_listing_type_time", "listing_id", "event_type", "created_at"),)

    listing_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("listings.id", ondelete="CASCADE"))
    event_type: Mapped[ListingEventType] = mapped_column(enum_type(ListingEventType, "listing_event_type"))
    user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    session_hash: Mapped[str | None] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class AuditLog(UUIDPk, Base):
    __tablename__ = "audit_logs"
    __table_args__ = (Index("ix_audit_logs_resource", "resource_type", "resource_id"),)

    actor_user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), index=True
    )
    action: Mapped[str] = mapped_column(String(80))
    resource_type: Mapped[str] = mapped_column(String(40))
    resource_id: Mapped[uuid.UUID | None] = mapped_column()
    data: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict, server_default="{}")
    ip_hash: Mapped[str | None] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

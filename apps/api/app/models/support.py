"""Support tickets (in-app bug reports) and personal API tokens (used by the MCP server)."""

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Integer, String, Text, false, func, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, Timestamps, UUIDPk
from app.models.enums import TicketCategory, TicketPriority, TicketStatus
from app.models.types import enum_type
from app.models.user import User


class Ticket(UUIDPk, Timestamps, Base):
    __tablename__ = "tickets"
    __table_args__ = (
        # Triage queue: newest first within a status; and "my tickets".
        Index("ix_tickets_status_created", "status", text("created_at DESC")),
        Index("ix_tickets_reporter_created", "reporter_user_id", text("created_at DESC")),
    )

    number: Mapped[int] = mapped_column(
        Integer, unique=True, server_default=text("nextval('ticket_number_seq')")
    )
    reporter_user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    assignee_user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), index=True
    )
    category: Mapped[TicketCategory] = mapped_column(enum_type(TicketCategory, "ticket_category"))
    status: Mapped[TicketStatus] = mapped_column(
        enum_type(TicketStatus, "ticket_status"), default=TicketStatus.open
    )
    priority: Mapped[TicketPriority] = mapped_column(
        enum_type(TicketPriority, "ticket_priority"), default=TicketPriority.normal
    )
    title: Mapped[str] = mapped_column(String(160))
    description: Mapped[str] = mapped_column(Text)
    # Context captured automatically by the floating button (helps reproduce the bug).
    page_url: Mapped[str | None] = mapped_column(String(500))
    context: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict, server_default="{}")
    attachment_key: Mapped[str | None] = mapped_column(String(300))
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    reporter: Mapped[User] = relationship(foreign_keys=[reporter_user_id], lazy="joined")
    assignee: Mapped[User | None] = relationship(foreign_keys=[assignee_user_id], lazy="joined")
    comments: Mapped[list["TicketComment"]] = relationship(
        lazy="selectin", order_by="TicketComment.created_at", cascade="all, delete-orphan"
    )


class TicketComment(UUIDPk, Base):
    __tablename__ = "ticket_comments"
    __table_args__ = (Index("ix_ticket_comments_ticket_created", "ticket_id", "created_at"),)

    ticket_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tickets.id", ondelete="CASCADE"))
    author_user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    body: Mapped[str] = mapped_column(Text)
    # Internal notes are visible to staff only, never to the reporter.
    is_internal: Mapped[bool] = mapped_column(Boolean, default=False, server_default=false())
    via: Mapped[str] = mapped_column(String(20), default="web", server_default="web")  # web | mcp
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    author: Mapped[User | None] = relationship(lazy="joined")


class ApiToken(UUIDPk, Base):
    """Personal access token. Only a SHA-256 hash is stored; the raw value is shown once at creation."""

    __tablename__ = "api_tokens"

    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(80))
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    prefix: Mapped[str] = mapped_column(String(12))  # first characters, to recognise a token in the UI
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    user: Mapped[User] = relationship(lazy="joined")

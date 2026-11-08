import uuid
from datetime import datetime
from typing import Any

from pydantic import Field, field_validator

from app.models.enums import TicketCategory, TicketPriority, TicketStatus
from app.schemas.common import APIModel

MAX_CONTEXT_KEYS = 20


class TicketCreate(APIModel):
    category: TicketCategory = TicketCategory.bug
    title: str = Field(min_length=3, max_length=160)
    description: str = Field(min_length=10, max_length=5000)
    page_url: str | None = Field(default=None, max_length=500)
    # Browser context captured by the floating button: locale, viewport, user agent, app version...
    context: dict[str, str | int | float | bool | None] = Field(default_factory=dict)

    @field_validator("context")
    @classmethod
    def _small_context(cls, v: dict[str, Any]) -> dict[str, Any]:
        if len(v) > MAX_CONTEXT_KEYS:
            raise ValueError(f"context may have at most {MAX_CONTEXT_KEYS} keys")
        return {str(k)[:40]: (val[:300] if isinstance(val, str) else val) for k, val in v.items()}


class TicketUpdate(APIModel):
    status: TicketStatus | None = None
    priority: TicketPriority | None = None
    category: TicketCategory | None = None
    assignee_user_id: uuid.UUID | None = None


class CommentCreate(APIModel):
    body: str = Field(min_length=1, max_length=5000)
    is_internal: bool = False


class PersonRef(APIModel):
    id: uuid.UUID
    name: str
    email: str | None = None  # only shown to staff


class CommentOut(APIModel):
    id: uuid.UUID
    body: str
    is_internal: bool
    via: str
    author: PersonRef | None
    author_is_staff: bool
    created_at: datetime


class TicketSummary(APIModel):
    id: uuid.UUID
    number: int
    title: str
    category: TicketCategory
    status: TicketStatus
    priority: TicketPriority
    reporter: PersonRef
    assignee: PersonRef | None
    comment_count: int
    created_at: datetime
    updated_at: datetime


class TicketOut(TicketSummary):
    description: str
    page_url: str | None
    context: dict[str, Any]
    has_attachment: bool
    resolved_at: datetime | None
    comments: list[CommentOut]

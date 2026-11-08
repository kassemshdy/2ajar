import uuid
from datetime import datetime

from pydantic import Field

from app.schemas.common import APIModel


class ApiTokenCreate(APIModel):
    name: str = Field(min_length=2, max_length=80)
    expires_in_days: int | None = Field(default=90, ge=1, le=365)


class ApiTokenOut(APIModel):
    id: uuid.UUID
    name: str
    prefix: str
    created_at: datetime
    expires_at: datetime | None
    last_used_at: datetime | None
    revoked_at: datetime | None


class ApiTokenCreated(ApiTokenOut):
    token: str  # shown exactly once

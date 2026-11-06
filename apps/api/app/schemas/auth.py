import uuid
from typing import Literal

from pydantic import EmailStr, Field

from app.models.enums import OrgRole, UserRole
from app.schemas.common import APIModel


class RegisterIn(APIModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=128)
    full_name: str = Field(min_length=2, max_length=120)
    phone: str | None = Field(default=None, max_length=32)
    role: Literal["seeker", "owner", "broker"]
    organization_name: str | None = Field(default=None, min_length=2, max_length=160)
    locale: Literal["en", "ar"] = "en"


class LoginIn(APIModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=128)


class MembershipOut(APIModel):
    organization_id: uuid.UUID
    organization_name: str
    role: OrgRole


class UserOut(APIModel):
    id: uuid.UUID
    email: str
    full_name: str
    phone_e164: str | None
    role: UserRole
    locale: str
    memberships: list[MembershipOut]

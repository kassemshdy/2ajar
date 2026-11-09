import uuid
from datetime import datetime

from pydantic import Field

from app.models.enums import OrgRole, Permission, UserRole
from app.schemas.common import APIModel


class AdminMembershipOut(APIModel):
    organization_id: uuid.UUID
    organization_name: str
    role: OrgRole


class AdminUserOut(APIModel):
    id: uuid.UUID
    email: str
    full_name: str
    phone_e164: str | None
    role: UserRole
    is_active: bool
    is_demo: bool
    is_verified: bool = False
    extra_permissions: list[Permission]
    permissions: list[Permission]  # effective = role defaults + extra grants
    memberships: list[AdminMembershipOut]
    created_at: datetime
    last_login_at: datetime | None


class AdminUserUpdate(APIModel):
    full_name: str | None = Field(default=None, min_length=2, max_length=120)
    role: UserRole | None = None
    is_active: bool | None = None
    is_verified: bool | None = None
    extra_permissions: list[Permission] | None = Field(default=None, max_length=len(Permission))


class PermissionInfo(APIModel):
    key: Permission
    grantable: bool
    roles: list[UserRole]  # roles that include it by default


class AdminAgencyOut(APIModel):
    id: uuid.UUID
    name: str
    slug: str
    is_verified: bool
    is_demo: bool
    members: int
    live_listings: int
    created_at: datetime


class AdminAgencyUpdate(APIModel):
    is_verified: bool

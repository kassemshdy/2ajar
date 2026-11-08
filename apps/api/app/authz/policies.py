"""Central authorization policies. Pure functions — easy to unit test as a matrix.

Rule of thumb: services call these before reading private data or mutating anything. Callers that fail
a check on a private resource get 404 (ADR-010).
"""

import uuid
from dataclasses import dataclass, field
from datetime import datetime

from app.models.enums import ListingStatus, OrgRole, Permission, UserRole


@dataclass(frozen=True)
class Principal:
    user_id: uuid.UUID
    role: UserRole
    org_roles: dict[uuid.UUID, OrgRole] = field(default_factory=dict)
    permissions: frozenset[Permission] = frozenset()

    def has(self, permission: Permission) -> bool:
        return permission in self.permissions

    @property
    def is_admin(self) -> bool:
        return self.role == UserRole.platform_admin

    @property
    def admin_org_ids(self) -> set[uuid.UUID]:
        return {org for org, r in self.org_roles.items() if r == OrgRole.agency_admin}

    @property
    def primary_org_id(self) -> uuid.UUID | None:
        # Deterministic choice when a broker belongs to several orgs (rare in MVP).
        return min(self.org_roles, key=str) if self.org_roles else None


@dataclass(frozen=True)
class ListingRef:
    """The subset of a listing needed for authorization decisions."""

    created_by_user_id: uuid.UUID
    organization_id: uuid.UUID | None
    status: ListingStatus
    expires_at: datetime | None
    is_demo: bool


def can_create_listing(p: Principal) -> bool:
    return p.role in (UserRole.owner, UserRole.broker, UserRole.platform_admin)


def can_manage_listing(p: Principal | None, listing: ListingRef) -> bool:
    if p is None:
        return False
    if p.is_admin:
        return True
    if listing.created_by_user_id == p.user_id:
        return True
    return listing.organization_id is not None and listing.organization_id in p.admin_org_ids


def can_view_leads_of(p: Principal | None, listing: ListingRef) -> bool:
    return can_manage_listing(p, listing)


def is_publicly_visible(listing: ListingRef, now: datetime, demo_mode: bool) -> bool:
    if listing.status != ListingStatus.published:
        return False
    if listing.expires_at is not None and listing.expires_at <= now:
        return False
    return not (listing.is_demo and not demo_mode)


def can_view_listing(p: Principal | None, listing: ListingRef, now: datetime, demo_mode: bool) -> bool:
    return is_publicly_visible(listing, now, demo_mode) or can_manage_listing(p, listing)

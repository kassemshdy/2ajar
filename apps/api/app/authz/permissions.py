"""Role → permission mapping (RBAC with per-user grants).

Roles describe *who someone is* on the marketplace; permissions describe *what they may do in the
back office*. Keeping the mapping in one table makes audits easy ("who can manage users?") and lets admins
grant a single capability (e.g. ``tickets.manage`` to a broker who helps with support) without a new role.
"""

from collections.abc import Iterable

from app.models.enums import Permission, UserRole

ROLE_PERMISSIONS: dict[UserRole, frozenset[Permission]] = {
    UserRole.platform_admin: frozenset(Permission),
    UserRole.staff: frozenset(
        {
            Permission.users_read,
            Permission.tickets_read,
            Permission.tickets_manage,
            Permission.listings_moderate,
            Permission.analytics_read,
            Permission.areas_manage,
            Permission.mcp_access,
        }
    ),
    UserRole.broker: frozenset(),
    UserRole.owner: frozenset(),
    UserRole.seeker: frozenset(),
}

# Grants that only role assignment may give: extra-permission grants can never escalate to user management.
NON_GRANTABLE: frozenset[Permission] = frozenset({Permission.users_manage})


def effective_permissions(role: UserRole, extra: Iterable[str] = ()) -> frozenset[Permission]:
    granted = {Permission(p) for p in extra if p in Permission._value2member_map_}
    return ROLE_PERMISSIONS.get(role, frozenset()) | (granted - NON_GRANTABLE)

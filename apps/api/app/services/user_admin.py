"""Back-office user management: search, inspect and change roles, status and permission grants.

Safety rules (enforced here so every caller — admin UI, future tools — gets them):
* You cannot change your own role or deactivate yourself (no accidental lock-out).
* The last active platform admin cannot be demoted or deactivated.
* Only platform admins may create or modify platform admins.
* ``users.manage`` can never be granted as an extra permission (only via the admin role).
* Deactivating a user ends all their sessions and revokes their API tokens immediately.
"""

import uuid
from typing import Any

from fastapi import Request
from sqlalchemy import func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.authz.permissions import NON_GRANTABLE, ROLE_PERMISSIONS, effective_permissions
from app.authz.policies import Principal
from app.core.errors import Conflict, Forbidden, NotFound, ValidationFailed
from app.core.security import utcnow
from app.models import ApiToken, RefreshToken, User
from app.models.enums import Permission, UserRole
from app.schemas.admin import AdminMembershipOut, AdminUserOut, AdminUserUpdate, PermissionInfo
from app.services.audit import AuditTrail


def present_user(user: User) -> AdminUserOut:
    extra = [Permission(p) for p in (user.extra_permissions or []) if p in Permission._value2member_map_]
    return AdminUserOut(
        id=user.id,
        email=user.email,
        full_name=user.full_name,
        phone_e164=user.phone_e164,
        role=user.role,
        is_active=user.is_active,
        is_demo=user.is_demo,
        extra_permissions=extra,
        permissions=sorted(effective_permissions(user.role, extra)),
        memberships=[
            AdminMembershipOut(
                organization_id=m.organization_id, organization_name=m.organization.name, role=m.role
            )
            for m in user.memberships
        ],
        created_at=user.created_at,
        last_login_at=user.last_login_at,
    )


def permission_catalog() -> list[PermissionInfo]:
    return [
        PermissionInfo(
            key=p,
            grantable=p not in NON_GRANTABLE,
            roles=[r for r, perms in ROLE_PERMISSIONS.items() if p in perms],
        )
        for p in Permission
    ]


class UserAdminService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._audit = AuditTrail(session)

    async def search(
        self,
        *,
        query: str | None = None,
        role: UserRole | None = None,
        is_active: bool | None = None,
        page: int = 1,
        page_size: int = 25,
    ) -> tuple[list[User], int]:
        stmt = select(User)
        if query:
            like = f"%{query.strip().lower()}%"
            stmt = stmt.where(or_(func.lower(User.email).like(like), func.lower(User.full_name).like(like)))
        if role:
            stmt = stmt.where(User.role == role)
        if is_active is not None:
            stmt = stmt.where(User.is_active.is_(is_active))
        total = await self._session.scalar(select(func.count()).select_from(stmt.subquery())) or 0
        rows = await self._session.scalars(
            stmt.order_by(User.created_at.desc(), User.id).offset((page - 1) * page_size).limit(page_size)
        )
        return list(rows), total

    async def get(self, user_id: uuid.UUID) -> User:
        user = await self._session.get(User, user_id)
        if user is None:
            raise NotFound("User not found")
        return user

    async def update(
        self, actor: Principal, user_id: uuid.UUID, data: AdminUserUpdate, request: Request | None = None
    ) -> User:
        user = await self.get(user_id)
        changes = data.model_dump(exclude_unset=True)
        before: dict[str, Any] = {
            "role": user.role.value,
            "is_active": user.is_active,
            "extra_permissions": list(user.extra_permissions or []),
            "full_name": user.full_name,
        }
        new_role: UserRole = changes.get("role") or user.role
        new_active: bool = changes["is_active"] if changes.get("is_active") is not None else user.is_active

        is_self = user.id == actor.user_id
        if is_self and (new_role != user.role or not new_active):
            raise Conflict("You cannot change your own role or deactivate your own account")
        touches_admin = user.role == UserRole.platform_admin or new_role == UserRole.platform_admin
        if touches_admin and not actor.is_admin:
            raise Forbidden("Only platform admins can manage platform admin accounts")
        losing_admin = user.role == UserRole.platform_admin and (
            new_role != UserRole.platform_admin or not new_active
        )
        if losing_admin and await self._active_admin_count() <= 1:
            raise Conflict("At least one active platform admin must remain")
        if changes.get("extra_permissions") is not None:
            requested = set(changes["extra_permissions"])
            forbidden = requested & NON_GRANTABLE
            if forbidden:
                raise ValidationFailed(
                    f"{', '.join(sorted(forbidden))} can only be given through the platform admin role"
                )
            user.extra_permissions = sorted(p.value for p in requested)

        if changes.get("full_name"):
            user.full_name = changes["full_name"]
        user.role = new_role
        deactivated = user.is_active and not new_active
        user.is_active = new_active
        if deactivated:
            await self._revoke_access(user.id)

        after = {
            "role": user.role.value,
            "is_active": user.is_active,
            "extra_permissions": list(user.extra_permissions or []),
            "full_name": user.full_name,
        }
        diff = {k: {"from": before[k], "to": after[k]} for k in after if before[k] != after[k]}
        if diff:
            self._audit.record(
                actor.user_id, "user.admin_update", "user", user.id, request=request, data=diff
            )
        await self._session.commit()
        await self._session.refresh(user, ["memberships"])
        return user

    async def _active_admin_count(self) -> int:
        stmt = (
            select(func.count())
            .select_from(User)
            .where(User.role == UserRole.platform_admin, User.is_active.is_(True))
        )
        return int(await self._session.scalar(stmt) or 0)

    async def _revoke_access(self, user_id: uuid.UUID) -> None:
        now = utcnow()
        await self._session.execute(
            update(RefreshToken)
            .where(RefreshToken.user_id == user_id, RefreshToken.revoked_at.is_(None))
            .values(revoked_at=now)
        )
        await self._session.execute(
            update(ApiToken)
            .where(ApiToken.user_id == user_id, ApiToken.revoked_at.is_(None))
            .values(revoked_at=now)
        )

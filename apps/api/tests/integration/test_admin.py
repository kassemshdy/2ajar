from typing import Any

import pytest
from sqlalchemy import select

from app.authz.permissions import effective_permissions
from app.core.config import Settings
from app.db.session import get_sessionmaker
from app.models import AuditLog, User
from app.models.enums import Permission, UserRole
from app.services.superuser import ensure_superuser
from tests.conftest import PASSWORD, promote


def test_role_permission_matrix() -> None:
    assert effective_permissions(UserRole.platform_admin) == frozenset(Permission)
    staff = effective_permissions(UserRole.staff)
    assert Permission.tickets_manage in staff and Permission.users_manage not in staff
    assert effective_permissions(UserRole.broker) == frozenset()
    assert effective_permissions(UserRole.broker, ["tickets.read", "users.manage", "bogus"]) == {
        Permission.tickets_read
    }, "users.manage is never grantable, unknown keys ignored"


async def test_superuser_bootstrap_from_env(anon: Any) -> None:
    settings = Settings(superuser_email="Boss@example.com", superuser_password="super-secret-pass-1")
    async with get_sessionmaker()() as session:
        assert (await ensure_superuser(session, settings)).action == "created"
        assert (await ensure_superuser(session, settings)).action == "unchanged"
        user = await session.scalar(select(User).where(User.email == "boss@example.com"))
        assert user is not None and user.role == UserRole.platform_admin
        user.role, user.is_active = UserRole.seeker, False
        await session.commit()
        rotated = Settings(superuser_email="boss@example.com", superuser_password="rotated-secret-pass-2")
        result = await ensure_superuser(session, rotated)
        assert result.action == "updated"
        await session.refresh(user)
        assert user.role == UserRole.platform_admin and user.is_active
        assert (await ensure_superuser(session, Settings())).action == "skipped"

    r = await anon.client.post(
        "/api/v1/auth/login", json={"email": "boss@example.com", "password": "rotated-secret-pass-2"}
    )
    assert r.status_code == 200 and "users.manage" in r.json()["permissions"]
    r = await anon.client.post(
        "/api/v1/auth/login", json={"email": "boss@example.com", "password": "super-secret-pass-1"}
    )
    assert r.status_code == 401


def test_superuser_config_validation() -> None:
    with pytest.raises(ValueError):
        Settings(superuser_email="a@b.co")
    with pytest.raises(ValueError):
        Settings(
            env="staging",
            jwt_secret="x" * 40,
            cookie_secure=True,
            superuser_email="a@b.co",
            superuser_password="short",
        )


async def test_admin_user_management(make_actor: Any) -> None:
    admin = await make_actor("seeker", "admin@example.com")
    await promote(admin, "platform_admin")
    broker = await make_actor("broker", "b@example.com", org="Cedar")
    seeker = await make_actor("seeker", "s@example.com")

    r = await admin.client.get("/api/v1/admin/users", params={"q": "example.com", "page_size": 2})
    body = r.json()
    assert r.status_code == 200 and body["total"] == 3 and len(body["items"]) == 2
    r = await admin.client.get("/api/v1/admin/users", params={"role": "broker"})
    item = r.json()["items"][0]
    assert item["email"] == "b@example.com" and item["memberships"][0]["organization_name"] == "Cedar"
    assert "password_hash" not in item
    perms = (await admin.client.get("/api/v1/admin/permissions")).json()
    assert {p["key"] for p in perms} == {p.value for p in Permission}
    assert next(p for p in perms if p["key"] == "users.manage")["grantable"] is False

    # Make the broker a support helper with one extra grant
    url = f"/api/v1/admin/users/{broker.user['id']}"
    r = await admin.client.patch(url, json={"extra_permissions": ["tickets.read", "tickets.manage"]})
    assert r.status_code == 200 and set(r.json()["permissions"]) == {"tickets.read", "tickets.manage"}
    r = await admin.client.patch(url, json={"extra_permissions": ["users.manage"]})
    assert r.status_code == 422
    assert (await broker.client.get("/api/v1/admin/tickets")).status_code == 200
    assert (await broker.client.get("/api/v1/admin/users")).status_code == 403

    # Promote seeker to staff, then deactivate: their session dies immediately
    r = await admin.client.patch(f"/api/v1/admin/users/{seeker.user['id']}", json={"role": "staff"})
    assert r.json()["role"] == "staff" and "tickets.manage" in r.json()["permissions"]
    r = await admin.client.patch(f"/api/v1/admin/users/{seeker.user['id']}", json={"is_active": False})
    assert r.status_code == 200 and r.json()["is_active"] is False
    assert (await seeker.client.get("/api/v1/me")).status_code == 401
    assert (await seeker.client.post("/api/v1/auth/refresh")).status_code == 401

    async with get_sessionmaker()() as s:
        diffs = (await s.scalars(select(AuditLog.data).where(AuditLog.action == "user.admin_update"))).all()
    assert {"role": {"from": "seeker", "to": "staff"}} in diffs

    assert (await admin.client.get(f"/api/v1/admin/users/{seeker.user['id']}")).json()["role"] == "staff"
    assert (
        await admin.client.get("/api/v1/admin/users/00000000-0000-0000-0000-000000000000")
    ).status_code == 404


async def test_admin_safety_guards(make_actor: Any) -> None:
    admin = await make_actor("seeker", "admin@example.com")
    await promote(admin, "platform_admin")
    staff = await make_actor("seeker", "staff@example.com")
    await promote(staff, "staff", ["users.manage"])  # stored but never effective

    me = f"/api/v1/admin/users/{admin.user['id']}"
    assert (await admin.client.patch(me, json={"role": "seeker"})).status_code == 409
    assert (await admin.client.patch(me, json={"is_active": False})).status_code == 409
    assert (await admin.client.patch(me, json={"full_name": "Chief Admin"})).status_code == 200
    # staff can read users but not manage them
    assert (await staff.client.get("/api/v1/admin/users")).status_code == 200
    assert (await staff.client.patch(me, json={"full_name": "x y"})).status_code == 403

    second = await make_actor("seeker", "second@example.com")
    await promote(second, "platform_admin")
    # Two admins: demoting one is fine, then the last one is protected
    r = await second.client.patch(me, json={"role": "staff"})
    assert r.status_code == 200
    await promote(admin, "platform_admin")
    await promote(second, "platform_admin")
    # Only platform admins may touch admin accounts — a staff member with users.manage is impossible anyway,
    # so simulate the service guard directly.
    from app.authz.policies import Principal
    from app.core.errors import Conflict, Forbidden
    from app.schemas.admin import AdminUserUpdate
    from app.services.user_admin import UserAdminService

    async with get_sessionmaker()() as s:
        svc = UserAdminService(s)
        staff_principal = Principal(user_id=staff.user["id"], role=UserRole.staff)
        with pytest.raises(Forbidden):
            await svc.update(staff_principal, admin.user["id"], AdminUserUpdate(full_name="Hacked Name"))
        await promote(second, "seeker")
        admin_principal = Principal(user_id=second.user["id"], role=UserRole.platform_admin)
        with pytest.raises(Conflict):
            await svc.update(admin_principal, admin.user["id"], AdminUserUpdate(is_active=False))


async def test_non_staff_cannot_reach_admin(make_actor: Any) -> None:
    owner = await make_actor("owner", "o@example.com")
    for path in (
        "/api/v1/admin/users",
        "/api/v1/admin/tickets",
        "/api/v1/admin/stats",
        "/api/v1/admin/permissions",
    ):
        assert (await owner.client.get(path)).status_code == 403, path
    anon = await make_actor()
    assert (await anon.client.get("/api/v1/admin/users")).status_code == 401
    me = (await owner.client.get("/api/v1/me")).json()
    assert me["permissions"] == []
    assert PASSWORD

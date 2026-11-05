from typing import Any

from tests.conftest import PASSWORD


async def test_register_login_me_logout(make_actor: Any) -> None:
    broker = await make_actor("broker", "Rami@Example.com", org="Cedar Homes")
    assert broker.user["email"] == "rami@example.com"
    assert broker.user["memberships"][0]["role"] == "agency_admin"
    assert broker.user["phone_e164"] == "+96171111111"

    me = await broker.client.get("/api/v1/me")
    assert me.status_code == 200
    assert me.json()["role"] == "broker"

    r = await broker.client.post("/api/v1/auth/logout")
    assert r.status_code == 204
    assert (await broker.client.get("/api/v1/me")).status_code == 401

    fresh = await make_actor()
    r = await fresh.client.post(
        "/api/v1/auth/login", json={"email": "RAMI@example.com", "password": PASSWORD}
    )
    assert r.status_code == 200
    cookie_header = ",".join(r.headers.get_list("set-cookie"))
    assert "access_token=" in cookie_header and "HttpOnly" in cookie_header
    assert "SameSite=lax" in cookie_header


async def test_password_not_exposed_and_hash_is_argon2(make_actor: Any) -> None:
    from sqlalchemy import select

    from app.db.session import get_sessionmaker
    from app.models import User

    actor = await make_actor("owner", "owner@example.com")
    assert "password" not in str(actor.user).lower()
    async with get_sessionmaker()() as s:
        user = await s.scalar(select(User).where(User.email == "owner@example.com"))
        assert user is not None and user.password_hash.startswith("$argon2id$")


async def test_duplicate_email_conflict(make_actor: Any) -> None:
    await make_actor("seeker", "dup@example.com")
    other = await make_actor()
    r = await other.client.post(
        "/api/v1/auth/register",
        json={"email": "DUP@example.com", "password": PASSWORD, "full_name": "X Y", "role": "owner"},
    )
    assert r.status_code == 409
    assert r.json()["error"]["code"] == "conflict"


async def test_register_validation(anon: Any) -> None:
    base = {"email": "a@example.com", "full_name": "A B", "role": "owner"}
    r = await anon.client.post("/api/v1/auth/register", json={**base, "password": "short"})
    assert r.status_code == 422
    r = await anon.client.post(
        "/api/v1/auth/register", json={**base, "password": PASSWORD, "role": "platform_admin"}
    )
    assert r.status_code == 422, "cannot self-register as platform admin"
    r = await anon.client.post(
        "/api/v1/auth/register", json={**base, "password": PASSWORD, "organization_name": "Owner Org"}
    )
    assert r.status_code == 422, "only brokers create agencies"
    r = await anon.client.post("/api/v1/auth/register", json={**base, "password": PASSWORD, "phone": "12"})
    assert r.status_code == 422


async def test_bad_login_is_generic(make_actor: Any, anon: Any) -> None:
    await make_actor("owner", "o@example.com")
    r1 = await anon.client.post(
        "/api/v1/auth/login", json={"email": "o@example.com", "password": "wrong-password"}
    )
    r2 = await anon.client.post(
        "/api/v1/auth/login", json={"email": "nobody@example.com", "password": "x" * 12}
    )
    assert r1.status_code == r2.status_code == 401
    assert r1.json()["error"]["message"] == r2.json()["error"]["message"]


async def test_login_rate_limited(anon: Any) -> None:
    codes = []
    for _ in range(12):
        r = await anon.client.post(
            "/api/v1/auth/login", json={"email": "x@example.com", "password": "x" * 12}
        )
        codes.append(r.status_code)
    assert codes[:10] == [401] * 10
    assert codes[-1] == 429


async def test_refresh_rotation_and_reuse_detection(make_actor: Any) -> None:
    actor = await make_actor("seeker", "s@example.com")
    old_refresh = actor.client.cookies.get("refresh_token")
    r = await actor.client.post("/api/v1/auth/refresh")
    assert r.status_code == 200
    new_refresh = actor.client.cookies.get("refresh_token")
    assert new_refresh and new_refresh != old_refresh

    # An attacker replays the old (rotated) token -> the whole family is revoked.
    attacker = await make_actor()
    attacker.client.cookies.set("refresh_token", old_refresh, path="/api/v1/auth")
    assert (await attacker.client.post("/api/v1/auth/refresh")).status_code == 401
    assert (await actor.client.post("/api/v1/auth/refresh")).status_code == 401


async def test_csrf_required_for_cookie_mutations(make_actor: Any) -> None:
    broker = await make_actor("broker", "b@example.com", org="Org")
    access = broker.client.cookies.get("access_token")
    raw = await make_actor()
    raw.client.cookies.set("access_token", access)  # cookie but no csrf cookie/header
    r = await raw.client.post("/api/v1/listings", json={})
    assert r.status_code == 403
    # Safe methods are fine without CSRF
    assert (await raw.client.get("/api/v1/me")).status_code == 200
    # Bearer auth (non-browser) does not need CSRF
    bearer = await make_actor()
    r = await bearer.client.get("/api/v1/me", headers={"Authorization": f"Bearer {access}"})
    assert r.status_code == 200


async def test_tampered_token_rejected(anon: Any) -> None:
    import jwt

    forged = jwt.encode(
        {"sub": "00000000-0000-0000-0000-000000000000", "typ": "access", "role": "platform_admin"},
        "wrong-secret",
        algorithm="HS256",
    )
    r = await anon.client.get("/api/v1/me", headers={"Authorization": f"Bearer {forged}"})
    assert r.status_code == 401
    none_alg = jwt.encode({"sub": "x", "typ": "access"}, None, algorithm="none")
    r = await anon.client.get("/api/v1/me", headers={"Authorization": f"Bearer {none_alg}"})
    assert r.status_code == 401

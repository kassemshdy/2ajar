import json
import logging
from typing import Any

import pytest
from sqlalchemy import func, select
from starlette.requests import Request

from app.core.logging import JsonFormatter, configure_logging
from app.core.ratelimit import client_ip
from app.db.session import get_sessionmaker
from app.models import Listing, ListingMedia, Organization, User
from tests.conftest import create_listing, upload_photo


async def test_media_route_serves_and_rejects(make_actor: Any, anon: Any) -> None:
    broker = await make_actor("broker", "b@example.com", org="Org")
    listing = await create_listing(broker)
    media = (await upload_photo(broker, listing["id"])).json()
    r = await anon.client.get(media["url"])
    assert r.status_code == 200
    assert r.headers["content-type"] == "image/webp"
    assert "immutable" in r.headers["cache-control"]
    assert r.content[:4] == b"RIFF"
    assert (await anon.client.get("/media/listings/nope.webp")).status_code == 404
    assert (await anon.client.get("/media/..%2F..%2Fetc%2Fpasswd")).status_code == 404


async def test_config_and_unknown_routes(anon: Any) -> None:
    cfg = (await anon.client.get("/api/v1/config")).json()
    assert cfg["consent_text_version"] == "2026-11-v1" and cfg["demo_mode"] is False
    r = await anon.client.get("/api/v1/does-not-exist")
    assert r.status_code == 404 and r.json()["error"]["code"] == "not_found"
    r = await anon.client.get("/healthz", headers={"X-Request-ID": "abc-123"})
    assert r.headers["x-request-id"] == "abc-123"


async def test_readyz_reports_db_failure(anon: Any, monkeypatch: Any) -> None:
    import app.main as main

    class Broken:
        def connect(self) -> Any:
            raise RuntimeError("db down")

    monkeypatch.setattr(main, "get_engine", lambda: Broken())
    r = await anon.client.get("/readyz")
    assert r.status_code == 503


async def test_lifespan_runs() -> None:
    from app.main import create_app

    app = create_app()
    async with app.router.lifespan_context(app):
        pass


def _request(xff: str | None, peer: str = "10.0.0.9") -> Request:
    headers = [(b"x-forwarded-for", xff.encode())] if xff is not None else []
    return Request({"type": "http", "headers": headers, "client": (peer, 1234)})


@pytest.mark.parametrize(
    ("hops", "xff", "expected"),
    [
        (0, "1.1.1.1", "10.0.0.9"),
        (2, None, "10.0.0.9"),
        (2, "6.6.6.6, 1.1.1.1, 100.64.0.2", "1.1.1.1"),  # spoofed left entry ignored
        (2, "1.1.1.1, 100.64.0.2", "1.1.1.1"),
        (3, "1.1.1.1, 2.2.2.2", "1.1.1.1"),
        (1, "1.1.1.1, 2.2.2.2", "2.2.2.2"),
    ],
)
def test_client_ip_trusted_hops(
    settings: Any, monkeypatch: Any, hops: int, xff: str | None, expected: str
) -> None:
    monkeypatch.setattr(settings, "forwarded_trusted_hops", hops)
    assert client_ip(_request(xff)) == expected


def test_client_ip_without_peer() -> None:
    assert client_ip(Request({"type": "http", "headers": [], "client": None})) == "unknown"


async def test_rate_limit_disabled(anon: Any, settings: Any, monkeypatch: Any) -> None:
    monkeypatch.setattr(settings, "rate_limit_enabled", False)
    for _ in range(12):
        r = await anon.client.post(
            "/api/v1/auth/login", json={"email": "x@example.com", "password": "x" * 12}
        )
        assert r.status_code == 401


def test_json_log_formatter() -> None:
    record = logging.LogRecord("ajar", logging.ERROR, __file__, 1, "boom %s", ("x",), None)
    record.extra_fields = {"k": 1}
    try:
        raise ValueError("bad")
    except ValueError:
        import sys

        record.exc_info = sys.exc_info()
    data = json.loads(JsonFormatter().format(record))
    assert data["msg"] == "boom x" and data["k"] == 1 and "ValueError" in data["exc"]
    configure_logging("WARNING")
    assert logging.getLogger().level == logging.WARNING


async def test_seed_demo_and_purge(settings: Any, monkeypatch: Any, capsys: Any) -> None:
    from app import seed

    assert await seed.main(demo=True) == 0
    async with get_sessionmaker()() as s:
        assert await s.scalar(select(func.count()).select_from(Listing).where(Listing.is_demo)) == 30
        assert await s.scalar(select(func.count()).select_from(ListingMedia)) == 30
        assert await s.scalar(select(func.count()).select_from(Organization).where(Organization.is_demo)) == 2
        demo_users = (await s.scalars(select(User.email).where(User.is_demo))).all()
        assert all(e.endswith("@demo.2ajar.invalid") for e in demo_users)
    assert await seed.main(demo=True) == 0  # idempotent
    assert "demo listings created: 0" in capsys.readouterr().out

    assert await seed.main(purge=True) == 0
    async with get_sessionmaker()() as s:
        assert await s.scalar(select(func.count()).select_from(Listing)) == 0
        assert await s.scalar(select(func.count()).select_from(User)) == 0
        assert await s.scalar(select(func.count()).select_from(Organization)) == 0

    monkeypatch.setattr(settings, "env", "production")
    assert await seed.main(demo=True) == 2
    assert await seed.main() == 0  # locations allowed in production


async def test_seed_demo_password(monkeypatch: Any) -> None:
    from app import seed

    monkeypatch.setenv("SEED_DEMO_PASSWORD", "demo-password-123")
    assert await seed.main(demo=True) == 0


def test_seed_cli_parsing(monkeypatch: Any) -> None:
    from app import seed

    calls: list[dict[str, bool]] = []

    async def fake_main(demo: bool = False, purge: bool = False) -> int:
        calls.append({"demo": demo, "purge": purge})
        return 0

    monkeypatch.setattr(seed, "main", fake_main)
    assert seed.cli(["--demo"]) == 0 and seed.cli(["--purge-demo"]) == 0 and seed.cli([]) == 0
    assert calls == [
        {"demo": True, "purge": False},
        {"demo": False, "purge": True},
        {"demo": False, "purge": False},
    ]
    with pytest.raises(SystemExit):
        seed.cli(["--demo", "--purge-demo"])

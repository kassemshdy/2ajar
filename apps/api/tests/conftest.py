import io
import os
import subprocess
import sys
import tempfile
from collections.abc import AsyncIterator, Iterator
from pathlib import Path
from typing import Any

# Configure the app for tests BEFORE importing it.
os.environ["ENV"] = "test"
os.environ.setdefault(
    "DATABASE_URL",
    os.environ.get("TEST_DATABASE_URL", "postgresql+psycopg://ajar:ajar@localhost:5432/ajar_test"),
)
os.environ["DEMO_MODE"] = "false"
os.environ["LOG_LEVEL"] = "WARNING"
os.environ["MEDIA_ROOT"] = tempfile.mkdtemp(prefix="ajar-media-")
os.environ["PUBLIC_WEB_BASE_URL"] = "https://2ajar.test"

import httpx
import pytest
from PIL import Image
from sqlalchemy import text

from app.core.config import get_settings
from app.core.ratelimit import limiter
from app.db.session import get_sessionmaker
from app.main import app
from app.models import Location
from app.seed import seed_locations

API_DIR = Path(__file__).resolve().parents[1]
BASE_URL = "http://testserver.local"
PASSWORD = "correct-horse-battery"
MUTABLE_TABLES = [
    "audit_logs",
    "listing_events",
    "leads",
    "listing_media",
    "listings",
    "properties",
    "refresh_tokens",
    "organization_members",
    "organizations",
    "users",
]


@pytest.fixture(scope="session", autouse=True)
def migrated_db() -> Iterator[None]:
    """Run real Alembic migrations against the test database once per session."""
    env = {**os.environ}
    for cmd in (["downgrade", "base"], ["upgrade", "head"]):
        subprocess.run([sys.executable, "-m", "alembic", *cmd], cwd=API_DIR, env=env, check=True)
    yield


@pytest.fixture(scope="session", autouse=True)
async def seeded_locations(migrated_db: None) -> None:
    async with get_sessionmaker()() as session:
        await seed_locations(session)


@pytest.fixture(autouse=True)
async def clean_db(seeded_locations: None) -> AsyncIterator[None]:
    limiter.reset()
    async with get_sessionmaker()() as session:
        await session.execute(text(f"TRUNCATE {', '.join(MUTABLE_TABLES)} CASCADE"))
        await session.commit()
    yield


@pytest.fixture
def settings() -> Any:
    return get_settings()


class Actor:
    """An HTTP client with its own cookie jar that behaves like a browser (sends CSRF header)."""

    def __init__(self) -> None:
        async def add_csrf(request: httpx.Request) -> None:
            token = self.client.cookies.get("csrf_token")
            if token and request.method not in ("GET", "HEAD", "OPTIONS"):
                request.headers["X-CSRF-Token"] = token

        self.client = httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url=BASE_URL, event_hooks={"request": [add_csrf]}
        )
        self.user: dict[str, Any] = {}

    async def register(self, role: str, email: str, organization_name: str | None = None) -> "Actor":
        body: dict[str, Any] = {
            "email": email,
            "password": PASSWORD,
            "full_name": f"Test {role.title()}",
            "role": role,
            "phone": "+96171111111",
        }
        if organization_name:
            body["organization_name"] = organization_name
        r = await self.client.post("/api/v1/auth/register", json=body)
        assert r.status_code == 201, r.text
        self.user = r.json()
        return self

    async def aclose(self) -> None:
        await self.client.aclose()


@pytest.fixture
async def make_actor() -> AsyncIterator[Any]:
    actors: list[Actor] = []

    async def factory(role: str | None = None, email: str | None = None, org: str | None = None) -> Actor:
        actor = Actor()
        actors.append(actor)
        if role:
            await actor.register(role, email or f"{role}{len(actors)}@example.com", org)
        return actor

    yield factory
    for a in actors:
        await a.aclose()


@pytest.fixture
async def anon(make_actor: Any) -> Actor:
    actor: Actor = await make_actor()
    return actor


async def location_id(slug: str) -> str:
    from sqlalchemy import select

    async with get_sessionmaker()() as session:
        loc = await session.scalar(select(Location).where(Location.slug == slug))
        assert loc is not None
        return str(loc.id)


def jpeg_bytes(size: tuple[int, int] = (800, 600), color: tuple[int, int, int] = (200, 30, 30)) -> bytes:
    img = Image.new("RGB", size, color)
    exif = Image.Exif()
    exif[0x010F] = "SecretCameraMaker"  # Make
    exif[0x8825] = {2: (33.0, 53.0, 0.0)}  # GPSInfo latitude
    out = io.BytesIO()
    img.save(out, format="JPEG", exif=exif)
    return out.getvalue()


async def create_listing(actor: Actor, **overrides: Any) -> dict[str, Any]:
    body: dict[str, Any] = {
        "transaction_type": "rent",
        "property_type": "apartment",
        "location_id": await location_id("achrafieh"),
        "price_usd": 1200,
        "price_period": "monthly",
        "bedrooms": 2,
        "bathrooms": 2,
        "area_sqm": 140,
        "furnished": "furnished",
        "amenities": ["generator_24_7", "parking"],
        "title_en": "Bright 2BR in Achrafieh",
        "title_ar": "شقة مشرقة في الأشرفية",
        "description_en": "Close to Sassine square.",
        "contact_whatsapp": "+961 70 123 456",
    }
    body.update(overrides)
    r = await actor.client.post("/api/v1/listings", json=body)
    assert r.status_code == 201, r.text
    return dict(r.json())


async def upload_photo(actor: Actor, listing_id: str, data: bytes | None = None) -> httpx.Response:
    files = {"file": ("photo.jpg", data if data is not None else jpeg_bytes(), "image/jpeg")}
    return await actor.client.post(f"/api/v1/listings/{listing_id}/media", files=files)


async def published_listing(actor: Actor, **overrides: Any) -> dict[str, Any]:
    listing = await create_listing(actor, **overrides)
    r = await upload_photo(actor, listing["id"])
    assert r.status_code == 201, r.text
    r = await actor.client.post(f"/api/v1/listings/{listing['id']}/publish")
    assert r.status_code == 200, r.text
    return dict(r.json())

"""Integration checks for caching, query efficiency, indexes and the moderation strategy."""

from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any

from sqlalchemy import event, text

from app.db.session import get_engine, get_sessionmaker
from app.repositories.locations import LocationDirectory
from tests.conftest import create_listing, location_id, published_listing, upload_photo


@contextmanager
def count_queries() -> Iterator[list[str]]:
    statements: list[str] = []

    def before(conn: Any, cursor: Any, statement: str, *args: Any) -> None:
        statements.append(statement)

    engine = get_engine().sync_engine
    event.listen(engine, "before_cursor_execute", before)
    try:
        yield statements
    finally:
        event.remove(engine, "before_cursor_execute", before)


async def test_location_directory_serves_from_cache() -> None:
    LocationDirectory.invalidate()
    async with get_sessionmaker()() as session:
        directory = LocationDirectory(session)
        with count_queries() as queries:
            first = await directory.by_slug("achrafieh")
            await directory.all()
            await directory.resolve("الأشرفية")
            await directory.resolve("ACHRAFIEH")
            await directory.resolve("Achrafieh")
        assert len(queries) == 1, "the whole tree loads once, then lookups are in memory"
        assert first is not None and first.path == "beirut/achrafieh"
        assert (await directory.resolve("الأشرفية")) == first
        assert await directory.resolve("Atlantis") is None
        assert (await directory.get(first.id)) == first


async def test_search_query_count_is_constant(make_actor: Any, anon: Any, settings: Any) -> None:
    """Guards against N+1: query count must not grow with the number of results."""
    broker = await make_actor("broker", "b@example.com", org="Org")
    await published_listing(broker)
    await anon.client.get("/api/v1/listings", params={"location": "beirut"})  # warm the location cache
    with count_queries() as one:
        r = await anon.client.get("/api/v1/listings", params={"location": "beirut"})
    assert r.json()["total"] == 1
    for _ in range(4):
        await published_listing(broker)
    with count_queries() as five:
        r = await anon.client.get("/api/v1/listings", params={"location": "beirut"})
    assert r.json()["total"] == 5
    assert len(five) == len(one) <= 4, five
    assert "Cache-Control" in r.headers and "public" in r.headers["cache-control"]


async def test_reference_endpoints_are_cacheable(anon: Any) -> None:
    for path in ("/api/v1/locations", "/api/v1/config"):
        r = await anon.client.get(path)
        assert "max-age=300" in r.headers["cache-control"], path


async def test_dashboard_lead_counts(make_actor: Any, anon: Any) -> None:
    broker = await make_actor("broker", "b@example.com", org="Org")
    listing = await published_listing(broker)
    other = await create_listing(broker)
    body = {"name": "Lea", "consent": True, "consent_text_version": "2026-11-v1"}
    for phone in ("70111111", "70222222"):
        await anon.client.post(f"/api/v1/listings/{listing['id']}/leads", json={**body, "phone": phone})
    mine = {x["id"]: x["lead_count"] for x in (await broker.client.get("/api/v1/me/listings")).json()}
    assert mine == {listing["id"]: 2, other["id"]: 0}
    inbox = (await broker.client.get("/api/v1/me/leads", params={"listing_id": listing["id"]})).json()
    assert len(inbox) == 2 and inbox[0]["last_contact_at"] >= inbox[1]["last_contact_at"]


async def test_query_driven_indexes_exist() -> None:
    async with get_sessionmaker()() as session:
        rows = (
            await session.execute(
                text("SELECT indexname, indexdef FROM pg_indexes WHERE schemaname='public'")
            )
        ).all()
    defs = {name: d for name, d in rows}
    assert "WHERE ((status)::text = 'published'::text)" in defs["ix_listings_published_newest"]
    assert "published_at DESC" in defs["ix_listings_published_newest"]
    assert "WHERE" in defs["ix_listings_published_price"]
    assert "updated_at DESC" in defs["ix_listings_creator_updated"]
    assert "last_contact_at DESC" in defs["ix_leads_listing_last_contact"]
    for superseded in (
        "ix_listings_public_search",
        "ix_listings_price_usd_cents",
        "ix_leads_listing_created",
    ):
        assert superseded not in defs
    assert "text_pattern_ops" in defs["ix_locations_path_pattern"]


async def test_moderation_policy_routes_to_review(
    make_actor: Any, anon: Any, settings: Any, monkeypatch: Any, notifications: Any
) -> None:
    monkeypatch.setattr(settings, "moderation_required", True)
    broker = await make_actor("broker", "b@example.com", org="Org")
    listing = await create_listing(broker, location_id=await location_id("hamra"))
    assert (await upload_photo(broker, listing["id"])).status_code == 201
    r = await broker.client.post(f"/api/v1/listings/{listing['id']}/publish")
    assert r.status_code == 200 and r.json()["status"] == "pending_review"
    assert r.json()["published_at"] is None
    assert (await anon.client.get(f"/api/v1/listings/{listing['id']}")).status_code == 404
    assert "submitted for review" in notifications.messages[-1]

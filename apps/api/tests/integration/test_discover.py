"""Home-page rows, near me, similar homes and favorites."""

from typing import Any

from sqlalchemy import func, select, update

from app.db.session import get_sessionmaker
from app.models import Listing, ListingEvent
from app.models.enums import ListingEventType
from tests.conftest import create_listing, location_id, promote, published_listing

HAMRA = (33.8960, 35.4820)


async def _view(actor: Any, listing_id: str, ua: str) -> None:
    r = await actor.client.post(f"/api/v1/listings/{listing_id}/view", headers={"user-agent": ua})
    assert r.status_code == 204


async def test_discover_rows(make_actor: Any, anon: Any) -> None:
    broker = await make_actor("broker", "b@example.com", org="Org")
    hamra = await location_id("hamra")
    # Three comparable monthly homes in Hamra (price per m²: 10, 10, 6) -> the cheap one is "great value".
    a = await published_listing(broker, price_usd=1000, area_sqm=100, location_id=hamra)
    await published_listing(broker, price_usd=1200, area_sqm=120, location_id=hamra)
    cheap = await published_listing(broker, price_usd=600, area_sqm=100, location_id=hamra)
    chalet = await published_listing(
        broker, property_type="chalet", price_period="nightly", price_usd=180, max_guests=6,
        location_id=await location_id("faraya"),
    )  # fmt: skip
    pool = await published_listing(
        broker,
        property_type="chalet",
        price_period="hourly",
        price_usd=30,
        location_id=await location_id("jiyeh"),
    )

    r = await anon.client.get("/api/v1/discover")
    assert r.status_code == 200 and "max-age" in r.headers["cache-control"]
    body = r.json()
    assert len(body["recent"]) == 5
    assert [x["id"] for x in body["nights"]] == [chalet["id"]]
    assert [x["id"] for x in body["hours"]] == [pool["id"]]
    assert body["most_viewed"] == []  # nothing honest to show yet
    assert [x["listing"]["id"] for x in body["great_value"]] == [cheap["id"]]
    assert body["great_value"][0]["below_area_median_pct"] == 40
    assert body["top_areas"] == []

    # Visitors: distinct daily visitor hashes, so reloading doesn't inflate the count.
    for ua in ("v1", "v2", "v1"):
        await _view(anon, a["id"], ua)
    await _view(anon, chalet["id"], "v3")
    viewed = (await anon.client.get("/api/v1/discover")).json()["most_viewed"]
    assert [(x["listing"]["id"], x["visitors_30d"]) for x in viewed] == [(a["id"], 2), (chalet["id"], 1)]


async def test_top_areas_use_curated_scores(
    make_actor: Any, anon: Any, settings: Any, monkeypatch: Any
) -> None:
    broker = await make_actor("broker", "b@example.com", org="Org")
    staff = await make_actor("seeker", "staff@example.com")
    await promote(staff, "staff")
    await published_listing(broker, location_id=await location_id("hamra"))
    await published_listing(broker, location_id=await location_id("achrafieh"))
    await published_listing(broker, location_id=await location_id("jounieh"))
    for slug, body in (
        ("beirut", {"safety_score": 3, "quiet_score": 3}),  # covers Hamra + Achrafieh
        ("jounieh", {"safety_score": 5, "quiet_score": 4}),
        ("baabda", {"safety_score": 5, "quiet_score": 5}),  # no listings: not shown
        ("kaslik", {"summary_en": "No scores yet"}),  # no scores: not ranked
    ):
        r = await staff.client.put(f"/api/v1/admin/areas/{await location_id(slug)}", json=body)
        assert r.status_code == 200, r.text
    top = (await anon.client.get("/api/v1/discover")).json()["top_areas"]
    assert [(x["area"]["location_slug"], x["listing_count"]) for x in top] == [("jounieh", 1), ("beirut", 2)]

    async with get_sessionmaker()() as s:  # demo profiles only count in demo mode
        from app.models import AreaProfile

        await s.execute(update(AreaProfile).values(is_demo=True))
        await s.commit()
    assert (await anon.client.get("/api/v1/discover")).json()["top_areas"] == []
    monkeypatch.setattr(settings, "demo_mode", True)
    assert len((await anon.client.get("/api/v1/discover")).json()["top_areas"]) == 2


async def test_nearby_and_similar(make_actor: Any, anon: Any) -> None:
    broker = await make_actor("broker", "b@example.com", org="Org")
    hamra = await published_listing(broker, location_id=await location_id("hamra"))
    verdun = await published_listing(broker, location_id=await location_id("verdun"))
    await published_listing(broker, location_id=await location_id("batroun"))  # ~45 km away
    chalet = await published_listing(
        broker, property_type="chalet", price_period="nightly", price_usd=120,
        location_id=await location_id("verdun"),
    )  # fmt: skip
    draft = await create_listing(broker)

    r = await anon.client.get("/api/v1/listings/nearby", params={"lat": HAMRA[0], "lng": HAMRA[1]})
    assert r.status_code == 200, r.text
    hits = r.json()
    assert hits[0]["listing"]["id"] == hamra["id"] and hits[0]["distance_km"] == 0.0
    assert {h["listing"]["id"] for h in hits} == {hamra["id"], verdun["id"], chalet["id"]}
    assert all(h["distance_km"] < 3 for h in hits)
    nights = await anon.client.get(
        "/api/v1/listings/nearby", params={"lat": HAMRA[0], "lng": HAMRA[1], "stay": "nights"}
    )
    assert [h["listing"]["id"] for h in nights.json()] == [chalet["id"]]
    assert (await anon.client.get("/api/v1/listings/nearby", params={"lat": 95, "lng": 0})).status_code == 422

    similar = (await anon.client.get(f"/api/v1/listings/{hamra['id']}/similar")).json()
    assert [h["listing"]["id"] for h in similar] == [
        verdun["id"]
    ]  # same kind of stay, nearest first, not itself
    assert (await anon.client.get(f"/api/v1/listings/{draft['id']}/similar")).status_code == 404


async def test_favorites(make_actor: Any, anon: Any) -> None:
    broker = await make_actor("broker", "b@example.com", org="Org")
    seeker = await make_actor("seeker", "s@example.com")
    first = await published_listing(broker, price_usd=900)
    second = await published_listing(broker, price_usd=1100)
    draft = await create_listing(broker)

    assert (await anon.client.put(f"/api/v1/me/favorites/{first['id']}")).status_code == 401
    assert (await anon.client.get("/api/v1/me/favorites")).status_code == 401
    for listing_id in (first["id"], second["id"], first["id"]):  # saving twice is fine
        assert (await seeker.client.put(f"/api/v1/me/favorites/{listing_id}")).status_code == 204
    assert (await seeker.client.put(f"/api/v1/me/favorites/{draft['id']}")).status_code == 404

    ids = (await seeker.client.get("/api/v1/me/favorites/ids")).json()["listing_ids"]
    assert ids == [second["id"], first["id"]]
    saved = (await seeker.client.get("/api/v1/me/favorites")).json()
    assert [x["id"] for x in saved] == [second["id"], first["id"]] and "contact_whatsapp" not in saved[0]
    async with get_sessionmaker()() as s:
        n = (
            select(func.count())
            .select_from(ListingEvent)
            .where(ListingEvent.event_type == ListingEventType.favorite)
        )
        assert await s.scalar(n) == 2  # one event per real save

    # A paused listing quietly drops out of the saved list; removing is idempotent.
    assert (await broker.client.post(f"/api/v1/listings/{second['id']}/pause")).status_code == 200
    assert [x["id"] for x in (await seeker.client.get("/api/v1/me/favorites")).json()] == [first["id"]]
    for _ in range(2):
        assert (await seeker.client.delete(f"/api/v1/me/favorites/{first['id']}")).status_code == 204
    assert (await seeker.client.get("/api/v1/me/favorites")).json() == []
    async with get_sessionmaker()() as s:
        assert await s.scalar(select(func.count()).select_from(Listing)) == 3

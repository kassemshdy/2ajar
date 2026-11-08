"""Smart search end to end: living factors, curated area info, ranking, relaxation, logging, area admin."""

from typing import Any

from sqlalchemy import func, select

from app.db.session import get_sessionmaker
from app.models import SearchQuery
from tests.conftest import location_id, promote, published_listing

ASK = "/api/v1/search/ask"


async def _ask(actor: Any, query: str, locale: str = "en") -> dict[str, Any]:
    r = await actor.client.post(ASK, json={"query": query, "locale": locale})
    assert r.status_code == 200, r.text
    return dict(r.json())


async def _set_area(admin: Any, slug: str, **body: Any) -> dict[str, Any]:
    r = await admin.client.put(f"/api/v1/admin/areas/{await location_id(slug)}", json=body)
    assert r.status_code == 200, r.text
    return dict(r.json())


async def test_living_factors_round_trip(make_actor: Any) -> None:
    broker = await make_actor("broker", "b@example.com", org="Org")
    listing = await published_listing(
        broker,
        electricity_supply="solar_battery",
        electricity_usd_month=40,
        generator_amps=10,
        water_source="municipal",
        water_usd_month=15,
        sewage="public_network",
        parking_spots=2,
        solar_ready=True,
        elevator_backup=True,
        winter_comfort="warm",
        summer_comfort="cool",
        highlights=["  Sunny all day ", "", "Near Sassine"],
        things_to_know=["Concierge closes at 10pm"],
    )
    living = listing["property"]["living"]
    assert living["electricity_supply"] == "solar_battery" and living["parking_spots"] == 2
    assert living["highlights"] == ["Sunny all day", "Near Sassine"]

    r = await broker.client.patch(
        f"/api/v1/listings/{listing['id']}", json={"highlights": None, "winter_comfort": "cold"}
    )
    assert r.status_code == 200, r.text
    living = r.json()["property"]["living"]
    assert living["highlights"] == [] and living["winter_comfort"] == "cold"

    too_many = await broker.client.patch(f"/api/v1/listings/{listing['id']}", json={"highlights": ["x"] * 7})
    assert too_many.status_code == 422


async def test_ask_ranks_by_preferences_and_explains(make_actor: Any, anon: Any) -> None:
    broker = await make_actor("broker", "b@example.com", org="Org")
    admin = await make_actor("seeker", "admin@example.com")
    await promote(admin, "platform_admin")
    good = await published_listing(
        broker,
        title_en="Quiet solar flat",
        electricity_supply="solar_battery",
        parking_spots=2,
        amenities=["elevator"],
        elevator_backup=True,
        winter_comfort="warm",
    )
    plain = await published_listing(
        broker,
        title_en="Plain flat",
        electricity_supply="edl_only",
        parking_spots=0,
        amenities=[],
    )
    await _set_area(admin, "achrafieh", safety_score=5, quiet_score=4, theft_reports_12m=3, flood_risk="low")

    res = await _ask(
        anon, "2 bedroom in Achrafieh under $1,500 with 24/7 electricity, parking for 2 cars, safe"
    )
    assert res["understood"]["location_slug"] == "achrafieh"
    assert res["understood"]["price_max"] == 1500 and res["understood"]["stay"] is None
    assert res["understood"]["parking_spots"] == 2
    assert res["total"] == 2 and res["relaxed"] == [] and res["clarification_en"] is None
    assert [h["listing"]["id"] for h in res["results"]] == [good["id"], plain["id"]]
    top = {r["key"]: r for r in res["results"][0]["reasons"]}
    assert top["location"]["source"] == "filter" and top["budget"]["status"] == "match"
    assert top["electricity_24_7"]["status"] == "match" and top["parking"]["label_en"] == "Parking for 2 cars"
    assert top["safe"] == {**top["safe"], "status": "match", "source": "area"}
    low = {r["key"]: r["status"] for r in res["results"][1]["reasons"]}
    assert low["electricity_24_7"] == "miss" and low["parking"] == "miss"
    area = res["results"][0]["listing"]["area"]
    assert area["safety_score"] == 5 and area["is_demo"] is False
    assert "contact_whatsapp" not in str(res)
    assert res["summary_en"].startswith("2+ bedroom") and "Achrafieh" in res["summary_en"]
    assert "الأشرفية" in res["summary_ar"]

    # The query is logged without personal data, with what was understood.
    async with get_sessionmaker()() as session:
        logged = await session.scalar(select(SearchQuery).where(SearchQuery.id == res["query_id"]))
        assert logged is not None and logged.result_count == 2 and logged.user_id is None
        assert logged.parsed["location"] == "achrafieh"


async def test_unknown_when_not_reported(make_actor: Any, anon: Any) -> None:
    broker = await make_actor("broker", "b@example.com", org="Org")
    await published_listing(broker, amenities=[])
    res = await _ask(anon, "warm in winter, quiet, public sewage in Achrafieh")
    statuses = {r["key"]: r["status"] for r in res["results"][0]["reasons"]}
    # Nobody reported these: the engine says "unknown" rather than guessing.
    assert statuses["warm_winter"] == statuses["quiet"] == statuses["sewage"] == "unknown"
    assert res["results"][0]["listing"]["area"] is None


async def test_relaxation_is_reported(make_actor: Any, anon: Any) -> None:
    broker = await make_actor("broker", "b@example.com", org="Org")
    await published_listing(broker, price_usd=1100)
    res = await _ask(anon, "2 bedroom in Achrafieh under 1000")
    assert res["total"] == 1 and [r["key"] for r in res["relaxed"]] == ["budget"]
    budget = next(r for r in res["results"][0]["reasons"] if r["key"] == "budget")
    assert budget["label_en"] == "Within $1,200"  # the filter actually applied, not the original wish

    res = await _ask(anon, "3 bedroom in Gemmayzeh under 950")
    assert [r["key"] for r in res["relaxed"]] == ["budget", "location", "bedrooms"]
    assert res["total"] == 1

    res = await _ask(anon, "villa in Hamra")
    assert res["total"] == 0 and res["results"] == []


async def test_clarification_and_validation(make_actor: Any, anon: Any) -> None:
    res = await _ask(anon, "hello there", locale="ar")
    assert res["clarification_en"] and res["clarification_ar"] and res["total"] == 0
    assert (await anon.client.post(ASK, json={"query": ""})).status_code == 422
    assert (await anon.client.post(ASK, json={"query": "x" * 301})).status_code == 422
    assert (await anon.client.post(ASK, json={"query": "hamra", "locale": "fr"})).status_code == 422


async def test_logged_in_user_is_recorded(make_actor: Any) -> None:
    seeker = await make_actor("seeker", "s@example.com")
    res = await _ask(seeker, "شقة في الحمرا", locale="ar")
    async with get_sessionmaker()() as session:
        row = await session.scalar(select(SearchQuery).where(SearchQuery.id == res["query_id"]))
        assert row is not None and str(row.user_id) == seeker.user["id"] and row.locale == "ar"


async def test_ask_is_rate_limited(anon: Any) -> None:
    for _ in range(60):
        assert (await anon.client.post(ASK, json={"query": "hamra"})).status_code == 200
    r = await anon.client.post(ASK, json={"query": "hamra"})
    assert r.status_code == 429
    async with get_sessionmaker()() as session:
        assert await session.scalar(select(func.count()).select_from(SearchQuery)) == 60


async def test_suggestions(anon: Any) -> None:
    r = await anon.client.get("/api/v1/search/suggestions")
    assert r.status_code == 200 and "max-age" in r.headers["cache-control"]
    items = r.json()
    assert len(items) >= 4 and all(i["text_en"] and i["text_ar"] for i in items)


async def test_area_admin_authz_and_detail(make_actor: Any, anon: Any) -> None:
    broker = await make_actor("broker", "b@example.com", org="Org")
    staff = await make_actor("seeker", "staff@example.com")
    await promote(staff, "staff")
    listing = await published_listing(broker)
    loc = await location_id("achrafieh")

    assert (await broker.client.get("/api/v1/admin/areas")).status_code == 403
    denied = await broker.client.put(f"/api/v1/admin/areas/{loc}", json={"safety_score": 5})
    assert denied.status_code == 403
    assert (await anon.client.get("/api/v1/admin/areas")).status_code == 401
    bad = await staff.client.put(f"/api/v1/admin/areas/{loc}", json={"safety_score": 6})
    assert bad.status_code == 422
    missing = await staff.client.put(
        "/api/v1/admin/areas/00000000-0000-0000-0000-000000000000", json={"safety_score": 3}
    )
    assert missing.status_code == 404

    # Profiles set on a parent area apply to its children unless a child has its own.
    beirut = await _set_area(staff, "beirut", safety_score=3, summary_en="Capital")
    assert beirut["location_slug"] == "beirut"
    detail = (await anon.client.get(f"/api/v1/listings/{listing['id']}")).json()
    assert detail["area"]["location_slug"] == "beirut"
    await _set_area(staff, "achrafieh", safety_score=4, garbage_collection="daily", noise_notes_ar="هادئ")
    detail = (await anon.client.get(f"/api/v1/listings/{listing['id']}")).json()
    assert detail["area"]["location_slug"] == "achrafieh" and detail["area"]["safety_score"] == 4
    owner_view = (await broker.client.get(f"/api/v1/listings/{listing['id']}")).json()
    assert owner_view["area"]["safety_score"] == 4

    listed = (await staff.client.get("/api/v1/admin/areas")).json()
    assert {a["location_slug"] for a in listed} == {"beirut", "achrafieh"}
    updated = await _set_area(staff, "achrafieh", safety_score=2)
    assert updated["safety_score"] == 2 and updated["garbage_collection"] is None  # PUT replaces


async def test_demo_area_profiles_only_in_demo_mode(
    make_actor: Any, anon: Any, settings: Any, monkeypatch: Any
) -> None:
    import uuid

    from app.models import AreaProfile

    broker = await make_actor("broker", "b@example.com", org="Org")
    listing = await published_listing(broker)
    async with get_sessionmaker()() as session:
        session.add(
            AreaProfile(location_id=uuid.UUID(await location_id("achrafieh")), safety_score=5, is_demo=True)
        )
        await session.commit()
    detail = (await anon.client.get(f"/api/v1/listings/{listing['id']}")).json()
    assert detail["area"] is None  # synthetic numbers never reach a real-inventory site
    monkeypatch.setattr(settings, "demo_mode", True)
    detail = (await anon.client.get(f"/api/v1/listings/{listing['id']}")).json()
    assert detail["area"]["is_demo"] is True and detail["area"]["safety_score"] == 5

"""Admin → Growth: value equation, funnel, supply gaps, recommendations and playbook, from real data."""

from datetime import timedelta
from typing import Any

from sqlalchemy import update

from app.core.security import utcnow
from app.db.session import get_sessionmaker
from app.models import Listing
from tests.conftest import create_listing, location_id, promote, published_listing, upload_photo
from tests.integration.test_leads import lead_body

GROWTH = "/api/v1/admin/growth"


async def test_growth_requires_analytics_permission(make_actor: Any, anon: Any) -> None:
    seeker = await make_actor("seeker", "s@example.com")
    assert (await anon.client.get(GROWTH)).status_code == 401
    assert (await seeker.client.get(GROWTH)).status_code == 403
    assert (await seeker.client.put(f"{GROWTH}/tasks/offer_defined", json={"done": True})).status_code == 403


async def test_empty_platform_says_not_enough_data(make_actor: Any) -> None:
    staff = await make_actor("seeker", "staff@example.com")
    await promote(staff, "staff")
    body = (await staff.client.get(GROWTH)).json()
    assert body["metrics"]["live_listings"] == 0 and body["metrics"]["conversion"] is None
    assert body["renters"]["index"] is None and body["owners"]["index"] is None
    assert body["area_gaps"] == [] and body["quiet_listings"] == []
    keys = [r["key"] for r in body["recommendations"]]
    assert keys[0] == "supply_sprint" and "start_content" in keys  # nothing else can be claimed yet
    assert all(r["priority"] in (1, 2, 3) for r in body["recommendations"])


async def test_dashboard_measures_real_activity(make_actor: Any, anon: Any) -> None:
    broker = await make_actor("broker", "b@example.com", org="Org")
    staff = await make_actor("seeker", "staff@example.com")
    await promote(staff, "staff")
    hamra = await location_id("hamra")
    full = await published_listing(
        broker,
        location_id=hamra,
        electricity_supply="generator_24_7",
        water_source="municipal",
        parking_spots=1,
    )
    for _ in range(2):
        assert (await upload_photo(broker, full["id"])).status_code == 201  # 3 photos in total
    bare = await published_listing(broker, location_id=hamra, amenities=[])
    await create_listing(broker)  # a draft: publishing friction
    r = await staff.client.put(f"/api/v1/admin/areas/{hamra}", json={"safety_score": 4, "quiet_score": 3})
    assert r.status_code == 200

    # Demand: 5 visitors on one listing, 1 WhatsApp tap + 1 lead on the other; searches incl. an empty one.
    for ua in ("a", "b", "c", "d", "e"):
        await anon.client.post(f"/api/v1/listings/{bare['id']}/view", headers={"user-agent": ua})
    await anon.client.post(f"/api/v1/listings/{full['id']}/view", headers={"user-agent": "f"})
    await anon.client.post(f"/api/v1/listings/{full['id']}/contact/whatsapp")
    assert (
        await anon.client.post(f"/api/v1/listings/{full['id']}/leads", json=lead_body())
    ).status_code == 201
    for q in ("2 bedroom in Hamra with 24/7 electricity, quiet", "villa in Verdun with pool", "hello"):
        assert (await anon.client.post("/api/v1/search/ask", json={"query": q})).status_code == 200

    body = (await staff.client.get(GROWTH)).json()
    m = body["metrics"]
    assert m["live_listings"] == 2 and m["active_publishers"] == 1
    assert m["bills_share"] == 0.5 and m["photos3_share"] == 0.5 and m["area_facts_share"] == 1.0
    assert m["weekly_searches"] == 3 and m["weekly_whatsapp"] == 1 and m["weekly_leads"] == 1
    assert m["weekly_inquiries"] == 2 and m["weekly_views"] == 6 and abs(m["conversion"] - 2 / 6) < 1e-9
    assert m["hours_to_first_inquiry"] is not None and m["listings_contacted_30d"] == 0.5
    assert body["funnel"] == {"searches": 3, "visitors": 6, "views": 6, "inquiries": 2}

    renters = {f["key"]: f for f in body["renters"]["factors"]}
    assert renters["dream"]["value"] == "50%" and renters["time"]["score"] is not None
    assert body["renters"]["index"] is not None and 0 < body["renters"]["index"] <= 100
    owners = {f["key"]: f for f in body["owners"]["factors"]}
    assert owners["dream"]["value"] == "1.00" and owners["effort"]["value"] == "33%"

    gaps = {g["slug"]: g for g in body["area_gaps"]}
    assert gaps["verdun"]["zero_results"] == 1 and gaps["verdun"]["live_listings"] == 0
    assert gaps["hamra"]["has_area_facts"] is True and gaps["hamra"]["live_listings"] == 2
    wishes = {w["key"]: w for w in body["wishes"]}
    assert wishes["electricity_24_7"]["data_coverage"] == 0.5 and wishes["quiet"]["data_coverage"] == 1.0
    assert wishes["pool"]["data_coverage"] is None
    assert body["quiet_listings"] == [{"id": bare["id"], "title": bare["title"]["en"], "visitors": 5}]

    recs = {r["key"]: r for r in body["recommendations"]}
    assert recs["fill_zero_results"]["params"]["areas_en"].startswith("Verdun")
    assert recs["ask_bills"]["params"]["share"] == "50%" and "call_quiet_listings" in recs
    assert recs["better_prompts"]["lever"] == "effort"


async def test_playbook_ticks_and_measured_steps(make_actor: Any) -> None:
    admin = await make_actor("seeker", "admin@example.com")
    await promote(admin, "platform_admin")
    broker = await make_actor("broker", "b@example.com", org="Org")
    await published_listing(broker)
    url = f"{GROWTH}/tasks"
    assert (await admin.client.put(f"{url}/offer_defined", json={"done": True})).status_code == 204
    assert (
        await admin.client.put(f"{url}/offer_defined", json={"done": True})
    ).status_code == 204  # idempotent
    assert (await admin.client.put(f"{url}/no_such_step", json={"done": True})).status_code == 404
    items = {x["key"]: x for x in (await admin.client.get(GROWTH)).json()["playbook"]}
    assert items["offer_defined"]["done"] is True and items["warm_list_100"]["done"] is False
    assert items["listings_100"]["auto"] is True and items["listings_100"]["progress"] == 0.01
    assert items["demo_off"]["done"] is True  # tests run with demo mode off
    assert (await admin.client.put(f"{url}/offer_defined", json={"done": False})).status_code == 204
    items = {x["key"]: x for x in (await admin.client.get(GROWTH)).json()["playbook"]}
    assert items["offer_defined"]["done"] is False


async def test_retention_and_stale_listings(make_actor: Any) -> None:
    staff = await make_actor("seeker", "staff@example.com")
    await promote(staff, "staff")
    broker = await make_actor("broker", "b@example.com", org="Org")
    old = await published_listing(broker)
    async with get_sessionmaker()() as s:  # published 90 days ago, confirmed 45 days ago, still live
        await s.execute(
            update(Listing)
            .where(Listing.id == old["id"])
            .values(
                published_at=utcnow() - timedelta(days=90),
                last_confirmed_at=utcnow() - timedelta(days=45),
                expires_at=utcnow() + timedelta(days=5),
            )
        )
        await s.commit()
    m = (await staff.client.get(GROWTH)).json()["metrics"]
    assert m["fresh_share"] == 0.0 and m["retention_60d"] == 0.0
    recs = [r["key"] for r in (await staff.client.get(GROWTH)).json()["recommendations"]]
    assert "confirm_reminders" in recs and "win_back_publishers" in recs

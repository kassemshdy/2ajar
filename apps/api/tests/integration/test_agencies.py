"""Broker/owner badges, staff verification, public agency pages and per-listing stats."""

from typing import Any

from sqlalchemy import update

from app.db.session import get_sessionmaker
from app.models import Organization
from tests.conftest import create_listing, promote, published_listing


async def test_verification_badges_and_agency_page(
    make_actor: Any, anon: Any, settings: Any, monkeypatch: Any
) -> None:
    broker = await make_actor("broker", "b@example.com", org="Cedar Homes")
    agent_listing = await published_listing(broker, price_usd=900)
    await create_listing(broker)  # drafts never appear on the agency page
    owner = await make_actor("owner", "o@example.com")
    owner_listing = await published_listing(owner, price_usd=700)
    staff = await make_actor("seeker", "staff@example.com")
    await promote(staff, "staff")
    admin = await make_actor("seeker", "admin@example.com")
    await promote(admin, "platform_admin")

    pub = (await anon.client.get(f"/api/v1/listings/{agent_listing['id']}")).json()["publisher"]
    assert pub["type"] == "broker" and pub["verified"] is False
    slug = pub["agency_slug"]
    page = (await anon.client.get(f"/api/v1/agencies/{slug}")).json()
    assert page["name"] == "Cedar Homes" and page["verified"] is False and page["members"] == 1
    assert [x["id"] for x in page["listings"]] == [agent_listing["id"]]
    assert (await anon.client.get("/api/v1/agencies/no-such-agency")).status_code == 404

    # Staff with listings.moderate verify agencies; brokers and anonymous visitors can't.
    assert (await broker.client.get("/api/v1/admin/agencies")).status_code == 403
    agencies = (await staff.client.get("/api/v1/admin/agencies")).json()
    cedar = next(a for a in agencies if a["slug"] == slug)
    assert cedar["live_listings"] == 1 and cedar["members"] == 1 and cedar["is_verified"] is False
    r = await staff.client.patch(f"/api/v1/admin/agencies/{cedar['id']}", json={"is_verified": True})
    assert r.status_code == 200 and r.json()["is_verified"] is True
    assert (
        await staff.client.patch(f"/api/v1/admin/agencies/{cedar['id']}", json={"is_verified": True})
    ).status_code == 200
    missing = await staff.client.patch(
        "/api/v1/admin/agencies/00000000-0000-0000-0000-000000000000", json={"is_verified": True}
    )
    assert missing.status_code == 404
    assert (await anon.client.get(f"/api/v1/agencies/{slug}")).json()["verified"] is True
    assert (await anon.client.get(f"/api/v1/listings/{agent_listing['id']}")).json()["publisher"][
        "verified"
    ] is True

    # Individual owners are verified on their user record (users.manage).
    owner_pub = (await anon.client.get(f"/api/v1/listings/{owner_listing['id']}")).json()["publisher"]
    assert (
        owner_pub["type"] == "owner" and owner_pub["verified"] is False and owner_pub["agency_slug"] is None
    )
    r = await admin.client.patch(f"/api/v1/admin/users/{owner.user['id']}", json={"is_verified": True})
    assert r.status_code == 200 and r.json()["is_verified"] is True
    assert (await anon.client.get(f"/api/v1/listings/{owner_listing['id']}")).json()["publisher"][
        "verified"
    ] is True

    # Demo agencies are hidden outside demo mode, like demo listings.
    async with get_sessionmaker()() as s:
        await s.execute(update(Organization).where(Organization.slug == slug).values(is_demo=True))
        await s.commit()
    assert (await anon.client.get(f"/api/v1/agencies/{slug}")).status_code == 404
    monkeypatch.setattr(settings, "demo_mode", True)
    assert (await anon.client.get(f"/api/v1/agencies/{slug}")).status_code == 200


async def test_dashboard_shows_listing_stats(make_actor: Any, anon: Any) -> None:
    broker = await make_actor("broker", "b@example.com", org="Org")
    seeker = await make_actor("seeker", "s@example.com")
    listing = await published_listing(broker)
    for ua in ("a", "b", "a"):
        await anon.client.post(f"/api/v1/listings/{listing['id']}/view", headers={"user-agent": ua})
    await anon.client.post(f"/api/v1/listings/{listing['id']}/contact/whatsapp")
    assert (await seeker.client.put(f"/api/v1/me/favorites/{listing['id']}")).status_code == 204
    from tests.integration.test_leads import lead_body

    assert (
        await anon.client.post(f"/api/v1/listings/{listing['id']}/leads", json=lead_body())
    ).status_code == 201
    mine = (await broker.client.get("/api/v1/me/listings")).json()
    assert mine[0]["stats"] == {"visitors_30d": 2, "whatsapp_30d": 1, "leads_30d": 1, "saves": 1}
    assert (await seeker.client.get("/api/v1/me/listings")).json() == []

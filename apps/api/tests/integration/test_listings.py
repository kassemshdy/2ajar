from datetime import timedelta
from pathlib import Path
from typing import Any

from sqlalchemy import select, update

from app.core.security import utcnow
from app.db.session import get_sessionmaker
from app.models import AuditLog, Listing, ListingEvent
from tests.conftest import create_listing, jpeg_bytes, location_id, published_listing, upload_photo


async def test_full_vertical_slice(make_actor: Any, anon: Any, settings: Any) -> None:
    broker = await make_actor("broker", "broker@example.com", org="Cedar Homes")
    draft = await create_listing(broker)
    assert draft["status"] == "draft"
    assert draft["publisher"] == {
        "type": "broker",
        "display_name": "Cedar Homes",
        "organization_name": "Cedar Homes",
    }

    # Drafts are invisible to the public
    assert (await anon.client.get(f"/api/v1/listings/{draft['id']}")).status_code == 404
    assert (await anon.client.get("/api/v1/listings")).json()["total"] == 0

    # Publishing requires a photo
    r = await broker.client.post(f"/api/v1/listings/{draft['id']}/publish")
    assert r.status_code == 422
    assert "photo" in r.json()["error"]["message"]

    r = await upload_photo(broker, draft["id"])
    assert r.status_code == 201
    media = r.json()
    stored = Path(settings.media_root) / media["url"].removeprefix("/media/")
    assert stored.exists() and b"SecretCameraMaker" not in stored.read_bytes()

    r = await broker.client.post(f"/api/v1/listings/{draft['id']}/publish")
    assert r.status_code == 200
    published = r.json()
    assert published["status"] == "published" and published["expires_at"]

    # Public search + detail
    page = (await anon.client.get("/api/v1/listings", params={"location": "beirut"})).json()
    assert page["total"] == 1
    public = (await anon.client.get(f"/api/v1/listings/{draft['id']}")).json()
    assert public["price_usd"] == 1200 and public["location"]["slug"] == "achrafieh"
    assert "contact_whatsapp" not in public, "publisher phone must not leak in public payload"
    assert "70123456" not in str(public)

    # The manager sees private fields
    private = (await broker.client.get(f"/api/v1/listings/{draft['id']}")).json()
    assert private["contact_whatsapp"] == "+96170123456"

    # WhatsApp handoff
    r = await anon.client.post(f"/api/v1/listings/{draft['id']}/contact/whatsapp", params={"locale": "ar"})
    assert r.status_code == 200
    url = r.json()["url"]
    assert url.startswith("https://wa.me/96170123456?text=")
    async with get_sessionmaker()() as s:
        events = (await s.scalars(select(ListingEvent.event_type))).all()
        assert "whatsapp_click" in events
        actions = set((await s.scalars(select(AuditLog.action))).all())
        assert {"listing.create", "listing.publish", "listing.media_add"} <= actions

    # Pause hides it again
    assert (await broker.client.post(f"/api/v1/listings/{draft['id']}/pause")).status_code == 200
    assert (await anon.client.get(f"/api/v1/listings/{draft['id']}")).status_code == 404
    assert (await anon.client.post(f"/api/v1/listings/{draft['id']}/contact/whatsapp")).status_code == 404


async def test_cross_tenant_access_denied(make_actor: Any) -> None:
    admin_a = await make_actor("broker", "admin-a@example.com", org="Agency A")
    other = await make_actor("broker", "admin-b@example.com", org="Agency B")
    owner = await make_actor("owner", "owner@example.com")
    seeker = await make_actor("seeker", "seeker@example.com")
    listing = await create_listing(admin_a)
    lid = listing["id"]

    for actor in (other, owner, seeker):
        assert (await actor.client.patch(f"/api/v1/listings/{lid}", json={"price_usd": 1})).status_code == 404
        assert (await actor.client.post(f"/api/v1/listings/{lid}/publish")).status_code == 404
        assert (await upload_photo(actor, lid)).status_code == 404
        assert (await actor.client.get(f"/api/v1/listings/{lid}")).status_code == 404
        mine = (await actor.client.get("/api/v1/me/listings")).json()
        assert all(x["id"] != lid for x in mine)

    # Seekers cannot create listings
    r = await seeker.client.post(
        "/api/v1/listings",
        json={
            "transaction_type": "rent",
            "property_type": "apartment",
            "location_id": await location_id("hamra"),
            "price_usd": 500,
            "price_period": "monthly",
        },
    )
    assert r.status_code == 403

    # Anonymous cannot create
    anon = await make_actor()
    assert (await anon.client.post("/api/v1/listings", json={})).status_code == 401


async def test_agency_admin_manages_agent_listing_but_not_vice_versa(make_actor: Any) -> None:
    from app.models import OrganizationMember, User
    from app.models.enums import OrgRole

    admin = await make_actor("broker", "admin@example.com", org="Agency")
    agent = await make_actor("broker", "agent@example.com")
    org_id = admin.user["memberships"][0]["organization_id"]
    async with get_sessionmaker()() as s:
        agent_user = await s.scalar(select(User).where(User.email == "agent@example.com"))
        assert agent_user is not None
        s.add(OrganizationMember(organization_id=org_id, user_id=agent_user.id, role=OrgRole.agent))
        await s.commit()

    agent_listing = await create_listing(agent)
    admin_listing = await create_listing(admin)
    assert agent_listing["publisher"]["organization_name"] == "Agency"

    r = await admin.client.patch(f"/api/v1/listings/{agent_listing['id']}", json={"price_usd": 999})
    assert r.status_code == 200 and r.json()["price_usd"] == 999
    r = await agent.client.patch(f"/api/v1/listings/{admin_listing['id']}", json={"price_usd": 1})
    assert r.status_code == 404
    admin_ids = {x["id"] for x in (await admin.client.get("/api/v1/me/listings")).json()}
    agent_ids = {x["id"] for x in (await agent.client.get("/api/v1/me/listings")).json()}
    assert admin_ids == {agent_listing["id"], admin_listing["id"]}
    assert agent_ids == {agent_listing["id"]}


async def test_update_validation(make_actor: Any) -> None:
    owner = await make_actor("owner", "o@example.com")
    listing = await create_listing(owner)
    lid = listing["id"]
    assert listing["publisher"]["type"] == "owner"
    r = await owner.client.patch(f"/api/v1/listings/{lid}", json={"transaction_type": "sale"})
    assert r.status_code == 422, "sale requires total price period"
    r = await owner.client.patch(
        f"/api/v1/listings/{lid}",
        json={"transaction_type": "sale", "price_period": "total", "price_usd": 250000},
    )
    assert r.status_code == 200 and r.json()["transaction_type"] == "sale"
    r = await owner.client.patch(f"/api/v1/listings/{lid}", json={"contact_whatsapp": "abc"})
    assert r.status_code == 422
    r = await owner.client.patch(
        f"/api/v1/listings/{lid}", json={"location_id": "00000000-0000-0000-0000-000000000000"}
    )
    assert r.status_code == 422
    r = await owner.client.patch(f"/api/v1/listings/{lid}", json={"bedrooms": 3, "amenities": ["sea_view"]})
    body = r.json()
    assert body["property"]["bedrooms"] == 3 and body["property"]["amenities"] == ["sea_view"]


async def test_search_filters(make_actor: Any, anon: Any) -> None:
    broker = await make_actor("broker", "b@example.com", org="Org")
    await published_listing(
        broker, price_usd=800, bedrooms=1, location_id=await location_id("hamra"), furnished="unfurnished"
    )
    await published_listing(broker, price_usd=1500, bedrooms=3, location_id=await location_id("achrafieh"))
    await published_listing(broker, price_usd=700, bedrooms=2, location_id=await location_id("jounieh"))
    await published_listing(
        broker,
        transaction_type="sale",
        price_period="total",
        price_usd=300000,
        bedrooms=3,
        location_id=await location_id("dbayeh"),
    )

    async def search(**params: Any) -> list[int]:
        r = await anon.client.get("/api/v1/listings", params=params)
        assert r.status_code == 200, r.text
        return [x["price_usd"] for x in r.json()["items"]]

    assert sorted(await search()) == [700, 800, 1500, 300000]
    assert sorted(await search(location="beirut")) == [800, 1500]
    assert sorted(await search(location="mount-lebanon")) == [700, 300000]
    assert await search(location="keserwan") == [700]
    assert await search(location="no-such-place") == []
    assert sorted(await search(transaction_type="rent", price_max=1000)) == [700, 800]
    assert await search(transaction_type="rent", bedrooms_min=3) == [1500]
    assert await search(transaction_type="sale") == [300000]
    assert await search(furnished="unfurnished") == [800]
    assert await search(transaction_type="rent", sort="price_asc") == [700, 800, 1500]
    assert await search(transaction_type="rent", sort="price_desc") == [1500, 800, 700]
    r = await anon.client.get("/api/v1/listings", params={"page_size": 2, "page": 2, "sort": "price_asc"})
    assert r.json()["total"] == 4 and len(r.json()["items"]) == 2
    assert (await anon.client.get("/api/v1/listings", params={"page_size": 500})).status_code == 422
    assert (await anon.client.get("/api/v1/listings", params={"sort": "drop table"})).status_code == 422


async def test_expired_and_demo_listings_hidden(
    make_actor: Any, anon: Any, settings: Any, monkeypatch: Any
) -> None:
    broker = await make_actor("broker", "b@example.com", org="Org")
    a = await published_listing(broker)
    b = await published_listing(broker)
    async with get_sessionmaker()() as s:
        await s.execute(
            update(Listing).where(Listing.id == a["id"]).values(expires_at=utcnow() - timedelta(hours=1))
        )
        await s.execute(update(Listing).where(Listing.id == b["id"]).values(is_demo=True))
        await s.commit()
    assert (await anon.client.get("/api/v1/listings")).json()["total"] == 0
    assert (await anon.client.get(f"/api/v1/listings/{a['id']}")).status_code == 404

    monkeypatch.setattr(settings, "demo_mode", True)
    page = (await anon.client.get("/api/v1/listings")).json()
    assert [x["id"] for x in page["items"]] == [b["id"]] and page["items"][0]["is_demo"] is True

    # Confirming availability revives the expired listing
    assert (await broker.client.post(f"/api/v1/listings/{a['id']}/confirm")).status_code == 200
    assert (await anon.client.get(f"/api/v1/listings/{a['id']}")).status_code == 200


async def test_upload_limits(make_actor: Any, settings: Any, monkeypatch: Any) -> None:
    broker = await make_actor("broker", "b@example.com", org="Org")
    listing = await create_listing(broker)
    r = await upload_photo(broker, listing["id"], b"#!/bin/sh\nrm -rf /\n")
    assert r.status_code == 422
    monkeypatch.setattr(settings, "max_upload_bytes", 1000)
    r = await upload_photo(broker, listing["id"], jpeg_bytes())
    assert r.status_code == 413
    monkeypatch.setattr(settings, "max_upload_bytes", 8 * 1024 * 1024)
    monkeypatch.setattr(settings, "max_media_per_listing", 1)
    assert (await upload_photo(broker, listing["id"])).status_code == 201
    assert (await upload_photo(broker, listing["id"])).status_code == 409


async def test_delete_media(make_actor: Any, settings: Any) -> None:
    broker = await make_actor("broker", "b@example.com", org="Org")
    other = await make_actor("broker", "c@example.com", org="Org2")
    listing = await create_listing(broker)
    media = (await upload_photo(broker, listing["id"])).json()
    path = Path(settings.media_root) / media["url"].removeprefix("/media/")
    url = f"/api/v1/listings/{listing['id']}/media/{media['id']}"
    assert (await other.client.delete(url)).status_code == 404
    assert (await broker.client.delete(url)).status_code == 204
    assert not path.exists()
    assert (await broker.client.delete(url)).status_code == 404


async def test_health(anon: Any) -> None:
    assert (await anon.client.get("/healthz")).json() == {"status": "ok"}
    r = await anon.client.get("/readyz")
    assert r.status_code == 200
    assert r.headers["x-content-type-options"] == "nosniff"
    assert r.headers["x-request-id"]
    locs = (await anon.client.get("/api/v1/locations")).json()
    assert {"beirut", "achrafieh", "jounieh"} <= {x["slug"] for x in locs}
    ach = next(x for x in locs if x["slug"] == "achrafieh")
    assert ach["name_ar"] == "الأشرفية" and ach["path"] == "beirut/achrafieh"

from typing import Any

from tests.conftest import jpeg_bytes, promote

TICKET = {
    "category": "bug",
    "title": "Map does not load",
    "description": "On the listing page the map stays grey on my phone.",
    "page_url": "https://2ajar.test/en/listings/abc",
    "context": {"locale": "en", "viewport": "390x844", "user_agent": "Mozilla/5.0", "dark": False},
}


async def test_ticket_lifecycle(make_actor: Any, notifications: Any) -> None:
    reporter = await make_actor("seeker", "r@example.com")
    other = await make_actor("owner", "o@example.com")
    staff = await make_actor("seeker", "staff@example.com")
    await promote(staff, "staff")

    r = await reporter.client.post("/api/v1/tickets", json=TICKET)
    assert r.status_code == 201, r.text
    ticket = r.json()
    tid = ticket["id"]
    assert ticket["status"] == "open" and ticket["number"] >= 1 and ticket["reporter"]["email"] is None
    assert ticket["context"]["viewport"] == "390x844"
    assert notifications.messages[-1].startswith(f"🐞 Ticket #{ticket['number']}")

    # Others cannot see it; staff can (with e-mails)
    assert (await other.client.get(f"/api/v1/tickets/{tid}")).status_code == 404
    staff_view = (await staff.client.get(f"/api/v1/tickets/{tid}")).json()
    assert staff_view["reporter"]["email"] == "r@example.com"

    # Staff internal note + public reply; reporter only sees the public reply
    await staff.client.post(
        f"/api/v1/tickets/{tid}/comments", json={"body": "Probably the CSP", "is_internal": True}
    )
    await staff.client.post(f"/api/v1/tickets/{tid}/comments", json={"body": "Thanks, looking into it"})
    mine = (await reporter.client.get(f"/api/v1/tickets/{tid}")).json()
    assert [c["body"] for c in mine["comments"]] == ["Thanks, looking into it"]
    assert mine["comments"][0]["author_is_staff"] is True
    assert len((await staff.client.get(f"/api/v1/tickets/{tid}")).json()["comments"]) == 2
    r = await reporter.client.post(f"/api/v1/tickets/{tid}/comments", json={"body": "x", "is_internal": True})
    assert r.status_code == 403
    assert (
        await other.client.post(f"/api/v1/tickets/{tid}/comments", json={"body": "hi"})
    ).status_code == 404

    # Triage: assign, resolve; reporter reply reopens
    r = await staff.client.patch(
        f"/api/v1/admin/tickets/{tid}",
        json={"status": "resolved", "priority": "high", "assignee_user_id": staff.user["id"]},
    )
    body = r.json()
    assert r.status_code == 200 and body["status"] == "resolved" and body["resolved_at"]
    assert body["assignee"]["id"] == staff.user["id"]
    r = await staff.client.patch(
        f"/api/v1/admin/tickets/{tid}", json={"assignee_user_id": reporter.user["id"]}
    )
    assert r.status_code == 422, "only staff can be assignees"
    assert (
        await reporter.client.patch(f"/api/v1/admin/tickets/{tid}", json={"status": "closed"})
    ).status_code == 403
    r = await reporter.client.post(f"/api/v1/tickets/{tid}/comments", json={"body": "Still broken"})
    assert r.json()["status"] == "open" and r.json()["resolved_at"] is None

    # Lists and filters
    assert [t["id"] for t in (await reporter.client.get("/api/v1/me/tickets")).json()] == [tid]
    page = (await staff.client.get("/api/v1/admin/tickets", params={"status": "open", "q": "map"})).json()
    assert page["total"] == 1 and page["items"][0]["comment_count"] == 3
    assert (await staff.client.get("/api/v1/admin/tickets", params={"priority": "low"})).json()["total"] == 0
    r = await staff.client.get("/api/v1/admin/tickets", params={"assignee_id": staff.user["id"]})
    assert r.json()["total"] == 1


async def test_ticket_attachment_is_private(make_actor: Any, settings: Any) -> None:
    reporter = await make_actor("seeker", "r@example.com")
    other = await make_actor("seeker", "x@example.com")
    staff = await make_actor("seeker", "staff@example.com")
    await promote(staff, "staff")
    tid = (await reporter.client.post("/api/v1/tickets", json=TICKET)).json()["id"]
    assert (await reporter.client.get(f"/api/v1/tickets/{tid}/attachment")).status_code == 404

    files = {"file": ("shot.jpg", jpeg_bytes(), "image/jpeg")}
    r = await reporter.client.post(f"/api/v1/tickets/{tid}/attachment", files=files)
    assert r.status_code == 200 and r.json()["has_attachment"] is True
    r = await reporter.client.post(f"/api/v1/tickets/{tid}/attachment", files=files)  # replaces the old one
    assert r.status_code == 200

    img = await staff.client.get(f"/api/v1/tickets/{tid}/attachment")
    assert img.status_code == 200 and img.headers["content-type"] == "image/webp"
    assert "no-store" in img.headers["cache-control"]
    assert (await other.client.get(f"/api/v1/tickets/{tid}/attachment")).status_code == 404
    assert (await other.client.post(f"/api/v1/tickets/{tid}/attachment", files=files)).status_code == 404
    r = await staff.client.post(f"/api/v1/tickets/{tid}/attachment", files=files)  # managers may attach
    assert r.status_code == 200
    bad = {"file": ("x.txt", b"not an image", "text/plain")}
    assert (await reporter.client.post(f"/api/v1/tickets/{tid}/attachment", files=bad)).status_code == 422


async def test_ticket_validation_and_auth(make_actor: Any) -> None:
    anon = await make_actor()
    assert (await anon.client.post("/api/v1/tickets", json=TICKET)).status_code == 401
    user = await make_actor("seeker", "u@example.com")
    assert (await user.client.post("/api/v1/tickets", json={**TICKET, "title": "x"})).status_code == 422
    big_context = {f"k{i}": i for i in range(30)}
    assert (
        await user.client.post("/api/v1/tickets", json={**TICKET, "context": big_context})
    ).status_code == 422
    r = await user.client.post("/api/v1/tickets", json={**TICKET, "context": {"ua": "x" * 1000}})
    assert r.status_code == 201 and len(r.json()["context"]["ua"]) == 300
    assert (await user.client.get("/api/v1/tickets/00000000-0000-0000-0000-000000000000")).status_code == 404

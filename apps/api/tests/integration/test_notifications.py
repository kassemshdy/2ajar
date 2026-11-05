from typing import Any

import httpx

from app.notify import (
    NullNotifier,
    TelegramNotifier,
    get_notifier,
    mask_phone,
    msg_lead,
    msg_listing,
    msg_user_registered,
    set_notifier,
)
from tests.conftest import create_listing, published_listing


async def test_events_are_announced(make_actor: Any, anon: Any, notifications: Any) -> None:
    broker = await make_actor("broker", "b@example.com", org="Cedar <Homes>")
    assert notifications.messages[-1].startswith("🆕 New broker account")
    assert "Cedar &lt;Homes&gt;" in notifications.messages[-1], "untrusted text is HTML-escaped"

    listing = await published_listing(broker, title_en="Nice <b>flat</b>")
    created, published = notifications.messages[-2:]
    assert created.startswith("📝 Listing created") and "Nice &lt;b&gt;flat&lt;/b&gt;" in created
    assert published.startswith("✅ Listing published") and "$1,200/month" in published
    assert f"/en/listings/{listing['id']}" in published

    url = f"/api/v1/listings/{listing['id']}/leads"
    body = {"name": "Lea", "phone": "03 123 456", "consent": True, "consent_text_version": "2026-11-v1",
            "message": "secret message"}  # fmt: skip
    await anon.client.post(url, json=body)
    lead_msg = notifications.messages[-1]
    assert lead_msg.startswith("📩 New lead") and "+9613***456" in lead_msg
    assert "secret message" not in lead_msg and "3123456" not in lead_msg
    count = len(notifications.messages)
    await anon.client.post(url, json=body)  # deduplicated: no second announcement
    assert len(notifications.messages) == count


async def test_failed_actions_are_not_announced(make_actor: Any, notifications: Any) -> None:
    broker = await make_actor("broker", "b@example.com", org="Org")
    draft = await create_listing(broker)
    before = len(notifications.messages)
    r = await broker.client.post(f"/api/v1/listings/{draft['id']}/publish")  # no photo
    assert r.status_code == 422
    assert len(notifications.messages) == before


def test_message_formatting(settings: Any, monkeypatch: Any) -> None:
    assert mask_phone("+9613123456") == "+9613***456"
    assert mask_phone("+1234") == "***"
    assert "[test]" in msg_user_registered("Rami Haddad", "owner", None)
    assert "Haddad" not in msg_user_registered("Rami Haddad", "owner", None)
    monkeypatch.setattr(settings, "env", "production")
    assert "[" not in msg_user_registered("", "owner", None)
    sale = msg_listing(
        "published", listing_id="x", title=None, price_usd=250000, period="total", area="Dbayeh", demo=True
    )
    assert "Untitled" in sale and "(DEMO)" in sale and "$250,000 ·" in sale
    assert "via ai" in msg_lead(listing_title=None, source="ai", phone_e164="+96170123456")


async def test_telegram_notifier_posts_and_never_raises(monkeypatch: Any, settings: Any) -> None:
    calls: list[httpx.Request] = []

    def ok(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        return httpx.Response(200, json={"ok": True})

    await TelegramNotifier("TOKEN123", "-100", transport=httpx.MockTransport(ok)).send("hello <b>x</b>")
    assert calls[0].url.path == "/botTOKEN123/sendMessage"
    import json

    payload = json.loads(calls[0].content)
    assert payload == {"chat_id": "-100", "text": "hello <b>x</b>", "parse_mode": "HTML",
                       "disable_web_page_preview": True}  # fmt: skip

    def bad(request: httpx.Request) -> httpx.Response:
        return httpx.Response(429)

    def boom(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("down")

    await TelegramNotifier("t", "c", transport=httpx.MockTransport(bad)).send("x")
    await TelegramNotifier("t", "c", transport=httpx.MockTransport(boom)).send("x")

    set_notifier(None)
    assert isinstance(get_notifier(), NullNotifier)
    await NullNotifier().send("ignored")
    monkeypatch.setattr(settings, "telegram_bot_token", "t")
    monkeypatch.setattr(settings, "telegram_chat_id", "c")
    assert isinstance(get_notifier(), TelegramNotifier)

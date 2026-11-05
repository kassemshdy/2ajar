"""Operational notifications (Telegram) for newly created items.

Notifications are best-effort: they run as background tasks after the request's transaction committed,
time out quickly, and never raise. Publisher-supplied text is HTML-escaped; lead phone numbers are masked.
"""

import html
import logging
from typing import Protocol

import httpx

from app.core.config import get_settings

log = logging.getLogger("ajar.notify")

TELEGRAM_API = "https://api.telegram.org"


class Notifier(Protocol):
    async def send(self, text: str) -> None: ...


class NullNotifier:
    async def send(self, text: str) -> None:
        return None


class TelegramNotifier:
    def __init__(self, token: str, chat_id: str, transport: httpx.AsyncBaseTransport | None = None) -> None:
        self.token = token
        self.chat_id = chat_id
        self.transport = transport

    async def send(self, text: str) -> None:
        try:
            async with httpx.AsyncClient(timeout=5.0, transport=self.transport) as client:
                r = await client.post(
                    f"{TELEGRAM_API}/bot{self.token}/sendMessage",
                    json={
                        "chat_id": self.chat_id,
                        "text": text[:4000],
                        "parse_mode": "HTML",
                        "disable_web_page_preview": True,
                    },
                )
            if r.status_code != 200:
                log.warning("telegram send failed", extra={"extra_fields": {"status": r.status_code}})
        except httpx.HTTPError as exc:
            # Never log the URL: it contains the bot token.
            log.warning("telegram send error", extra={"extra_fields": {"error": type(exc).__name__}})


_override: Notifier | None = None


def get_notifier() -> Notifier:
    if _override is not None:
        return _override
    s = get_settings()
    if s.telegram_bot_token and s.telegram_chat_id:
        return TelegramNotifier(s.telegram_bot_token, s.telegram_chat_id)
    return NullNotifier()


def set_notifier(notifier: Notifier | None) -> None:
    """Testing hook."""
    global _override
    _override = notifier


# ---------- message formatting ----------


def esc(value: object) -> str:
    return html.escape(str(value), quote=False)


def mask_phone(phone: str) -> str:
    """+9613123456 -> +9613***456 (keeps country/operator prefix and last 3 digits)."""
    if len(phone) <= 7:
        return "***"
    return f"{phone[:5]}***{phone[-3:]}"


def env_tag() -> str:
    s = get_settings()
    return "" if s.env == "production" else f" [{esc(s.env)}]"


def listing_link(listing_id: object) -> str:
    base = get_settings().public_web_base_url.rstrip("/")
    return f"{base}/en/listings/{listing_id}"


async def notify(text: str) -> None:
    await get_notifier().send(text)


def msg_user_registered(full_name: str, role: str, organization: str | None) -> str:
    first = full_name.split()[0] if full_name.split() else "?"
    org = f" — {esc(organization)}" if organization else ""
    return f"🆕 New {esc(role)} account{env_tag()}: <b>{esc(first)}</b>{org}"


def msg_listing(
    verb: str, *, listing_id: object, title: str | None, price_usd: int, period: str, area: str, demo: bool
) -> str:
    icon = {"created": "📝", "published": "✅"}.get(verb, "•")
    suffix = {"monthly": "/month", "yearly": "/year"}.get(period, "")
    demo_tag = " (DEMO)" if demo else ""
    return (
        f"{icon} Listing {esc(verb)}{env_tag()}{demo_tag}: <b>{esc(title or 'Untitled')}</b>\n"
        f"${price_usd:,}{suffix} · {esc(area)}\n{listing_link(listing_id)}"
    )


def msg_lead(*, listing_title: str | None, source: str, phone_e164: str) -> str:
    return (
        f"📩 New lead{env_tag()} for <b>{esc(listing_title or 'Untitled')}</b>\n"
        f"via {esc(source)} · {esc(mask_phone(phone_e164))}"
    )


def msg_import(*, created: int, actor_name: str) -> str:
    return f"📦 CSV import{env_tag()}: {created} draft listing(s) created by <b>{esc(actor_name)}</b>"

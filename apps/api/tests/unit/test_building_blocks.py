"""Unit tests for reusable building blocks: cache, rate limiter, event bus, publish rules, link builder."""

import asyncio
import uuid
from types import SimpleNamespace
from typing import Any

import pytest

from app.core.cache import TTLCache
from app.core.config import Settings
from app.core.events import CollectingEventRecorder, EventBus
from app.core.ratelimit import SlidingWindowLimiter
from app.domain.events import DomainEvent, LeadReceived, ListingCreated, ListingSnapshot
from app.models.enums import ListingStatus, PropertyType
from app.services.contact import WhatsAppLinkBuilder
from app.services.publishing import (
    AutoPublishPolicy,
    HasPhoto,
    ModerationPolicy,
    publish_policy_for,
)


class FakeClock:
    def __init__(self) -> None:
        self.now = 1000.0

    def __call__(self) -> float:
        return self.now


# ---------- TTLCache ----------


def test_cache_expires_and_evicts_lru() -> None:
    clock = FakeClock()
    cache: TTLCache[str, int] = TTLCache(ttl_seconds=10, max_size=2, clock=clock)
    cache.set("a", 1)
    cache.set("b", 2)
    assert cache.get("a") == 1  # "a" becomes most recently used
    cache.set("c", 3)  # evicts "b", the least recently used
    assert cache.get("b") is None and cache.get("a") == 1 and len(cache) == 2
    clock.now += 11
    assert cache.get("a") is None  # expired
    assert cache.stats.evictions == 1 and cache.stats.hits == 2 and cache.stats.misses == 2
    cache.set("x", 9)
    cache.invalidate("x")
    assert cache.get("x") is None
    cache.set("y", 1)
    cache.clear()
    assert len(cache) == 0


def test_cache_rejects_bad_config() -> None:
    with pytest.raises(ValueError):
        TTLCache(ttl_seconds=0)
    with pytest.raises(ValueError):
        TTLCache(ttl_seconds=1, max_size=0)


async def test_cache_single_flight_loader() -> None:
    cache: TTLCache[str, int] = TTLCache(ttl_seconds=60)
    calls = 0

    async def loader() -> int:
        nonlocal calls
        calls += 1
        await asyncio.sleep(0.01)
        return 42

    results = await asyncio.gather(*(cache.get_or_load("k", loader) for _ in range(20)))
    assert results == [42] * 20
    assert calls == 1, "concurrent misses must share one load"
    assert await cache.get_or_load("k", loader) == 42 and calls == 1


# ---------- rate limiter memory bounds ----------


def test_limiter_caps_tracked_keys() -> None:
    limiter = SlidingWindowLimiter(max_keys=100, sweep_every=10_000)
    for i in range(1_000):
        limiter.hit(f"ip-{i}", limit=5, window_s=60)
    assert len(limiter) == 100


def test_limiter_sweeps_expired_keys_and_still_limits() -> None:
    clock = FakeClock()
    limiter = SlidingWindowLimiter(sweep_every=50, clock=clock)
    for i in range(49):
        limiter.hit(f"old-{i}", limit=5, window_s=10)
    clock.now += 11  # every window elapsed
    assert limiter.hit("fresh", limit=1, window_s=10)  # 50th call triggers the sweep
    assert len(limiter) == 1
    assert not limiter.hit("fresh", limit=1, window_s=10)
    limiter.reset()
    assert len(limiter) == 0


# ---------- event bus ----------


def _snapshot() -> ListingSnapshot:
    return ListingSnapshot(uuid.uuid4(), "Flat", 900, "monthly", "Hamra", False)


async def test_event_bus_dispatches_by_type_and_isolates_failures() -> None:
    bus = EventBus()
    seen: list[str] = []

    async def on_created(event: DomainEvent) -> None:
        seen.append("created")

    async def on_any(event: DomainEvent) -> None:
        seen.append(type(event).__name__)

    async def broken(event: DomainEvent) -> None:
        raise RuntimeError("subscriber bug")

    bus.subscribe(ListingCreated, broken)
    bus.subscribe(ListingCreated, on_created)
    bus.subscribe(DomainEvent, on_any)
    await bus.dispatch(ListingCreated(_snapshot()))
    await bus.dispatch(LeadReceived(uuid.uuid4(), None, "web", "+96170123456"))
    assert seen == ["created", "ListingCreated", "LeadReceived"]


def test_collecting_recorder() -> None:
    recorder = CollectingEventRecorder()
    event = ListingCreated(_snapshot())
    recorder.record(event)
    assert recorder.events == [event]


# ---------- publish policy ----------


def _listing(**kw: Any) -> Any:
    prop = SimpleNamespace(
        property_type=kw.pop("property_type", PropertyType.apartment), bedrooms=kw.pop("bedrooms", 2)
    )
    base = {
        "title_en": "T",
        "title_ar": None,
        "contact_whatsapp_e164": "+96170123456",
        "media": [object()],
        "property": prop,
    }
    base.update(kw)
    return SimpleNamespace(**base)


def test_publish_policy_rules_and_factory() -> None:
    policy = publish_policy_for(Settings())
    assert isinstance(policy, AutoPublishPolicy) and policy.target_status == ListingStatus.published
    assert policy.problems(_listing()) == []
    problems = policy.problems(_listing(title_en=None, contact_whatsapp_e164=None, bedrooms=None, media=[]))
    assert problems == [
        "A title in English or Arabic is required",
        "A WhatsApp contact number is required",
        "Number of bedrooms is required for residential properties",
        "At least one photo is required",
    ]
    assert policy.problems(_listing(property_type=PropertyType.office, bedrooms=None)) == []

    moderated = publish_policy_for(Settings(moderation_required=True, publish_requires_media=False))
    assert isinstance(moderated, ModerationPolicy) and moderated.target_status == ListingStatus.pending_review
    assert not any(isinstance(r, HasPhoto) for r in moderated.rules)


# ---------- WhatsApp links ----------


def test_whatsapp_link_builder() -> None:
    builder = WhatsAppLinkBuilder("https://2ajar.test/")
    lid = uuid.UUID("12345678-1234-1234-1234-123456789012")
    listing = SimpleNamespace(id=lid, title_en=None, title_ar="شقة", contact_whatsapp_e164="+96170123456")
    url = builder.build(listing, "en")  # type: ignore[arg-type]
    assert url.startswith("https://wa.me/96170123456?text=")
    assert "2ajar.test/en/listings/12345678-1234" in url and "Ref%3A%2012345678" in url
    assert "%D8%B4%D9%82%D8%A9" in url  # falls back to the Arabic title
    with pytest.raises(ValueError):
        builder.build(SimpleNamespace(**{**listing.__dict__, "contact_whatsapp_e164": None}), "ar")  # type: ignore[arg-type]

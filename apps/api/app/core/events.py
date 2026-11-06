"""In-process event bus (Observer pattern).

Services *record* domain events after their transaction commits; subscribers (e.g. Telegram notifications,
later analytics or e-mail) *react* to them. Neither side knows about the other, so adding a new reaction
never touches business code (Open/Closed principle).

Delivery is best-effort and asynchronous: in HTTP requests events are dispatched as FastAPI background tasks,
i.e. after the response was sent, and a failing subscriber is logged and isolated from the others.
"""

import logging
from collections import defaultdict
from collections.abc import Awaitable, Callable
from typing import Protocol

from fastapi import BackgroundTasks

from app.domain.events import DomainEvent

log = logging.getLogger("ajar.events")

Handler = Callable[[DomainEvent], Awaitable[None]]


class EventBus:
    def __init__(self) -> None:
        self._handlers: dict[type[DomainEvent], list[Handler]] = defaultdict(list)

    def subscribe(self, event_type: type[DomainEvent], handler: Handler) -> None:
        self._handlers[event_type].append(handler)

    def handlers_for(self, event: DomainEvent) -> list[Handler]:
        # Exact type plus base classes, so a subscriber may listen to a whole family of events.
        return [h for cls in type(event).__mro__ for h in self._handlers.get(cls, [])]

    async def dispatch(self, event: DomainEvent) -> None:
        for handler in self.handlers_for(event):
            try:
                await handler(event)
            except Exception:
                log.exception("event handler failed", extra={"extra_fields": {"event": type(event).__name__}})


class EventRecorder(Protocol):
    """What services depend on: somewhere to put events (Dependency Inversion)."""

    def record(self, event: DomainEvent) -> None: ...


class BackgroundEventRecorder:
    """Defers dispatch until after the HTTP response is sent."""

    def __init__(self, bus: EventBus, background: BackgroundTasks) -> None:
        self._bus = bus
        self._background = background

    def record(self, event: DomainEvent) -> None:
        self._background.add_task(self._bus.dispatch, event)


class CollectingEventRecorder:
    """Keeps events in memory: used by CLI jobs and tests."""

    def __init__(self) -> None:
        self.events: list[DomainEvent] = []

    def record(self, event: DomainEvent) -> None:
        self.events.append(event)


_bus: EventBus | None = None


def get_event_bus() -> EventBus:
    """Process-wide bus, wired once with the default subscribers."""
    global _bus
    if _bus is None:
        from app.notify import register_notification_subscribers

        _bus = EventBus()
        register_notification_subscribers(_bus)
    return _bus

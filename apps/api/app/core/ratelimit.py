"""In-process sliding-window rate limiter (single replica only, see ADR-007)."""

import time
from collections import OrderedDict, deque
from collections.abc import Awaitable, Callable

from fastapi import Request

from app.core.config import get_settings
from app.core.errors import RateLimited


class SlidingWindowLimiter:
    """Sliding-window counter keyed by ``scope:client``.

    Memory is bounded: keys whose window has fully elapsed are swept periodically, and the number of tracked
    keys is capped (oldest-touched keys are dropped first). Dropping a key can only make the limiter more
    lenient for that client, never block a legitimate one.
    """

    def __init__(
        self,
        *,
        max_keys: int = 100_000,
        sweep_every: int = 1_000,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._hits: OrderedDict[str, deque[float]] = OrderedDict()
        self._windows: dict[str, float] = {}
        self._max_keys = max_keys
        self._sweep_every = sweep_every
        self._calls = 0
        self._clock = clock

    def __len__(self) -> int:
        return len(self._hits)

    def hit(self, key: str, limit: int, window_s: float) -> bool:
        now = self._clock()
        self._calls += 1
        if self._calls % self._sweep_every == 0:
            self._sweep(now)
        q = self._hits.get(key)
        if q is None:
            q = self._hits[key] = deque()
            while len(self._hits) > self._max_keys:
                evicted, _ = self._hits.popitem(last=False)
                self._windows.pop(evicted, None)
        self._hits.move_to_end(key)
        self._windows[key] = window_s
        while q and q[0] <= now - window_s:
            q.popleft()
        if len(q) >= limit:
            return False
        q.append(now)
        return True

    def _sweep(self, now: float) -> None:
        stale = [k for k, q in self._hits.items() if not q or q[-1] <= now - self._windows.get(k, 0.0)]
        for k in stale:
            del self._hits[k]
            self._windows.pop(k, None)

    def reset(self) -> None:
        self._hits.clear()
        self._windows.clear()
        self._calls = 0


limiter = SlidingWindowLimiter()


def client_ip(request: Request) -> str:
    """Client IP, honouring X-Forwarded-For only for the configured number of trusted proxy hops.

    Each trusted proxy appends the address it received the request from, so the real client is the
    N-th entry from the right. Entries further left are client-controlled and ignored.
    """
    peer = request.client.host if request.client else "unknown"
    hops = get_settings().forwarded_trusted_hops
    if hops <= 0:
        return peer
    chain = [p.strip() for p in request.headers.get("x-forwarded-for", "").split(",") if p.strip()]
    if not chain:
        return peer
    return chain[-hops] if len(chain) >= hops else chain[0]


def rate_limit(scope: str, limit: int, window_s: float) -> Callable[[Request], Awaitable[None]]:
    async def dependency(request: Request) -> None:
        if not get_settings().rate_limit_enabled:
            return
        if not limiter.hit(f"{scope}:{client_ip(request)}", limit, window_s):
            raise RateLimited("Too many requests, please slow down")

    return dependency

"""In-process sliding-window rate limiter (single replica only, see ADR-007)."""

import time
from collections import defaultdict, deque
from collections.abc import Awaitable, Callable

from fastapi import Request

from app.core.config import get_settings
from app.core.errors import RateLimited


class SlidingWindowLimiter:
    def __init__(self) -> None:
        self._hits: dict[str, deque[float]] = defaultdict(deque)

    def hit(self, key: str, limit: int, window_s: float) -> bool:
        now = time.monotonic()
        q = self._hits[key]
        while q and q[0] <= now - window_s:
            q.popleft()
        if len(q) >= limit:
            return False
        q.append(now)
        return True

    def reset(self) -> None:
        self._hits.clear()


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

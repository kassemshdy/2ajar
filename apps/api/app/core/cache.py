"""In-process caching primitives.

Design notes
------------
* ``Cache`` is a small protocol so callers depend on an abstraction (Dependency Inversion). The MVP runs a
  single API replica, so ``TTLCache`` (in-memory) is enough; a Redis-backed implementation can be dropped in
  later without touching callers (see ADR-007 / ADR-014).
* ``TTLCache`` is bounded twice: by time (TTL) and by size (LRU eviction), so memory use has a hard ceiling
  no matter how many distinct keys traffic produces.
* ``get_or_load`` is *single-flight*: concurrent misses for the same key await one loader call instead of
  stampeding the database.
* Only cache data that is (a) read far more often than written and (b) safe to serve slightly stale.
  In this codebase that is reference data such as the location tree — never per-user or authz data.
"""

import asyncio
import time
from collections import OrderedDict
from collections.abc import Awaitable, Callable, Hashable
from dataclasses import dataclass
from typing import Protocol


@dataclass
class CacheStats:
    hits: int = 0
    misses: int = 0
    evictions: int = 0


class Cache[K: Hashable, V](Protocol):
    def get(self, key: K) -> V | None: ...
    def set(self, key: K, value: V) -> None: ...
    def invalidate(self, key: K) -> None: ...
    def clear(self) -> None: ...
    async def get_or_load(self, key: K, loader: Callable[[], Awaitable[V]]) -> V: ...


class TTLCache[K: Hashable, V]:
    """Bounded LRU cache whose entries expire ``ttl_seconds`` after being stored."""

    def __init__(
        self, *, ttl_seconds: float, max_size: int = 1024, clock: Callable[[], float] = time.monotonic
    ) -> None:
        if ttl_seconds <= 0 or max_size <= 0:
            raise ValueError("ttl_seconds and max_size must be positive")
        self._ttl = ttl_seconds
        self._max_size = max_size
        self._clock = clock
        self._data: OrderedDict[K, tuple[float, V]] = OrderedDict()
        self._locks: dict[K, asyncio.Lock] = {}
        self.stats = CacheStats()

    def __len__(self) -> int:
        return len(self._data)

    def get(self, key: K) -> V | None:
        entry = self._data.get(key)
        if entry is None:
            self.stats.misses += 1
            return None
        expires_at, value = entry
        if expires_at <= self._clock():
            del self._data[key]
            self.stats.misses += 1
            return None
        self._data.move_to_end(key)  # mark as most recently used
        self.stats.hits += 1
        return value

    def set(self, key: K, value: V) -> None:
        self._data[key] = (self._clock() + self._ttl, value)
        self._data.move_to_end(key)
        while len(self._data) > self._max_size:
            self._data.popitem(last=False)  # evict least recently used
            self.stats.evictions += 1

    def invalidate(self, key: K) -> None:
        self._data.pop(key, None)

    def clear(self) -> None:
        self._data.clear()
        self._locks.clear()

    async def get_or_load(self, key: K, loader: Callable[[], Awaitable[V]]) -> V:
        cached = self.get(key)
        if cached is not None:
            return cached
        lock = self._locks.setdefault(key, asyncio.Lock())
        async with lock:
            cached = self.get(key)  # another coroutine may have filled it while we waited
            if cached is not None:
                return cached
            value = await loader()
            self.set(key, value)
            return value

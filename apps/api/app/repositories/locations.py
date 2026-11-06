"""Location reference data, cached in memory.

Locations change only through migrations/seeding, but are read on almost every request (search filters,
listing forms, CSV imports). ``LocationDirectory`` loads the whole tree once into an immutable
``LocationSnapshot`` and serves lookups from memory until the TTL expires.

Snapshots hold frozen dataclasses rather than ORM objects: ORM instances are bound to one session and must
never be shared across requests, while frozen records are safe to share between concurrent coroutines.
"""

import uuid
from dataclasses import dataclass, field

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.cache import TTLCache
from app.models import Location
from app.models.enums import LocationLevel


@dataclass(frozen=True, slots=True)
class LocationRecord:
    id: uuid.UUID
    parent_id: uuid.UUID | None
    level: LocationLevel
    slug: str
    name_en: str
    name_ar: str
    path: str


@dataclass(frozen=True)
class LocationSnapshot:
    records: tuple[LocationRecord, ...]
    by_id: dict[uuid.UUID, LocationRecord] = field(repr=False)
    by_slug: dict[str, LocationRecord] = field(repr=False)
    by_name: dict[str, LocationRecord] = field(repr=False)

    @classmethod
    def build(cls, records: list[LocationRecord]) -> "LocationSnapshot":
        by_name: dict[str, LocationRecord] = {}
        for r in records:
            for key in (r.slug, r.name_en.casefold(), r.name_ar.strip()):
                by_name.setdefault(key, r)
        return cls(
            records=tuple(records),
            by_id={r.id: r for r in records},
            by_slug={r.slug: r for r in records},
            by_name=by_name,
        )


class LocationDirectory:
    """Read-only, cached access to the location tree."""

    # Shared by all instances: one snapshot per process. Locations are tiny (~50 rows), so one entry suffices.
    _cache: TTLCache[str, LocationSnapshot] = TTLCache(ttl_seconds=600, max_size=1)
    _KEY = "all"

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def snapshot(self) -> LocationSnapshot:
        return await self._cache.get_or_load(self._KEY, self._load)

    async def _load(self) -> LocationSnapshot:
        rows = (await self._session.scalars(select(Location).order_by(Location.path))).all()
        return LocationSnapshot.build(
            [LocationRecord(r.id, r.parent_id, r.level, r.slug, r.name_en, r.name_ar, r.path) for r in rows]
        )

    async def all(self) -> tuple[LocationRecord, ...]:
        return (await self.snapshot()).records

    async def get(self, location_id: uuid.UUID) -> LocationRecord | None:
        return (await self.snapshot()).by_id.get(location_id)

    async def by_slug(self, slug: str) -> LocationRecord | None:
        return (await self.snapshot()).by_slug.get(slug)

    async def resolve(self, text: str) -> LocationRecord | None:
        """Match user-supplied text (slug, English or Arabic name) to a location."""
        key = text.strip()
        snap = await self.snapshot()
        return snap.by_name.get(key) or snap.by_name.get(key.casefold())

    @classmethod
    def invalidate(cls) -> None:
        """Call after changing locations (seeding) so the next read reloads them."""
        cls._cache.clear()

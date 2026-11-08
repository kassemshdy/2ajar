"""Staff-curated neighbourhood profiles (safety, theft reports, noise, garbage, flooding).

A listing shows the profile of its own area, or the closest ancestor that has one (e.g. a district-level
profile covers its villages). Lookups go through the cached ``LocationDirectory`` for the ancestry and a
single query for the profiles, so search results never trigger one query per listing.
"""

import uuid
from collections.abc import Iterable

from fastapi import Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.authz.policies import Principal
from app.core.errors import Forbidden, NotFound
from app.models import AreaProfile
from app.models.enums import Permission
from app.repositories.locations import LocationDirectory
from app.schemas.listing import AreaProfileIn
from app.services.audit import AuditTrail


class AreaProfileService:
    def __init__(self, session: AsyncSession, *, include_demo: bool = False) -> None:
        self._session = session
        # Demo profiles hold synthetic numbers: shown only while DEMO_MODE is on, like demo listings.
        self._include_demo = include_demo
        self._locations = LocationDirectory(session)
        self._audit = AuditTrail(session)

    async def list_all(self) -> list[AreaProfile]:
        rows = await self._session.scalars(select(AreaProfile))
        return sorted(rows.unique(), key=lambda a: a.location.path)

    async def for_locations(self, location_ids: Iterable[uuid.UUID]) -> dict[uuid.UUID, AreaProfile]:
        """Map each location id to its own profile or its nearest ancestor's (one query)."""
        snap = await self._locations.snapshot()
        chains: dict[uuid.UUID, list[uuid.UUID]] = {}
        for loc_id in set(location_ids):
            chain: list[uuid.UUID] = []
            current = snap.by_id.get(loc_id)
            while current is not None:
                chain.append(current.id)
                current = snap.by_id.get(current.parent_id) if current.parent_id else None
            chains[loc_id] = chain
        wanted = {i for chain in chains.values() for i in chain}
        if not wanted:
            return {}
        stmt = select(AreaProfile).where(AreaProfile.location_id.in_(wanted))
        if not self._include_demo:
            stmt = stmt.where(AreaProfile.is_demo.is_(False))
        profiles = {p.location_id: p for p in (await self._session.scalars(stmt)).unique()}
        result: dict[uuid.UUID, AreaProfile] = {}
        for loc_id, chain in chains.items():
            found = next((profiles[i] for i in chain if i in profiles), None)
            if found is not None:
                result[loc_id] = found
        return result

    async def for_location(self, location_id: uuid.UUID) -> AreaProfile | None:
        return (await self.for_locations([location_id])).get(location_id)

    async def upsert(
        self, p: Principal, location_id: uuid.UUID, data: AreaProfileIn, request: Request | None = None
    ) -> AreaProfile:
        if not p.has(Permission.areas_manage):
            raise Forbidden("You do not have permission to edit area information")
        if await self._locations.get(location_id) is None:
            raise NotFound("Location not found")
        profile = await self._session.scalar(
            select(AreaProfile).where(AreaProfile.location_id == location_id)
        )
        if profile is None:
            profile = AreaProfile(location_id=location_id)
            self._session.add(profile)
        for key, value in data.model_dump().items():
            setattr(profile, key, value)
        profile.is_demo = False  # a human just reviewed it
        profile.updated_by_user_id = p.user_id
        await self._session.flush()
        self._audit.record(
            p.user_id,
            "area_profile.upsert",
            "location",
            location_id,
            request=request,
            data=data.model_dump(mode="json", exclude_none=True),
        )
        await self._session.commit()
        await self._session.refresh(profile)
        return profile

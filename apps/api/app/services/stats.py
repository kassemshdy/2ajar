"""Read-only platform metrics (back office dashboard and MCP)."""

from datetime import timedelta
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import utcnow
from app.models import Lead, Listing, Ticket, User


class PlatformStats:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def snapshot(self) -> dict[str, object]:
        now = utcnow()

        async def grouped(stmt: Any) -> dict[str, int]:
            rows = (await self._session.execute(stmt)).all()
            return {str(getattr(k, "value", k)): int(n) for k, n in rows}

        async def count_since(days: int) -> int:
            stmt = select(func.count()).select_from(Lead).where(Lead.created_at > now - timedelta(days=days))
            return int(await self._session.scalar(stmt) or 0)

        return {
            "users_by_role": await grouped(select(User.role, func.count()).group_by(User.role)),
            "active_users": int(
                await self._session.scalar(select(func.count()).select_from(User).where(User.is_active)) or 0
            ),
            "listings_by_status": await grouped(
                select(Listing.status, func.count()).group_by(Listing.status)
            ),
            "leads_last_7_days": await count_since(7),
            "leads_last_30_days": await count_since(30),
            "tickets_by_status": await grouped(select(Ticket.status, func.count()).group_by(Ticket.status)),
            "generated_at": now.isoformat(),
        }

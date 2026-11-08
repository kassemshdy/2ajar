"""Personal API tokens for machine clients (the MCP server).

Tokens are random 256-bit values with a recognisable prefix (``2ajar_``) so leaked tokens can be found by
secret scanners. Only their SHA-256 hash is stored. A token acts *as its owner*: the owner's current role and
permissions are re-evaluated on every request, so demoting or deactivating a user immediately limits or kills
their tokens.
"""

import secrets
import uuid
from collections.abc import Callable
from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.authz.policies import Principal
from app.core.errors import Forbidden, NotFound
from app.core.security import sha256_hex, utcnow
from app.models import ApiToken, User
from app.models.enums import Permission
from app.services.audit import AuditTrail

TOKEN_PREFIX = "2ajar_"  # noqa: S105 (public prefix, not a secret)
MAX_ACTIVE_TOKENS = 10
LAST_USED_RESOLUTION = timedelta(minutes=5)  # avoid a write on every single request

Clock = Callable[[], datetime]


class ApiTokenService:
    def __init__(self, session: AsyncSession, *, clock: Clock = utcnow) -> None:
        self._session = session
        self._clock = clock
        self._audit = AuditTrail(session)

    async def create(self, p: Principal, name: str, expires_in_days: int | None) -> tuple[ApiToken, str]:
        if not p.has(Permission.mcp_access):
            raise Forbidden("Your account cannot create API tokens")
        active = [t for t in await self.list(p) if t.revoked_at is None]
        if len(active) >= MAX_ACTIVE_TOKENS:
            raise Forbidden(f"At most {MAX_ACTIVE_TOKENS} active tokens; revoke one first")
        raw = TOKEN_PREFIX + secrets.token_urlsafe(32)
        now = self._clock()
        token = ApiToken(
            user_id=p.user_id,
            name=name,
            token_hash=sha256_hex(raw),
            prefix=raw[: len(TOKEN_PREFIX) + 6],
            expires_at=now + timedelta(days=expires_in_days) if expires_in_days else None,
        )
        self._session.add(token)
        await self._session.flush()
        self._audit.record(p.user_id, "api_token.create", "api_token", token.id, data={"name": name})
        await self._session.commit()
        await self._session.refresh(token)
        return token, raw

    async def list(self, p: Principal) -> list[ApiToken]:
        stmt = select(ApiToken).where(ApiToken.user_id == p.user_id).order_by(ApiToken.created_at.desc())
        return list((await self._session.scalars(stmt)).unique())

    async def revoke(self, p: Principal, token_id: uuid.UUID) -> None:
        token = await self._session.get(ApiToken, token_id)
        if token is None or token.user_id != p.user_id:
            raise NotFound("Token not found")
        if token.revoked_at is None:
            token.revoked_at = self._clock()
            self._audit.record(p.user_id, "api_token.revoke", "api_token", token.id)
            await self._session.commit()

    async def authenticate(self, raw: str) -> User | None:
        """Return the active owner of a valid, unexpired, unrevoked token; otherwise None."""
        if not raw.startswith(TOKEN_PREFIX) or len(raw) > 100:
            return None
        token = await self._session.scalar(select(ApiToken).where(ApiToken.token_hash == sha256_hex(raw)))
        now = self._clock()
        if token is None or token.revoked_at is not None or (token.expires_at and token.expires_at <= now):
            return None
        user = token.user
        if not user.is_active:
            return None
        if token.last_used_at is None or now - token.last_used_at > LAST_USED_RESOLUTION:
            token.last_used_at = now
            await self._session.commit()
        return user

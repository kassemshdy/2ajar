"""Accounts and sessions.

Split by responsibility (SRP):
* ``AccountService`` — registration and credential checks.
* ``TokenService``   — access/refresh token lifecycle with rotation and reuse detection.
"""

import re
import secrets
import uuid
from collections.abc import Callable
from datetime import datetime, timedelta

from fastapi import Request
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.errors import Conflict, Unauthorized, ValidationFailed
from app.core.events import EventRecorder
from app.core.phone import normalize_phone
from app.core.security import (
    DUMMY_PASSWORD_HASH,
    create_access_token,
    hash_password,
    new_opaque_token,
    password_problems,
    sha256_hex,
    utcnow,
    verify_password,
)
from app.domain.events import UserRegistered
from app.models import Organization, OrganizationMember, RefreshToken, User
from app.models.enums import OrgRole, UserRole
from app.schemas.auth import RegisterIn
from app.services.audit import AuditTrail

Clock = Callable[[], datetime]
_GENERIC_LOGIN_ERROR = "Invalid email or password"  # same message for unknown e-mail and wrong password


def slugify(text: str) -> str:
    base = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")[:60] or "org"
    return f"{base}-{secrets.token_hex(3)}"


class AccountService:
    def __init__(self, session: AsyncSession, *, events: EventRecorder, clock: Clock = utcnow) -> None:
        self._session = session
        self._events = events
        self._clock = clock
        self._audit = AuditTrail(session)

    async def register(self, data: RegisterIn, request: Request | None = None) -> User:
        email = data.email.lower()
        problems = password_problems(data.password)
        if problems:
            raise ValidationFailed(problems[0], details=problems)
        phone = None
        if data.phone:
            phone = normalize_phone(data.phone)
            if phone is None:
                raise ValidationFailed("Invalid phone number")
        if data.organization_name and data.role != "broker":
            raise ValidationFailed("Only brokers can create an agency")
        if await self._session.scalar(select(User.id).where(User.email == email)):
            raise Conflict("An account with this email already exists")

        user = User(
            email=email,
            password_hash=hash_password(data.password),
            full_name=data.full_name,
            phone_e164=phone,
            role=UserRole(data.role),
            locale=data.locale,
        )
        self._session.add(user)
        await self._session.flush()
        if data.role == "broker" and data.organization_name:
            # A broker who names an agency becomes its admin (tenant owner).
            org = Organization(
                name=data.organization_name, slug=slugify(data.organization_name), phone_e164=phone
            )
            self._session.add(org)
            await self._session.flush()
            self._session.add(
                OrganizationMember(organization_id=org.id, user_id=user.id, role=OrgRole.agency_admin)
            )
        self._audit.record(
            user.id, "user.register", "user", user.id, request=request, data={"role": data.role}
        )
        await self._session.commit()
        await self._session.refresh(user, ["memberships"])
        self._events.record(UserRegistered(user.full_name, user.role.value, data.organization_name))
        return user

    async def authenticate(self, email: str, password: str, request: Request | None = None) -> User:
        user = await self._session.scalar(select(User).where(User.email == email.lower()))
        if user is None:
            verify_password(DUMMY_PASSWORD_HASH, password)  # equalize timing to resist account enumeration
            raise Unauthorized(_GENERIC_LOGIN_ERROR)
        if not verify_password(user.password_hash, password) or not user.is_active:
            self._audit.record(user.id, "user.login_failed", "user", user.id, request=request)
            await self._session.commit()
            raise Unauthorized(_GENERIC_LOGIN_ERROR)
        user.last_login_at = self._clock()
        self._audit.record(user.id, "user.login", "user", user.id, request=request)
        await self._session.commit()
        return user


class TokenService:
    """Short-lived JWT access tokens + opaque, rotating refresh tokens stored hashed.

    Each login starts a token *family*. Every refresh revokes the presented token and issues a new one in the
    same family; presenting an already-revoked token means it was copied, so the whole family is revoked.
    """

    def __init__(self, session: AsyncSession, *, settings: Settings, clock: Clock = utcnow) -> None:
        self._session = session
        self._settings = settings
        self._clock = clock

    async def issue(self, user: User, family_id: uuid.UUID | None = None) -> tuple[str, str]:
        refresh = new_opaque_token()
        now = self._clock()
        self._session.add(
            RefreshToken(
                user_id=user.id,
                family_id=family_id or uuid.uuid4(),
                token_hash=sha256_hex(refresh),  # only the hash is stored
                created_at=now,
                expires_at=now + timedelta(days=self._settings.refresh_token_ttl_days),
            )
        )
        await self._session.commit()
        return create_access_token(user.id, user.role.value), refresh

    async def rotate(self, raw: str) -> tuple[User, str, str]:
        token = await self._find(raw)
        now = self._clock()
        if token is None:
            raise Unauthorized("Invalid session")
        if token.revoked_at is not None:
            await self.revoke_family(token.family_id)
            raise Unauthorized("Session revoked")
        if token.expires_at <= now:
            raise Unauthorized("Session expired")
        user = await self._session.get(User, token.user_id)
        if user is None or not user.is_active:
            raise Unauthorized("Invalid session")
        token.revoked_at = now
        access, refresh = await self.issue(user, token.family_id)
        return user, access, refresh

    async def revoke_family(self, family_id: uuid.UUID) -> None:
        await self._session.execute(
            update(RefreshToken)
            .where(RefreshToken.family_id == family_id, RefreshToken.revoked_at.is_(None))
            .values(revoked_at=self._clock())
        )
        await self._session.commit()

    async def logout(self, raw_refresh: str | None) -> None:
        if not raw_refresh:
            return
        token = await self._find(raw_refresh)
        if token is not None:
            await self.revoke_family(token.family_id)

    async def _find(self, raw: str) -> RefreshToken | None:
        return await self._session.scalar(
            select(RefreshToken).where(RefreshToken.token_hash == sha256_hex(raw))
        )

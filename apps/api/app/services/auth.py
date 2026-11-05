import re
import secrets
import uuid
from datetime import timedelta

from fastapi import Request
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.errors import Conflict, Unauthorized, ValidationFailed
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
from app.models import Organization, OrganizationMember, RefreshToken, User
from app.models.enums import OrgRole, UserRole
from app.schemas.auth import RegisterIn
from app.services.audit import audit


def slugify(text: str) -> str:
    base = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")[:60] or "org"
    return f"{base}-{secrets.token_hex(3)}"


async def get_user_with_memberships(session: AsyncSession, user_id: uuid.UUID) -> User | None:
    return await session.get(User, user_id)


async def register_user(session: AsyncSession, data: RegisterIn, request: Request | None) -> User:
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
    if await session.scalar(select(User.id).where(User.email == email)):
        raise Conflict("An account with this email already exists")

    user = User(
        email=email,
        password_hash=hash_password(data.password),
        full_name=data.full_name,
        phone_e164=phone,
        role=UserRole(data.role),
        locale=data.locale,
    )
    session.add(user)
    await session.flush()
    if data.role == "broker" and data.organization_name:
        org = Organization(
            name=data.organization_name, slug=slugify(data.organization_name), phone_e164=phone
        )
        session.add(org)
        await session.flush()
        session.add(OrganizationMember(organization_id=org.id, user_id=user.id, role=OrgRole.agency_admin))
    audit(
        session,
        actor_id=user.id,
        action="user.register",
        resource_type="user",
        resource_id=user.id,
        data={"role": data.role},
        request=request,
    )
    await session.commit()
    await session.refresh(user, ["memberships"])
    return user


async def authenticate(session: AsyncSession, email: str, password: str, request: Request | None) -> User:
    user = await session.scalar(select(User).where(User.email == email.lower()))
    if user is None:
        verify_password(DUMMY_PASSWORD_HASH, password)  # equalize timing
        raise Unauthorized("Invalid email or password")
    if not verify_password(user.password_hash, password) or not user.is_active:
        audit(
            session,
            actor_id=user.id,
            action="user.login_failed",
            resource_type="user",
            resource_id=user.id,
            request=request,
        )
        await session.commit()
        raise Unauthorized("Invalid email or password")
    user.last_login_at = utcnow()
    audit(
        session,
        actor_id=user.id,
        action="user.login",
        resource_type="user",
        resource_id=user.id,
        request=request,
    )
    await session.commit()
    return user


async def issue_tokens(
    session: AsyncSession, user: User, family_id: uuid.UUID | None = None
) -> tuple[str, str]:
    s = get_settings()
    refresh = new_opaque_token()
    now = utcnow()
    session.add(
        RefreshToken(
            user_id=user.id,
            family_id=family_id or uuid.uuid4(),
            token_hash=sha256_hex(refresh),
            created_at=now,
            expires_at=now + timedelta(days=s.refresh_token_ttl_days),
        )
    )
    await session.commit()
    return create_access_token(user.id, user.role.value), refresh


async def rotate_refresh_token(session: AsyncSession, raw: str) -> tuple[User, str, str]:
    token = await session.scalar(select(RefreshToken).where(RefreshToken.token_hash == sha256_hex(raw)))
    now = utcnow()
    if token is None:
        raise Unauthorized("Invalid session")
    if token.revoked_at is not None:
        # Reuse of a rotated token: assume theft, revoke the whole family.
        await revoke_family(session, token.family_id)
        raise Unauthorized("Session revoked")
    if token.expires_at <= now:
        raise Unauthorized("Session expired")
    user = await session.get(User, token.user_id)
    if user is None or not user.is_active:
        raise Unauthorized("Invalid session")
    token.revoked_at = now
    access, refresh = await issue_tokens(session, user, token.family_id)
    return user, access, refresh


async def revoke_family(session: AsyncSession, family_id: uuid.UUID) -> None:
    await session.execute(
        update(RefreshToken)
        .where(RefreshToken.family_id == family_id, RefreshToken.revoked_at.is_(None))
        .values(revoked_at=utcnow())
    )
    await session.commit()


async def logout(session: AsyncSession, raw_refresh: str | None) -> None:
    if not raw_refresh:
        return
    token = await session.scalar(
        select(RefreshToken).where(RefreshToken.token_hash == sha256_hex(raw_refresh))
    )
    if token is not None:
        await revoke_family(session, token.family_id)

import secrets
import uuid
from collections.abc import Awaitable, Callable
from typing import Annotated

from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.authz.permissions import effective_permissions
from app.authz.policies import Principal
from app.core.errors import Forbidden, Unauthorized
from app.core.security import decode_access_token
from app.db.session import get_session
from app.models import User
from app.models.enums import Permission

SessionDep = Annotated[AsyncSession, Depends(get_session)]

ACCESS_COOKIE = "access_token"
REFRESH_COOKIE = "refresh_token"
CSRF_COOKIE = "csrf_token"
CSRF_HEADER = "x-csrf-token"
SAFE_METHODS = {"GET", "HEAD", "OPTIONS"}


def _csrf_ok(request: Request) -> bool:
    cookie = request.cookies.get(CSRF_COOKIE)
    header = request.headers.get(CSRF_HEADER)
    return bool(cookie and header and secrets.compare_digest(cookie, header))


async def _resolve(request: Request, session: AsyncSession) -> tuple[User | None, bool]:
    """Returns (user, authenticated_via_cookie)."""
    auth = request.headers.get("authorization", "")
    via_cookie = False
    if auth.lower().startswith("bearer "):
        token = auth[7:].strip()
    else:
        token = request.cookies.get(ACCESS_COOKIE, "")
        via_cookie = True
    if not token:
        return None, False
    payload = decode_access_token(token)
    if payload is None:
        return None, via_cookie
    try:
        user_id = uuid.UUID(payload["sub"])
    except (KeyError, ValueError):
        return None, via_cookie
    user = await session.get(User, user_id)
    if user is None or not user.is_active:
        return None, via_cookie
    return user, via_cookie


async def get_optional_user(request: Request, session: SessionDep) -> User | None:
    user, via_cookie = await _resolve(request, session)
    if user and via_cookie and request.method not in SAFE_METHODS and not _csrf_ok(request):
        return None  # treat as anonymous rather than act on ambient credentials
    return user


async def get_current_user(request: Request, session: SessionDep) -> User:
    user, via_cookie = await _resolve(request, session)
    if user is None:
        raise Unauthorized("Authentication required")
    if via_cookie and request.method not in SAFE_METHODS and not _csrf_ok(request):
        raise Forbidden("CSRF token missing or invalid")
    return user


def principal_of(user: User) -> Principal:
    return Principal(
        user_id=user.id,
        role=user.role,
        org_roles={m.organization_id: m.role for m in user.memberships},
        permissions=effective_permissions(user.role, user.extra_permissions or []),
    )


def require_permission(permission: Permission) -> Callable[[Principal], Awaitable[Principal]]:
    """Dependency factory: 403 unless the caller holds ``permission`` (back-office endpoints)."""

    async def dependency(p: Annotated[Principal, Depends(get_principal)]) -> Principal:
        if not p.has(permission):
            raise Forbidden("You do not have permission to do this")
        return p

    return dependency


async def get_principal(user: Annotated[User, Depends(get_current_user)]) -> Principal:
    return principal_of(user)


async def get_optional_principal(
    user: Annotated[User | None, Depends(get_optional_user)],
) -> Principal | None:
    return principal_of(user) if user else None


CurrentUser = Annotated[User, Depends(get_current_user)]
OptionalUser = Annotated[User | None, Depends(get_optional_user)]
PrincipalDep = Annotated[Principal, Depends(get_principal)]
OptionalPrincipal = Annotated[Principal | None, Depends(get_optional_principal)]

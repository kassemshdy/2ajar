from fastapi import APIRouter, BackgroundTasks, Depends, Request, Response, status

from app.api.deps import (
    ACCESS_COOKIE,
    CSRF_COOKIE,
    REFRESH_COOKIE,
    CurrentUser,
    SessionDep,
)
from app.core.config import get_settings
from app.core.errors import Unauthorized
from app.core.ratelimit import rate_limit
from app.core.security import new_opaque_token
from app.models import User
from app.notify import msg_user_registered, notify
from app.schemas.auth import LoginIn, MembershipOut, RegisterIn, UserOut
from app.services import auth as auth_service

router = APIRouter(prefix="/auth", tags=["auth"])

REFRESH_PATH = "/api/v1/auth"


def user_out(user: User) -> UserOut:
    return UserOut(
        id=user.id,
        email=user.email,
        full_name=user.full_name,
        phone_e164=user.phone_e164,
        role=user.role,
        locale=user.locale,
        memberships=[
            MembershipOut(
                organization_id=m.organization_id, organization_name=m.organization.name, role=m.role
            )
            for m in user.memberships
        ],
    )


def _set_cookie(
    response: Response, name: str, value: str, *, max_age: int, path: str, httponly: bool
) -> None:
    s = get_settings()
    response.set_cookie(
        name,
        value,
        max_age=max_age,
        path=path,
        httponly=httponly,
        secure=s.cookie_secure,
        samesite="lax",
        domain=s.cookie_domain,
    )


def set_auth_cookies(response: Response, access: str, refresh: str) -> None:
    s = get_settings()
    refresh_age = s.refresh_token_ttl_days * 86400
    _set_cookie(
        response, ACCESS_COOKIE, access, max_age=s.access_token_ttl_minutes * 60, path="/", httponly=True
    )
    _set_cookie(response, REFRESH_COOKIE, refresh, max_age=refresh_age, path=REFRESH_PATH, httponly=True)
    # Readable by JS on purpose: double-submit CSRF token.
    _set_cookie(response, CSRF_COOKIE, new_opaque_token(), max_age=refresh_age, path="/", httponly=False)


def clear_auth_cookies(response: Response) -> None:
    s = get_settings()
    response.delete_cookie(ACCESS_COOKIE, path="/", domain=s.cookie_domain)
    response.delete_cookie(REFRESH_COOKIE, path=REFRESH_PATH, domain=s.cookie_domain)
    response.delete_cookie(CSRF_COOKIE, path="/", domain=s.cookie_domain)


@router.post(
    "/register",
    response_model=UserOut,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(rate_limit("register", 10, 3600))],
)
async def register(
    data: RegisterIn, request: Request, response: Response, session: SessionDep, background: BackgroundTasks
) -> UserOut:
    user = await auth_service.register_user(session, data, request)
    access, refresh = await auth_service.issue_tokens(session, user)
    set_auth_cookies(response, access, refresh)
    out = user_out(user)
    org = out.memberships[0].organization_name if out.memberships else None
    background.add_task(notify, msg_user_registered(user.full_name, user.role.value, org))
    return out


@router.post("/login", response_model=UserOut, dependencies=[Depends(rate_limit("login", 10, 300))])
async def login(data: LoginIn, request: Request, response: Response, session: SessionDep) -> UserOut:
    user = await auth_service.authenticate(session, data.email, data.password, request)
    access, refresh = await auth_service.issue_tokens(session, user)
    set_auth_cookies(response, access, refresh)
    return user_out(user)


@router.post("/refresh", response_model=UserOut, dependencies=[Depends(rate_limit("refresh", 60, 300))])
async def refresh(request: Request, response: Response, session: SessionDep) -> UserOut:
    raw = request.cookies.get(REFRESH_COOKIE)
    if not raw:
        raise Unauthorized("No session")
    user, access, new_refresh = await auth_service.rotate_refresh_token(session, raw)
    set_auth_cookies(response, access, new_refresh)
    return user_out(user)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(request: Request, session: SessionDep) -> Response:
    await auth_service.logout(session, request.cookies.get(REFRESH_COOKIE))
    response = Response(status_code=status.HTTP_204_NO_CONTENT)
    clear_auth_cookies(response)
    return response


me_router = APIRouter(tags=["me"])


@me_router.get("/me", response_model=UserOut)
async def me(user: CurrentUser) -> UserOut:
    return user_out(user)

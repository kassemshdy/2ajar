"""Back-office endpoints. Every route declares the permission it needs (``require_permission``)."""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request, status

from app.api.deps import SessionDep, require_permission
from app.api.providers import AreaServiceDep, SettingsDep, TicketServiceDep, UserAdminDep
from app.authz.policies import Principal
from app.models.enums import Permission, TicketPriority, TicketStatus, UserRole
from app.schemas.admin import AdminUserOut, AdminUserUpdate, PermissionInfo
from app.schemas.common import Page
from app.schemas.growth import GrowthOut, GrowthTaskIn
from app.schemas.listing import AreaProfileIn, AreaProfileOut
from app.schemas.tickets import TicketOut, TicketSummary, TicketUpdate
from app.services.growth import GrowthService
from app.services.presenters import ListingPresenter
from app.services.stats import PlatformStats
from app.services.tickets import TicketPresenter
from app.services.user_admin import permission_catalog, present_user

router = APIRouter(prefix="/admin", tags=["admin"])

UsersRead = Annotated[Principal, Depends(require_permission(Permission.users_read))]
UsersManage = Annotated[Principal, Depends(require_permission(Permission.users_manage))]
TicketsRead = Annotated[Principal, Depends(require_permission(Permission.tickets_read))]
TicketsManage = Annotated[Principal, Depends(require_permission(Permission.tickets_manage))]
AnalyticsRead = Annotated[Principal, Depends(require_permission(Permission.analytics_read))]


@router.get("/permissions", response_model=list[PermissionInfo])
async def permissions(_: UsersRead) -> list[PermissionInfo]:
    return permission_catalog()


@router.get("/users", response_model=Page[AdminUserOut])
async def list_users(
    _: UsersRead,
    users: UserAdminDep,
    q: Annotated[str | None, Query(max_length=100)] = None,
    role: UserRole | None = None,
    is_active: bool | None = None,
    page: Annotated[int, Query(ge=1, le=1000)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 25,
) -> Page[AdminUserOut]:
    items, total = await users.search(query=q, role=role, is_active=is_active, page=page, page_size=page_size)
    return Page(items=[present_user(u) for u in items], total=total, page=page, page_size=page_size)


@router.get("/users/{user_id}", response_model=AdminUserOut)
async def get_user(user_id: uuid.UUID, _: UsersRead, users: UserAdminDep) -> AdminUserOut:
    return present_user(await users.get(user_id))


@router.patch("/users/{user_id}", response_model=AdminUserOut)
async def update_user(
    user_id: uuid.UUID, data: AdminUserUpdate, request: Request, actor: UsersManage, users: UserAdminDep
) -> AdminUserOut:
    return present_user(await users.update(actor, user_id, data, request))


@router.get("/tickets", response_model=Page[TicketSummary])
async def list_tickets(
    p: TicketsRead,
    tickets: TicketServiceDep,
    status: TicketStatus | None = None,
    priority: TicketPriority | None = None,
    q: Annotated[str | None, Query(max_length=100)] = None,
    assignee_id: uuid.UUID | None = None,
    page: Annotated[int, Query(ge=1, le=1000)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 25,
) -> Page[TicketSummary]:
    items, total = await tickets.search(
        status=status, priority=priority, query=q, assignee_id=assignee_id, page=page, page_size=page_size
    )
    view = TicketPresenter(p)
    return Page(items=[view.summary(t) for t in items], total=total, page=page, page_size=page_size)


@router.patch("/tickets/{ticket_id}", response_model=TicketOut)
async def update_ticket(
    ticket_id: uuid.UUID, data: TicketUpdate, request: Request, p: TicketsManage, tickets: TicketServiceDep
) -> TicketOut:
    return TicketPresenter(p).detail(await tickets.update(p, ticket_id, data, request))


@router.get("/growth", response_model=GrowthOut)
async def growth(_: AnalyticsRead, session: SessionDep, settings: SettingsDep) -> GrowthOut:
    return GrowthOut.model_validate(await GrowthService(session, settings=settings).dashboard())


@router.put("/growth/tasks/{key}", status_code=status.HTTP_204_NO_CONTENT)
async def set_growth_task(
    key: str, data: GrowthTaskIn, p: AnalyticsRead, session: SessionDep, settings: SettingsDep
) -> None:
    await GrowthService(session, settings=settings).set_task(p, key, data.done)


@router.get("/stats")
async def stats(_: AnalyticsRead, session: SessionDep) -> dict[str, object]:
    return await PlatformStats(session).snapshot()


AreasManage = Annotated[Principal, Depends(require_permission(Permission.areas_manage))]


@router.get("/areas", response_model=list[AreaProfileOut])
async def list_areas(_: AreasManage, areas: AreaServiceDep) -> list[AreaProfileOut]:
    return [out for a in await areas.list_all() if (out := ListingPresenter.area(a)) is not None]


@router.put("/areas/{location_id}", response_model=AreaProfileOut)
async def upsert_area(
    location_id: uuid.UUID, data: AreaProfileIn, request: Request, p: AreasManage, areas: AreaServiceDep
) -> AreaProfileOut:
    out = ListingPresenter.area(await areas.upsert(p, location_id, data, request))
    assert out is not None
    return out

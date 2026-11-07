"""Reporter-facing ticket endpoints (the floating "Report a bug" button and "My tickets")."""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, File, Request, Response, UploadFile, status

from app.api.deps import PrincipalDep
from app.api.providers import ApiTokensDep, TicketServiceDep
from app.core.ratelimit import rate_limit
from app.schemas.tickets import CommentCreate, TicketCreate, TicketOut, TicketSummary
from app.schemas.tokens import ApiTokenCreate, ApiTokenCreated, ApiTokenOut
from app.services.tickets import TicketPresenter

router = APIRouter(tags=["tickets"])


@router.post(
    "/tickets",
    response_model=TicketOut,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(rate_limit("ticket", 20, 3600))],
)
async def create_ticket(
    data: TicketCreate, request: Request, p: PrincipalDep, tickets: TicketServiceDep
) -> TicketOut:
    return TicketPresenter(p).detail(await tickets.create(p, data, request))


@router.get("/me/tickets", response_model=list[TicketSummary])
async def my_tickets(p: PrincipalDep, tickets: TicketServiceDep) -> list[TicketSummary]:
    view = TicketPresenter(p)
    return [view.summary(t) for t in await tickets.list_mine(p)]


@router.get("/tickets/{ticket_id}", response_model=TicketOut)
async def get_ticket(ticket_id: uuid.UUID, p: PrincipalDep, tickets: TicketServiceDep) -> TicketOut:
    return TicketPresenter(p).detail(await tickets.get_visible(p, ticket_id))


@router.post(
    "/tickets/{ticket_id}/comments",
    response_model=TicketOut,
    dependencies=[Depends(rate_limit("ticket_comment", 60, 3600))],
)
async def comment(
    ticket_id: uuid.UUID, data: CommentCreate, request: Request, p: PrincipalDep, tickets: TicketServiceDep
) -> TicketOut:
    return TicketPresenter(p).detail(await tickets.comment(p, ticket_id, data, request=request))


@router.post(
    "/tickets/{ticket_id}/attachment",
    response_model=TicketOut,
    dependencies=[Depends(rate_limit("ticket_upload", 30, 3600))],
)
async def attach(
    ticket_id: uuid.UUID, p: PrincipalDep, tickets: TicketServiceDep, file: Annotated[UploadFile, File()]
) -> TicketOut:
    return TicketPresenter(p).detail(await tickets.attach(p, ticket_id, file))


@router.get("/tickets/{ticket_id}/attachment", include_in_schema=False)
async def attachment(ticket_id: uuid.UUID, p: PrincipalDep, tickets: TicketServiceDep) -> Response:
    data, content_type = await tickets.attachment(p, ticket_id)
    # Private: never cache in shared caches.
    return Response(content=data, media_type=content_type, headers={"Cache-Control": "private, no-store"})


# ---------- personal API tokens (for the MCP server) ----------


@router.get("/me/api-tokens", response_model=list[ApiTokenOut], tags=["me"])
async def list_tokens(p: PrincipalDep, tokens: ApiTokensDep) -> list[ApiTokenOut]:
    return [ApiTokenOut.model_validate(t) for t in await tokens.list(p)]


@router.post(
    "/me/api-tokens", response_model=ApiTokenCreated, status_code=status.HTTP_201_CREATED, tags=["me"]
)
async def create_token(data: ApiTokenCreate, p: PrincipalDep, tokens: ApiTokensDep) -> ApiTokenCreated:
    token, raw = await tokens.create(p, data.name, data.expires_in_days)
    return ApiTokenCreated(**ApiTokenOut.model_validate(token).model_dump(), token=raw)


@router.delete("/me/api-tokens/{token_id}", status_code=status.HTTP_204_NO_CONTENT, tags=["me"])
async def revoke_token(token_id: uuid.UUID, p: PrincipalDep, tokens: ApiTokensDep) -> Response:
    await tokens.revoke(p, token_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)

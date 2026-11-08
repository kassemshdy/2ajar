"""Plain-text smart search ("ask"). Rule-based: no LLM or paid API is called (see app.search)."""

from fastapi import APIRouter, Depends, Response

from app.api.deps import OptionalUser
from app.api.providers import SmartSearchDep
from app.core.ratelimit import rate_limit
from app.schemas.search import AskRequest, AskResponse, Suggestion
from app.search.presenter import to_response
from app.search.suggestions import SUGGESTIONS

router = APIRouter(prefix="/search", tags=["search"])


@router.post("/ask", response_model=AskResponse, dependencies=[Depends(rate_limit("ask", 60, 600))])
async def ask(data: AskRequest, engine: SmartSearchDep, user: OptionalUser) -> AskResponse:
    result = await engine.ask(data.query, data.locale, user_id=user.id if user else None)
    return to_response(result)


@router.get("/suggestions", response_model=list[Suggestion])
async def suggestions(response: Response) -> list[Suggestion]:
    response.headers["Cache-Control"] = "public, max-age=3600"
    return list(SUGGESTIONS)

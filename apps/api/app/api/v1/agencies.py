"""Public agency pages: an agency's live listings at one shareable address (e.g. for its Instagram bio)."""

from fastapi import APIRouter, Response

from app.api.providers import AgencyServiceDep
from app.schemas.agency import AgencyPage
from app.services.presenters import ListingPresenter as present

router = APIRouter(prefix="/agencies", tags=["agencies"])


@router.get("/{slug}", response_model=AgencyPage)
async def agency_page(slug: str, service: AgencyServiceDep, response: Response) -> AgencyPage:
    org, listings, members = await service.public_page(slug)
    response.headers["Cache-Control"] = "public, max-age=30, stale-while-revalidate=120"
    return AgencyPage(
        name=org.name,
        slug=org.slug,
        verified=org.is_verified,
        is_demo=org.is_demo,
        members=members,
        on_2ajar_since=org.created_at,
        listings=[present.to_public(x) for x in listings],
    )

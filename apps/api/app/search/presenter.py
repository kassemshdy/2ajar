"""Maps engine results (domain dataclasses) to API schemas."""

from app.schemas.search import (
    AskHit,
    AskResponse,
    ReasonOut,
    RelaxationOut,
    Understood,
    UnderstoodPreference,
)
from app.search.engine import AskResult
from app.services.presenters import ListingPresenter


def to_response(result: AskResult) -> AskResponse:
    q = result.parsed
    return AskResponse(
        query_id=result.query_id,
        understood=Understood(
            stay=q.stay,
            guests_min=q.guests_min,
            property_type=q.property_type,
            location_slug=q.location.slug if q.location else None,
            location_name_en=q.location.name_en if q.location else None,
            location_name_ar=q.location.name_ar if q.location else None,
            price_min=q.price_min,
            price_max=q.price_max,
            bedrooms_min=q.bedrooms_min,
            bathrooms_min=q.bathrooms_min,
            furnished=q.furnished,
            parking_spots=q.parking_spots,
            preferences=[
                UnderstoodPreference(key=p.key, label_en=p.label_en, label_ar=p.label_ar)
                for p in q.preferences
            ],
            sort=q.sort,
        ),
        summary_en=result.summary_en,
        summary_ar=result.summary_ar,
        clarification_en=result.clarification_en,
        clarification_ar=result.clarification_ar,
        relaxed=[RelaxationOut(key=r.key, label_en=r.label_en, label_ar=r.label_ar) for r in result.relaxed],
        results=[
            AskHit(
                listing=ListingPresenter.to_public(h.listing, h.area),
                score=h.score,
                reasons=[
                    ReasonOut(
                        key=r.key, label_en=r.label_en, label_ar=r.label_ar, status=r.status, source=r.source
                    )
                    for r in h.reasons
                ],
            )
            for h in result.hits
        ],
        total=result.total,
    )

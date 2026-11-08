"""Smart search: parse → filter (SQL) → relax if empty → rank by preferences → explain.

Grounding rules
* Hard constraints (area, budget, rooms, deal/property type, furnishing) are SQL filters: a result never
  violates them unless the response lists the relaxation that was applied.
* Preferences only *rank* results. Each reason is computed from a stored field and labelled with its status:
  match, miss or unknown (not reported) — never guessed.
"""

import time
import uuid
from collections.abc import Callable
from dataclasses import dataclass, field, replace
from typing import Literal

from sqlalchemy.ext.asyncio import AsyncSession

from app.models import AreaProfile, Listing, SearchQuery
from app.models.enums import Furnished, PropertyType, TransactionType
from app.repositories.listings import SearchCriteria
from app.search.parser import ParsedQuery, QueryParser
from app.search.preferences import Preference, Status, _parking
from app.services.areas import AreaProfileService
from app.services.listings import ListingService

CANDIDATE_POOL = 60  # hard-filtered listings considered for ranking
MAX_RESULTS = 12
RELAX_BUDGET_FACTOR = 1.2

ReasonStatus = Literal["match", "miss", "unknown"]


@dataclass(frozen=True)
class Reason:
    key: str
    label_en: str
    label_ar: str
    status: ReasonStatus
    source: Literal["filter", "listing", "area"]


@dataclass
class Hit:
    listing: Listing
    area: AreaProfile | None
    score: int
    reasons: list[Reason]


@dataclass
class Relaxation:
    key: str
    label_en: str
    label_ar: str


@dataclass
class AskResult:
    parsed: ParsedQuery
    summary_en: str
    summary_ar: str
    clarification_en: str | None
    clarification_ar: str | None
    relaxed: list[Relaxation]
    hits: list[Hit]
    total: int
    criteria: SearchCriteria
    query_id: uuid.UUID | None = None
    extras: dict[str, object] = field(default_factory=dict)


# ---------- wording (EN / AR) ----------

_TYPE_EN = {
    PropertyType.apartment: "apartments",
    PropertyType.studio: "studios",
    PropertyType.duplex: "duplexes",
    PropertyType.villa: "villas",
    PropertyType.house: "houses",
    PropertyType.chalet: "chalets",
    PropertyType.office: "offices",
    PropertyType.shop: "shops",
    PropertyType.land: "land",
}
_TYPE_AR = {
    PropertyType.apartment: "شقق",
    PropertyType.studio: "استوديوهات",
    PropertyType.duplex: "دوبلكس",
    PropertyType.villa: "فلل",
    PropertyType.house: "منازل",
    PropertyType.chalet: "شاليهات",
    PropertyType.office: "مكاتب",
    PropertyType.shop: "محلات",
    PropertyType.land: "أراضٍ",
}
_FURN_EN = {
    Furnished.furnished: "furnished",
    Furnished.semi: "semi-furnished",
    Furnished.unfurnished: "unfurnished",
}
_FURN_AR = {Furnished.furnished: "مفروشة", Furnished.semi: "نصف مفروشة", Furnished.unfurnished: "غير مفروشة"}


def _usd(n: int) -> str:
    return f"${n:,}"


def summarize(q: ParsedQuery) -> tuple[str, str]:
    """One-line description of what we understood, in English and Arabic."""
    en: list[str] = []
    ar: list[str] = []
    if q.furnished:
        en.append(_FURN_EN[q.furnished])
    if q.bedrooms_min == 0:
        en.append("studio")
    elif q.bedrooms_min:
        en.append(f"{q.bedrooms_min}+ bedroom")
    if q.property_type is None:
        en.append("homes")
    elif q.property_type != PropertyType.studio:
        en.append(_TYPE_EN.get(q.property_type, "homes"))
    ar.append(_TYPE_AR.get(q.property_type, "عقارات") if q.property_type else "عقارات")
    if q.bedrooms_min:
        ar.append(f"من {q.bedrooms_min} غرف نوم أو أكثر")
    if q.furnished:
        ar.append(_FURN_AR[q.furnished])
    if q.transaction == TransactionType.rent:
        en.append("for rent")
        ar.append("للإيجار")
    elif q.transaction == TransactionType.sale:
        en.append("for sale")
        ar.append("للبيع")
    if q.location:
        en.append(f"in {q.location.name_en}")
        ar.append(f"في {q.location.name_ar}")
    if q.price_min and q.price_max:
        en.append(f"between {_usd(q.price_min)} and {_usd(q.price_max)}")
        ar.append(f"بين {_usd(q.price_min)} و{_usd(q.price_max)}")
    elif q.price_max:
        en.append(f"up to {_usd(q.price_max)}")
        ar.append(f"حتى {_usd(q.price_max)}")
    elif q.price_min:
        en.append(f"from {_usd(q.price_min)}")
        ar.append(f"ابتداءً من {_usd(q.price_min)}")
    if q.preferences:
        en.append("· prefers " + ", ".join(p.label_en.lower() for p in q.preferences))
        ar.append("· يفضّل " + "، ".join(p.label_ar for p in q.preferences))
    sentence = " ".join(w for w in en if w).strip()
    # Upper-case only the first letter: str.capitalize() would also lower-case place names.
    return sentence[:1].upper() + sentence[1:], " ".join(w for w in ar if w).strip()


def filter_reasons(q: ParsedQuery) -> list[Reason]:
    """Hard constraints every result satisfies (they were applied as filters)."""
    out: list[Reason] = []
    if q.location:
        out.append(Reason("location", q.location.name_en, q.location.name_ar, "match", "filter"))
    if q.price_max:
        out.append(
            Reason("budget", f"Within {_usd(q.price_max)}", f"ضمن {_usd(q.price_max)}", "match", "filter")
        )
    if q.bedrooms_min:
        out.append(
            Reason("bedrooms", f"{q.bedrooms_min}+ bedrooms", f"{q.bedrooms_min}+ غرف نوم", "match", "filter")
        )
    if q.furnished:
        out.append(
            Reason("furnished", _FURN_EN[q.furnished].capitalize(), _FURN_AR[q.furnished], "match", "filter")
        )
    return out


# ---------- engine ----------


class SmartSearch:
    def __init__(
        self,
        session: AsyncSession,
        *,
        listings: ListingService,
        areas: AreaProfileService,
        timer: Callable[[], float] = time.perf_counter,
    ) -> None:
        self._session = session
        self._listings = listings
        self._areas = areas
        self._timer = timer

    async def ask(
        self, query: str, locale: str, user_id: uuid.UUID | None = None, log: bool = True
    ) -> AskResult:
        started = self._timer()
        snapshot = await self._listings.locations.snapshot()
        parser = QueryParser(snapshot)
        q = parser.parse(query)
        criteria = SearchCriteria(
            transaction_type=q.transaction,
            price_min=q.price_min,
            price_max=q.price_max,
            bedrooms_min=q.bedrooms_min if q.bedrooms_min else None,
            bathrooms_min=q.bathrooms_min,
            furnished=q.furnished,
            property_type=q.property_type,
            sort=q.sort,
            page=1,
            page_size=CANDIDATE_POOL,
        )
        location_slug = q.location.slug if q.location else None
        items, total = await self._listings.search(criteria, location_slug)
        relaxed: list[Relaxation] = []
        if total == 0 and q.has_hard_constraints:
            items, total, criteria, location_slug, relaxed = await self._relax(q, criteria, location_slug)
        # Reasons describe the filters actually applied (after any relaxation), never the original wish.
        applied = replace(
            q,
            price_max=criteria.price_max,
            bedrooms_min=criteria.bedrooms_min if q.bedrooms_min else q.bedrooms_min,
            location=snapshot.by_slug.get(location_slug) if location_slug else None,
        )

        areas = await self._areas.for_locations(x.property.location_id for x in items)
        hits = [self._score(applied, x, areas.get(x.property.location_id)) for x in items]
        # Stable sort keeps the SQL order (newest / price) as the tie-breaker.
        hits.sort(key=lambda h: -h.score)

        clar_en = clar_ar = None
        if q.is_empty or (not q.has_hard_constraints and total > MAX_RESULTS):
            clar_en = (
                "Which area and what monthly budget? For example: “2 bedrooms in Achrafieh under $1,200”."
            )
            clar_ar = "أي منطقة وما الميزانية الشهرية؟ مثلاً: «غرفتا نوم في الأشرفية حتى 1,200$»."
        summary_en, summary_ar = summarize(q)
        result = AskResult(
            q, summary_en, summary_ar, clar_en, clar_ar, relaxed, hits[:MAX_RESULTS], total, criteria
        )
        if log:
            entry = SearchQuery(
                query=query[:300],
                locale=locale,
                parsed={**q.as_log(), "relaxed": [r.key for r in relaxed]},
                result_count=total,
                clarification=clar_en is not None,
                latency_ms=round((self._timer() - started) * 1000),
                user_id=user_id,
            )
            self._session.add(entry)
            await self._session.commit()
            result.query_id = entry.id
        return result

    async def _relax(
        self, q: ParsedQuery, criteria: SearchCriteria, location_slug: str | None
    ) -> tuple[list[Listing], int, SearchCriteria, str | None, list[Relaxation]]:
        """Loosen one constraint at a time until something matches; report exactly what was loosened."""
        relaxed: list[Relaxation] = []
        steps: list[tuple[Relaxation, SearchCriteria, str | None]] = []
        if criteria.price_max:
            new_max = round(criteria.price_max * RELAX_BUDGET_FACTOR)
            criteria = replace(criteria, price_max=new_max)
            steps.append(
                (
                    Relaxation(
                        "budget", f"Budget raised to {_usd(new_max)}", f"رفعنا الميزانية إلى {_usd(new_max)}"
                    ),
                    criteria,
                    location_slug,
                )
            )
        if q.location and q.location.parent_id:
            parent = (await self._listings.locations.snapshot()).by_id.get(q.location.parent_id)
            if parent is not None:
                location_slug = parent.slug
                steps.append(
                    (
                        Relaxation(
                            "location", f"Widened to {parent.name_en}", f"وسّعنا البحث إلى {parent.name_ar}"
                        ),
                        criteria,
                        location_slug,
                    )
                )
        if criteria.bedrooms_min and criteria.bedrooms_min > 1:
            criteria = replace(criteria, bedrooms_min=criteria.bedrooms_min - 1)
            steps.append(
                (
                    Relaxation(
                        "bedrooms",
                        f"Also {criteria.bedrooms_min} bedrooms",
                        f"شملنا {criteria.bedrooms_min} غرف نوم",
                    ),
                    criteria,
                    location_slug,
                )
            )
        for relaxation, step_criteria, step_slug in steps:
            relaxed.append(relaxation)
            items, total = await self._listings.search(step_criteria, step_slug)
            if total:
                return items, total, step_criteria, step_slug, relaxed
        return [], 0, criteria, location_slug, relaxed

    @staticmethod
    def _score(q: ParsedQuery, listing: Listing, area: AreaProfile | None) -> Hit:
        reasons = filter_reasons(q)
        score = 0
        for pref in q.preferences:
            status = _check(pref, listing, area, q)
            score += {Status.match: 2, Status.unknown: 0, Status.miss: -1}[status]
            source: Literal["listing", "area"] = "area" if pref.source == "area" else "listing"
            label_en, label_ar = pref.label_en, pref.label_ar
            if pref.key == "parking" and q.parking_spots and q.parking_spots > 1:
                label_en, label_ar = f"Parking for {q.parking_spots} cars", f"موقف لـ{q.parking_spots} سيارات"
            reasons.append(Reason(pref.key, label_en, label_ar, status.value, source))
        return Hit(listing=listing, area=area, score=score, reasons=reasons)


def _check(pref: Preference, listing: Listing, area: AreaProfile | None, q: ParsedQuery) -> Status:
    if pref.key == "parking":
        return _parking(listing, area, q.parking_spots or 1)
    return pref.check(listing, area)

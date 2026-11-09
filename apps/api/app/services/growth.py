"""Growth dashboard: Alex Hormozi's value equation and marketing playbook, measured on 2ajar's own data.

Everything here is computed from stored facts (listings, events, leads, logged searches). Nothing is
estimated: when there isn't enough data, a metric is ``None`` and the UI says "not enough data yet".

The value equation (from *$100M Offers*):

    value = (dream outcome x perceived likelihood) / (time delay x effort & sacrifice)

Each factor is mapped to a measurable proxy (0..1) for each side of the marketplace; the index is
``100 x D x L / (delay x effort)`` where ``delay`` and ``effort`` run from 1 (none) to 5 (worst). So 100
is the ceiling and every factor visibly drags the score down.
"""

import uuid
from collections import Counter
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta
from statistics import median
from typing import Any, Literal

from sqlalchemy import distinct, func, or_, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.authz.policies import Principal
from app.core.config import Settings
from app.core.errors import NotFound
from app.core.security import utcnow
from app.models import (
    AreaProfile,
    GrowthTask,
    Lead,
    Listing,
    ListingEvent,
    ListingMedia,
    SearchQuery,
)
from app.models.enums import ListingEventType, ListingStatus
from app.repositories.listings import ListingSpecs
from app.repositories.locations import LocationDirectory, LocationSnapshot

Lever = Literal["dream", "likelihood", "time", "effort", "leads"]

# Targets from the growth plan (docs/2ajar-growth-plan-hormozi.pdf). Starting guesses, meant to be tuned.
TARGETS: dict[str, tuple[float, float]] = {  # metric -> (day 30, day 90)
    "live_listings": (150, 600),
    "active_publishers": (15, 80),
    "weekly_searches": (500, 5000),
    "conversion": (0.05, 0.08),
    "weekly_inquiries": (50, 400),
    "retention_60d": (0.7, 0.7),
}

# Which soft wishes a listing can actually answer, and how to tell (for "wishes vs data" coverage).
WISH_FIELDS: dict[str, Callable[[Any], bool]] = {
    "electricity_24_7": lambda p: p.electricity_supply is not None or "generator_24_7" in (p.amenities or []),
    "low_electricity_bill": lambda p: p.electricity_usd_month is not None,
    "solar": lambda p: p.solar_ready is not None or p.electricity_supply is not None,
    "water": lambda p: p.water_source is not None or p.water_usd_month is not None,
    "sewage": lambda p: p.sewage is not None,
    "elevator_backup": lambda p: p.elevator_backup is not None,
    "parking": lambda p: p.parking_spots is not None or "parking" in (p.amenities or []),
    "warm_winter": lambda p: p.winter_comfort is not None,
    "cool_summer": lambda p: p.summer_comfort is not None,
}
AREA_WISHES = {"quiet", "safe", "low_theft", "clean", "no_flooding"}


@dataclass(frozen=True)
class Factor:
    key: str
    score: float | None  # 0..1, higher is better for the customer (None = not enough data)
    value: str  # the measured number, preformatted (e.g. "62%", "18 h")
    metric: str  # what was measured (machine key; labels live in the UI)


@dataclass(frozen=True)
class Recommendation:
    key: str
    priority: int  # 1 = do this week
    lever: Lever
    channel: str | None  # Core Four channel, when it is a marketing action
    params: dict[str, Any]  # numbers / names the UI inserts into the localized text


PLAYBOOK: list[tuple[str, int, str | None, float | None]] = [
    # (key, phase 1/2/3, auto metric, target): phases = days 1-30 supply, 31-60 demand & proof, 61-90 multiply
    ("offer_defined", 1, None, None),
    ("warm_list_100", 1, None, None),
    ("daily_outreach", 1, None, None),
    ("area_facts_top10", 1, "areas_with_facts", 10),
    ("first_10_partners", 1, "active_publishers", 10),
    ("listings_100", 1, "live_listings", 100),
    ("demo_off", 1, "demo_off", 1),
    ("daily_content", 1, None, None),
    ("listings_150", 1, "live_listings", 150),
    ("partners_15", 1, "active_publishers", 15),
    ("lead_magnet", 2, None, None),
    ("affiliates", 2, None, None),
    ("monthly_report", 2, None, None),
    ("case_studies", 2, None, None),
    ("double_best_channel", 2, None, None),
    ("weekly_inquiries_50", 2, "weekly_inquiries", 50),
    ("referrals", 3, None, None),
    ("paid_ads", 3, None, None),
    ("expand_keserwan_baabda", 3, None, None),
    ("monetisation_test", 3, None, None),
    ("listings_600", 3, "live_listings", 600),
    ("weekly_inquiries_400", 3, "weekly_inquiries", 400),
]
PLAYBOOK_KEYS = {k for k, *_ in PLAYBOOK}


def _ratio(part: float, whole: float) -> float | None:
    return part / whole if whole else None


def _pct(x: float | None) -> str:
    return "–" if x is None else f"{round(x * 100)}%"


def _index(
    dream: float | None, likelihood: float | None, delay: float | None, effort: float | None
) -> float | None:
    if None in (dream, likelihood, delay, effort):
        return None
    return round(100 * dream * likelihood / (delay * effort), 1)  # type: ignore[operator]


class GrowthService:
    def __init__(
        self, session: AsyncSession, *, settings: Settings, clock: Callable[[], datetime] = utcnow
    ) -> None:
        self._session = session
        self._settings = settings
        self._now = clock()
        self._locations = LocationDirectory(session)

    # ---------- raw measurements ----------

    async def _scalar(self, stmt: Any) -> int:
        return int(await self._session.scalar(stmt) or 0)

    def _visible(self) -> Any:
        return ListingSpecs.publicly_visible(self._now, self._settings.demo_mode)

    async def _supply(self) -> dict[str, Any]:
        live = await self._session.scalars(select(Listing).join(Listing.property).where(self._visible()))
        listings = list(live.unique())
        photo_counts = (
            dict(
                (
                    await self._session.execute(
                        select(ListingMedia.listing_id, func.count())
                        .where(ListingMedia.listing_id.in_([x.id for x in listings]))
                        .group_by(ListingMedia.listing_id)
                    )
                ).all()
            )
            if listings
            else {}
        )
        fresh_after = self._now - timedelta(days=30)
        n = len(listings)
        props = [x.property for x in listings]
        bills = sum(
            1
            for p in props
            if (p.electricity_supply or p.electricity_usd_month is not None) and p.water_source
        )
        drafts = await self._scalar(
            select(func.count()).select_from(Listing).where(Listing.status == ListingStatus.draft)
        )
        published_ever = await self._scalar(
            select(func.count()).select_from(Listing).where(Listing.published_at.is_not(None))
        )
        return {
            "listings": listings,
            "live": n,
            "fresh": _ratio(
                sum(
                    1 for x in listings if (x.last_confirmed_at or x.published_at or self._now) >= fresh_after
                ),
                n,
            ),
            "photos3": _ratio(sum(1 for x in listings if photo_counts.get(x.id, 0) >= 3), n),
            "bills": _ratio(bills, n),
            "publishers": len({x.created_by_user_id for x in listings}),
            "draft_share": _ratio(drafts, drafts + published_ever),
            "demo_share": _ratio(sum(1 for x in listings if x.is_demo), n),
        }

    async def _area_coverage(
        self, listings: list[Listing], snap: LocationSnapshot
    ) -> tuple[float | None, set[uuid.UUID]]:
        stmt = select(AreaProfile.location_id).where(
            or_(AreaProfile.safety_score.is_not(None), AreaProfile.quiet_score.is_not(None))
        )
        if not self._settings.demo_mode:
            stmt = stmt.where(AreaProfile.is_demo.is_(False))
        with_facts = set((await self._session.scalars(stmt)).all())

        def covered(location_id: uuid.UUID) -> bool:
            current = snap.by_id.get(location_id)
            while current is not None:
                if current.id in with_facts:
                    return True
                current = snap.by_id.get(current.parent_id) if current.parent_id else None
            return False

        return _ratio(sum(1 for x in listings if covered(x.property.location_id)), len(listings)), with_facts

    async def _demand(self, days: int) -> dict[str, Any]:
        since = self._now - timedelta(days=days)
        searches = list(
            (
                await self._session.execute(
                    select(SearchQuery.result_count, SearchQuery.clarification, SearchQuery.parsed).where(
                        SearchQuery.created_at > since
                    )
                )
            ).all()
        )
        n = len(searches)
        views = await self._scalar(
            select(
                func.count(distinct(func.concat(ListingEvent.listing_id, ListingEvent.session_hash)))
            ).where(ListingEvent.event_type == ListingEventType.view, ListingEvent.created_at > since)
        )
        visitors = await self._scalar(
            select(func.count(distinct(ListingEvent.session_hash))).where(
                ListingEvent.event_type == ListingEventType.view, ListingEvent.created_at > since
            )
        )
        clicks = await self._scalar(
            select(func.count())
            .select_from(ListingEvent)
            .where(
                ListingEvent.event_type == ListingEventType.whatsapp_click, ListingEvent.created_at > since
            )
        )
        leads = await self._scalar(select(func.count()).select_from(Lead).where(Lead.created_at > since))
        return {
            "searches": n,
            "zero_rate": _ratio(sum(1 for r, _, _ in searches if r == 0), n),
            "clarify_rate": _ratio(sum(1 for _, c, _ in searches if c), n),
            "relaxed_rate": _ratio(sum(1 for _, _, p in searches if (p or {}).get("relaxed")), n),
            "parsed": [(r, p or {}) for r, _, p in searches],
            "views": views,
            "visitors": visitors,
            "clicks": clicks,
            "leads": leads,
            "inquiries": clicks + leads,
            "conversion": _ratio(clicks + leads, views),
        }

    async def _first_contact_hours(self) -> float | None:
        """Median hours from publishing to the first inquiry, for listings published in the last 60 days."""
        since = self._now - timedelta(days=60)
        first_event = (
            select(ListingEvent.listing_id, func.min(ListingEvent.created_at).label("at"))
            .where(ListingEvent.event_type.in_([ListingEventType.whatsapp_click, ListingEventType.lead]))
            .group_by(ListingEvent.listing_id)
            .subquery()
        )
        first_lead = (
            select(Lead.listing_id, func.min(Lead.created_at).label("at"))
            .group_by(Lead.listing_id)
            .subquery()
        )
        rows = (
            await self._session.execute(
                select(Listing.published_at, func.least(first_event.c.at, first_lead.c.at))
                .outerjoin(first_event, first_event.c.listing_id == Listing.id)
                .outerjoin(first_lead, first_lead.c.listing_id == Listing.id)
                .where(
                    Listing.published_at > since,
                    or_(first_event.c.at.is_not(None), first_lead.c.at.is_not(None)),
                )
            )
        ).all()
        hours = [max(0.0, (at - pub).total_seconds() / 3600) for pub, at in rows if pub and at]
        return round(median(hours), 1) if hours else None

    async def _contacted_share(self, listings: list[Listing]) -> float | None:
        if not listings:
            return None
        since = self._now - timedelta(days=30)
        ids = [x.id for x in listings]
        contacted = set(
            (
                await self._session.scalars(
                    select(ListingEvent.listing_id).where(
                        ListingEvent.listing_id.in_(ids),
                        ListingEvent.event_type == ListingEventType.whatsapp_click,
                        ListingEvent.created_at > since,
                    )
                )
            ).all()
        ) | set(
            (
                await self._session.scalars(
                    select(Lead.listing_id).where(Lead.listing_id.in_(ids), Lead.created_at > since)
                )
            ).all()
        )
        return len(contacted) / len(listings)

    async def _retention(self) -> float | None:
        """Of people who published 60+ days ago, the share with a live listing confirmed in the last 30."""
        cutoff = self._now - timedelta(days=60)
        cohort = set(
            (
                await self._session.scalars(
                    select(Listing.created_by_user_id).distinct().where(Listing.published_at < cutoff)
                )
            ).all()
        )
        if not cohort:
            return None
        active = set(
            (
                await self._session.scalars(
                    select(Listing.created_by_user_id)
                    .distinct()
                    .where(self._visible(), Listing.last_confirmed_at > self._now - timedelta(days=30))
                )
            ).all()
        )
        return len(cohort & active) / len(cohort)

    async def _quiet_listings(self, listings: list[Listing]) -> list[dict[str, Any]]:
        """Most-viewed live listings with no inquiry in 30 days: owners to call."""
        since = self._now - timedelta(days=30)
        ids = [x.id for x in listings]
        if not ids:
            return []
        views = func.count(distinct(ListingEvent.session_hash))
        rows = (
            await self._session.execute(
                select(ListingEvent.listing_id, views)
                .where(
                    ListingEvent.listing_id.in_(ids),
                    ListingEvent.event_type == ListingEventType.view,
                    ListingEvent.created_at > since,
                )
                .group_by(ListingEvent.listing_id)
                .having(views >= 5)
                .order_by(views.desc())
                .limit(20)
            )
        ).all()
        contacted = set(
            (
                await self._session.scalars(
                    select(ListingEvent.listing_id).where(
                        ListingEvent.listing_id.in_([r[0] for r in rows]),
                        ListingEvent.event_type.in_([ListingEventType.whatsapp_click, ListingEventType.lead]),
                        ListingEvent.created_at > since,
                    )
                )
            ).all()
        )
        by_id = {x.id: x for x in listings}
        return [
            {"id": str(i), "title": by_id[i].title_en or by_id[i].title_ar or "", "visitors": int(v)}
            for i, v in rows
            if i not in contacted and i in by_id
        ][:5]

    # ---------- the dashboard ----------

    async def dashboard(self) -> dict[str, Any]:
        snap = await self._locations.snapshot()
        supply = await self._supply()
        listings: list[Listing] = supply["listings"]
        area_cov, with_facts = await self._area_coverage(listings, snap)
        week = await self._demand(7)
        month = await self._demand(30)
        first_contact = await self._first_contact_hours()
        contacted = await self._contacted_share(listings)
        retention = await self._retention()

        # --- value equation, renters ---
        likelihood_parts = [x for x in (supply["fresh"], supply["photos3"], area_cov) if x is not None]
        r_dream = supply["bills"]
        r_like = sum(likelihood_parts) / len(likelihood_parts) if likelihood_parts else None
        r_delay = None if month["zero_rate"] is None else 1 + 4 * month["zero_rate"]
        r_effort = None if month["clarify_rate"] is None else 1 + 4 * month["clarify_rate"]
        renters: dict[str, Any] = {
            "index": _index(r_dream, r_like, r_delay, r_effort),
            "factors": [
                Factor("dream", r_dream, _pct(r_dream), "bills_reported"),
                Factor("likelihood", r_like, _pct(r_like), "fresh_photos_areafacts"),
                Factor(
                    "time",
                    None if r_delay is None else 1 - month["zero_rate"],
                    _pct(month["zero_rate"]),
                    "zero_result_searches",
                ),
                Factor(
                    "effort",
                    None if r_effort is None else 1 - month["clarify_rate"],
                    _pct(month["clarify_rate"]),
                    "needed_clarification",
                ),
            ],
        }
        # --- value equation, owners & brokers ---
        per_listing_week = _ratio(week["inquiries"], supply["live"])
        o_dream = (
            None if per_listing_week is None else min(1.0, per_listing_week)
        )  # target: 1 inquiry / listing / week
        o_delay = None if first_contact is None else 1 + min(first_contact / 72, 4)
        o_effort = None if supply["draft_share"] is None else 1 + 4 * supply["draft_share"]
        owners: dict[str, Any] = {
            "index": _index(o_dream, contacted, o_delay, o_effort),
            "factors": [
                Factor(
                    "dream",
                    o_dream,
                    "–" if per_listing_week is None else f"{per_listing_week:.2f}",
                    "inquiries_per_listing_week",
                ),
                Factor("likelihood", contacted, _pct(contacted), "listings_contacted_30d"),
                Factor(
                    "time",
                    None if first_contact is None else max(0.0, 1 - first_contact / 288),
                    "–" if first_contact is None else f"{first_contact:g} h",
                    "hours_to_first_inquiry",
                ),
                Factor(
                    "effort",
                    None if o_effort is None else 1 - supply["draft_share"],
                    _pct(supply["draft_share"]),
                    "drafts_never_published",
                ),
            ],
        }

        # --- supply gaps: what people ask for vs what we have ---
        area_searches: Counter[str] = Counter()
        area_zero: Counter[str] = Counter()
        wishes: Counter[str] = Counter()
        types: Counter[str] = Counter()
        for result_count, parsed in month["parsed"]:
            if parsed.get("location"):
                area_searches[parsed["location"]] += 1
                if result_count == 0:
                    area_zero[parsed["location"]] += 1
            for key in parsed.get("preferences") or []:
                wishes[key] += 1
            if parsed.get("property_type"):
                types[str(parsed["property_type"])] += 1
        live_by_loc: Counter[uuid.UUID] = Counter(x.property.location_id for x in listings)

        def live_in(slug: str) -> int:
            rec = snap.by_slug.get(slug)
            if rec is None:
                return 0
            return sum(
                n
                for loc_id, n in live_by_loc.items()
                if (r := snap.by_id.get(loc_id)) and (r.path == rec.path or r.path.startswith(rec.path + "/"))
            )

        gaps: list[dict[str, Any]] = []
        for slug, count in area_searches.most_common(15):
            rec = snap.by_slug.get(slug)
            if rec is None:
                continue
            gaps.append(
                {
                    "slug": slug,
                    "name_en": rec.name_en,
                    "name_ar": rec.name_ar,
                    "searches": count,
                    "zero_results": area_zero[slug],
                    "live_listings": live_in(slug),
                    "has_area_facts": rec.id in with_facts,
                }
            )
        gaps.sort(key=lambda g: (-(g["zero_results"] / g["searches"]), -g["searches"]))
        props = [x.property for x in listings]
        wish_rows = []
        for key, count in wishes.most_common(12):
            if key in WISH_FIELDS:
                coverage = _ratio(sum(1 for p in props if WISH_FIELDS[key](p)), len(props))
            elif key in AREA_WISHES:
                coverage = area_cov
            else:  # amenity wishes (sea view, pool...) are always answerable from amenities
                coverage = None
            wish_rows.append({"key": key, "searches": count, "data_coverage": coverage})

        metrics = {
            "live_listings": supply["live"],
            "fresh_share": supply["fresh"],
            "photos3_share": supply["photos3"],
            "bills_share": supply["bills"],
            "area_facts_share": area_cov,
            "areas_with_facts": len(with_facts),
            "active_publishers": supply["publishers"],
            "demo_share": supply["demo_share"],
            "weekly_searches": week["searches"],
            "weekly_visitors": week["visitors"],
            "weekly_views": week["views"],
            "weekly_whatsapp": week["clicks"],
            "weekly_leads": week["leads"],
            "weekly_inquiries": week["inquiries"],
            "conversion": week["conversion"],
            "zero_result_rate": month["zero_rate"],
            "clarification_rate": month["clarify_rate"],
            "relaxed_rate": month["relaxed_rate"],
            "hours_to_first_inquiry": first_contact,
            "listings_contacted_30d": contacted,
            "retention_60d": retention,
            "demo_off": 0 if self._settings.demo_mode else 1,
        }
        quiet = await self._quiet_listings(listings)
        return {
            "generated_at": self._now.isoformat(),
            "demo_mode": self._settings.demo_mode,
            "metrics": metrics,
            "targets": {k: {"day30": a, "day90": b} for k, (a, b) in TARGETS.items()},
            "renters": {"index": renters["index"], "factors": [f.__dict__ for f in renters["factors"]]},
            "owners": {"index": owners["index"], "factors": [f.__dict__ for f in owners["factors"]]},
            "funnel": {
                "searches": week["searches"],
                "visitors": week["visitors"],
                "views": week["views"],
                "inquiries": week["inquiries"],
            },
            "area_gaps": gaps[:10],
            "wishes": wish_rows,
            "property_types": [{"key": k, "searches": n} for k, n in types.most_common(6)],
            "quiet_listings": quiet,
            "recommendations": [r.__dict__ for r in self._recommend(metrics, gaps, wish_rows, quiet)],
            "playbook": await self._playbook(metrics),
        }

    # ---------- next steps (rules over the measurements) ----------

    @staticmethod
    def _recommend(
        m: dict[str, Any],
        gaps: list[dict[str, Any]],
        wishes: list[dict[str, Any]],
        quiet: list[dict[str, Any]],
    ) -> list[Recommendation]:
        out: list[Recommendation] = []
        weak_areas = [g for g in gaps if g["zero_results"] or g["live_listings"] < 5][:5]
        if m["live_listings"] < 300:
            out.append(
                Recommendation(
                    "supply_sprint",
                    1,
                    "leads",
                    "warm_cold_outreach",
                    {
                        "live": m["live_listings"],
                        "missing": 300 - m["live_listings"],
                        "areas_en": ", ".join(g["name_en"] for g in weak_areas),
                        "areas_ar": "، ".join(g["name_ar"] for g in weak_areas),
                    },
                )
            )
        if m["demo_off"] == 0:
            out.append(
                Recommendation("go_live", 1, "likelihood", None, {"demo_share": _pct(m["demo_share"])})
            )
        if m["zero_result_rate"] is not None and m["zero_result_rate"] > 0.2:
            out.append(
                Recommendation(
                    "fill_zero_results",
                    1,
                    "time",
                    "cold_outreach",
                    {
                        "rate": _pct(m["zero_result_rate"]),
                        "areas_en": ", ".join(g["name_en"] for g in weak_areas),
                        "areas_ar": "، ".join(g["name_ar"] for g in weak_areas),
                    },
                )
            )
        if m["bills_share"] is not None and m["bills_share"] < 0.6:
            out.append(Recommendation("ask_bills", 1, "dream", None, {"share": _pct(m["bills_share"])}))
        missing_facts = [g for g in gaps if not g["has_area_facts"]][:5]
        if (m["area_facts_share"] is not None and m["area_facts_share"] < 0.7) or missing_facts:
            out.append(
                Recommendation(
                    "enter_area_facts",
                    2,
                    "likelihood",
                    None,
                    {
                        "share": _pct(m["area_facts_share"]),
                        "areas_en": ", ".join(g["name_en"] for g in missing_facts),
                        "areas_ar": "، ".join(g["name_ar"] for g in missing_facts),
                    },
                )
            )
        if m["fresh_share"] is not None and m["fresh_share"] < 0.8:
            out.append(
                Recommendation("confirm_reminders", 2, "likelihood", None, {"share": _pct(m["fresh_share"])})
            )
        if m["photos3_share"] is not None and m["photos3_share"] < 0.7:
            out.append(
                Recommendation("more_photos", 2, "likelihood", None, {"share": _pct(m["photos3_share"])})
            )
        thin = [w for w in wishes if w["data_coverage"] is not None and w["data_coverage"] < 0.5][:3]
        if thin:
            out.append(
                Recommendation("answer_top_wishes", 2, "dream", None, {"wishes": [w["key"] for w in thin]})
            )
        if quiet:
            out.append(
                Recommendation("call_quiet_listings", 2, "likelihood", "warm_outreach", {"count": len(quiet)})
            )
        if m["conversion"] is not None and m["weekly_views"] >= 50 and m["conversion"] < 0.03:
            out.append(
                Recommendation("improve_conversion", 2, "likelihood", None, {"rate": _pct(m["conversion"])})
            )
        if m["weekly_searches"] < 500:
            out.append(
                Recommendation("start_content", 2, "leads", "content", {"searches": m["weekly_searches"]})
            )
        if m["clarification_rate"] is not None and m["clarification_rate"] > 0.3:
            out.append(
                Recommendation("better_prompts", 3, "effort", None, {"rate": _pct(m["clarification_rate"])})
            )
        if m["hours_to_first_inquiry"] is not None and m["hours_to_first_inquiry"] > 72:
            out.append(
                Recommendation(
                    "feature_new_listings", 3, "time", None, {"hours": m["hours_to_first_inquiry"]}
                )
            )
        if m["weekly_inquiries"] >= 50 and m["live_listings"] >= 150:
            out.append(
                Recommendation("start_paid_ads", 3, "leads", "paid_ads", {"inquiries": m["weekly_inquiries"]})
            )
        if m["retention_60d"] is not None and m["retention_60d"] < 0.7:
            out.append(
                Recommendation(
                    "win_back_publishers",
                    2,
                    "likelihood",
                    "warm_outreach",
                    {"rate": _pct(m["retention_60d"])},
                )
            )
        return sorted(out, key=lambda r: r.priority)

    # ---------- the 90-day playbook ----------

    async def _playbook(self, m: dict[str, Any]) -> list[dict[str, Any]]:
        done = {t.key: t for t in (await self._session.scalars(select(GrowthTask))).all()}
        items = []
        for key, phase, metric, target in PLAYBOOK:
            current = m.get(metric) if metric else None
            auto_done = (
                metric is not None and current is not None and target is not None and current >= target
            )
            items.append(
                {
                    "key": key,
                    "phase": phase,
                    "metric": metric,
                    "target": target,
                    "current": current,
                    "progress": None if current is None or not target else min(1.0, float(current) / target),
                    "done": auto_done or bool(done.get(key) and done[key].done),
                    "auto": metric is not None,
                }
            )
        return items

    async def set_task(self, p: Principal, key: str, done: bool) -> None:
        if key not in PLAYBOOK_KEYS:
            raise NotFound("Unknown playbook step")
        stmt = insert(GrowthTask).values(
            key=key, done=done, updated_by_user_id=p.user_id, updated_at=self._now
        )
        await self._session.execute(
            stmt.on_conflict_do_update(
                index_elements=[GrowthTask.key],
                set_={"done": done, "updated_by_user_id": p.user_id, "updated_at": self._now},
            )
        )
        await self._session.commit()

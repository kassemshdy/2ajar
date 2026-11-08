"""Query-understanding corpus: English, Arabic and Arabizi phrasings people actually type in Lebanon.

Each case lists only the fields it asserts; anything not listed must stay unset (no invented constraints).
"""

from typing import Any

import pytest

from app.db.session import get_sessionmaker
from app.models.enums import Furnished, PropertyType, Stay
from app.repositories.locations import LocationDirectory
from app.search.parser import ParsedQuery, QueryParser
from app.search.suggestions import SUGGESTIONS
from app.search.text import consume_phrase, contains_phrase, is_arabic, normalize

CHECKED = (
    "stay",
    "guests_min",
    "sale_requested",
    "property_type",
    "location",
    "price_min",
    "price_max",
    "bedrooms_min",
    "furnished",
)

CORPUS: list[tuple[str, dict[str, Any], set[str]]] = [
    # (query, expected hard fields, expected preference keys)
    (
        "Furnished 2 bedroom in Hamra under $1,000 with 24/7 electricity",
        {
            "location": "hamra",
            "price_max": 1000,
            "bedrooms_min": 2,
            "furnished": Furnished.furnished,
        },
        {"electricity_24_7"},
    ),
    (
        "شقة بغرفتين بالحمرا مفروشة حتى ١٠٠٠ دولار مع مولد",
        {
            "property_type": PropertyType.apartment,
            "location": "hamra",
            "price_max": 1000,
            "bedrooms_min": 2,
            "furnished": Furnished.furnished,
        },
        {"electricity_24_7"},
    ),
    (
        "bade chi 2 ghoraf bl achrafieh ma3 moteur ta7et 800",
        {"location": "achrafieh", "price_max": 800, "bedrooms_min": 2},
        {"electricity_24_7"},
    ),
    (
        "studio in Mar Mikhael for rent",
        {
            "property_type": PropertyType.studio,
            "location": "mar-mikhael",
            "bedrooms_min": 0,
        },
        set(),
    ),
    (
        "3 bedroom apartment for sale in Ras Beirut between 200k and 350k",
        {
            "sale_requested": True,
            "property_type": PropertyType.apartment,
            "location": "ras-beirut",
            "price_min": 200_000,
            "price_max": 350_000,
            "bedrooms_min": 3,
        },
        set(),
    ),
    (
        "quiet place, no dogs barking behind, safe with few thefts",
        {},
        {"quiet", "safe", "low_theft"},
    ),
    (
        "I hate the dogs noise behind my building",
        {},
        {"quiet"},
    ),
    (
        "villa with pool and garden in Keserwan",
        {"property_type": PropertyType.villa, "location": "keserwan"},
        {"pool", "garden"},
    ),
    (
        "بيت مع حديقة ويسمح بالحيوانات في كسروان",
        {"property_type": PropertyType.house, "location": "keserwan"},
        {"garden", "pets"},
    ),
    (
        "شقة مطلة على البحر للبيع في بيروت",
        {"sale_requested": True, "property_type": PropertyType.apartment, "location": "beirut"},
        {"sea_view"},
    ),
    (
        "cheap unfurnished apartment in Baabda, solar ready, low electricity bill, municipal water",
        {"property_type": PropertyType.apartment, "location": "baabda", "furnished": Furnished.unfurnished},
        {"solar", "low_electricity_bill", "water"},
    ),
    ("warm in winter and cool in summer, Jounieh", {"location": "jounieh"}, {"warm_winter", "cool_summer"}),
    ("elevator with backup and public sewage", {}, {"elevator_backup", "sewage"}),
    ("clean area that doesn't flood", {}, {"clean", "no_flooding"}),
    ("parking for 2 cars in Achrafieh", {"location": "achrafieh"}, {"parking"}),
    (
        "شقة 3 غرف نوم في بعبدا هادئة وآمنة مع موقفين",
        {"property_type": PropertyType.apartment, "location": "baabda", "bedrooms_min": 3},
        {"quiet", "safe", "parking"},
    ),
    ("1500$ max", {"price_max": 1500}, set()),
    ("under 1.2k", {"price_max": 1200}, set()),
    ("hello", {}, set()),
    # Rentals of any length: hours → nights → months/years
    (
        "Chalet in Faraya for the weekend for 6 guests under $250 a night",
        {
            "stay": Stay.nights,
            "guests_min": 6,
            "property_type": PropertyType.chalet,
            "location": "faraya",
            "price_max": 250,
        },
        set(),
    ),
    (
        "شاليه مع مسبح خاص في الجية بالساعة لـ10 أشخاص",
        {"stay": Stay.hours, "guests_min": 10, "property_type": PropertyType.chalet, "location": "jiyeh"},
        {"pool"},
    ),
    ("3 nights in Batroun", {"stay": Stay.nights, "location": "batroun"}, set()),
    ("for 2 hours in jbeil", {"stay": Stay.hours, "location": "byblos"}, set()),
    (
        "apartment in hamra for 6 months",
        {"stay": Stay.months, "property_type": PropertyType.apartment, "location": "hamra"},
        set(),
    ),
    ("yearly lease in Verdun", {"stay": Stay.months, "location": "verdun"}, set()),
    ("ويكند بكفرذبيان", {"stay": Stay.nights, "location": "kfardebian"}, set()),
    # Not stay lengths
    ("quiet at night in Hamra", {"location": "hamra"}, {"quiet"}),
    ("24 hour electricity", {}, {"electricity_24_7"}),
]


@pytest.fixture
async def parser() -> QueryParser:
    async with get_sessionmaker()() as session:
        return QueryParser(await LocationDirectory(session).snapshot())


def _actual(q: ParsedQuery) -> dict[str, Any]:
    log = q.as_log()
    return {k: log[k] for k in CHECKED if log[k] is not None and log[k] is not False}


@pytest.mark.parametrize(("query", "hard", "prefs"), CORPUS, ids=[c[0][:40] for c in CORPUS])
async def test_corpus(parser: QueryParser, query: str, hard: dict[str, Any], prefs: set[str]) -> None:
    q = parser.parse(query)
    assert _actual(q) == hard
    assert {p.key for p in q.preferences} == prefs


async def test_parking_spots_and_flags(parser: QueryParser) -> None:
    assert parser.parse("parking for 2 cars").parking_spots == 2
    assert parser.parse("مع موقفين").parking_spots == 2
    assert parser.parse("2 parking spots").parking_spots == 2
    assert parser.parse("with parking").parking_spots is None
    q = parser.parse("hello")
    assert q.is_empty and not q.has_hard_constraints
    assert parser.parse("cheapest in hamra").sort == "price_asc"
    assert parser.parse("luxury flat in achrafieh").sort == "price_desc"
    assert parser.parse("شقة في الحمرا").language == "ar"


async def test_24_7_is_not_a_budget(parser: QueryParser) -> None:
    q = parser.parse("24/7 electricity 2 bedroom hamra")
    assert q.price_max is None and q.price_min is None and q.bedrooms_min == 2


async def test_most_specific_location_wins(parser: QueryParser) -> None:
    assert parser.parse("ras beirut").location.slug == "ras-beirut"  # type: ignore[union-attr]
    assert parser.parse("Beirut, Hamra").location.slug == "hamra"  # type: ignore[union-attr]


async def test_every_suggestion_parses_to_constraints(parser: QueryParser) -> None:
    for s in SUGGESTIONS:
        for text in (s.text_en, s.text_ar):
            q = parser.parse(text)
            assert q.location is not None, text
            assert q.preferences or q.stay or q.property_type, text


def test_text_helpers() -> None:
    assert normalize("  Achrafiéh,  ٢ غرف!! ") == "achrafieh 2 غرف"
    assert normalize("على آمنة") == "علي امنه"
    text = " " + normalize("شقة بالحمرا") + " "
    assert contains_phrase(text, "الحمرا") and contains_phrase(text, "حمرا")
    assert consume_phrase(text, "الحمرا").strip() == "شقه"
    assert consume_phrase(text, "missing") == text
    assert is_arabic("مرحبا") and not is_arabic("hello")


async def test_summaries_cover_all_constraints(parser: QueryParser) -> None:
    from app.search.engine import summarize

    en, ar = summarize(parser.parse("semi furnished villa monthly in Baabda between 3000 and 5000$"))
    assert en == "Semi-furnished villas by the month or year in Baabda between $3,000 and $5,000"
    assert "فلل" in ar and "بالشهر" in ar and "بين" in ar
    en, ar = summarize(parser.parse("studio in hamra from $500"))
    assert en.startswith("Studio") and "to rent" in en and "from $500" in en and "ابتداءً" in ar
    en, ar = summarize(parser.parse("apartment with 2 bedrooms"))
    assert en == "2+ bedroom apartments to rent"
    en, ar = summarize(parser.parse("chalet for 8 guests by the hour"))
    assert en == "Chalets by the hour or day for 8+ guests" and "بالساعة" in ar and "لـ8" in ar
    en, _ = summarize(parser.parse("weekend getaway in Batroun"))
    assert en == "Homes for nights and weekends in Batroun"

"""Rule-based query understanding for Arabic, English and Arabizi.

Strategy: match the most specific things first and *consume* them (blank them out of the text) so later
rules cannot misread them, e.g. "24/7 electricity" must not become a $24 budget and "ras beirut" must not
also match "beirut".
"""

import re
from dataclasses import dataclass, field
from typing import Any, Literal

from app.models.enums import Furnished, PropertyType, Stay
from app.repositories.locations import LocationRecord, LocationSnapshot
from app.search import vocabulary as V
from app.search.preferences import PREFERENCES, Preference
from app.search.text import consume_phrase, contains_phrase, is_arabic, normalize

SortHint = Literal["newest", "price_asc", "price_desc"]
_GUESTS = re.compile(
    r"(?:for\s+)?(\d{1,3})\s*(?:guests?|people|persons?|pax|adults|visitors|ضيوف|ضيف|اشخاص|شخص|نفر|انفار|ashkhas)\b"
)
_COUNTED_STAY = (
    (Stay.hours, re.compile(r"\b\d{1,2}\s*(?:hours?|hrs?|ساعات|ساعه)\b(?!\s*(?:electricity|power|كهرباء))")),
    (Stay.nights, re.compile(r"\b\d{1,2}\s*(?:nights?|ليالي|ليال|ليله)\b")),
    (Stay.months, re.compile(r"\b\d{1,2}\s*(?:months?|years?|اشهر|شهور|سنوات|سنين)\b")),
)

_NUM = r"(\d+(?:[.,]\d+)?)\s*(k|الف|alf)?"
_CHEAP = ("cheap", "cheapest", "affordable", "budget friendly", "low price", "رخيص", "رخيصه", "ارخص", "rkhis")
_LUXURY = ("luxury", "luxurious", "high end", "premium", "فخم", "فخمه", "راقي")


@dataclass
class ParsedQuery:
    text: str
    language: Literal["en", "ar"]
    stay: Stay | None = None  # hours / nights / months
    guests_min: int | None = None
    sale_requested: bool = False  # 2ajar is rentals only; the answer says so
    property_type: PropertyType | None = None
    location: LocationRecord | None = None
    price_min: int | None = None
    price_max: int | None = None
    bedrooms_min: int | None = None
    bathrooms_min: int | None = None
    furnished: Furnished | None = None
    parking_spots: int | None = None
    preferences: list[Preference] = field(default_factory=list)
    sort: SortHint = "newest"

    @property
    def has_hard_constraints(self) -> bool:
        return any(
            v is not None
            for v in (
                self.location,
                self.price_min,
                self.price_max,
                self.bedrooms_min,
                self.property_type,
                self.stay,
                self.guests_min,
            )
        )

    @property
    def is_empty(self) -> bool:
        return not self.has_hard_constraints and not self.preferences and self.stay is None

    def as_log(self) -> dict[str, Any]:
        return {
            "stay": self.stay,
            "guests_min": self.guests_min,
            "sale_requested": self.sale_requested,
            "property_type": self.property_type,
            "location": self.location.slug if self.location else None,
            "price_min": self.price_min,
            "price_max": self.price_max,
            "bedrooms_min": self.bedrooms_min,
            "bathrooms_min": self.bathrooms_min,
            "furnished": self.furnished,
            "parking_spots": self.parking_spots,
            "preferences": [p.key for p in self.preferences],
            "sort": self.sort,
        }


def _to_int(number: str, thousands: str | None) -> int:
    value = (
        float(number.replace(",", ""))
        if number.count(",") and len(number.split(",")[-1]) == 3
        else float(number.replace(",", "."))
    )
    return round(value * 1000) if thousands else round(value)


class QueryParser:
    """Stateless parser bound to the (cached) location index."""

    def __init__(self, locations: LocationSnapshot) -> None:
        self._location_phrases = self._build_location_index(locations)

    @staticmethod
    def _build_location_index(snapshot: LocationSnapshot) -> list[tuple[str, LocationRecord]]:
        phrases: dict[str, LocationRecord] = {}
        for rec in snapshot.records:
            for phrase in (
                rec.name_en,
                rec.name_ar,
                rec.slug.replace("-", " "),
                *V.LOCATION_ALIASES.get(rec.slug, ()),
            ):
                key = normalize(phrase)
                if key and key not in phrases:
                    phrases[key] = rec
        # Longest first so "ras beirut" wins over "beirut".
        return sorted(phrases.items(), key=lambda kv: -len(kv[0]))

    def parse(self, raw: str) -> ParsedQuery:
        text = f" {normalize(raw)} "
        q = ParsedQuery(text=raw, language="ar" if is_arabic(raw) else "en")

        text = self._preferences(text, q)
        text = self._location(text, q)
        text = self._parking(text, q)
        text = self._stay_and_guests(text, q)
        text = self._rooms(text, q)
        text = self._prices(text, q)
        text = self._phrase_tables(text, q)
        return q

    # ---------- steps ----------

    @staticmethod
    def _consume(text: str, phrase: str) -> str:
        return consume_phrase(text, phrase)

    def _preferences(self, text: str, q: ParsedQuery) -> str:
        phrases = sorted(((p, pref) for pref in PREFERENCES for p in pref.phrases), key=lambda x: -len(x[0]))
        seen: set[str] = set()
        for phrase, pref in phrases:
            if contains_phrase(text, phrase):
                text = self._consume(text, phrase)
                if pref.key not in seen:
                    seen.add(pref.key)
                    q.preferences.append(pref)
        # "noise"/"noisy" anywhere (e.g. "dogs noise behind") means the person cares about quiet.
        if re.search(r"\b(noise|noisy|dogs barking|barking)\b|ضجه|ضجيج|نباح", text) and "quiet" not in seen:
            q.preferences.append(next(p for p in PREFERENCES if p.key == "quiet"))
        return text

    def _location(self, text: str, q: ParsedQuery) -> str:
        for phrase, rec in self._location_phrases:
            if contains_phrase(text, phrase):
                # Keep the most specific (deepest) location mentioned.
                if q.location is None or rec.path.count("/") > q.location.path.count("/"):
                    q.location = rec
                text = self._consume(text, phrase)
        return text

    def _parking(self, text: str, q: ParsedQuery) -> str:
        m = re.search(
            r"\b(\d)\s*(?:parking|parkings|car|cars|garages?|spots?|مواقف|موقف|سيارات|سيارتين)\b", text
        )
        if m:
            q.parking_spots = int(m.group(1))
            text = text.replace(m.group(0), " " * len(m.group(0)), 1)
        elif contains_phrase(text, "سيارتين") or contains_phrase(text, "موقفين"):
            q.parking_spots = 2
        if q.parking_spots and not any(p.key == "parking" for p in q.preferences):
            q.preferences.append(next(p for p in PREFERENCES if p.key == "parking"))
        return text

    def _stay_and_guests(self, text: str, q: ParsedQuery) -> str:
        m = _GUESTS.search(text)
        if m:
            q.guests_min = int(m.group(1))
            text = text.replace(m.group(0), " " * len(m.group(0)), 1)
        for stay, pattern in _COUNTED_STAY:
            m = pattern.search(text)
            if m:
                q.stay = stay
                text = text.replace(m.group(0), " " * len(m.group(0)), 1)
                break
        if q.stay is None:
            ranked = sorted(((p, s) for s, ps in V.STAYS.items() for p in ps), key=lambda x: -len(x[0]))
            q.stay = next((s for p, s in ranked if contains_phrase(text, p)), None)
        q.sale_requested = any(contains_phrase(text, w) for w in V.SALE_WORDS)
        return text

    def _rooms(self, text: str, q: ParsedQuery) -> str:
        if contains_phrase(text, "studio") or contains_phrase(text, "استوديو"):
            q.bedrooms_min = 0
        for phrase in V.SINGLE_ROOM:
            if contains_phrase(text, phrase):
                q.bedrooms_min, text = 1, self._consume(text, phrase)
        for phrase in V.DUAL_ROOMS:
            if contains_phrase(text, phrase):
                q.bedrooms_min, text = 2, self._consume(text, phrase)
        for phrase in V.DUAL_BATHS:
            if contains_phrase(text, phrase):
                q.bathrooms_min, text = 2, self._consume(text, phrase)
        number = r"(\d{1,2}|" + "|".join(map(re.escape, V.WORD_NUMBERS)) + r")"
        for words, attr in ((V.ROOM_WORDS, "bedrooms_min"), (V.BATH_WORDS, "bathrooms_min")):
            alternation = "|".join(map(re.escape, sorted(words, key=len, reverse=True)))
            m = re.search(rf"(?:^|\s){number}\s*-?\s*(?:{alternation})(?=\s|$)", text)
            if m:
                token = m.group(1)
                value = int(token) if token.isdigit() else V.WORD_NUMBERS[token]
                if 0 < value <= 20:
                    setattr(q, attr, value)
                    text = text.replace(m.group(0), " " * len(m.group(0)), 1)
        return text

    def _prices(self, text: str, q: ParsedQuery) -> str:
        cur = "|".join(map(re.escape, V.CURRENCY))
        money = rf"(?:\$\s*)?{_NUM}\s*(?:{cur})?"
        between = re.search(rf"(?:between|from|بين|من)\s+{money}\s+(?:and|to|-|و|الى|ل)\s+{money}", text)
        dash = re.search(rf"{money}\s*-\s*{money}", text)
        for m in (between, dash):
            if m:
                a, b = _to_int(m.group(1), m.group(2)), _to_int(m.group(3), m.group(4))
                q.price_min, q.price_max = min(a, b), max(a, b)
                return text.replace(m.group(0), " " * len(m.group(0)), 1)
        for markers, attr in ((V.MAX_MARKERS, "price_max"), (V.MIN_MARKERS, "price_min")):
            alternation = "|".join(map(re.escape, sorted(markers, key=len, reverse=True)))
            m = re.search(rf"(?:^|\s)(?:{alternation})\s*(?:of\s*)?{money}", text)
            if m:
                setattr(q, attr, _to_int(m.group(1), m.group(2)))
                text = text.replace(m.group(0), " " * len(m.group(0)), 1)
        if q.price_max is None and q.price_min is None:
            # A bare amount with a currency or "k" ("1200$", "$900", "1.5k") reads as the budget ceiling.
            m = re.search(rf"\$\s*{_NUM}|{_NUM}\s*(?:{cur})", text) or re.search(
                r"(\d+(?:[.,]\d+)?)\s*(k)\b", text
            )
            if m:
                groups = [g for g in m.groups()]
                number = next(g for g in groups if g and g[0].isdigit())
                thousands = next((g for g in groups if g in ("k", "الف", "alf")), None)
                q.price_max = _to_int(number, thousands)
                text = text.replace(m.group(0), " " * len(m.group(0)), 1)
        return text

    @staticmethod
    def _phrase_tables(text: str, q: ParsedQuery) -> str:
        def first(table: dict[Any, tuple[str, ...]]) -> Any:
            ranked = sorted(((p, k) for k, ps in table.items() for p in ps), key=lambda x: -len(x[0]))
            return next((k for p, k in ranked if contains_phrase(text, p)), None)

        q.furnished = first(V.FURNISHED)
        if q.property_type is None:
            q.property_type = first(V.PROPERTY_TYPES)
        if q.property_type == PropertyType.studio:
            q.bedrooms_min = 0
        if any(contains_phrase(text, w) for w in _CHEAP):
            q.sort = "price_asc"
        elif any(contains_phrase(text, w) for w in _LUXURY):
            q.sort = "price_desc"
        return text

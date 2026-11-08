"""Every preference check, with match / miss / unknown driven only by stored facts."""

from types import SimpleNamespace
from typing import Any

import pytest

from app.models.enums import (
    ElectricitySupply as E,
)
from app.models.enums import (
    FloodRisk,
    Sewage,
    SummerComfort,
    WinterComfort,
)
from app.models.enums import (
    GarbageCollection as G,
)
from app.models.enums import (
    WaterSource as W,
)
from app.search.preferences import BY_KEY, Status, _parking

M, X, U = Status.match, Status.miss, Status.unknown

PROPERTY_DEFAULTS: dict[str, Any] = {
    "amenities": [],
    "electricity_supply": None,
    "electricity_usd_month": None,
    "water_source": None,
    "water_usd_month": None,
    "sewage": None,
    "parking_spots": None,
    "solar_ready": None,
    "elevator_backup": None,
    "winter_comfort": None,
    "summer_comfort": None,
}
AREA_DEFAULTS: dict[str, Any] = {
    "safety_score": None,
    "quiet_score": None,
    "theft_reports_12m": None,
    "garbage_collection": None,
    "flood_risk": None,
}


def listing(**prop: Any) -> Any:
    return SimpleNamespace(property=SimpleNamespace(**{**PROPERTY_DEFAULTS, **prop}))


def area(**fields: Any) -> Any:
    return SimpleNamespace(**{**AREA_DEFAULTS, **fields})


LISTING_CASES: list[tuple[str, dict[str, Any], Status]] = [
    ("electricity_24_7", {}, U),
    ("electricity_24_7", {"amenities": ["generator_24_7"]}, M),
    ("electricity_24_7", {"electricity_supply": E.solar_battery}, M),
    ("electricity_24_7", {"electricity_supply": E.edl_only}, X),
    ("low_electricity_bill", {}, U),
    ("low_electricity_bill", {"electricity_usd_month": 60}, M),
    ("low_electricity_bill", {"electricity_usd_month": 61, "electricity_supply": E.solar}, X),
    ("low_electricity_bill", {"electricity_supply": E.solar}, M),
    ("low_electricity_bill", {"electricity_supply": E.edl_plus_generator}, U),
    ("solar", {"electricity_supply": E.solar}, M),
    ("solar", {"amenities": ["solar_power"]}, M),
    ("solar", {}, U),
    ("solar", {"solar_ready": True}, M),
    ("solar", {"solar_ready": False}, X),
    ("water", {"water_usd_month": 10, "water_source": W.tanker}, M),
    ("water", {}, U),
    ("water", {"water_source": W.well}, M),
    ("water", {"water_source": W.tanker, "water_usd_month": 50}, X),
    ("sewage", {}, U),
    ("sewage", {"sewage": Sewage.public_network}, M),
    ("sewage", {"sewage": Sewage.septic_tank}, X),
    ("elevator", {"amenities": ["elevator"]}, M),
    ("elevator", {}, X),
    ("elevator_backup", {}, X),
    ("elevator_backup", {"amenities": ["elevator"]}, U),
    ("elevator_backup", {"amenities": ["elevator"], "elevator_backup": True}, M),
    ("elevator_backup", {"amenities": ["elevator"], "elevator_backup": False}, X),
    ("parking", {}, U),
    ("parking", {"amenities": ["parking"]}, M),
    ("parking", {"parking_spots": 0, "amenities": ["parking"]}, X),
    ("warm_winter", {}, U),
    ("warm_winter", {"winter_comfort": WinterComfort.warm}, M),
    ("warm_winter", {"winter_comfort": WinterComfort.cold, "amenities": ["central_heating"]}, X),
    ("warm_winter", {"amenities": ["central_heating"]}, M),
    ("cool_summer", {}, U),
    ("cool_summer", {"summer_comfort": SummerComfort.cool}, M),
    ("cool_summer", {"summer_comfort": SummerComfort.hot}, X),
    ("cool_summer", {"amenities": ["air_conditioning"]}, M),
    ("pets", {"amenities": ["pets_allowed"]}, M),
]


@pytest.mark.parametrize(("key", "prop", "expected"), LISTING_CASES)
def test_listing_checks(key: str, prop: dict[str, Any], expected: Status) -> None:
    assert BY_KEY[key].check(listing(**prop), None) == expected


AREA_CASES: list[tuple[str, dict[str, Any] | None, Status]] = [
    ("quiet", None, U),
    ("quiet", {}, U),
    ("quiet", {"quiet_score": 4}, M),
    ("quiet", {"quiet_score": 3}, X),
    ("safe", {"safety_score": 5}, M),
    ("low_theft", {}, U),
    ("low_theft", {"theft_reports_12m": 10}, M),
    ("low_theft", {"theft_reports_12m": 11, "safety_score": 5}, X),
    ("low_theft", {"safety_score": 4}, M),
    ("low_theft", {"safety_score": 2}, X),
    ("clean", {}, U),
    ("clean", {"garbage_collection": G.several_weekly}, M),
    ("clean", {"garbage_collection": G.irregular}, X),
    ("no_flooding", {}, U),
    ("no_flooding", {"flood_risk": FloodRisk.low}, M),
    ("no_flooding", {"flood_risk": FloodRisk.high}, X),
]


@pytest.mark.parametrize(("key", "fields", "expected"), AREA_CASES)
def test_area_checks(key: str, fields: dict[str, Any] | None, expected: Status) -> None:
    pref = BY_KEY[key]
    assert pref.source == "area"
    assert pref.check(listing(), None if fields is None else area(**fields)) == expected


def test_parking_spots_needed() -> None:
    assert _parking(listing(parking_spots=1), None, spots=2) == X
    assert _parking(listing(parking_spots=2), None, spots=2) == M
    # "parking" amenity says nothing about how many cars fit.
    assert _parking(listing(amenities=["parking"]), None, spots=2) == U


def test_every_preference_has_bilingual_labels_and_phrases() -> None:
    for pref in BY_KEY.values():
        assert pref.label_en and pref.label_ar and pref.phrases

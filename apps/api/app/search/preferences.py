"""Soft preferences: what people care about beyond rooms and budget.

Each ``Preference`` knows (a) the phrases that ask for it and (b) how to judge a listing against it using
*only stored facts*. A check returns MATCH, MISS or UNKNOWN (data not reported), and the UI shows that status
verbatim, so the search can never claim something the data doesn't say (Specification pattern).
"""

from collections.abc import Callable
from dataclasses import dataclass
from enum import StrEnum

from app.models import AreaProfile, Listing
from app.models.enums import (
    Amenity,
    ElectricitySupply,
    FloodRisk,
    GarbageCollection,
    Sewage,
    SummerComfort,
    WaterSource,
    WinterComfort,
)

LOW_ELECTRICITY_BILL_USD = 60  # per month; Lebanese generator + EDL bills above this feel expensive
LOW_WATER_BILL_USD = 20


class Status(StrEnum):
    match = "match"
    miss = "miss"
    unknown = "unknown"


Check = Callable[[Listing, AreaProfile | None], Status]


def _yes(value: bool) -> Status:
    return Status.match if value else Status.miss


def _amenity(name: Amenity) -> Check:
    return lambda listing, _area: _yes(name.value in (listing.property.amenities or []))


def _electricity_24_7(listing: Listing, _area: AreaProfile | None) -> Status:
    supply = listing.property.electricity_supply
    if Amenity.generator_24_7.value in (listing.property.amenities or []):
        return Status.match
    if supply is None:
        return Status.unknown
    return _yes(supply in (ElectricitySupply.generator_24_7, ElectricitySupply.solar_battery))


def _low_electricity_bill(listing: Listing, _area: AreaProfile | None) -> Status:
    prop = listing.property
    if prop.electricity_usd_month is not None:
        return _yes(prop.electricity_usd_month <= LOW_ELECTRICITY_BILL_USD)
    if prop.electricity_supply in (ElectricitySupply.solar, ElectricitySupply.solar_battery):
        return Status.match
    return Status.unknown


def _solar(listing: Listing, _area: AreaProfile | None) -> Status:
    prop = listing.property
    if prop.electricity_supply in (ElectricitySupply.solar, ElectricitySupply.solar_battery):
        return Status.match
    if Amenity.solar_power.value in (prop.amenities or []):
        return Status.match
    if prop.solar_ready is None:
        return Status.unknown
    return _yes(prop.solar_ready)


def _water(listing: Listing, _area: AreaProfile | None) -> Status:
    prop = listing.property
    if prop.water_usd_month is not None and prop.water_usd_month <= LOW_WATER_BILL_USD:
        return Status.match
    if prop.water_source is None:
        return Status.unknown
    return _yes(prop.water_source in (WaterSource.municipal, WaterSource.well))


def _sewage(listing: Listing, _area: AreaProfile | None) -> Status:
    if listing.property.sewage is None:
        return Status.unknown
    return _yes(listing.property.sewage == Sewage.public_network)


def _elevator_backup(listing: Listing, _area: AreaProfile | None) -> Status:
    if Amenity.elevator.value not in (listing.property.amenities or []):
        return Status.miss
    if listing.property.elevator_backup is None:
        return Status.unknown
    return _yes(listing.property.elevator_backup)


def _parking(listing: Listing, _area: AreaProfile | None, spots: int = 1) -> Status:
    if listing.property.parking_spots is not None:
        return _yes(listing.property.parking_spots >= spots)
    if spots <= 1 and Amenity.parking.value in (listing.property.amenities or []):
        return Status.match
    return Status.unknown


def _warm_winter(listing: Listing, _area: AreaProfile | None) -> Status:
    if listing.property.winter_comfort is not None:
        return _yes(listing.property.winter_comfort == WinterComfort.warm)
    if Amenity.central_heating.value in (listing.property.amenities or []):
        return Status.match
    return Status.unknown


def _cool_summer(listing: Listing, _area: AreaProfile | None) -> Status:
    if listing.property.summer_comfort is not None:
        return _yes(listing.property.summer_comfort == SummerComfort.cool)
    if Amenity.air_conditioning.value in (listing.property.amenities or []):
        return Status.match
    return Status.unknown


def _area_check(fn: Callable[[AreaProfile], bool | None]) -> Check:
    def check(_listing: Listing, area: AreaProfile | None) -> Status:
        if area is None:
            return Status.unknown
        result = fn(area)
        return Status.unknown if result is None else _yes(result)

    return check


def _score_at_least(attr: str, minimum: int) -> Callable[[AreaProfile], bool | None]:
    def fn(area: AreaProfile) -> bool | None:
        value = getattr(area, attr)
        return None if value is None else value >= minimum

    return fn


def _low_theft(area: AreaProfile) -> bool | None:
    if area.theft_reports_12m is not None:
        return area.theft_reports_12m <= 10
    return None if area.safety_score is None else area.safety_score >= 4


def _clean(area: AreaProfile) -> bool | None:
    if area.garbage_collection is None:
        return None
    return area.garbage_collection in (GarbageCollection.daily, GarbageCollection.several_weekly)


def _no_flood(area: AreaProfile) -> bool | None:
    return None if area.flood_risk is None else area.flood_risk == FloodRisk.low


@dataclass(frozen=True)
class Preference:
    key: str
    label_en: str
    label_ar: str
    phrases: tuple[str, ...]
    check: Check
    source: str = "listing"  # "listing" (publisher-reported) or "area" (staff-curated)


PREFERENCES: tuple[Preference, ...] = (
    Preference(
        "electricity_24_7",
        "24/7 electricity",
        "كهرباء ٢٤/٢٤",
        (
            "24/7 electricity",
            "24/7 power",
            "24 hour electricity",
            "24h electricity",
            "24/24",
            "24/7",
            "always electricity",
            "no power cuts",
            "generator",
            "كهرباء 24",
            "كهربا 24",
            "24 ساعه",
            "مولد",
            "موتور",
            "kahraba 24",
            "moteur",
        ),
        _electricity_24_7,
    ),
    Preference(
        "low_electricity_bill",
        "Low electricity bill",
        "فاتورة كهرباء منخفضة",
        (
            "low electricity bill",
            "cheap electricity",
            "low bills",
            "low utility",
            "cheap utilities",
            "low electricity",
            "فاتوره كهرباء رخيصه",
            "فاتوره كهرباء منخفضه",
            "كهرباء منخفضه",
            "كهرباء رخيصه",
            "فاتوره منخفضه",
        ),
        _low_electricity_bill,
    ),
    Preference(
        "solar",
        "Solar power or solar-ready",
        "طاقة شمسية أو جاهزة لها",
        (
            "solar panels",
            "solar ready",
            "can install solar",
            "solar",
            "طاقه شمسيه",
            "الواح شمسيه",
            "taka shamsiye",
            "shamsi",
        ),
        _solar,
    ),
    Preference(
        "water",
        "Reliable / cheap water",
        "مياه منتظمة أو رخيصة",
        (
            "good water",
            "reliable water",
            "cheap water",
            "municipal water",
            "water 24/7",
            "no water problems",
            "مياه الدوله",
            "مي الدوله",
            "مياه منتظمه",
            "مياه رخيصه",
        ),
        _water,
    ),
    Preference(
        "sewage",
        "Public sewage network",
        "شبكة صرف صحي عامة",
        ("public sewage", "sewage", "sewer", "no septic", "صرف صحي", "مجارير"),
        _sewage,
    ),
    Preference(
        "elevator",
        "Elevator",
        "مصعد",
        ("elevator", "lift", "مصعد", "asanseur", "ascenseur"),
        _amenity(Amenity.elevator),
    ),
    Preference(
        "elevator_backup",
        "Elevator works during power cuts",
        "مصعد يعمل عند انقطاع الكهرباء",
        (
            "elevator on generator",
            "elevator backup",
            "elevator with backup",
            "backup elevator",
            "elevator works during power cuts",
            "مصعد على المولد",
            "مصعد يعمل على المولد",
            "مصعد مع مولد",
        ),
        _elevator_backup,
    ),
    Preference(
        "parking",
        "Parking",
        "موقف سيارة",
        ("parking", "garage", "car spot", "موقف", "باركينغ", "باركنغ", "parking spot"),
        _parking,
    ),
    Preference(
        "warm_winter",
        "Warm in winter",
        "دافئة في الشتاء",
        (
            "warm in winter",
            "not cold",
            "warm",
            "heating",
            "central heating",
            "دافي",
            "دافيه",
            "دافئ",
            "تدفئه",
            "shofaj",
            "chauffage",
        ),
        _warm_winter,
    ),
    Preference(
        "cool_summer",
        "Cool in summer",
        "باردة في الصيف",
        (
            "cool in summer",
            "not hot",
            "air conditioning",
            "air conditioned",
            "ac",
            "a/c",
            "مكيف",
            "تكييف",
            "بارد بالصيف",
        ),
        _cool_summer,
    ),
    Preference(
        "quiet",
        "Quiet area",
        "منطقة هادئة",
        (
            "quiet",
            "calm",
            "peaceful",
            "no noise",
            "no dogs barking",
            "no barking",
            "no dog noise",
            "هادئ",
            "هادي",
            "هاديه",
            "بعيد عن الضجه",
            "hadi",
            "hedye",
        ),
        _area_check(_score_at_least("quiet_score", 4)),
        "area",
    ),
    Preference(
        "safe",
        "Safe area",
        "منطقة آمنة",
        (
            "safe",
            "secure",
            "safety",
            "low crime",
            "family",
            "families",
            "kids",
            "امان",
            "امن",
            "امنه",
            "اامن",
            "عائلي",
            "عيله",
            "amen",
        ),
        _area_check(_score_at_least("safety_score", 4)),
        "area",
    ),
    Preference(
        "low_theft",
        "Few thefts reported",
        "سرقات قليلة",
        ("no theft", "no thefts", "few thefts", "no stealing", "no burglary", "سرقات", "سرقه", "حرامي"),
        _area_check(_low_theft),
        "area",
    ),
    Preference(
        "clean",
        "Regular garbage collection",
        "جمع نفايات منتظم",
        ("clean", "garbage", "trash collection", "no garbage", "نظيف", "نظيفه", "نفايات", "زباله"),
        _area_check(_clean),
        "area",
    ),
    Preference(
        "no_flooding",
        "Low flood risk",
        "خطر فيضان منخفض",
        ("no flooding", "doesn't flood", "doesnt flood", "no flood", "dry", "فيضان", "طوفان", "ما بتطوف"),
        _area_check(_no_flood),
        "area",
    ),
    Preference(
        "sea_view",
        "Sea view",
        "إطلالة بحرية",
        (
            "sea view",
            "seaview",
            "sea facing",
            "ocean view",
            "منظر بحر",
            "اطلاله بحريه",
            "مطله على البحر",
            "مطل على البحر",
            "على البحر",
        ),
        _amenity(Amenity.sea_view),
    ),
    Preference(
        "mountain_view",
        "Mountain view",
        "إطلالة جبلية",
        ("mountain view", "اطلاله جبليه", "منظر جبل"),
        _amenity(Amenity.mountain_view),
    ),
    Preference(
        "balcony", "Balcony", "شرفة", ("balcony", "شرفه", "بلكون", "balcon"), _amenity(Amenity.balcony)
    ),
    Preference(
        "terrace", "Terrace", "تراس", ("terrace", "rooftop", "roof", "تراس", "سطح"), _amenity(Amenity.terrace)
    ),
    Preference("garden", "Garden", "حديقة", ("garden", "yard", "حديقه", "جنينه"), _amenity(Amenity.garden)),
    Preference("pool", "Pool", "مسبح", ("pool", "swimming", "مسبح", "بيسين"), _amenity(Amenity.pool)),
    Preference("gym", "Gym", "نادٍ رياضي", ("gym", "fitness", "نادي رياضي"), _amenity(Amenity.gym)),
    Preference(
        "security",
        "Building security",
        "حراسة",
        ("security guard", "guard", "concierge", "ناطور", "حارس"),
        _amenity(Amenity.security),
    ),
    Preference(
        "pets",
        "Pets allowed",
        "يُسمح بالحيوانات",
        (
            "pets",
            "pet friendly",
            "pet-friendly",
            "my dog",
            "with a dog",
            "my cat",
            "with a cat",
            "حيوانات",
            "كلبي",
            "قطتي",
        ),
        _amenity(Amenity.pets_allowed),
    ),
)

BY_KEY: dict[str, Preference] = {p.key: p for p in PREFERENCES}

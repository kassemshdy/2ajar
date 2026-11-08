"""Phrase tables (already normalised: lowercase, folded Arabic). Longest phrases are tried first.

Includes common Lebanese spellings and Arabizi (Arabic in Latin letters, e.g. "2ijar", "sha2a", "gherfeh").
"""

from app.models.enums import Furnished, PropertyType, TransactionType

TRANSACTION: dict[TransactionType, tuple[str, ...]] = {
    TransactionType.rent: (
        "for rent", "to rent", "rent", "renting", "rental", "lease", "monthly", "per month", "/month",
        "ijar", "2ijar", "ajar", "2ajar", "للايجار", "ايجار", "استيجار", "استئجار", "بالشهر", "شهري",
    ),
    TransactionType.sale: (
        "for sale", "to buy", "buy", "buying", "purchase", "sale", "own", "للبيع", "بيع", "شراء", "اشتري",
        "lal bay3", "bay3",
    ),
}  # fmt: skip

PROPERTY_TYPES: dict[PropertyType, tuple[str, ...]] = {
    PropertyType.studio: ("studio", "استوديو", "ستوديو"),
    PropertyType.duplex: ("duplex", "دوبلكس"),
    PropertyType.villa: ("villa", "فيلا", "فيلله"),
    PropertyType.house: ("house", "home", "بيت", "منزل", "beit"),
    PropertyType.chalet: ("chalet", "شاليه"),
    PropertyType.office: ("office", "مكتب"),
    PropertyType.shop: ("shop", "store", "محل", "دكان"),
    PropertyType.land: ("land", "plot", "ارض"),
    PropertyType.apartment: ("apartment", "apt", "flat", "شقه", "شقق", "sha2a", "sha2ah", "chakka"),
}  # fmt: skip

FURNISHED: dict[Furnished, tuple[str, ...]] = {
    Furnished.unfurnished: ("unfurnished", "not furnished", "empty", "غير مفروش", "غير مفروشه", "مش مفروش",
                            "فاضي", "fadye"),
    Furnished.semi: ("semi furnished", "semi-furnished", "partly furnished", "نصف مفروش", "نص مفروش"),
    Furnished.furnished: ("fully furnished", "furnished", "مفروش", "مفروشه", "mafroush", "mafroushe"),
}  # fmt: skip

# Extra spellings for known locations (slug -> aliases). Official EN/AR names come from the database.
LOCATION_ALIASES: dict[str, tuple[str, ...]] = {
    "achrafieh": ("ashrafieh", "ashrafiyeh", "achrafiyeh", "ashrafiye", "ashrafie", "ashrafiya", "الاشرفيه"),
    "hamra": ("el hamra", "al hamra", "hamra street"),
    "mar-mikhael": ("mar mkhayel", "mar michael", "mar mikhail", "مار مخايل"),
    "gemmayzeh": ("gemmayze", "gemayzeh", "jemmayze", "jemmeize"),
    "verdun": ("fardan",),
    "ras-beirut": ("ras beyrouth", "raas beirut"),
    "downtown-beirut": ("downtown", "dt", "solidere", "beirut central district", "wust beirut", "wasat beirut"),
    "ain-el-mreisseh": ("ain el mreisse", "ain mreisseh", "ain al mraiseh"),
    "jdeideh": ("jdaideh", "jdeide", "jdeidet el metn"),
    "dbayeh": ("dbaye", "dbayyeh"),
    "sin-el-fil": ("sin elfil", "sin il fil"),
    "jal-el-dib": ("jal eldib", "jal il dib"),
    "hazmieh": ("hazmiyeh", "hazmiye", "hazmieh"),
    "hadath": ("hadas", "el hadath"),
    "furn-el-chebbak": ("furn el shebbak", "forn el chebbak"),
    "jounieh": ("jounie", "juniyeh", "junieh"),
    "zouk-mosbeh": ("zouk", "zouk mosbeh", "zouk mosbe"),
    "aley": ("alay",),
    "mount-lebanon": ("jabal lebnan", "mount lebanon", "جبل لبنان"),
    "metn": ("matn", "el metn", "al matn", "المتن"),
    "keserwan": ("kesrouan", "kesrwan", "kesrwen"),
    "beirut": ("beyrouth", "bayrout", "بيروت"),
}  # fmt: skip

# Budget markers around numbers.
MAX_MARKERS = (
    "under", "below", "less than", "max", "maximum", "up to", "upto", "within", "no more than", "budget",
    "not more than", "at most", "<", "اقل من", "تحت", "حتى", "لحد", "بحدود", "ما بيتعدى", "ما يتعدى",
    "ma bt3ade", "ta7et", "a2al men",
)  # fmt: skip
MIN_MARKERS = (
    "over",
    "above",
    "more than",
    "at least",
    "minimum",
    "min",
    "from",
    ">",
    "اكثر من",
    "فوق",
    "من",
)
CURRENCY = ("$", "usd", "dollars", "dollar", "دولار", "دولارات", "fresh")
THOUSANDS = ("k", "الف", "ألف", "alf")

ROOM_WORDS = ("bedrooms", "bedroom", "beds", "bed", "br", "bdr", "rooms", "room", "غرف نوم", "غرفه نوم", "غرف",
              "ghoraf", "ghraf")  # fmt: skip
BATH_WORDS = ("bathrooms", "bathroom", "baths", "bath", "حمامات", "حمام")
WORD_NUMBERS = {
    "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "single": 1, "double": 2,
    "واحده": 1, "واحد": 1, "اثنين": 2, "ثلاث": 3, "تلات": 3, "اربع": 4, "خمس": 5,
}  # fmt: skip
# Arabic duals: "غرفتين" = two rooms, "حمامين" = two bathrooms.
DUAL_ROOMS = ("غرفتين", "غرفتي نوم", "ghorfetein", "ghereftein", "2 ghoraf")
DUAL_BATHS = ("حمامين",)
SINGLE_ROOM = ("غرفه نوم واحده", "غرفه واحده", "one bedroom", "1 bedroom")

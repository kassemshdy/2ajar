from enum import StrEnum


class UserRole(StrEnum):
    seeker = "seeker"
    owner = "owner"
    broker = "broker"
    staff = "staff"  # 2ajar support/moderation team: back-office only, cannot publish listings
    platform_admin = "platform_admin"


class Permission(StrEnum):
    """Back-office capabilities. Roles grant a default set; admins may grant extras per user."""

    users_read = "users.read"
    users_manage = "users.manage"
    tickets_read = "tickets.read"
    tickets_manage = "tickets.manage"
    listings_moderate = "listings.moderate"
    analytics_read = "analytics.read"
    areas_manage = "areas.manage"
    mcp_access = "mcp.access"


class OrgRole(StrEnum):
    agency_admin = "agency_admin"
    agent = "agent"


class LocationLevel(StrEnum):
    governorate = "governorate"
    district = "district"
    area = "area"


class PropertyType(StrEnum):
    apartment = "apartment"
    studio = "studio"
    duplex = "duplex"
    house = "house"
    villa = "villa"
    chalet = "chalet"
    office = "office"
    shop = "shop"
    land = "land"


RESIDENTIAL_TYPES = {
    PropertyType.apartment,
    PropertyType.studio,
    PropertyType.duplex,
    PropertyType.house,
    PropertyType.villa,
    PropertyType.chalet,
}


class Furnished(StrEnum):
    unfurnished = "unfurnished"
    semi = "semi"
    furnished = "furnished"


class Amenity(StrEnum):
    generator_24_7 = "generator_24_7"
    solar_power = "solar_power"
    elevator = "elevator"
    parking = "parking"
    balcony = "balcony"
    terrace = "terrace"
    sea_view = "sea_view"
    mountain_view = "mountain_view"
    air_conditioning = "air_conditioning"
    central_heating = "central_heating"
    water_tank = "water_tank"
    security = "security"
    concierge = "concierge"
    gym = "gym"
    pool = "pool"
    garden = "garden"
    storage = "storage"
    pets_allowed = "pets_allowed"


class TransactionType(StrEnum):
    rent = "rent"
    sale = "sale"


class PricePeriod(StrEnum):
    """2ajar is rentals of any length: from an hour (day-use chalet, pool, hall) to years."""

    hourly = "hourly"
    daily = "daily"
    nightly = "nightly"
    weekly = "weekly"
    monthly = "monthly"
    yearly = "yearly"
    total = "total"  # legacy: sale listings, no longer accepted (2ajar is rentals only)


class Stay(StrEnum):
    """How long people rent for; groups price periods for search and browsing."""

    hours = "hours"  # hourly / day use
    nights = "nights"  # nightly / weekly (chalets, holiday homes)
    months = "months"  # monthly / yearly (homes)


STAY_PERIODS: dict[Stay, tuple[PricePeriod, ...]] = {
    Stay.hours: (PricePeriod.hourly, PricePeriod.daily),
    Stay.nights: (PricePeriod.nightly, PricePeriod.weekly),
    Stay.months: (PricePeriod.monthly, PricePeriod.yearly),
}


class ListingStatus(StrEnum):
    draft = "draft"
    pending_review = "pending_review"
    published = "published"
    paused = "paused"
    archived = "archived"
    rejected = "rejected"


class LeadSource(StrEnum):
    web = "web"
    whatsapp = "whatsapp"
    ai = "ai"


class LeadStatus(StrEnum):
    new = "new"
    contacted = "contacted"
    qualified = "qualified"
    closed = "closed"
    spam = "spam"


class ListingEventType(StrEnum):
    view = "view"
    whatsapp_click = "whatsapp_click"
    lead = "lead"
    favorite = "favorite"
    share = "share"


class TicketStatus(StrEnum):
    open = "open"
    in_progress = "in_progress"
    resolved = "resolved"
    closed = "closed"


class TicketPriority(StrEnum):
    low = "low"
    normal = "normal"
    high = "high"
    urgent = "urgent"


class TicketCategory(StrEnum):
    bug = "bug"
    feedback = "feedback"
    question = "question"


# ---------- living factors (publisher-reported, per property) ----------


class ElectricitySupply(StrEnum):
    """How the unit gets power — the #1 running-cost question in Lebanon."""

    edl_only = "edl_only"  # state grid only (a few hours/day)
    edl_plus_generator = "edl_plus_generator"  # grid + building/neighbourhood generator subscription
    generator_24_7 = "generator_24_7"
    solar = "solar"
    solar_battery = "solar_battery"  # solar with batteries: near-24/7 without generator


class WaterSource(StrEnum):
    municipal = "municipal"
    well = "well"
    tanker = "tanker"  # bought by truck
    mixed = "mixed"


class Sewage(StrEnum):
    public_network = "public_network"
    septic_tank = "septic_tank"


class WinterComfort(StrEnum):
    warm = "warm"
    moderate = "moderate"
    cold = "cold"


class SummerComfort(StrEnum):
    cool = "cool"
    moderate = "moderate"
    hot = "hot"


# ---------- area profile (staff-curated, per location) ----------


class GarbageCollection(StrEnum):
    daily = "daily"
    several_weekly = "several_weekly"
    weekly = "weekly"
    irregular = "irregular"


class FloodRisk(StrEnum):
    low = "low"
    medium = "medium"
    high = "high"

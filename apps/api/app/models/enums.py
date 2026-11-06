from enum import StrEnum


class UserRole(StrEnum):
    seeker = "seeker"
    owner = "owner"
    broker = "broker"
    platform_admin = "platform_admin"


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
    monthly = "monthly"
    yearly = "yearly"
    total = "total"


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

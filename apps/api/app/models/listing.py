import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    SmallInteger,
    String,
    Text,
    false,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, Timestamps, UUIDPk
from app.models.enums import (
    ElectricitySupply,
    Furnished,
    ListingStatus,
    PricePeriod,
    PropertyType,
    Sewage,
    SummerComfort,
    TransactionType,
    WaterSource,
    WinterComfort,
)
from app.models.location import Location
from app.models.types import enum_type
from app.models.user import Organization, User


class Property(UUIDPk, Timestamps, Base):
    """The physical unit. Advertisements live in `listings`."""

    __tablename__ = "properties"
    __table_args__ = (
        CheckConstraint("max_guests IS NULL OR max_guests BETWEEN 1 AND 200", name="max_guests_range"),
    )

    owner_user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), index=True)
    organization_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("organizations.id"), index=True)
    location_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("locations.id"), index=True)
    property_type: Mapped[PropertyType] = mapped_column(enum_type(PropertyType, "property_type"))
    bedrooms: Mapped[int | None] = mapped_column(Integer, index=True)
    bathrooms: Mapped[int | None] = mapped_column(Integer)
    area_sqm: Mapped[int | None] = mapped_column(Integer)
    floor: Mapped[int | None] = mapped_column(Integer)
    max_guests: Mapped[int | None] = mapped_column(SmallInteger)
    furnished: Mapped[Furnished | None] = mapped_column(enum_type(Furnished, "furnished"))
    amenities: Mapped[list[str]] = mapped_column(JSONB, default=list, server_default="[]")
    lat: Mapped[Decimal | None] = mapped_column(Numeric(9, 6))
    lng: Mapped[Decimal | None] = mapped_column(Numeric(9, 6))
    is_demo: Mapped[bool] = mapped_column(Boolean, default=False, server_default=false())

    # ---- Living factors (reported by the publisher; shown as "reported by publisher") ----
    electricity_supply: Mapped[ElectricitySupply | None] = mapped_column(
        enum_type(ElectricitySupply, "electricity_supply")
    )
    generator_amps: Mapped[int | None] = mapped_column(Integer)  # subscription size, e.g. 5A / 10A
    electricity_usd_month: Mapped[int | None] = mapped_column(Integer)  # typical monthly bill
    water_source: Mapped[WaterSource | None] = mapped_column(enum_type(WaterSource, "water_source"))
    water_usd_month: Mapped[int | None] = mapped_column(Integer)
    sewage: Mapped[Sewage | None] = mapped_column(enum_type(Sewage, "sewage"))
    parking_spots: Mapped[int | None] = mapped_column(Integer)
    solar_ready: Mapped[bool | None] = mapped_column(Boolean)  # roof/space where panels can be installed
    elevator_backup: Mapped[bool | None] = mapped_column(Boolean)  # elevator works during power cuts
    winter_comfort: Mapped[WinterComfort | None] = mapped_column(enum_type(WinterComfort, "winter_comfort"))
    summer_comfort: Mapped[SummerComfort | None] = mapped_column(enum_type(SummerComfort, "summer_comfort"))
    highlights: Mapped[list[str]] = mapped_column(JSONB, default=list, server_default="[]")
    things_to_know: Mapped[list[str]] = mapped_column(JSONB, default=list, server_default="[]")

    location: Mapped[Location] = relationship(lazy="joined")


class Listing(UUIDPk, Timestamps, Base):
    """An advertisement of a property (rent or sale) with its own lifecycle."""

    __tablename__ = "listings"
    __table_args__ = (
        CheckConstraint("price_usd_cents > 0", name="price_positive"),
        # Indexes are shaped by measured query plans (docs/DATABASE.md "Index strategy").
        # Public search only ever reads published rows, so partial indexes stay small and hot.
        Index(
            "ix_listings_published_newest",
            "transaction_type",
            text("published_at DESC"),
            postgresql_where=text("status = 'published'"),
        ),
        Index(
            "ix_listings_published_price",
            "transaction_type",
            "price_usd_cents",
            postgresql_where=text("status = 'published'"),
        ),
        # Dashboards: "my listings, most recently updated first" for creators and agency admins.
        Index("ix_listings_creator_updated", "created_by_user_id", text("updated_at DESC")),
        Index("ix_listings_org_updated", "organization_id", text("updated_at DESC")),
    )

    property_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("properties.id", ondelete="CASCADE"), index=True
    )
    created_by_user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
    organization_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("organizations.id"))
    transaction_type: Mapped[TransactionType] = mapped_column(enum_type(TransactionType, "transaction_type"))
    price_usd_cents: Mapped[int] = mapped_column(BigInteger)
    price_period: Mapped[PricePeriod] = mapped_column(enum_type(PricePeriod, "price_period"))
    status: Mapped[ListingStatus] = mapped_column(
        enum_type(ListingStatus, "listing_status"), default=ListingStatus.draft
    )
    title_en: Mapped[str | None] = mapped_column(String(140))
    title_ar: Mapped[str | None] = mapped_column(String(140))
    description_en: Mapped[str | None] = mapped_column(Text)
    description_ar: Mapped[str | None] = mapped_column(Text)
    contact_whatsapp_e164: Mapped[str | None] = mapped_column(String(20))
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    is_demo: Mapped[bool] = mapped_column(Boolean, default=False, server_default=false())

    property: Mapped[Property] = relationship(lazy="joined")
    created_by: Mapped[User] = relationship(lazy="joined")
    organization: Mapped[Organization | None] = relationship(lazy="joined")
    media: Mapped[list["ListingMedia"]] = relationship(
        lazy="selectin", order_by="ListingMedia.position", cascade="all, delete-orphan"
    )


class ListingMedia(UUIDPk, Timestamps, Base):
    __tablename__ = "listing_media"
    __table_args__ = (Index("ix_listing_media_listing_position", "listing_id", "position"),)

    listing_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("listings.id", ondelete="CASCADE"))
    storage_key: Mapped[str] = mapped_column(String(300), unique=True)
    content_type: Mapped[str] = mapped_column(String(50))
    width: Mapped[int] = mapped_column(Integer)
    height: Mapped[int] = mapped_column(Integer)
    byte_size: Mapped[int] = mapped_column(Integer)
    position: Mapped[int] = mapped_column(Integer, default=0)

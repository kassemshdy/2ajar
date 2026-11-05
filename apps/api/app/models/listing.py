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
    String,
    Text,
    false,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, Timestamps, UUIDPk
from app.models.enums import Furnished, ListingStatus, PricePeriod, PropertyType, TransactionType
from app.models.location import Location
from app.models.types import enum_type
from app.models.user import Organization, User


class Property(UUIDPk, Timestamps, Base):
    """The physical unit. Advertisements live in `listings`."""

    __tablename__ = "properties"

    owner_user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), index=True)
    organization_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("organizations.id"), index=True)
    location_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("locations.id"), index=True)
    property_type: Mapped[PropertyType] = mapped_column(enum_type(PropertyType, "property_type"))
    bedrooms: Mapped[int | None] = mapped_column(Integer, index=True)
    bathrooms: Mapped[int | None] = mapped_column(Integer)
    area_sqm: Mapped[int | None] = mapped_column(Integer)
    floor: Mapped[int | None] = mapped_column(Integer)
    furnished: Mapped[Furnished | None] = mapped_column(enum_type(Furnished, "furnished"))
    amenities: Mapped[list[str]] = mapped_column(JSONB, default=list, server_default="[]")
    lat: Mapped[Decimal | None] = mapped_column(Numeric(9, 6))
    lng: Mapped[Decimal | None] = mapped_column(Numeric(9, 6))
    is_demo: Mapped[bool] = mapped_column(Boolean, default=False, server_default=false())

    location: Mapped[Location] = relationship(lazy="joined")


class Listing(UUIDPk, Timestamps, Base):
    """An advertisement of a property (rent or sale) with its own lifecycle."""

    __tablename__ = "listings"
    __table_args__ = (
        CheckConstraint("price_usd_cents > 0", name="price_positive"),
        Index("ix_listings_public_search", "status", "transaction_type", "published_at"),
    )

    property_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("properties.id", ondelete="CASCADE"), index=True
    )
    created_by_user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), index=True)
    organization_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("organizations.id"), index=True)
    transaction_type: Mapped[TransactionType] = mapped_column(enum_type(TransactionType, "transaction_type"))
    price_usd_cents: Mapped[int] = mapped_column(BigInteger, index=True)
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

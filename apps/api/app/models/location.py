import uuid
from decimal import Decimal

from sqlalchemy import ForeignKey, Index, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, Timestamps, UUIDPk
from app.models.enums import LocationLevel
from app.models.types import enum_type


class Location(UUIDPk, Timestamps, Base):
    __tablename__ = "locations"
    __table_args__ = (
        Index("ix_locations_path_pattern", "path", postgresql_ops={"path": "text_pattern_ops"}),
    )

    parent_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("locations.id", ondelete="RESTRICT"), index=True
    )
    level: Mapped[LocationLevel] = mapped_column(enum_type(LocationLevel, "location_level"))
    slug: Mapped[str] = mapped_column(String(80), unique=True)
    name_en: Mapped[str] = mapped_column(String(120))
    name_ar: Mapped[str] = mapped_column(String(120))
    # Slash-joined ancestor slugs including self, e.g. "beirut/achrafieh". Enables descendant LIKE queries.
    path: Mapped[str] = mapped_column(String(400), unique=True)
    lat: Mapped[Decimal | None] = mapped_column(Numeric(9, 6))
    lng: Mapped[Decimal | None] = mapped_column(Numeric(9, 6))

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, String, UniqueConstraint, false, true
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, Timestamps, UUIDPk
from app.models.enums import OrgRole, UserRole
from app.models.types import enum_type


class User(UUIDPk, Timestamps, Base):
    __tablename__ = "users"

    email: Mapped[str] = mapped_column(String(254), unique=True, index=True)
    phone_e164: Mapped[str | None] = mapped_column(String(20))
    password_hash: Mapped[str] = mapped_column(String(255))
    full_name: Mapped[str] = mapped_column(String(120))
    role: Mapped[UserRole] = mapped_column(enum_type(UserRole, "user_role"))
    locale: Mapped[str] = mapped_column(String(5), default="en", server_default="en")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default=true())
    is_demo: Mapped[bool] = mapped_column(Boolean, default=False, server_default=false())
    # Checked by 2ajar staff (identity / ownership). Shown as a "verified" badge on an owner's listings.
    is_verified: Mapped[bool] = mapped_column(Boolean, default=False, server_default=false())
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # Back-office permissions granted on top of the role's defaults (see app/authz/permissions.py).
    extra_permissions: Mapped[list[str]] = mapped_column(JSONB, default=list, server_default="[]")

    memberships: Mapped[list["OrganizationMember"]] = relationship(back_populates="user", lazy="selectin")


class Organization(UUIDPk, Timestamps, Base):
    __tablename__ = "organizations"

    name: Mapped[str] = mapped_column(String(160))
    slug: Mapped[str] = mapped_column(String(180), unique=True)
    phone_e164: Mapped[str | None] = mapped_column(String(20))
    is_verified: Mapped[bool] = mapped_column(Boolean, default=False, server_default=false())
    is_demo: Mapped[bool] = mapped_column(Boolean, default=False, server_default=false())


class OrganizationMember(UUIDPk, Timestamps, Base):
    __tablename__ = "organization_members"
    __table_args__ = (UniqueConstraint("organization_id", "user_id", name="uq_org_member"),)

    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), index=True
    )
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    role: Mapped[OrgRole] = mapped_column(enum_type(OrgRole, "org_role"))

    user: Mapped[User] = relationship(back_populates="memberships")
    organization: Mapped[Organization] = relationship(lazy="joined")


class RefreshToken(UUIDPk, Base):
    __tablename__ = "refresh_tokens"

    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    family_id: Mapped[uuid.UUID] = mapped_column(index=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

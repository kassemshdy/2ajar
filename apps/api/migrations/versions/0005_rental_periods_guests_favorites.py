"""rental periods (hourly → yearly), guest capacity, favorites

2ajar is rentals only, from an hour to years. Enums are VARCHAR + CHECK (see app/models/types.py), so widening the
allowed price periods is a constraint swap; the downgrade first maps the new periods back to 'monthly'.

Revision ID: 0005
Revises: 0004
Create Date: 2026-11-08 11:14:30.914199
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0005"
down_revision: str | None = "0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


NEW_PERIODS = ("hourly", "daily", "nightly", "weekly")
OLD_PERIODS = ("monthly", "yearly", "total")


def _period_check(values: Sequence[str]) -> None:
    op.drop_constraint(op.f("ck_listings_price_period"), "listings", type_="check")
    allowed = ", ".join(f"'{v}'" for v in values)
    op.create_check_constraint(op.f("ck_listings_price_period"), "listings", f"price_period IN ({allowed})")


def upgrade() -> None:
    _period_check((*NEW_PERIODS, *OLD_PERIODS))
    op.create_table(
        "favorites",
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("listing_id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(
            ["listing_id"], ["listings.id"], name=op.f("fk_favorites_listing_id_listings"), ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name=op.f("fk_favorites_user_id_users"), ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("user_id", "listing_id", name=op.f("pk_favorites")),
    )
    op.create_index(op.f("ix_favorites_listing_id"), "favorites", ["listing_id"], unique=False)
    op.add_column("properties", sa.Column("max_guests", sa.SmallInteger(), nullable=True))
    op.create_check_constraint(
        op.f("ck_properties_max_guests_range"),
        "properties",
        "max_guests IS NULL OR max_guests BETWEEN 1 AND 200",
    )


def downgrade() -> None:
    values = ", ".join(f"'{v}'" for v in NEW_PERIODS)
    # Built from the module constant NEW_PERIODS, never from input.
    op.execute(f"UPDATE listings SET price_period = 'monthly' WHERE price_period IN ({values})")  # noqa: S608
    _period_check(OLD_PERIODS)
    op.drop_constraint(op.f("ck_properties_max_guests_range"), "properties", type_="check")
    op.drop_column("properties", "max_guests")
    op.drop_index(op.f("ix_favorites_listing_id"), table_name="favorites")
    op.drop_table("favorites")

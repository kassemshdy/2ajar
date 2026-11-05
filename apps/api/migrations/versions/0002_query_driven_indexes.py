"""query-driven indexes

Revision ID: 0002
Revises: 0001
Create Date: 2026-11-05 20:50:05.879043
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Replace generic indexes with ones shaped by measured query plans (see docs/DATABASE.md).

    New indexes are created before old ones are dropped so queries never lose index support mid-deploy.
    """
    op.create_index(
        "ix_listings_published_newest",
        "listings",
        ["transaction_type", sa.literal_column("published_at DESC")],
        postgresql_where=sa.text("status = 'published'"),
    )
    op.create_index(
        "ix_listings_published_price",
        "listings",
        ["transaction_type", "price_usd_cents"],
        postgresql_where=sa.text("status = 'published'"),
    )
    op.create_index(
        "ix_listings_creator_updated",
        "listings",
        ["created_by_user_id", sa.literal_column("updated_at DESC")],
    )
    op.create_index(
        "ix_listings_org_updated", "listings", ["organization_id", sa.literal_column("updated_at DESC")]
    )
    op.create_index(
        "ix_leads_listing_last_contact", "leads", ["listing_id", sa.literal_column("last_contact_at DESC")]
    )
    # Superseded: leading columns of the composites above cover these lookups.
    op.drop_index("ix_listings_public_search", table_name="listings")
    op.drop_index("ix_listings_price_usd_cents", table_name="listings")
    op.drop_index("ix_listings_created_by_user_id", table_name="listings")
    op.drop_index("ix_listings_organization_id", table_name="listings")
    op.drop_index("ix_leads_listing_created", table_name="leads")


def downgrade() -> None:
    op.create_index("ix_leads_listing_created", "leads", ["listing_id", "created_at"])
    op.create_index("ix_listings_organization_id", "listings", ["organization_id"])
    op.create_index("ix_listings_created_by_user_id", "listings", ["created_by_user_id"])
    op.create_index("ix_listings_price_usd_cents", "listings", ["price_usd_cents"])
    op.create_index("ix_listings_public_search", "listings", ["status", "transaction_type", "published_at"])
    op.drop_index("ix_leads_listing_last_contact", table_name="leads")
    op.drop_index("ix_listings_org_updated", table_name="listings")
    op.drop_index("ix_listings_creator_updated", table_name="listings")
    op.drop_index("ix_listings_published_price", table_name="listings")
    op.drop_index("ix_listings_published_newest", table_name="listings")

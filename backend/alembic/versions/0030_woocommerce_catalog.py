"""add read-only WooCommerce catalog integration

Revision ID: 0030_woocommerce_catalog
Revises: 0029_conversation_archive
Create Date: 2026-08-22
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0030_woocommerce_catalog"
down_revision: Union[str, None] = "0029_conversation_archive"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "woocommerce_catalog_integrations",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("profile_id", sa.Integer(), nullable=False),
        sa.Column("store_url", sa.String(length=2048), nullable=False),
        sa.Column(
            "enabled", sa.Boolean(), server_default=sa.text("false"), nullable=False
        ),
        sa.Column(
            "catalog_metadata",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column("verified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("metadata_refreshed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["profile_id"], ["assistant_profiles.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("profile_id"),
    )
    op.create_index(
        "ix_woocommerce_catalog_integrations_profile_id",
        "woocommerce_catalog_integrations",
        ["profile_id"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_woocommerce_catalog_integrations_profile_id",
        table_name="woocommerce_catalog_integrations",
    )
    op.drop_table("woocommerce_catalog_integrations")

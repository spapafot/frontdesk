"""generalize catalog integration providers

Revision ID: 0031_provider_neutral_catalog
Revises: 0030_woocommerce_catalog
Create Date: 2026-08-22
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0031_provider_neutral_catalog"
down_revision: Union[str, None] = "0030_woocommerce_catalog"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.rename_table("woocommerce_catalog_integrations", "catalog_integrations")
    op.drop_index(
        "ix_woocommerce_catalog_integrations_profile_id",
        table_name="catalog_integrations",
    )
    op.add_column(
        "catalog_integrations",
        sa.Column(
            "provider",
            sa.String(length=32),
            server_default="woocommerce",
            nullable=False,
        ),
    )
    op.create_check_constraint(
        "ck_catalog_integrations_provider",
        "catalog_integrations",
        "provider IN ('woocommerce', 'shopify')",
    )
    op.create_index(
        "ix_catalog_integrations_profile_id",
        "catalog_integrations",
        ["profile_id"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_catalog_integrations_profile_id", table_name="catalog_integrations"
    )
    op.drop_constraint(
        "ck_catalog_integrations_provider",
        "catalog_integrations",
        type_="check",
    )
    op.drop_column("catalog_integrations", "provider")
    op.rename_table("catalog_integrations", "woocommerce_catalog_integrations")
    op.create_index(
        "ix_woocommerce_catalog_integrations_profile_id",
        "woocommerce_catalog_integrations",
        ["profile_id"],
        unique=True,
    )

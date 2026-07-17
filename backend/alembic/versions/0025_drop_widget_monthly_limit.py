"""drop widget_installations.monthly_limit

The per-site message ceiling is dead: the monthly quota is enforced
account-wide (pooled across all the owner's sites) against the plan limits in
``app/core/plans.py`` via ``SubscriptionRepository.reserve_account_message``
(migration 0024). Per-site usage stays visible through ``widget_usage``.

Revision ID: 0025_drop_widget_monthly_limit
Revises: 0024_billing
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0025_drop_widget_monthly_limit"
down_revision: Union[str, None] = "0024_billing"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_column("widget_installations", "monthly_limit")


def downgrade() -> None:
    op.add_column(
        "widget_installations",
        sa.Column("monthly_limit", sa.Integer, nullable=False, server_default="5000"),
    )

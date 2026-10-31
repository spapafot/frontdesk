"""add visitor_usage: daily per-IP-per-installation widget message budget

The visitor's IP is never stored raw - only its SHA-256 hex digest (same
treatment as ``conversations.visitor_session_id_hash``). One row accumulates
per active (installation, IP, UTC day); enforcement is a guarded upsert in
``WidgetRepository.reserve_visitor_message``. Rows are small and currently
never pruned (a cleanup job is future work).

Revision ID: 0026_visitor_daily_budget
Revises: 0025_drop_widget_monthly_limit
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0026_visitor_daily_budget"
down_revision: Union[str, None] = "0025_drop_widget_monthly_limit"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "visitor_usage",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "installation_id",
            sa.Integer(),
            sa.ForeignKey("widget_installations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("ip_hash", sa.String(64), nullable=False),
        sa.Column("day", sa.Date(), nullable=False),
        sa.Column("message_count", sa.Integer(), nullable=False, server_default="0"),
        sa.UniqueConstraint(
            "installation_id", "ip_hash", "day", name="uq_visitor_usage_daily"
        ),
    )
    op.create_index(
        "ix_visitor_usage_installation_id", "visitor_usage", ["installation_id"]
    )


def downgrade() -> None:
    op.drop_table("visitor_usage")

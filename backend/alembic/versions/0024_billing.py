"""add billing: subscriptions, pooled account usage, webhook idempotency

Revision ID: 0024_billing
Revises: 0023_visitor_moderation
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0024_billing"
down_revision: Union[str, None] = "0023_visitor_moderation"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "subscriptions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("owner_user_id", sa.String(128), nullable=False),
        sa.Column("plan", sa.String(16), nullable=False, server_default="trial"),
        sa.Column("status", sa.String(24), nullable=False, server_default="trialing"),
        sa.Column("stripe_customer_id", sa.String(64), nullable=True),
        sa.Column("stripe_subscription_id", sa.String(64), nullable=True),
        sa.Column("billing_interval", sa.String(8), nullable=True),
        sa.Column("trial_ends_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("current_period_end", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.UniqueConstraint("owner_user_id", name="uq_subscriptions_owner"),
    )
    op.create_index(
        "ix_subscriptions_owner_user_id", "subscriptions", ["owner_user_id"]
    )

    op.create_table(
        "account_usage",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("owner_user_id", sa.String(128), nullable=False),
        sa.Column("period", sa.Date(), nullable=False),
        sa.Column("message_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("bonus_messages", sa.Integer(), nullable=False, server_default="0"),
        sa.UniqueConstraint(
            "owner_user_id", "period", name="uq_account_usage_period"
        ),
    )
    op.create_index(
        "ix_account_usage_owner_user_id", "account_usage", ["owner_user_id"]
    )

    op.create_table(
        "billing_events",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("stripe_event_id", sa.String(64), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.UniqueConstraint(
            "stripe_event_id", name="uq_billing_events_event_id"
        ),
    )
    op.create_index(
        "ix_billing_events_stripe_event_id", "billing_events", ["stripe_event_id"]
    )


def downgrade() -> None:
    op.drop_table("billing_events")
    op.drop_table("account_usage")
    op.drop_table("subscriptions")

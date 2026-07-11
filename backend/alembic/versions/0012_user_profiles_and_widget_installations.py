"""replace shared businesses with user-owned profiles and widget installations

Revision ID: 0012_user_profiles_widgets
Revises: 0011_embedding_dim_1536

This migration intentionally discards existing tenant data. The previous schema
had no authenticated owner, so assigning it automatically would be unsafe.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0012_user_profiles_widgets"
down_revision: Union[str, None] = "0011_embedding_dim_1536"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("TRUNCATE conversation_messages, conversations, knowledge_chunks, knowledge_documents, businesses CASCADE")
    for table in ("price_rules", "schedules", "vessels", "routes"):
        op.execute(f"DROP TABLE IF EXISTS {table} CASCADE")

    op.drop_constraint("uq_businesses_public_key", "businesses", type_="unique")
    op.drop_column("businesses", "public_key")
    op.rename_table("businesses", "assistant_profiles")
    op.add_column("assistant_profiles", sa.Column("owner_user_id", sa.String(128), nullable=False))
    op.create_unique_constraint(
        "uq_assistant_profiles_owner_user_id", "assistant_profiles", ["owner_user_id"]
    )

    for table in ("knowledge_documents", "knowledge_chunks", "conversations"):
        op.alter_column(table, "business_id", new_column_name="profile_id")

    op.create_table(
        "widget_installations",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column(
            "profile_id",
            sa.Integer,
            sa.ForeignKey("assistant_profiles.id", ondelete="CASCADE"),
            nullable=False,
            unique=True,
        ),
        sa.Column("public_key", sa.String(64), nullable=False, unique=True),
        sa.Column("allowed_origin", sa.String(255), nullable=True),
        sa.Column("is_enabled", sa.Boolean, nullable=False, server_default=sa.true()),
        sa.Column("monthly_limit", sa.Integer, nullable=False, server_default="5000"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_widget_installations_public_key", "widget_installations", ["public_key"])
    op.create_table(
        "widget_usage",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column(
            "installation_id",
            sa.Integer,
            sa.ForeignKey("widget_installations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("period", sa.Date, nullable=False),
        sa.Column("message_count", sa.Integer, nullable=False, server_default="0"),
        sa.UniqueConstraint("installation_id", "period", name="uq_widget_usage_period"),
    )


def downgrade() -> None:
    raise RuntimeError("0012 is intentionally destructive and cannot be downgraded")

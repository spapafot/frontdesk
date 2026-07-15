"""add live human escalation state and audit records

Revision ID: 0019_live_escalation
Revises: 0018_document_source_url
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0019_live_escalation"
down_revision: Union[str, None] = "0018_document_source_url"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "assistant_profiles",
        sa.Column(
            "live_human_escalation_enabled",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
    )
    for column in (
        sa.Column("mode", sa.String(24), nullable=False, server_default="ai"),
        sa.Column("assigned_user_id", sa.String(128), nullable=True),
        sa.Column("visitor_session_id_hash", sa.String(64), nullable=True),
        sa.Column("escalation_requested_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("escalation_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("accepted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_message_at", sa.DateTime(timezone=True), nullable=True),
    ):
        op.add_column("conversations", column)
    op.create_index(
        "ix_conversations_profile_mode",
        "conversations",
        ["profile_id", "mode"],
    )

    op.add_column(
        "conversation_messages", sa.Column("client_message_id", sa.String(36), nullable=True)
    )
    op.add_column(
        "conversation_messages", sa.Column("sender_type", sa.String(16), nullable=True)
    )
    op.add_column(
        "conversation_messages", sa.Column("sender_user_id", sa.String(128), nullable=True)
    )
    op.add_column(
        "conversation_messages", sa.Column("sender_display_name", sa.String(120), nullable=True)
    )
    op.execute(
        """
        UPDATE conversation_messages
        SET sender_type = CASE
            WHEN role = 'user' THEN 'visitor'
            WHEN role = 'assistant' THEN 'ai'
            ELSE 'system'
        END
        """
    )
    op.alter_column(
        "conversation_messages", "sender_type", nullable=False, server_default="system"
    )
    op.create_unique_constraint(
        "uq_conversation_messages_client_id",
        "conversation_messages",
        ["conversation_id", "client_message_id"],
    )

    op.create_table(
        "conversation_events",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "conversation_id",
            sa.Integer(),
            sa.ForeignKey("conversations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("type", sa.String(32), nullable=False),
        sa.Column("actor_type", sa.String(16), nullable=False),
        sa.Column("actor_id", sa.String(128), nullable=True),
        sa.Column("metadata", postgresql.JSONB(), nullable=False, server_default="{}"),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
    )
    op.create_index(
        "ix_conversation_events_conversation_id",
        "conversation_events",
        ["conversation_id"],
    )

    op.create_table(
        "escalation_tickets",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "conversation_id",
            sa.Integer(),
            sa.ForeignKey("conversations.id", ondelete="CASCADE"),
            nullable=False,
            unique=True,
        ),
        sa.Column(
            "profile_id",
            sa.Integer(),
            sa.ForeignKey("assistant_profiles.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("customer_name", sa.String(120), nullable=True),
        sa.Column("customer_email", sa.String(254), nullable=False),
        sa.Column("customer_message", sa.Text(), nullable=True),
        sa.Column(
            "reason", sa.String(64), nullable=False, server_default="no_agent_available"
        ),
        sa.Column("status", sa.String(16), nullable=False, server_default="pending"),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_escalation_tickets_profile_id", "escalation_tickets", ["profile_id"])


def downgrade() -> None:
    op.drop_table("escalation_tickets")
    op.drop_table("conversation_events")
    op.drop_constraint(
        "uq_conversation_messages_client_id", "conversation_messages", type_="unique"
    )
    for name in (
        "sender_display_name",
        "sender_user_id",
        "sender_type",
        "client_message_id",
    ):
        op.drop_column("conversation_messages", name)
    op.drop_index("ix_conversations_profile_mode", table_name="conversations")
    for name in (
        "last_message_at",
        "closed_at",
        "accepted_at",
        "escalation_expires_at",
        "escalation_requested_at",
        "visitor_session_id_hash",
        "assigned_user_id",
        "mode",
    ):
        op.drop_column("conversations", name)
    op.drop_column("assistant_profiles", "live_human_escalation_enabled")

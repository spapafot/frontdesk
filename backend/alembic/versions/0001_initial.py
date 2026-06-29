"""initial schema with pgvector

Revision ID: 0001_initial
Revises:
Create Date: 2026-06-29

"""
from typing import Sequence, Union

import sqlalchemy as sa
from pgvector.sqlalchemy import Vector
from sqlalchemy.dialects import postgresql

from alembic import op

from app.core.config import settings

revision: str = "0001_initial"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    op.create_table(
        "businesses",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("type", sa.String(64), nullable=False),
        sa.Column("timezone", sa.String(64), nullable=False, server_default="Europe/Athens"),
        sa.Column("default_language", sa.String(8), nullable=False, server_default="en"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        "knowledge_documents",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column(
            "business_id",
            sa.Integer,
            sa.ForeignKey("businesses.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("type", sa.String(64), nullable=False, server_default="text"),
        sa.Column("content", sa.Text, nullable=False),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_knowledge_documents_business_id", "knowledge_documents", ["business_id"])

    op.create_table(
        "knowledge_chunks",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column(
            "business_id",
            sa.Integer,
            sa.ForeignKey("businesses.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "document_id",
            sa.Integer,
            sa.ForeignKey("knowledge_documents.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("content", sa.Text, nullable=False),
        sa.Column("embedding", Vector(settings.embedding_dim), nullable=False),
        sa.Column("metadata", postgresql.JSONB, nullable=False, server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_knowledge_chunks_business_id", "knowledge_chunks", ["business_id"])
    op.create_index("ix_knowledge_chunks_document_id", "knowledge_chunks", ["document_id"])

    op.create_table(
        "routes",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column(
            "business_id",
            sa.Integer,
            sa.ForeignKey("businesses.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("origin", sa.String(128), nullable=False),
        sa.Column("destination", sa.String(128), nullable=False),
        sa.Column("active", sa.Boolean, nullable=False, server_default=sa.true()),
    )
    op.create_index("ix_routes_business_id", "routes", ["business_id"])

    op.create_table(
        "vessels",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column(
            "business_id",
            sa.Integer,
            sa.ForeignKey("businesses.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("name", sa.String(128), nullable=False),
        sa.Column("supports_vehicles", sa.Boolean, nullable=False, server_default=sa.true()),
        sa.Column("supports_pets", sa.Boolean, nullable=False, server_default=sa.true()),
        sa.Column("active", sa.Boolean, nullable=False, server_default=sa.true()),
    )
    op.create_index("ix_vessels_business_id", "vessels", ["business_id"])

    op.create_table(
        "schedules",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column(
            "business_id",
            sa.Integer,
            sa.ForeignKey("businesses.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "route_id",
            sa.Integer,
            sa.ForeignKey("routes.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "vessel_id",
            sa.Integer,
            sa.ForeignKey("vessels.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("departure_time", sa.Time, nullable=False),
        sa.Column("arrival_time", sa.Time, nullable=True),
        sa.Column("valid_from", sa.Date, nullable=True),
        sa.Column("valid_until", sa.Date, nullable=True),
        sa.Column("days_of_week", postgresql.ARRAY(sa.Integer), nullable=False, server_default="{}"),
        sa.Column("active", sa.Boolean, nullable=False, server_default=sa.true()),
    )
    op.create_index("ix_schedules_business_id", "schedules", ["business_id"])
    op.create_index("ix_schedules_route_id", "schedules", ["route_id"])

    op.create_table(
        "price_rules",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column(
            "business_id",
            sa.Integer,
            sa.ForeignKey("businesses.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "route_id",
            sa.Integer,
            sa.ForeignKey("routes.id", ondelete="CASCADE"),
            nullable=True,
        ),
        sa.Column("passenger_type", sa.String(32), nullable=True),
        sa.Column("vehicle_type", sa.String(32), nullable=True),
        sa.Column("price", sa.Numeric(10, 2), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False, server_default="EUR"),
        sa.Column("valid_from", sa.Date, nullable=True),
        sa.Column("valid_until", sa.Date, nullable=True),
        sa.Column("active", sa.Boolean, nullable=False, server_default=sa.true()),
    )
    op.create_index("ix_price_rules_business_id", "price_rules", ["business_id"])

    op.create_table(
        "conversations",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column(
            "business_id",
            sa.Integer,
            sa.ForeignKey("businesses.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("channel", sa.String(16), nullable=False, server_default="chat"),
        sa.Column("started_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("summary", sa.Text, nullable=True),
    )
    op.create_index("ix_conversations_business_id", "conversations", ["business_id"])

    op.create_table(
        "conversation_messages",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column(
            "conversation_id",
            sa.Integer,
            sa.ForeignKey("conversations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("role", sa.String(16), nullable=False),
        sa.Column("content", sa.Text, nullable=False, server_default=""),
        sa.Column("tool_name", sa.String(64), nullable=True),
        sa.Column("metadata", postgresql.JSONB, nullable=False, server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index(
        "ix_conversation_messages_conversation_id",
        "conversation_messages",
        ["conversation_id"],
    )


def downgrade() -> None:
    op.drop_table("conversation_messages")
    op.drop_table("conversations")
    op.drop_table("price_rules")
    op.drop_table("schedules")
    op.drop_table("vessels")
    op.drop_table("routes")
    op.drop_table("knowledge_chunks")
    op.drop_table("knowledge_documents")
    op.drop_table("businesses")
    op.execute("DROP EXTENSION IF EXISTS vector")

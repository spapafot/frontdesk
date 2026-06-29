"""drop ferry domain and seeded demo data (document-RAG pivot)

Revision ID: 0002_document_rag
Revises: 0001_initial
Create Date: 2026-06-29

"""
from typing import Sequence, Union

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0002_document_rag"
down_revision: Union[str, None] = "0001_initial"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Remove all seeded demo content (cascades to its knowledge + conversations).
    op.execute("DELETE FROM businesses WHERE name = 'Ionian Demo Ferries'")

    # Drop the ferry-specific structured tables (child tables first).
    op.drop_table("price_rules")
    op.drop_table("schedules")
    op.drop_table("vessels")
    op.drop_table("routes")


def downgrade() -> None:
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

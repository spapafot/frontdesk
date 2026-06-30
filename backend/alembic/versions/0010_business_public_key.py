"""add public_key (widget site key) to businesses

Revision ID: 0010_business_public_key
Revises: 0009_knowledge_chunk_hnsw_index
Create Date: 2026-06-30

"""
from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

revision: str = "0010_business_public_key"
down_revision: Union[str, None] = "0009_knowledge_chunk_hnsw_index"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "businesses",
        sa.Column("public_key", sa.String(length=48), nullable=True),
    )
    # Backfill existing rows with a unique, non-secret site key (no extensions
    # required: derive from md5 of random + id).
    op.execute(
        "UPDATE businesses "
        "SET public_key = 'pk_live_' || substr(md5(random()::text || id::text), 1, 24) "
        "WHERE public_key IS NULL"
    )
    op.create_unique_constraint(
        "uq_businesses_public_key", "businesses", ["public_key"]
    )


def downgrade() -> None:
    op.drop_constraint("uq_businesses_public_key", "businesses", type_="unique")
    op.drop_column("businesses", "public_key")

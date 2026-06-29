"""add assistant_name and custom_instructions to businesses

Revision ID: 0003_business_settings
Revises: 0002_document_rag
Create Date: 2026-06-29

"""
from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

revision: str = "0003_business_settings"
down_revision: Union[str, None] = "0002_document_rag"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "businesses",
        sa.Column(
            "assistant_name",
            sa.String(120),
            nullable=False,
            server_default="Assistant",
        ),
    )
    op.add_column(
        "businesses",
        sa.Column("custom_instructions", sa.Text(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("businesses", "custom_instructions")
    op.drop_column("businesses", "assistant_name")

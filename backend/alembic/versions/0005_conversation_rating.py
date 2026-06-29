"""add rating + rating_comment to conversations

Revision ID: 0005_conversation_rating
Revises: 0004_conversation_title
Create Date: 2026-06-29

"""
from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

revision: str = "0005_conversation_rating"
down_revision: Union[str, None] = "0004_conversation_title"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "conversations",
        sa.Column("rating", sa.String(8), nullable=True),
    )
    op.add_column(
        "conversations",
        sa.Column("rating_comment", sa.Text(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("conversations", "rating_comment")
    op.drop_column("conversations", "rating")

"""drop rating_comment from conversations

Revision ID: 0006_drop_rating_comment
Revises: 0005_conversation_rating
Create Date: 2026-06-29

"""
from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

revision: str = "0006_drop_rating_comment"
down_revision: Union[str, None] = "0005_conversation_rating"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_column("conversations", "rating_comment")


def downgrade() -> None:
    op.add_column(
        "conversations",
        sa.Column("rating_comment", sa.Text(), nullable=True),
    )

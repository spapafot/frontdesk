"""add title to conversations and backfill from first user message

Revision ID: 0004_conversation_title
Revises: 0003_business_settings
Create Date: 2026-06-29

"""
from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

revision: str = "0004_conversation_title"
down_revision: Union[str, None] = "0003_business_settings"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "conversations",
        sa.Column("title", sa.String(160), nullable=True),
    )
    # Backfill: use the first user message (truncated) as the title.
    op.execute(
        """
        UPDATE conversations c
        SET title = sub.title
        FROM (
            SELECT DISTINCT ON (conversation_id)
                   conversation_id,
                   left(content, 120) AS title
            FROM conversation_messages
            WHERE role = 'user'
            ORDER BY conversation_id, id
        ) AS sub
        WHERE sub.conversation_id = c.id
        """
    )


def downgrade() -> None:
    op.drop_column("conversations", "title")

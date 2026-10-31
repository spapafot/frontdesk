"""add conversation archiving

Revision ID: 0029_conversation_archive
Revises: 0028_embedding_halfvec
Create Date: 2026-08-08

Archiving replaces deletion as the everyday History action: deleting a
conversation cascades away its messages, audit events, and any escalation
ticket (including pending callback requests), and a visitor whose browser
still references the deleted conversation would otherwise hit dead 404s.
Archived conversations are hidden in the dashboard but stay live for the
visitor; new activity un-archives them.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0029_conversation_archive"
down_revision: Union[str, None] = "0028_embedding_halfvec"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "conversations",
        sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("conversations", "archived_at")

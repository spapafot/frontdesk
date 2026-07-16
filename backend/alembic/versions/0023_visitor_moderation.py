"""add visitor abuse moderation toggle and strike counter

Revision ID: 0023_visitor_moderation
Revises: 0022_ticket_board
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0023_visitor_moderation"
down_revision: Union[str, None] = "0022_ticket_board"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "assistant_profiles",
        sa.Column(
            "moderation_enabled",
            sa.Boolean(),
            nullable=False,
            server_default=sa.true(),
        ),
    )
    op.add_column(
        "conversations",
        sa.Column(
            "moderation_strikes",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
    )


def downgrade() -> None:
    op.drop_column("conversations", "moderation_strikes")
    op.drop_column("assistant_profiles", "moderation_enabled")

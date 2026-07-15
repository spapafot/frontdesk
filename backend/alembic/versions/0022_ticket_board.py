"""add assignee and archived to escalation tickets for the board view

Revision ID: 0022_ticket_board
Revises: 0021_team_members
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0022_ticket_board"
down_revision: Union[str, None] = "0021_team_members"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "escalation_tickets",
        sa.Column("assignee_user_id", sa.String(128), nullable=True),
    )
    op.add_column(
        "escalation_tickets",
        sa.Column(
            "archived", sa.Boolean(), nullable=False, server_default=sa.false()
        ),
    )


def downgrade() -> None:
    op.drop_column("escalation_tickets", "archived")
    op.drop_column("escalation_tickets", "assignee_user_id")

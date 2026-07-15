"""add team_members for invite-based multi-operator access

Revision ID: 0021_team_members
Revises: 0020_notification_email
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0021_team_members"
down_revision: Union[str, None] = "0020_notification_email"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "team_members",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("owner_user_id", sa.String(128), nullable=False),
        sa.Column("invited_email", sa.String(254), nullable=False),
        sa.Column("member_user_id", sa.String(128), nullable=True),
        sa.Column(
            "status", sa.String(16), nullable=False, server_default="invited"
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("activated_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint(
            "owner_user_id", "invited_email", name="uq_team_members_owner_email"
        ),
    )
    op.create_index(
        "ix_team_members_owner_user_id", "team_members", ["owner_user_id"]
    )
    op.create_index(
        "ix_team_members_invited_email", "team_members", ["invited_email"]
    )
    op.create_index(
        "ix_team_members_member_user_id", "team_members", ["member_user_id"]
    )


def downgrade() -> None:
    op.drop_table("team_members")

"""add per-site ticket notification email

Revision ID: 0020_notification_email
Revises: 0019_live_escalation
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0020_notification_email"
down_revision: Union[str, None] = "0019_live_escalation"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "assistant_profiles",
        sa.Column("notification_email", sa.String(254), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("assistant_profiles", "notification_email")

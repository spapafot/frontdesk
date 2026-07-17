"""add configurable talk-to-person message threshold

Revision ID: 0027_talk_to_person_after
Revises: 0026_visitor_daily_budget
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0027_talk_to_person_after"
down_revision: Union[str, None] = "0026_visitor_daily_budget"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "assistant_profiles",
        sa.Column(
            "talk_to_person_after",
            sa.Integer(),
            nullable=False,
            server_default="3",
        ),
    )


def downgrade() -> None:
    op.drop_column("assistant_profiles", "talk_to_person_after")

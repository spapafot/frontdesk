"""add tts_voice to businesses

Revision ID: 0007_business_tts_voice
Revises: 0006_drop_rating_comment
Create Date: 2026-06-30

"""
from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

revision: str = "0007_business_tts_voice"
down_revision: Union[str, None] = "0006_drop_rating_comment"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "businesses",
        sa.Column(
            "tts_voice",
            sa.String(32),
            nullable=False,
            server_default="nova",
        ),
    )


def downgrade() -> None:
    op.drop_column("businesses", "tts_voice")

"""add tts_speed to businesses

Revision ID: 0008_business_tts_speed
Revises: 0007_business_tts_voice
Create Date: 2026-06-30

"""
from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

revision: str = "0008_business_tts_speed"
down_revision: Union[str, None] = "0007_business_tts_voice"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "businesses",
        sa.Column(
            "tts_speed",
            sa.Float(),
            nullable=False,
            server_default="1.1",
        ),
    )


def downgrade() -> None:
    op.drop_column("businesses", "tts_speed")

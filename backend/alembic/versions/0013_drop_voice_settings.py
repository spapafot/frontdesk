"""drop obsolete voice settings

Revision ID: 0013_drop_voice_settings
Revises: 0012_user_profiles_widgets
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0013_drop_voice_settings"
down_revision: Union[str, None] = "0012_user_profiles_widgets"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_column("assistant_profiles", "tts_speed")
    op.drop_column("assistant_profiles", "tts_voice")


def downgrade() -> None:
    op.add_column(
        "assistant_profiles",
        sa.Column("tts_voice", sa.String(32), nullable=False, server_default="nova"),
    )
    op.add_column(
        "assistant_profiles",
        sa.Column("tts_speed", sa.Float(), nullable=False, server_default="1.1"),
    )

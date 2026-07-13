"""add widget appearance settings

Revision ID: 0015_widget_appearance
Revises: 0014_async_document_ingestion
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0015_widget_appearance"
down_revision: Union[str, None] = "0014_async_document_ingestion"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "widget_installations",
        sa.Column("accent_color", sa.String(9), nullable=False, server_default="#0284c7"),
    )
    op.add_column(
        "widget_installations",
        sa.Column("launcher_icon", sa.String(32), nullable=False, server_default="chat"),
    )
    op.add_column(
        "widget_installations",
        sa.Column(
            "launcher_position", sa.String(16), nullable=False, server_default="bottom-right"
        ),
    )
    op.add_column(
        "widget_installations",
        sa.Column(
            "greeting",
            sa.String(500),
            nullable=False,
            server_default="Hi! How can I help you today?",
        ),
    )
    op.add_column(
        "widget_installations",
        sa.Column("launcher_label", sa.String(60), nullable=True),
    )
    op.add_column(
        "widget_installations",
        sa.Column("show_branding", sa.Boolean, nullable=False, server_default=sa.true()),
    )


def downgrade() -> None:
    for column in (
        "show_branding",
        "launcher_label",
        "greeting",
        "launcher_position",
        "launcher_icon",
        "accent_color",
    ):
        op.drop_column("widget_installations", column)

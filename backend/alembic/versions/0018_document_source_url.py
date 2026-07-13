"""add source_url to knowledge_documents

Revision ID: 0018_document_source_url
Revises: 0017_multi_site_per_owner

Stores the origin URL for link-sourced knowledge entries (type == "url") so the
page can be rescanned on demand. NULL for uploaded files. The revision id is
kept short to fit alembic_version.version_num (varchar(32)).
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0018_document_source_url"
down_revision: Union[str, None] = "0017_multi_site_per_owner"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "knowledge_documents",
        sa.Column("source_url", sa.String(length=2048), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("knowledge_documents", "source_url")

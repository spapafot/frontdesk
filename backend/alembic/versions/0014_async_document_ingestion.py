"""add asynchronous document processing state

Revision ID: 0014_async_document_ingestion
Revises: 0013_drop_voice_settings
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0014_async_document_ingestion"
down_revision: Union[str, None] = "0013_drop_voice_settings"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "knowledge_documents",
        sa.Column(
            "processing_status",
            sa.String(length=20),
            nullable=False,
            server_default="ready",
        ),
    )
    op.add_column(
        "knowledge_documents", sa.Column("processing_error", sa.Text(), nullable=True)
    )
    op.add_column(
        "knowledge_documents", sa.Column("storage_key", sa.String(1024), nullable=True)
    )
    op.add_column(
        "knowledge_documents",
        sa.Column("processed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index(
        "ix_knowledge_documents_processing_status",
        "knowledge_documents",
        ["processing_status"],
    )
    op.execute(
        "UPDATE knowledge_documents SET processed_at = COALESCE(updated_at, created_at)"
    )


def downgrade() -> None:
    op.drop_index(
        "ix_knowledge_documents_processing_status",
        table_name="knowledge_documents",
    )
    op.drop_column("knowledge_documents", "processed_at")
    op.drop_column("knowledge_documents", "storage_key")
    op.drop_column("knowledge_documents", "processing_error")
    op.drop_column("knowledge_documents", "processing_status")

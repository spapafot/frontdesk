"""add full-text search indexes for ranked hybrid retrieval

Revision ID: 0016_ranked_fts
Revises: 0015_widget_appearance
"""

from typing import Sequence, Union

from alembic import op

revision: str = "0016_ranked_fts"
down_revision: Union[str, None] = "0015_widget_appearance"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # The expressions intentionally match KnowledgeRepository.search_text.
    # PostgreSQL's built-in `simple` configuration is language-neutral, which is
    # important for this application's mixed Greek/English knowledge bases.
    op.execute(
        "CREATE INDEX IF NOT EXISTS knowledge_chunks_content_fts_idx "
        "ON knowledge_chunks USING gin (to_tsvector('simple', content))"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS knowledge_documents_title_fts_idx "
        "ON knowledge_documents USING gin (to_tsvector('simple', title))"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS knowledge_documents_title_fts_idx")
    op.execute("DROP INDEX IF EXISTS knowledge_chunks_content_fts_idx")

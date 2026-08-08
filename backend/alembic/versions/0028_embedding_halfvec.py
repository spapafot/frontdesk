"""switch embedding column to half-precision (halfvec)

Revision ID: 0028_embedding_halfvec
Revises: 0027_talk_to_person_after
Create Date: 2026-08-08

fp16 halves the embedding column and HNSW index storage with negligible
retrieval-quality impact; dimensions stay at 1536, so existing vectors are
cast in place. Requires the Postgres ``vector`` extension >= 0.7.0
(``SELECT extversion FROM pg_extension WHERE extname = 'vector'``; if older,
``ALTER EXTENSION vector UPDATE`` — or recreate a stale local compose volume).
The extension is deliberately not auto-updated here: the statement fails when
already current, and extension ownership varies on managed Postgres.

"""
from typing import Sequence, Union

from alembic import op

revision: str = "0028_embedding_halfvec"
down_revision: Union[str, None] = "0027_talk_to_person_after"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("DROP INDEX IF EXISTS knowledge_chunks_embedding_hnsw_idx")
    op.execute(
        "ALTER TABLE knowledge_chunks ALTER COLUMN embedding "
        "TYPE halfvec(1536) USING embedding::halfvec(1536)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS knowledge_chunks_embedding_hnsw_idx "
        "ON knowledge_chunks USING hnsw (embedding halfvec_cosine_ops)"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS knowledge_chunks_embedding_hnsw_idx")
    op.execute(
        "ALTER TABLE knowledge_chunks ALTER COLUMN embedding "
        "TYPE vector(1536) USING embedding::vector(1536)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS knowledge_chunks_embedding_hnsw_idx "
        "ON knowledge_chunks USING hnsw (embedding vector_cosine_ops)"
    )

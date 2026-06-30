"""add HNSW index on knowledge_chunks.embedding (cosine)

Revision ID: 0009_knowledge_chunk_hnsw_index
Revises: 0008_business_tts_speed
Create Date: 2026-06-30

"""
from typing import Sequence, Union

from alembic import op

revision: str = "0009_knowledge_chunk_hnsw_index"
down_revision: Union[str, None] = "0008_business_tts_speed"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Approximate-nearest-neighbour index for cosine distance. Matches the
    # `embedding <=> query` (cosine_distance) ordering used by the search query,
    # so it can replace the sequential scan as the table grows.
    op.execute(
        "CREATE INDEX IF NOT EXISTS knowledge_chunks_embedding_hnsw_idx "
        "ON knowledge_chunks USING hnsw (embedding vector_cosine_ops)"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS knowledge_chunks_embedding_hnsw_idx")

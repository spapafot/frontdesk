"""switch embeddings to OpenAI text-embedding-3-small (1536 dims)

Revision ID: 0011_embedding_dim_1536
Revises: 0010_business_public_key
Create Date: 2026-06-30

Changing the embedding model changes the vector dimensions, and old vectors are
not comparable to new ones. We drop the ANN index, clear existing chunk vectors
(chunks are rebuilt from each document's stored content via reingest_documents.py),
widen the column to 1536 dims, then recreate the HNSW index.

"""
from typing import Sequence, Union

from alembic import op

revision: str = "0011_embedding_dim_1536"
down_revision: Union[str, None] = "0010_business_public_key"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("DROP INDEX IF EXISTS knowledge_chunks_embedding_hnsw_idx")
    # Old 384-dim vectors can't be cast to 1536; clear them. Documents keep their
    # text, so reingest_documents.py rebuilds the chunks with the new model.
    op.execute("TRUNCATE TABLE knowledge_chunks")
    op.execute("ALTER TABLE knowledge_chunks ALTER COLUMN embedding TYPE vector(1536)")
    op.execute(
        "CREATE INDEX IF NOT EXISTS knowledge_chunks_embedding_hnsw_idx "
        "ON knowledge_chunks USING hnsw (embedding vector_cosine_ops)"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS knowledge_chunks_embedding_hnsw_idx")
    op.execute("TRUNCATE TABLE knowledge_chunks")
    op.execute("ALTER TABLE knowledge_chunks ALTER COLUMN embedding TYPE vector(384)")
    op.execute(
        "CREATE INDEX IF NOT EXISTS knowledge_chunks_embedding_hnsw_idx "
        "ON knowledge_chunks USING hnsw (embedding vector_cosine_ops)"
    )

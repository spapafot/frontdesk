from types import SimpleNamespace

from pgvector.sqlalchemy import HALFVEC
from sqlalchemy.dialects import postgresql

from app.core.config import settings
from app.models.knowledge import KnowledgeChunk
from app.repositories.knowledge_repository import KnowledgeRepository


def test_embedding_column_is_half_precision():
    column_type = KnowledgeChunk.embedding.type
    assert isinstance(column_type, HALFVEC)
    assert column_type.dim == settings.embedding_dim == 1536


async def test_semantic_search_orders_by_cosine_distance():
    chunk = SimpleNamespace(id=1)

    class FakeResult:
        def all(self):
            return [(chunk, "Pricing", 0.12)]

    class FakeSession:
        def __init__(self):
            self.statement = None

        async def execute(self, statement):
            self.statement = statement
            return FakeResult()

    session = FakeSession()
    rows = await KnowledgeRepository(session).search(
        7, [0.1] * settings.embedding_dim, limit=5
    )

    sql = str(session.statement.compile(dialect=postgresql.dialect()))
    assert "<=>" in sql
    assert rows == [(chunk, "Pricing", 0.12)]


async def test_full_text_search_is_or_based_ranked_and_language_neutral():
    chunk = SimpleNamespace(id=1)

    class FakeResult:
        def all(self):
            return [(chunk, "Pricing", 0.75)]

    class FakeSession:
        def __init__(self):
            self.statement = None

        async def execute(self, statement):
            self.statement = statement
            return FakeResult()

    session = FakeSession()
    rows = await KnowledgeRepository(session).search_text(
        7, ["τιμή", "price", "price"], limit=5
    )

    compiled = session.statement.compile(dialect=postgresql.dialect())
    sql = str(compiled)
    assert "to_tsvector('simple', knowledge_chunks.content)" in sql
    assert "to_tsvector('simple', knowledge_documents.title)" in sql
    assert "@@" in sql
    assert "ts_rank_cd" in sql
    assert "DESC" in sql
    assert "τιμή | price" in compiled.params.values()
    assert rows == [(chunk, "Pricing", 0.75)]


async def test_full_text_search_skips_empty_terms():
    class NoExecuteSession:
        async def execute(self, _statement):
            raise AssertionError("empty lexical search must not hit the database")

    assert await KnowledgeRepository(NoExecuteSession()).search_text(7, [], limit=5) == []

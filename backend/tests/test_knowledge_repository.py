from types import SimpleNamespace

from sqlalchemy.dialects import postgresql

from app.repositories.knowledge_repository import KnowledgeRepository


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

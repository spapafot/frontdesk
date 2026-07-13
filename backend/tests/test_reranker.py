from types import SimpleNamespace

from app.services import rag_service, reranker


async def test_rerank_skipped_without_key(monkeypatch, settings):
    monkeypatch.setattr(settings, "rag_reranker", True)
    monkeypatch.setattr(settings, "jina_api_key", "")

    async def _no_request(_payload):
        raise AssertionError("rerank must not call the API without a key")

    monkeypatch.setattr(reranker, "_request", _no_request)

    assert await reranker.rerank("q", ["a", "b"], top_n=2) is None


async def test_rerank_skipped_when_disabled(monkeypatch, settings):
    monkeypatch.setattr(settings, "rag_reranker", False)
    monkeypatch.setattr(settings, "jina_api_key", "test-key")

    async def _no_request(_payload):
        raise AssertionError("rerank must not run when disabled")

    monkeypatch.setattr(reranker, "_request", _no_request)

    assert await reranker.rerank("q", ["a", "b"], top_n=2) is None


async def test_rerank_returns_reordered_indices_and_truncates_docs(monkeypatch, settings):
    monkeypatch.setattr(settings, "rag_reranker", True)
    monkeypatch.setattr(settings, "jina_api_key", "test-key")
    monkeypatch.setattr(settings, "rag_rerank_snippet_chars", 5)
    sent: dict = {}

    async def _request(payload):
        sent.update(payload)
        return {"results": [{"index": 2}, {"index": 0}]}

    monkeypatch.setattr(reranker, "_request", _request)

    order = await reranker.rerank("query", ["first-doc", "second", "third-doc"], top_n=2)

    assert order == [2, 0]
    # Documents are truncated to the snippet length before they leave the process.
    assert sent["documents"] == ["first", "secon", "third"]
    assert sent["top_n"] == 2


async def test_rerank_drops_out_of_range_or_duplicate_indices(monkeypatch, settings):
    monkeypatch.setattr(settings, "rag_reranker", True)
    monkeypatch.setattr(settings, "jina_api_key", "test-key")

    async def _request(_payload):
        return {"results": [{"index": 1}, {"index": 9}, {"index": 1}, {"index": 0}]}

    monkeypatch.setattr(reranker, "_request", _request)

    order = await reranker.rerank("q", ["a", "b"], top_n=5)

    assert order == [1, 0]


async def test_rerank_degrades_on_error(monkeypatch, settings):
    monkeypatch.setattr(settings, "rag_reranker", True)
    monkeypatch.setattr(settings, "jina_api_key", "test-key")

    async def _request(_payload):
        raise RuntimeError("jina unavailable")

    monkeypatch.setattr(reranker, "_request", _request)

    assert await reranker.rerank("q", ["a", "b"], top_n=2) is None


def _fake_repo_returning(rows):
    class FakeRepository:
        async def search(self, _profile_id, _embedding, limit):
            return rows

        async def search_text(self, _profile_id, terms, limit):
            return []

    return FakeRepository()


async def test_search_knowledge_applies_rerank_order(monkeypatch):
    # Three chunks retrieved; the reranker prefers the lowest-scoring one.
    rows = [
        (SimpleNamespace(id=1, document_id=10, content="alpha"), "Doc", 0.2),
        (SimpleNamespace(id=2, document_id=10, content="beta"), "Doc", 0.4),
        (SimpleNamespace(id=3, document_id=10, content="gamma"), "Doc", 0.6),
    ]
    monkeypatch.setattr(rag_service, "KnowledgeRepository", lambda _s: _fake_repo_returning(rows))

    async def embed(_query):
        return [0.1, 0.2]

    async def no_contextualize(query, _history):
        return query

    async def fake_rerank(_query, documents, top_n):
        # Reverse the retrieval order: gamma, beta, then keep top_n=2.
        return [2, 1]

    monkeypatch.setattr(rag_service, "embed_query", embed)
    monkeypatch.setattr(rag_service, "contextualize_query", no_contextualize)
    monkeypatch.setattr(rag_service, "rerank", fake_rerank)

    results = await rag_service.search_knowledge(SimpleNamespace(), 7, "q", limit=2)

    assert [r["chunk_id"] for r in results] == [3, 2]


async def test_search_knowledge_backfills_partial_rerank(monkeypatch):
    rows = [
        (SimpleNamespace(id=1, document_id=10, content="alpha"), "Doc", 0.2),
        (SimpleNamespace(id=2, document_id=10, content="beta"), "Doc", 0.4),
        (SimpleNamespace(id=3, document_id=10, content="gamma"), "Doc", 0.6),
    ]
    monkeypatch.setattr(rag_service, "KnowledgeRepository", lambda _s: _fake_repo_returning(rows))

    async def embed(_query):
        return [0.1, 0.2]

    async def no_contextualize(query, _history):
        return query

    async def fake_rerank(_query, documents, top_n):
        # Reranker only returns one index; the rest must be backfilled by score.
        return [2]

    monkeypatch.setattr(rag_service, "embed_query", embed)
    monkeypatch.setattr(rag_service, "contextualize_query", no_contextualize)
    monkeypatch.setattr(rag_service, "rerank", fake_rerank)

    results = await rag_service.search_knowledge(SimpleNamespace(), 7, "q", limit=3)

    # gamma (reranked first), then best-by-score of the remainder: alpha (0.2), beta (0.4).
    assert [r["chunk_id"] for r in results] == [3, 1, 2]


async def test_search_knowledge_keeps_score_order_when_rerank_unavailable(monkeypatch):
    rows = [
        (SimpleNamespace(id=1, document_id=10, content="alpha"), "Doc", 0.2),
        (SimpleNamespace(id=2, document_id=10, content="beta"), "Doc", 0.6),
    ]
    monkeypatch.setattr(rag_service, "KnowledgeRepository", lambda _s: _fake_repo_returning(rows))

    async def embed(_query):
        return [0.1, 0.2]

    async def no_contextualize(query, _history):
        return query

    async def no_rerank(_query, documents, top_n):
        return None

    monkeypatch.setattr(rag_service, "embed_query", embed)
    monkeypatch.setattr(rag_service, "contextualize_query", no_contextualize)
    monkeypatch.setattr(rag_service, "rerank", no_rerank)

    results = await rag_service.search_knowledge(SimpleNamespace(), 7, "q", limit=2)

    # Lower cosine distance -> higher score -> first. id=1 (0.2) outranks id=2 (0.6).
    assert [r["chunk_id"] for r in results] == [1, 2]

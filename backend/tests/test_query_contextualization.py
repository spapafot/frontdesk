import json
from types import SimpleNamespace

from app.services import query_contextualization, rag_service


def _fake_client(content: str):
    """A stand-in AsyncOpenAI whose chat completion returns ``content``."""

    class _Completions:
        def __init__(self):
            self.calls: list[dict] = []

        async def create(self, **kwargs):
            self.calls.append(kwargs)
            message = SimpleNamespace(content=content)
            return SimpleNamespace(choices=[SimpleNamespace(message=message)])

    return SimpleNamespace(chat=SimpleNamespace(completions=_Completions()))


async def test_contextualize_query_rewrites_follow_up_with_bounded_history(
    monkeypatch, settings
):
    monkeypatch.setattr(settings, "rag_query_contextualization", True)
    monkeypatch.setattr(settings, "deepseek_api_key", "test-key")
    monkeypatch.setattr(settings, "rag_query_context_messages", 2)
    monkeypatch.setattr(settings, "rag_query_context_chars", 1000)
    client = _fake_client('Standalone query: "What is the price of Acme Pro?"')
    monkeypatch.setattr(query_contextualization, "_client", lambda: client)

    history = [
        {"role": "user", "content": "This old turn must be excluded."},
        {"role": "assistant", "content": "Acme offers Basic and Acme Pro."},
        {"role": "user", "content": "Tell me about Acme Pro."},
    ]
    result = await query_contextualization.contextualize_query(
        "What about the price?", history
    )

    assert result == "What is the price of Acme Pro?"
    call = client.chat.completions.calls[0]
    payload = json.loads(call["messages"][1]["content"])
    assert payload == {
        "conversation_history": history[-2:],
        "latest_user_message": "What about the price?",
    }
    assert call["temperature"] == 0
    assert call["max_tokens"] == 128


async def test_contextualize_query_skips_first_turn(monkeypatch, settings):
    monkeypatch.setattr(settings, "rag_query_contextualization", True)
    monkeypatch.setattr(settings, "deepseek_api_key", "test-key")

    def _no_client():
        raise AssertionError("a first-turn query must not trigger a rewrite call")

    monkeypatch.setattr(query_contextualization, "_client", _no_client)

    assert await query_contextualization.contextualize_query("What are your hours?") == (
        "What are your hours?"
    )


async def test_contextualize_query_falls_back_on_client_error(monkeypatch, settings):
    monkeypatch.setattr(settings, "rag_query_contextualization", True)
    monkeypatch.setattr(settings, "deepseek_api_key", "test-key")

    class _Boom:
        async def create(self, **kwargs):
            raise RuntimeError("provider unavailable")

    client = SimpleNamespace(chat=SimpleNamespace(completions=_Boom()))
    monkeypatch.setattr(query_contextualization, "_client", lambda: client)

    query = "What about the price?"
    assert await query_contextualization.contextualize_query(
        query, [{"role": "user", "content": "Tell me about Acme Pro."}]
    ) == query


async def test_search_uses_literal_and_standalone_queries_and_reranks_standalone(
    monkeypatch,
):
    chunk = SimpleNamespace(id=1, document_id=10, content="Acme Pro costs EUR 50")

    class FakeRepository:
        async def search(self, _profile_id, _embedding, limit):
            return [(chunk, "Pricing", 0.4)]

        async def search_text(self, _profile_id, terms, limit):
            return []

    embedded: list[str] = []
    reranked_with: list[str] = []

    async def embed(query):
        embedded.append(query)
        return [0.1, 0.2]

    async def contextualize(query, history):
        assert history == [{"role": "user", "content": "Tell me about Acme Pro."}]
        return "What is the price of Acme Pro?"

    async def rerank(query, documents, top_n):
        reranked_with.append(query)
        return [0]

    monkeypatch.setattr(rag_service, "KnowledgeRepository", lambda _session: FakeRepository())
    monkeypatch.setattr(rag_service, "embed_query", embed)
    monkeypatch.setattr(rag_service, "contextualize_query", contextualize)
    monkeypatch.setattr(rag_service, "rerank", rerank)

    results = await rag_service.search_knowledge(
        SimpleNamespace(),
        7,
        "What about the price?",
        limit=8,
        history=[{"role": "user", "content": "Tell me about Acme Pro."}],
    )

    assert set(embedded) == {
        "What is the price of Acme Pro?",
        "What about the price?",
    }
    assert reranked_with == ["What is the price of Acme Pro?"]
    assert [result["chunk_id"] for result in results] == [1]


async def test_search_survives_a_failing_literal_variant(monkeypatch):
    chunk = SimpleNamespace(id=2, document_id=11, content="good chunk")

    class FakeRepository:
        async def search(self, _profile_id, _embedding, limit):
            return [(chunk, "Doc", 0.3)]

        async def search_text(self, _profile_id, terms, limit):
            return []

    async def embed(query):
        if query == "boom":
            raise RuntimeError("embedding backend down")
        return [0.1, 0.2]

    async def contextualize(query, history):
        return "healthy standalone query"

    monkeypatch.setattr(rag_service, "KnowledgeRepository", lambda _session: FakeRepository())
    monkeypatch.setattr(rag_service, "embed_query", embed)
    monkeypatch.setattr(rag_service, "contextualize_query", contextualize)

    results = await rag_service.search_knowledge(
        SimpleNamespace(), 7, "boom", limit=8, history=[{"role": "user", "content": "x"}]
    )

    assert [result["chunk_id"] for result in results] == [2]

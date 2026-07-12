from types import SimpleNamespace

from app.services import query_expansion, rag_service


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


async def test_expand_query_parses_cleans_and_caps(monkeypatch, settings):
    monkeypatch.setattr(settings, "rag_query_expansion", True)
    monkeypatch.setattr(settings, "deepseek_api_key", "test-key")
    monkeypatch.setattr(settings, "rag_query_expansion_count", 3)
    raw = (
        "1. καταληκτική ημερομηνία παραλαβής προσφορών\n"
        '- "τελευταία μέρα υποβολής"\n'
        "\n"
        "προθεσμία κατάθεσης\n"
        "μία παραπάνω γραμμή που πρέπει να κοπεί\n"
    )
    monkeypatch.setattr(query_expansion, "_client", lambda: _fake_client(raw))

    result = await query_expansion.expand_query("πότε είναι η προθεσμία υποβολής;")

    assert result == [
        "καταληκτική ημερομηνία παραλαβής προσφορών",
        "τελευταία μέρα υποβολής",
        "προθεσμία κατάθεσης",
    ]


async def test_expand_query_skipped_without_chat_key(monkeypatch, settings):
    monkeypatch.setattr(settings, "rag_query_expansion", True)
    monkeypatch.setattr(settings, "deepseek_api_key", "")

    def _no_client():
        raise AssertionError("expansion must not build a client without a chat key")

    monkeypatch.setattr(query_expansion, "_client", _no_client)

    assert await query_expansion.expand_query("οτιδήποτε") == []


async def test_expand_query_skipped_when_disabled(monkeypatch, settings):
    monkeypatch.setattr(settings, "rag_query_expansion", False)
    monkeypatch.setattr(settings, "deepseek_api_key", "test-key")

    def _no_client():
        raise AssertionError("expansion must not run when disabled")

    monkeypatch.setattr(query_expansion, "_client", _no_client)

    assert await query_expansion.expand_query("οτιδήποτε") == []


async def test_expand_query_degrades_on_client_error(monkeypatch, settings):
    monkeypatch.setattr(settings, "rag_query_expansion", True)
    monkeypatch.setattr(settings, "deepseek_api_key", "test-key")

    class _Boom:
        async def create(self, **kwargs):
            raise RuntimeError("provider unavailable")

    client = SimpleNamespace(chat=SimpleNamespace(completions=_Boom()))
    monkeypatch.setattr(query_expansion, "_client", lambda: client)

    assert await query_expansion.expand_query("οτιδήποτε") == []


async def test_search_knowledge_retrieves_on_expansions(monkeypatch):
    """Paraphrases from expansion are embedded and searched alongside the query."""
    chunk = SimpleNamespace(id=1, document_id=10, content="deadline chunk")

    class FakeRepository:
        async def search(self, _profile_id, _embedding, limit):
            return [(chunk, "Tender", 0.4)]

        async def search_text(self, _profile_id, terms, limit):
            return []

    embedded: list[str] = []

    async def embed(query):
        embedded.append(query)
        return [0.1, 0.2]

    async def fake_expand(query):
        return ["καταληκτική ημερομηνία παραλαβής των προσφορών"]

    monkeypatch.setattr(rag_service, "KnowledgeRepository", lambda _session: FakeRepository())
    monkeypatch.setattr(rag_service, "embed_query", embed)
    monkeypatch.setattr(rag_service, "expand_query", fake_expand)

    results = await rag_service.search_knowledge(
        SimpleNamespace(), 7, "πότε είναι η προθεσμία υποβολής;", limit=8
    )

    assert "καταληκτική ημερομηνία παραλαβής των προσφορών" in embedded
    assert "πότε είναι η προθεσμία υποβολής;" in embedded
    assert [r["chunk_id"] for r in results] == [1]


async def test_search_knowledge_survives_a_failing_variant(monkeypatch):
    """A single variant's embedding error must not sink the whole search."""
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

    async def fake_expand(query):
        return ["boom"]

    monkeypatch.setattr(rag_service, "KnowledgeRepository", lambda _session: FakeRepository())
    monkeypatch.setattr(rag_service, "embed_query", embed)
    monkeypatch.setattr(rag_service, "expand_query", fake_expand)

    results = await rag_service.search_knowledge(
        SimpleNamespace(), 7, "healthy query", limit=8
    )

    assert [r["chunk_id"] for r in results] == [2]

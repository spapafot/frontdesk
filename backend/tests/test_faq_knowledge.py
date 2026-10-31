from datetime import datetime, timezone
from types import SimpleNamespace

import pytest
from pydantic import ValidationError

from app.api.routes import knowledge
from app.schemas.knowledge import FaqRequest
from app.services import ingestion_service

QUESTION = "What are your opening hours?"
ANSWER = "We are open 9am to 5pm, Monday to Friday."


class _Session:
    def __init__(self):
        self.commits = 0
        self.rollbacks = 0

    async def commit(self):
        self.commits += 1

    async def rollback(self):
        self.rollbacks += 1

    async def flush(self):
        return None


def _faq_document(**overrides):
    base = dict(
        id=42,
        profile_id=7,
        title=QUESTION,
        type="faq",
        source_url=None,
        content=ANSWER,
        is_active=True,
        processing_status="ready",
        storage_key=None,
        processing_error=None,
        created_at=datetime.now(timezone.utc),
        processed_at=datetime.now(timezone.utc),
    )
    base.update(overrides)
    return SimpleNamespace(**base)


def _configure(monkeypatch, calls, *, existing=None, embed=None):
    """Patch the repository/embeddings at the ingestion_service module level:
    the route calls the real ingest helpers, which resolve their globals there."""

    class _Repo:
        def __init__(self, session):
            pass

        async def create_document(self, **kwargs):
            calls["document"] = kwargs
            return _faq_document(**kwargs)

        async def add_chunk(self, **kwargs):
            calls.setdefault("chunks", []).append(kwargs)

        async def delete_chunks(self, document_id):
            calls["deleted_chunks"] = document_id

        async def get_document(self, profile_id, document_id):
            calls["get_document"] = (profile_id, document_id)
            return existing

        async def list_chunks(self, document_id):
            return [SimpleNamespace(id=1, content=f"{QUESTION}\n{ANSWER}")]

    async def _embed(text):
        calls.setdefault("embedded", []).append(text)
        if embed is not None:
            return embed(text)
        return [0.0] * 3

    monkeypatch.setattr(knowledge, "KnowledgeRepository", _Repo)
    monkeypatch.setattr(ingestion_service, "KnowledgeRepository", _Repo)
    monkeypatch.setattr(ingestion_service, "embed_passage", _embed)


async def test_add_faq_creates_ready_active_document_with_chunks(monkeypatch):
    calls: dict = {}
    _configure(monkeypatch, calls)
    session = _Session()

    result = await knowledge.add_faq(
        body=SimpleNamespace(question=QUESTION, answer=ANSWER),
        session=session,
        profile=SimpleNamespace(id=7, owner_user_id="owner-1"),
    )

    assert result.type == "faq"
    assert result.processing_status == "ready"
    assert result.is_active is True
    assert result.chunk_count == 1
    # The answer is echoed so the edit dialog can prefill without a round-trip.
    assert result.content == ANSWER
    assert calls["document"]["title"] == QUESTION
    assert calls["document"]["content"] == ANSWER
    assert calls["document"]["processed_at"] is not None
    assert "storage_key" not in calls["document"]
    assert "source_url" not in calls["document"]
    # The indexed chunk carries both question and answer for retrieval.
    (chunk,) = calls["chunks"]
    assert QUESTION in chunk["content"]
    assert ANSWER in chunk["content"]
    assert chunk["meta"] == {"title": QUESTION}
    assert session.commits == 1


async def test_add_faq_does_not_require_aws_ingestion(monkeypatch):
    calls: dict = {}
    _configure(monkeypatch, calls)

    async def _forbidden(*args, **kwargs):  # pragma: no cover - must not run
        raise AssertionError("FAQ ingestion must not touch S3/SQS")

    monkeypatch.setattr(knowledge.aws_ingestion, "is_configured", lambda: False)
    monkeypatch.setattr(knowledge.aws_ingestion, "upload_source", _forbidden)
    monkeypatch.setattr(knowledge.aws_ingestion, "enqueue", _forbidden)

    result = await knowledge.add_faq(
        body=SimpleNamespace(question=QUESTION, answer=ANSWER),
        session=_Session(),
        profile=SimpleNamespace(id=7, owner_user_id="owner-1"),
    )
    assert result.processing_status == "ready"


async def test_add_faq_embedding_failure_rolls_back_with_502(monkeypatch):
    calls: dict = {}

    def _boom(text):
        raise RuntimeError("embeddings API down")

    _configure(monkeypatch, calls, embed=_boom)
    session = _Session()

    with pytest.raises(Exception) as exc:
        await knowledge.add_faq(
            body=SimpleNamespace(question=QUESTION, answer=ANSWER),
            session=session,
            profile=SimpleNamespace(id=7, owner_user_id="owner-1"),
        )
    assert getattr(exc.value, "status_code", None) == 502
    assert session.rollbacks == 1
    assert session.commits == 0


async def test_add_faq_unindexable_text_returns_422(monkeypatch):
    calls: dict = {}
    _configure(monkeypatch, calls)
    session = _Session()

    # Passes length checks but every chunk fails the junk filter (no alnum).
    with pytest.raises(Exception) as exc:
        await knowledge.add_faq(
            body=SimpleNamespace(question=".....", answer=".........."),
            session=session,
            profile=SimpleNamespace(id=7, owner_user_id="owner-1"),
        )
    assert getattr(exc.value, "status_code", None) == 422
    assert session.rollbacks == 1
    assert "chunks" not in calls


def test_faq_request_validation():
    with pytest.raises(ValidationError):
        FaqRequest(question="Why?", answer=ANSWER)  # question < 5 chars
    with pytest.raises(ValidationError):
        FaqRequest(question=QUESTION, answer="Too short")  # answer < 10 chars
    with pytest.raises(ValidationError):
        FaqRequest(question="q" * 256, answer=ANSWER)
    with pytest.raises(ValidationError):
        FaqRequest(question=QUESTION, answer="a" * 4001)
    trimmed = FaqRequest(question=f"  {QUESTION}  ", answer=f"  {ANSWER}  ")
    assert trimmed.question == QUESTION
    assert trimmed.answer == ANSWER


async def test_update_faq_replaces_chunks_and_preserves_active(monkeypatch):
    calls: dict = {}
    document = _faq_document(is_active=False, processed_at=None)
    _configure(monkeypatch, calls, existing=document)
    session = _Session()

    new_question = "When do you close on weekends?"
    new_answer = "We are closed on Saturdays and Sundays."
    result = await knowledge.update_faq(
        document_id=42,
        body=SimpleNamespace(question=new_question, answer=new_answer),
        session=session,
        profile=SimpleNamespace(id=7, owner_user_id="owner-1"),
    )

    assert calls["deleted_chunks"] == 42
    (chunk,) = calls["chunks"]
    assert new_question in chunk["content"]
    assert new_answer in chunk["content"]
    assert document.title == new_question
    assert document.content == new_answer
    assert document.processing_status == "ready"
    assert document.processed_at is not None
    # Editing a disabled FAQ must not silently re-enable it.
    assert document.is_active is False
    assert result.is_active is False
    assert result.content == new_answer
    assert session.commits == 1


async def test_update_faq_rejects_non_faq_document(monkeypatch):
    calls: dict = {}
    document = _faq_document(type="url", source_url="https://example.com")
    _configure(monkeypatch, calls, existing=document)

    with pytest.raises(Exception) as exc:
        await knowledge.update_faq(
            document_id=42,
            body=SimpleNamespace(question=QUESTION, answer=ANSWER),
            session=_Session(),
            profile=SimpleNamespace(id=7, owner_user_id="owner-1"),
        )
    assert getattr(exc.value, "status_code", None) == 409
    assert "deleted_chunks" not in calls


async def test_update_faq_missing_document_returns_404(monkeypatch):
    calls: dict = {}
    _configure(monkeypatch, calls, existing=None)

    with pytest.raises(Exception) as exc:
        await knowledge.update_faq(
            document_id=42,
            body=SimpleNamespace(question=QUESTION, answer=ANSWER),
            session=_Session(),
            profile=SimpleNamespace(id=7, owner_user_id="owner-1"),
        )
    assert getattr(exc.value, "status_code", None) == 404


async def test_preview_returns_chunks_for_ready_faq(monkeypatch):
    calls: dict = {}
    _configure(monkeypatch, calls, existing=_faq_document())

    chunks = await knowledge.preview_chunks(
        document_id=42, session=_Session(), profile=SimpleNamespace(id=7, owner_user_id="owner-1")
    )

    assert len(chunks) == 1
    assert QUESTION in chunks[0].content

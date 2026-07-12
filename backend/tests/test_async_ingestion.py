from types import SimpleNamespace
from datetime import datetime, timezone

import pytest

from app.api.routes import knowledge


class _Upload:
    filename = "guide.txt"
    content_type = "text/plain"

    async def read(self):
        return b"Useful document content"


class _Session:
    async def commit(self):
        return None

    async def rollback(self):
        return None


@pytest.mark.asyncio
async def test_upload_stores_and_queues_document(monkeypatch):
    calls: dict = {}
    document = SimpleNamespace(
        id=42,
        title="guide.txt",
        type="txt",
        is_active=False,
        processing_status="queued",
        created_at=datetime.now(timezone.utc),
        processed_at=None,
    )

    class _Repo:
        def __init__(self, session):
            pass

        async def create_document(self, **kwargs):
            calls["document"] = kwargs
            return document

    async def _upload(key, data, content_type):
        calls["upload"] = (key, data, content_type)

    async def _enqueue(payload):
        calls["message"] = payload

    monkeypatch.setattr(knowledge, "KnowledgeRepository", _Repo)
    monkeypatch.setattr(knowledge.aws_ingestion, "is_configured", lambda: True)
    monkeypatch.setattr(knowledge.aws_ingestion, "upload_source", _upload)
    monkeypatch.setattr(knowledge.aws_ingestion, "enqueue", _enqueue)

    result = await knowledge.upload_document(
        file=_Upload(), session=_Session(), profile=SimpleNamespace(id=7)
    )

    assert result.processing_status == "queued"
    assert calls["document"]["is_active"] is False
    assert calls["upload"][1] == b"Useful document content"
    assert calls["message"]["document_id"] == 42
    assert calls["message"]["profile_id"] == 7


@pytest.mark.asyncio
async def test_pending_document_cannot_be_toggled(monkeypatch):
    document = SimpleNamespace(processing_status="processing")

    class _Repo:
        def __init__(self, session):
            pass

        async def get_document(self, profile_id, document_id):
            return document

    monkeypatch.setattr(knowledge, "KnowledgeRepository", _Repo)
    with pytest.raises(Exception) as exc:
        await knowledge.toggle_document(
            document_id=1,
            body=SimpleNamespace(is_active=True),
            session=_Session(),
            profile=SimpleNamespace(id=7),
        )
    assert getattr(exc.value, "status_code", None) == 409

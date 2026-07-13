from datetime import datetime, timezone
from types import SimpleNamespace

from app.services import ingestion_service


class _Session:
    async def flush(self):
        return None


class _Repo:
    def __init__(self, session):
        pass

    async def delete_chunks(self, document_id):
        return None

    async def add_chunk(self, **kwargs):
        return None


async def _process(monkeypatch, *, is_active, processed_at, preserve_active):
    async def _embed(_chunk):
        return [0.0, 0.1, 0.2]

    monkeypatch.setattr(ingestion_service, "embed_passage", _embed)
    monkeypatch.setattr(ingestion_service, "KnowledgeRepository", _Repo)

    document = SimpleNamespace(
        id=1,
        profile_id=7,
        title="Pricing",
        content="",
        is_active=is_active,
        processing_status="queued",
        processing_error="stale",
        processed_at=processed_at,
    )
    count = await ingestion_service.process_existing_document(
        _Session(),
        document,
        "page.txt",
        b"This is a readable body with enough text to survive chunk filtering.",
        preserve_active=preserve_active,
    )
    return document, count


async def test_first_ingest_activates_and_marks_ready(monkeypatch):
    document, count = await _process(
        monkeypatch, is_active=False, processed_at=None, preserve_active=False
    )
    assert count == 1
    assert document.processing_status == "ready"
    assert document.processing_error is None
    assert document.is_active is True


async def test_rescan_keeps_disabled_entry_disabled(monkeypatch):
    document, _ = await _process(
        monkeypatch,
        is_active=False,
        processed_at=datetime.now(timezone.utc),
        preserve_active=True,
    )
    assert document.processing_status == "ready"
    # A disabled page stays disabled after a content refresh.
    assert document.is_active is False


async def test_rescan_keeps_enabled_entry_enabled(monkeypatch):
    document, _ = await _process(
        monkeypatch,
        is_active=True,
        processed_at=datetime.now(timezone.utc),
        preserve_active=True,
    )
    assert document.is_active is True

from datetime import datetime, timezone
from types import SimpleNamespace

import pytest

from app.api.routes import knowledge
from app.services.jina_reader import JinaReaderError


class _Session:
    async def commit(self):
        return None

    async def rollback(self):
        return None


def _url_document(**overrides):
    base = dict(
        id=42,
        title="Example",
        type="url",
        source_url="https://example.com/page",
        is_active=False,
        processing_status="queued",
        storage_key=None,
        processing_error=None,
        created_at=datetime.now(timezone.utc),
        processed_at=None,
    )
    base.update(overrides)
    return SimpleNamespace(**base)


def _configure(monkeypatch, calls, *, configured=True, existing=None, fetch=None):
    document = _url_document()

    class _Repo:
        def __init__(self, session):
            pass

        async def get_by_source_url(self, profile_id, url):
            calls["dedup"] = (profile_id, url)
            return existing

        async def create_document(self, **kwargs):
            calls["document"] = kwargs
            return document

        async def get_document(self, profile_id, document_id):
            return document

    async def _upload(key, data, content_type):
        calls["upload"] = (key, data, content_type)

    async def _enqueue(payload):
        calls["message"] = payload

    async def _fetch(url, *, no_cache=False):
        calls["fetch"] = (url, no_cache)
        if fetch is not None:
            return fetch(url, no_cache)
        return ("Example", "# Heading\n\nBody text")

    monkeypatch.setattr(knowledge, "KnowledgeRepository", _Repo)
    monkeypatch.setattr(knowledge.aws_ingestion, "is_configured", lambda: configured)
    monkeypatch.setattr(knowledge.aws_ingestion, "upload_source", _upload)
    monkeypatch.setattr(knowledge.aws_ingestion, "enqueue", _enqueue)
    monkeypatch.setattr(knowledge.jina_reader, "fetch_url", _fetch)
    return document


async def test_add_link_fetches_stores_and_queues(monkeypatch):
    calls: dict = {}
    _configure(monkeypatch, calls)

    result = await knowledge.add_link(
        body=SimpleNamespace(url="https://example.com/page"),
        session=_Session(),
        profile=SimpleNamespace(id=7),
    )

    assert result.processing_status == "queued"
    assert result.type == "url"
    assert result.source_url == "https://example.com/page"
    # Persisted as a link source, inactive until processed.
    assert calls["document"]["type"] == "url"
    assert calls["document"]["source_url"] == "https://example.com/page"
    assert calls["document"]["is_active"] is False
    # The fetched markdown is what gets stored, encoded as UTF-8 bytes.
    assert calls["upload"][1] == b"# Heading\n\nBody text"
    assert calls["fetch"] == ("https://example.com/page", False)
    # The Lambda selects its text extractor from the filename, so it must be .txt.
    assert calls["message"]["filename"] == "page.txt"
    assert calls["message"]["document_id"] == 42
    assert calls["message"]["profile_id"] == 7
    assert calls["message"]["storage_key"].startswith("profiles/7/")
    # A first ingest activates the entry on completion (no preserve flag).
    assert calls["message"].get("preserve_active") is not True


async def test_add_link_requires_ingestion_configured(monkeypatch):
    calls: dict = {}
    _configure(monkeypatch, calls, configured=False)

    with pytest.raises(Exception) as exc:
        await knowledge.add_link(
            body=SimpleNamespace(url="https://example.com/page"),
            session=_Session(),
            profile=SimpleNamespace(id=7),
        )
    assert getattr(exc.value, "status_code", None) == 503


async def test_add_link_rejects_duplicate_url(monkeypatch):
    calls: dict = {}
    _configure(monkeypatch, calls, existing=_url_document())

    with pytest.raises(Exception) as exc:
        await knowledge.add_link(
            body=SimpleNamespace(url="https://example.com/page"),
            session=_Session(),
            profile=SimpleNamespace(id=7),
        )
    assert getattr(exc.value, "status_code", None) == 409
    assert "upload" not in calls  # never touched storage


async def test_add_link_surfaces_fetch_failure(monkeypatch):
    calls: dict = {}

    def _boom(url, no_cache):
        raise JinaReaderError("The page could not be reached.")

    _configure(monkeypatch, calls, fetch=_boom)

    with pytest.raises(Exception) as exc:
        await knowledge.add_link(
            body=SimpleNamespace(url="https://example.com/page"),
            session=_Session(),
            profile=SimpleNamespace(id=7),
        )
    assert getattr(exc.value, "status_code", None) == 502
    assert "upload" not in calls


async def test_rescan_refetches_and_requeues(monkeypatch):
    calls: dict = {}
    document = _configure(monkeypatch, calls)
    document.processing_status = "ready"
    document.storage_key = None

    result = await knowledge.rescan_document(
        document_id=42, session=_Session(), profile=SimpleNamespace(id=7)
    )

    assert result.processing_status == "queued"
    # Rescan must force a live fetch so a stale cached copy isn't re-ingested.
    assert calls["fetch"] == ("https://example.com/page", True)
    # A fresh object is uploaded and the row points at it before enqueue.
    assert document.storage_key.startswith("profiles/7/")
    assert calls["message"]["storage_key"] == document.storage_key
    assert calls["message"]["filename"] == "page.txt"
    # Rescan must keep the entry's enable/disable state instead of forcing active.
    assert calls["message"]["preserve_active"] is True


async def test_rescan_rejects_non_link_document(monkeypatch):
    calls: dict = {}
    document = _configure(monkeypatch, calls)
    document.type = "pdf"
    document.source_url = None

    with pytest.raises(Exception) as exc:
        await knowledge.rescan_document(
            document_id=42, session=_Session(), profile=SimpleNamespace(id=7)
        )
    assert getattr(exc.value, "status_code", None) == 409
    assert "fetch" not in calls

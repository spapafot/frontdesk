import pytest

from app import ingestion_handler


class _FakeEngine:
    def __init__(self):
        self.disposed = 0

    async def dispose(self):
        self.disposed += 1


async def test_handle_disposes_engine_after_processing(monkeypatch):
    fake = _FakeEngine()

    async def _noop(record):
        return None

    monkeypatch.setattr(ingestion_handler, "engine", fake)
    monkeypatch.setattr(ingestion_handler, "_process_record", _noop)

    await ingestion_handler._handle({"Records": [{"body": "{}"}]})

    assert fake.disposed == 1


async def test_handle_disposes_engine_even_on_error(monkeypatch):
    """The pool must be released within this loop even when a record raises, so
    the next warm invocation doesn't reuse a connection on a closed loop."""
    fake = _FakeEngine()

    async def _boom(record):
        raise RuntimeError("processing failed")

    monkeypatch.setattr(ingestion_handler, "engine", fake)
    monkeypatch.setattr(ingestion_handler, "_process_record", _boom)

    with pytest.raises(RuntimeError):
        await ingestion_handler._handle({"Records": [{"body": "{}"}]})

    assert fake.disposed == 1

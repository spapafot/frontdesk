import httpx
import pytest

from app.services import jina_reader
from app.services.jina_reader import JinaReaderError

_URL = "https://example.com/page"


def _install_client(monkeypatch, *, response=None, raises=None, capture=None):
    """Replace jina_reader's httpx.AsyncClient with a fake returning ``response``
    (a real httpx.Response) or raising ``raises`` from ``post``."""

    class _Client:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *exc):
            return False

        async def post(self, url, headers=None, json=None):
            if capture is not None:
                capture["url"] = url
                capture["headers"] = headers
                capture["json"] = json
            if raises is not None:
                raise raises
            return response

    monkeypatch.setattr(jina_reader.httpx, "AsyncClient", _Client)


def _response(status_code=200, body=None):
    return httpx.Response(
        status_code, json=body, request=httpx.Request("POST", jina_reader._JINA_READER_URL)
    )


async def test_fetch_url_returns_title_and_content(monkeypatch, settings):
    monkeypatch.setattr(settings, "jina_api_key", "test-key")
    capture: dict = {}
    # Default format is `text`, so Reader returns the body in the `text` field
    # (there is no `content` field in that mode) — mirror the real response.
    _install_client(
        monkeypatch,
        response=_response(body={"data": {"title": "Example", "text": "Body text"}}),
        capture=capture,
    )

    title, content = await jina_reader.fetch_url(_URL)

    assert (title, content) == ("Example", "Body text")
    assert capture["json"] == {"url": _URL}
    assert capture["headers"]["Authorization"] == "Bearer test-key"
    assert capture["headers"]["Accept"] == "application/json"
    # Defaults extract clean text and strip site chrome to cut nav boilerplate.
    assert capture["headers"]["X-Return-Format"] == "text"
    assert "nav" in capture["headers"]["X-Remove-Selector"]
    # Default add path uses the cache; only rescan bypasses it.
    assert "X-No-Cache" not in capture["headers"]
    # No site-specific target selector unless configured.
    assert "X-Target-Selector" not in capture["headers"]


async def test_fetch_url_honors_selector_settings(monkeypatch, settings):
    monkeypatch.setattr(settings, "jina_api_key", "test-key")
    monkeypatch.setattr(settings, "jina_reader_format", "markdown")
    monkeypatch.setattr(settings, "jina_reader_remove_selector", "")
    monkeypatch.setattr(settings, "jina_reader_target_selector", "main#content")
    capture: dict = {}
    _install_client(
        monkeypatch,
        response=_response(body={"data": {"title": "T", "content": "x"}}),
        capture=capture,
    )

    await jina_reader.fetch_url(_URL)

    assert capture["headers"]["X-Return-Format"] == "markdown"
    assert capture["headers"]["X-Target-Selector"] == "main#content"
    # Empty remove-selector disables the header entirely.
    assert "X-Remove-Selector" not in capture["headers"]


async def test_fetch_url_sends_no_cache_header_on_rescan(monkeypatch, settings):
    monkeypatch.setattr(settings, "jina_api_key", "test-key")
    capture: dict = {}
    _install_client(
        monkeypatch,
        response=_response(body={"data": {"title": "T", "content": "x"}}),
        capture=capture,
    )

    await jina_reader.fetch_url(_URL, no_cache=True)

    assert capture["headers"]["X-No-Cache"] == "true"


async def test_fetch_url_falls_back_to_url_when_title_missing(monkeypatch, settings):
    monkeypatch.setattr(settings, "jina_api_key", "test-key")
    _install_client(
        monkeypatch, response=_response(body={"data": {"title": "", "content": "x"}})
    )

    title, _ = await jina_reader.fetch_url(_URL)

    assert title == _URL


async def test_fetch_url_raises_without_key(monkeypatch, settings):
    monkeypatch.setattr(settings, "jina_api_key", "")

    def _fail(*a, **k):
        raise AssertionError("must not call the API without a key")

    monkeypatch.setattr(jina_reader.httpx, "AsyncClient", _fail)

    with pytest.raises(JinaReaderError):
        await jina_reader.fetch_url(_URL)


async def test_fetch_url_raises_on_empty_content(monkeypatch, settings):
    monkeypatch.setattr(settings, "jina_api_key", "test-key")
    _install_client(
        monkeypatch, response=_response(body={"data": {"title": "T", "content": "   "}})
    )

    with pytest.raises(JinaReaderError):
        await jina_reader.fetch_url(_URL)


async def test_fetch_url_raises_on_http_error(monkeypatch, settings):
    monkeypatch.setattr(settings, "jina_api_key", "test-key")
    _install_client(monkeypatch, response=_response(status_code=502, body={}))

    with pytest.raises(JinaReaderError):
        await jina_reader.fetch_url(_URL)


async def test_fetch_url_raises_on_transport_error(monkeypatch, settings):
    monkeypatch.setattr(settings, "jina_api_key", "test-key")
    _install_client(monkeypatch, raises=httpx.ConnectError("boom"))

    with pytest.raises(JinaReaderError):
        await jina_reader.fetch_url(_URL)

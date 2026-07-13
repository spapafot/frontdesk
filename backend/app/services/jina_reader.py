"""Fetch a web page as clean markdown via the Jina Reader API (r.jina.ai).

Lets an admin add a URL to the knowledge base: Reader renders the page and
returns LLM-friendly markdown, which we then chunk/embed like an uploaded file.

Unlike ``reranker`` (best-effort, degrades to ``None``), this raises
``JinaReaderError`` on any failure, because adding/rescanning a link must report
a bad URL or an unreachable page back to the admin rather than silently no-op.
Vendor-isolated: swapping Reader for another fetcher is a change to this module.
"""

import httpx

from app.core.config import settings

_JINA_READER_URL = "https://r.jina.ai/"


class JinaReaderError(RuntimeError):
    """Raised when a URL could not be fetched/parsed into usable text."""


async def fetch_url(url: str, *, no_cache: bool = False) -> tuple[str, str]:
    """Return ``(title, markdown_content)`` for ``url``.

    ``no_cache=True`` forces Reader to re-fetch the live page (used by rescan) so
    a stale cached copy is never re-ingested. Raises ``JinaReaderError`` on a
    missing key, transport/HTTP error, or empty content.
    """
    if not settings.jina_api_key:
        raise JinaReaderError("Reading web pages is not configured.")

    headers = {
        "Authorization": f"Bearer {settings.jina_api_key}",
        "Accept": "application/json",
        "X-Return-Format": settings.jina_reader_format or "text",
        # Text mode already drops images; harmless (and future-proof) to be explicit.
        "X-Retain-Images": "none",
    }
    # Strip site chrome (menus/header/footer/forms) so nav boilerplate doesn't
    # swamp the real content when chunking.
    if settings.jina_reader_remove_selector:
        headers["X-Remove-Selector"] = settings.jina_reader_remove_selector
    if settings.jina_reader_target_selector:
        headers["X-Target-Selector"] = settings.jina_reader_target_selector
    if no_cache:
        headers["X-No-Cache"] = "true"

    try:
        async with httpx.AsyncClient(timeout=settings.jina_reader_timeout) as client:
            response = await client.post(
                _JINA_READER_URL, headers=headers, json={"url": url}
            )
            response.raise_for_status()
            body = response.json()
    except httpx.HTTPStatusError as exc:
        raise JinaReaderError(
            f"The page could not be read (status {exc.response.status_code})."
        ) from exc
    except httpx.HTTPError as exc:
        raise JinaReaderError("The page could not be reached.") from exc
    except ValueError as exc:  # non-JSON body
        raise JinaReaderError("The reader returned an unexpected response.") from exc

    data = body.get("data") if isinstance(body, dict) else None
    if not isinstance(data, dict):
        raise JinaReaderError("The reader returned an unexpected response.")

    content = (data.get("content") or "").strip()
    if not content:
        raise JinaReaderError("The page had no readable content.")

    title = (data.get("title") or "").strip() or url
    return title, content

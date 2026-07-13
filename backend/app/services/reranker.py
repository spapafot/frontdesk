"""Cross-encoder reranking via the Jina Reranker API.

Retrieval (even multi-query + lexical) ranks by embedding similarity, which is
recall-oriented and noisy about ordering. A cross-encoder scores each candidate
*against the question directly*, so the passage that actually answers it rises to
the top and near-duplicate distractors sink - letting us retrieve a wide net and
still inject a small, high-signal context.

Best-effort: ``rerank`` returns ``None`` (caller keeps retrieval order) whenever
reranking is disabled, no key is configured, or the call errors/times out. It is
also feature-flagged and vendor-isolated so swapping Jina for another reranker is
a change to this module alone.
"""

import logging

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)

_JINA_RERANK_URL = "https://api.jina.ai/v1/rerank"


async def _request(payload: dict) -> dict:
    """POST to Jina and return the parsed JSON body. Raises on transport/HTTP error."""
    async with httpx.AsyncClient(timeout=settings.rag_rerank_timeout) as client:
        response = await client.post(
            _JINA_RERANK_URL,
            headers={"Authorization": f"Bearer {settings.jina_api_key}"},
            json=payload,
        )
        response.raise_for_status()
        return response.json()


async def rerank(query: str, documents: list[str], top_n: int) -> list[int] | None:
    """Return indices into ``documents`` reordered best-first, truncated to ``top_n``.

    ``None`` signals "no reranking happened" - the caller should keep its existing
    order. Only indices the API actually returned are included, so the caller must
    backfill to ``top_n`` from retrieval order if it needs a full set.
    """
    if not settings.rag_reranker or top_n <= 0 or not documents:
        return None
    if not settings.jina_api_key:
        return None

    snippet = settings.rag_rerank_snippet_chars
    payload = {
        "model": settings.jina_reranker_model,
        "query": query,
        "documents": [doc[:snippet] for doc in documents],
        "top_n": min(top_n, len(documents)),
        "return_documents": False,
    }
    try:
        data = await _request(payload)
    except Exception:  # network / auth / timeout / bad status - never block the answer
        logger.warning("rerank failed; using retrieval order", exc_info=True)
        return None

    results = data.get("results") if isinstance(data, dict) else None
    if not isinstance(results, list) or not results:
        return None

    order: list[int] = []
    seen: set[int] = set()
    for item in results:
        index = item.get("index") if isinstance(item, dict) else None
        if isinstance(index, int) and 0 <= index < len(documents) and index not in seen:
            seen.add(index)
            order.append(index)
    return order or None

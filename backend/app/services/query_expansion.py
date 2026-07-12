"""LLM query expansion for retrieval.

Before a RAG search we ask the chat model for a few alternative phrasings of the
user's question. Retrieving on those as well as the literal query closes the
vocabulary gap that otherwise sinks obvious questions — e.g. a user asking for
the "προθεσμία υποβολής" (submission deadline) when the source document only ever
says "καταληκτική ημερομηνία παραλαβής των προσφορών".

This module keeps its own OpenAI-compatible client rather than importing the one
in ``chat_service`` (which imports ``rag_service``, which imports this module) so
there is no import cycle.
"""

import logging
import re
from functools import lru_cache
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from openai import AsyncOpenAI

from app.core.config import settings

logger = logging.getLogger(__name__)

# Terse, non-thinking prompt: this runs on the chat's critical path, before the
# answer can start streaming, so latency matters more than eloquence.
_EXPANSION_SYSTEM = (
    "You rewrite a user's question into alternative search queries for a document "
    "search engine. Produce {count} short, standalone reformulations that a relevant "
    "passage might use instead of the user's wording: swap in synonyms, formal or "
    "domain terminology, and closely related phrasings. Write every reformulation in "
    "the SAME language as the question. Output ONLY the reformulations, one per line, "
    "with no numbering, bullets, quotes, or any other text."
)

# Strip leading list markers a model may add despite instructions: "1.", "2)", "-", "•".
_PREFIX_RE = re.compile(r"^\s*(?:[-*•]|\d+[.)])\s*")


@lru_cache
def _client() -> "AsyncOpenAI":
    from openai import AsyncOpenAI

    return AsyncOpenAI(
        api_key=settings.deepseek_api_key,
        base_url=settings.deepseek_base_url,
    )


def _parse(raw: str, *, limit: int) -> list[str]:
    phrasings: list[str] = []
    for line in raw.splitlines():
        cleaned = _PREFIX_RE.sub("", line).strip().strip('"').strip()
        if cleaned:
            phrasings.append(cleaned)
    return phrasings[:limit]


async def expand_query(query: str) -> list[str]:
    """Return alternative phrasings of ``query`` to widen retrieval recall.

    Best-effort: returns ``[]`` when expansion is disabled, when no chat key is
    configured, or on any client error/timeout, so the caller cleanly falls back
    to the literal query.
    """
    count = settings.rag_query_expansion_count
    if not settings.rag_query_expansion or count <= 0:
        return []
    if not settings.deepseek_api_key:
        return []

    try:
        response = await _client().chat.completions.create(
            model=settings.deepseek_model,
            messages=[
                {"role": "system", "content": _EXPANSION_SYSTEM.format(count=count)},
                {"role": "user", "content": query},
            ],
            stream=False,
            temperature=0.3,
            max_tokens=256,
            timeout=settings.rag_query_expansion_timeout,
            extra_body={"thinking": {"type": "disabled"}},
        )
    except Exception:  # network / auth / timeout — never block retrieval on this
        logger.warning("query expansion failed; using literal query only", exc_info=True)
        return []

    choices = getattr(response, "choices", None) or []
    if not choices or not choices[0].message.content:
        return []
    return _parse(choices[0].message.content, limit=count)

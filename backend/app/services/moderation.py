"""Visitor-abuse moderation via the OpenAI Moderation API.

Classifies inbound widget messages so the chat service can warn on abusive
language and auto-close a conversation after repeated flags.

Best-effort and fail-open: ``classify`` returns ``None`` (caller answers
normally) whenever moderation is disabled, no key is configured, or the call
errors/times out - a moderation outage must never block support. Vendor-
isolated so swapping providers is a change to this module alone.
"""

import logging
from dataclasses import dataclass
from functools import lru_cache
from typing import TYPE_CHECKING

from app.core.config import settings

if TYPE_CHECKING:
    from openai import AsyncOpenAI

logger = logging.getLogger(__name__)

# Categories that count as abuse strikes. Self-harm categories are deliberately
# excluded: a visitor in distress must never be warned or locked out. Plain
# "violence" is also excluded because it fires on victims describing incidents;
# threats are still caught by the */threatening categories.
STRIKE_CATEGORIES = frozenset(
    {
        "harassment",
        "harassment/threatening",
        "hate",
        "hate/threatening",
        "sexual",
        "sexual/minors",
        "violence/graphic",
    }
)


@dataclass(frozen=True)
class ModerationVerdict:
    flagged: bool
    categories: tuple[str, ...]


@lru_cache
def _client() -> "AsyncOpenAI":
    from openai import AsyncOpenAI

    return AsyncOpenAI(api_key=settings.openai_api_key)


async def _request(text: str):
    """POST to the Moderation API. Raises on transport/HTTP error."""
    return await _client().moderations.create(
        model=settings.moderation_model,
        input=text,
        timeout=settings.moderation_timeout,
    )


async def classify(text: str) -> ModerationVerdict | None:
    """Return a verdict for ``text``, or ``None`` when no verdict is possible.

    ``None`` means "answer normally": moderation disabled, no API key, blank
    input, or the API call failed. ``flagged`` is True only when at least one
    strike-eligible category fired.
    """
    if not settings.moderation_enabled or not settings.openai_api_key:
        return None
    if not text.strip():
        return None

    try:
        response = await _request(text)
        # by_alias yields API-style keys ("harassment/threatening"); filtering
        # against STRIKE_CATEGORIES makes unknown categories harmless.
        raw = response.results[0].categories.model_dump(by_alias=True)
    except Exception:  # network / auth / timeout / shape - never block the answer
        logger.warning("moderation failed; allowing message", exc_info=True)
        return None

    categories = tuple(
        sorted(name for name, hit in raw.items() if hit and name in STRIKE_CATEGORIES)
    )
    return ModerationVerdict(flagged=bool(categories), categories=categories)

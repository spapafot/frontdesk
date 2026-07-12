import asyncio
import logging
import re
import unicodedata

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.repositories.knowledge_repository import KnowledgeRepository
from app.services.embeddings import embed_query
from app.services.query_expansion import expand_query
from app.services.reranker import rerank

logger = logging.getLogger(__name__)

# cosine distance ranges 0 (identical) .. 2 (opposite). Convert to a 0..1 score.
# Anything below this score is treated as not confidently relevant.
RELEVANCE_THRESHOLD = 0.30

_GREEK_RE = re.compile(r"[\u0370-\u03ff\u1f00-\u1fff]")
_WORD_RE = re.compile(r"[a-z0-9]+")
_GREEK_DIGRAPHS = {
    "ου": "ou",
    "αι": "ai",
    "ει": "ei",
    "οι": "oi",
    "υι": "yi",
    "αυ": "av",
    "ευ": "ev",
    "μπ": "b",
    "ντ": "d",
    "γκ": "g",
    "γγ": "ng",
    "τσ": "ts",
    "τζ": "tz",
}
_GREEK_CHARS = str.maketrans(
    {
        "α": "a", "β": "v", "γ": "g", "δ": "d", "ε": "e", "ζ": "z",
        "η": "i", "θ": "th", "ι": "i", "κ": "k", "λ": "l", "μ": "m",
        "ν": "n", "ξ": "x", "ο": "o", "π": "p", "ρ": "r", "σ": "s",
        "ς": "s", "τ": "t", "υ": "y", "φ": "f", "χ": "ch", "ψ": "ps",
        "ω": "o",
    }
)
_TRANSLITERATED_STOPWORDS = frozenset(
    {
        "apo", "afto", "afton", "einai", "ena", "enas", "gia", "kai", "me",
        "mou", "na", "poios", "poia", "poio", "pou", "se", "ston", "stin",
        "stis", "sto", "ta", "tin", "tis", "to", "ton", "tou", "xereis",
        "ksereis", "sxetika", "plirofories",
    }
)


def transliterate_greek(text: str) -> str:
    """Produce a stable Latin query variant for Greek names and identifiers."""
    normalized = unicodedata.normalize("NFD", text.lower())
    normalized = "".join(char for char in normalized if not unicodedata.combining(char))
    for greek, latin in _GREEK_DIGRAPHS.items():
        normalized = normalized.replace(greek, latin)
    return unicodedata.normalize("NFC", normalized.translate(_GREEK_CHARS))


def _query_variants(query: str) -> list[str]:
    variants = [query]
    if _GREEK_RE.search(query):
        transliterated = transliterate_greek(query)
        if transliterated.casefold() != query.casefold():
            variants.append(transliterated)
    return variants


def _lexical_terms(query_variants: list[str]) -> list[str]:
    terms: list[str] = []
    for variant in query_variants:
        for term in _WORD_RE.findall(variant.lower()):
            if len(term) >= 4 and term not in _TRANSLITERATED_STOPWORDS and term not in terms:
                terms.append(term)
    return terms[:8]


def _distance_to_score(distance: float) -> float:
    return max(0.0, 1.0 - distance / 2.0)


async def _expanded_variants(query: str, variants: list[str]) -> list[str]:
    """Append model-suggested paraphrases of the query, de-duplicated.

    Widens recall across vocabulary gaps: a question worded "προθεσμία υποβολής"
    can then reach a passage worded "καταληκτική ημερομηνία παραλαβής". Best-effort
    — ``expand_query`` yields nothing when disabled or unavailable, leaving the
    literal query variants untouched.
    """
    seen = {variant.casefold() for variant in variants}
    for phrasing in await expand_query(query):
        key = phrasing.casefold()
        if key and key not in seen:
            seen.add(key)
            variants.append(phrasing)
    return variants


async def _rerank_candidates(query: str, candidates: list[dict], limit: int) -> list[dict]:
    """Reorder candidates with the cross-encoder and return the best ``limit``.

    Falls back to retrieval (cosine-score) order when reranking is unavailable, and
    backfills any slots the reranker didn't return so the caller always gets up to
    ``limit`` results.
    """
    pool = candidates[: settings.rag_rerank_candidates]
    order = await rerank(query, [candidate["content"] or "" for candidate in pool], limit)
    if order is None:
        return candidates[:limit]
    reranked = [pool[index] for index in order]
    chosen = {candidate["chunk_id"] for candidate in reranked}
    for candidate in candidates:
        if len(reranked) >= limit:
            break
        if candidate["chunk_id"] not in chosen:
            reranked.append(candidate)
            chosen.add(candidate["chunk_id"])
    return reranked[:limit]


async def search_knowledge(
    session: AsyncSession, profile_id: int, query: str, limit: int | None = None
) -> list[dict]:
    """Embed the query (plus alternative phrasings) and return the most relevant
    knowledge chunks, blended with a lexical fallback and reordered by a reranker."""
    if limit is None:
        limit = settings.rag_top_k
    # With reranking on, cast a wider net so the cross-encoder has real choices;
    # the pool is trimmed back to `limit` after reranking.
    candidate_limit = (
        max(limit, settings.rag_rerank_candidates) if settings.rag_reranker else limit
    )
    repo = KnowledgeRepository(session)
    variants = await _expanded_variants(query, _query_variants(query))
    by_chunk: dict[int, dict] = {}

    async def _semantic(variant: str):
        embedding = await embed_query(variant)
        return await repo.search(profile_id, embedding, limit=candidate_limit)

    # Each variant is an independent embed+search round-trip; expansion can add
    # several, so run them concurrently rather than serially on the chat's
    # critical path. One variant failing must not sink the rest of the search.
    variant_rows = await asyncio.gather(
        *(_semantic(variant) for variant in variants), return_exceptions=True
    )
    for variant, rows in zip(variants, variant_rows):
        if isinstance(rows, BaseException):
            logger.warning("semantic search failed for variant %r", variant, exc_info=rows)
            continue
        for chunk, title, distance in rows:
            score = _distance_to_score(distance)
            if score < RELEVANCE_THRESHOLD:
                continue
            existing = by_chunk.get(chunk.id)
            if existing is None or score > existing["score"]:
                by_chunk[chunk.id] = {
                    "chunk_id": chunk.id,
                    "document_id": chunk.document_id,
                    "title": title,
                    "content": chunk.content,
                    "distance": round(distance, 4),
                    "score": round(score, 4),
                    "match": "semantic",
                }

    terms = _lexical_terms(variants)
    for chunk, title in await repo.search_text(profile_id, terms, limit=candidate_limit):
        existing = by_chunk.get(chunk.id)
        if existing is None:
            by_chunk[chunk.id] = {
                "chunk_id": chunk.id,
                "document_id": chunk.document_id,
                "title": title,
                "content": chunk.content,
                "distance": None,
                "score": 1.0,
                "match": "lexical",
            }
        else:
            existing["match"] = "semantic+lexical"
            existing["score"] = max(existing["score"], 1.0)

    candidates = sorted(by_chunk.values(), key=lambda item: item["score"], reverse=True)
    return await _rerank_candidates(query, candidates, limit)

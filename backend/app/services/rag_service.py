from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.repositories.knowledge_repository import KnowledgeRepository
from app.services.embeddings import embed

# cosine distance ranges 0 (identical) .. 2 (opposite). Convert to a 0..1 score.
# Anything below this score is treated as not confidently relevant.
RELEVANCE_THRESHOLD = 0.30


def _distance_to_score(distance: float) -> float:
    return max(0.0, 1.0 - distance / 2.0)


async def search_knowledge(
    session: AsyncSession, business_id: int, query: str, limit: int | None = None
) -> list[dict]:
    """Embed the query and return the most relevant knowledge chunks."""
    if limit is None:
        limit = settings.rag_top_k
    query_embedding = await embed(query)
    repo = KnowledgeRepository(session)
    rows = await repo.search(business_id, query_embedding, limit=limit)

    results: list[dict] = []
    for chunk, title, distance in rows:
        score = _distance_to_score(distance)
        if score < RELEVANCE_THRESHOLD:
            continue
        results.append(
            {
                "chunk_id": chunk.id,
                "document_id": chunk.document_id,
                "title": title,
                "content": chunk.content,
                "distance": round(distance, 4),
                "score": round(score, 4),
            }
        )
    return results

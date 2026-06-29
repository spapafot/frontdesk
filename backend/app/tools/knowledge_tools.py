from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.services.rag_service import search_knowledge


async def search_knowledge_base(
    session: AsyncSession, business_id: int, now: datetime, query: str
) -> dict:
    """Semantic search over the business knowledge base (policies, FAQs)."""
    results = await search_knowledge(session, business_id, query)
    if not results:
        return {"results": [], "note": "No knowledge base entries found."}
    return {"results": results}

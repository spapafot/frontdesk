from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_session
from app.repositories.analytics_repository import AnalyticsRepository
from app.repositories.business_repository import BusinessRepository
from app.schemas.analytics import AnalyticsOut

router = APIRouter(prefix="/analytics", tags=["analytics"])


@router.get("", response_model=AnalyticsOut)
async def get_analytics(session: AsyncSession = Depends(get_session)) -> AnalyticsOut:
    business = await BusinessRepository(session).get_or_create_default()
    await session.commit()
    repo = AnalyticsRepository(session)
    overview = await repo.overview(business.id)
    unanswered = await repo.unanswered(business.id)
    return AnalyticsOut(
        total_conversations=overview["total_conversations"],
        last_7_days=overview["last_7_days"],
        ratings=overview["ratings"],
        unanswered=unanswered,
    )

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_session
from app.api.dependencies import get_current_profile
from app.models.profile import AssistantProfile
from app.repositories.analytics_repository import AnalyticsRepository
from app.schemas.analytics import AnalyticsOut

router = APIRouter(prefix="/analytics", tags=["analytics"])


@router.get("", response_model=AnalyticsOut)
async def get_analytics(
    session: AsyncSession = Depends(get_session),
    profile: AssistantProfile = Depends(get_current_profile),
) -> AnalyticsOut:
    repo = AnalyticsRepository(session)
    overview = await repo.overview(profile.id)
    unanswered = await repo.unanswered(profile.id)
    return AnalyticsOut(
        total_conversations=overview["total_conversations"],
        last_7_days=overview["last_7_days"],
        ratings=overview["ratings"],
        unanswered=unanswered,
    )

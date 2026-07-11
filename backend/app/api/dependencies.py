from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import AdminUser, require_admin
from app.core.db import get_session
from app.models.profile import AssistantProfile
from app.repositories.profile_repository import ProfileRepository


async def get_current_profile(
    user: AdminUser = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
) -> AssistantProfile:
    profile = await ProfileRepository(session).get_or_create_for_owner(user.id, user.email)
    await session.commit()
    return profile

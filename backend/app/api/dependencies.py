from fastapi import Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import AdminUser, require_admin
from app.core.db import get_session
from app.models.profile import AssistantProfile
from app.repositories.profile_repository import ProfileRepository


async def get_selected_site(
    site_id: int | None = Query(default=None),
    user: AdminUser = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
) -> AssistantProfile:
    """Resolve which of the owner's sites (profiles) a request targets.

    ``?site_id=`` omitted falls back to the owner's default site (bootstrapping
    a first one on first login), so an un-updated client keeps working. A
    ``site_id`` the caller does not own yields 404 (don't leak existence)."""
    repo = ProfileRepository(session)
    if site_id is None:
        profile = await repo.get_or_create_default(user.id, user.email)
        await session.commit()
        return profile
    profile = await repo.get_owned(site_id, user.id)
    if profile is None:
        raise HTTPException(status_code=404, detail="Site not found.")
    return profile

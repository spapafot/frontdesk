from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_session
from app.repositories.business_repository import BusinessRepository
from app.schemas.settings import SettingsOut, SettingsUpdate

router = APIRouter(prefix="/settings", tags=["settings"])


def _to_out(business) -> SettingsOut:
    return SettingsOut(
        business_name=business.name,
        assistant_name=business.assistant_name,
        custom_instructions=business.custom_instructions,
    )


@router.get("", response_model=SettingsOut)
async def get_settings(session: AsyncSession = Depends(get_session)) -> SettingsOut:
    business = await BusinessRepository(session).get_or_create_default()
    await session.commit()
    return _to_out(business)


@router.put("", response_model=SettingsOut)
async def update_settings(
    body: SettingsUpdate, session: AsyncSession = Depends(get_session)
) -> SettingsOut:
    repo = BusinessRepository(session)
    business = await repo.get_or_create_default()
    await repo.update_settings(
        business,
        name=body.business_name,
        assistant_name=body.assistant_name,
        custom_instructions=body.custom_instructions,
    )
    await session.commit()
    return _to_out(business)

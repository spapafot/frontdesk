from datetime import date, datetime, timezone
from urllib.parse import urlsplit

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_current_profile
from app.core.db import get_session
from app.models.profile import AssistantProfile
from app.repositories.profile_repository import ProfileRepository
from app.repositories.widget_repository import WidgetRepository
from app.schemas.settings import SettingsOut, SettingsUpdate

router = APIRouter(prefix="/settings", tags=["settings"])


def _month() -> tuple[date, str]:
    now = datetime.now(timezone.utc)
    period = date(now.year, now.month, 1)
    if now.month == 12:
        reset = datetime(now.year + 1, 1, 1, tzinfo=timezone.utc)
    else:
        reset = datetime(now.year, now.month + 1, 1, tzinfo=timezone.utc)
    return period, reset.isoformat()


def _normalize_origin(value: str | None) -> str | None:
    if value is None or not value.strip():
        return None
    parsed = urlsplit(value.strip())
    if (
        parsed.scheme not in {"http", "https"}
        or not parsed.hostname
        or parsed.username
        or parsed.password
        or parsed.path not in {"", "/"}
        or parsed.query
        or parsed.fragment
    ):
        raise HTTPException(status_code=422, detail="Website must be an exact HTTP(S) origin.")
    if parsed.scheme == "http" and parsed.hostname not in {"localhost", "127.0.0.1"}:
        raise HTTPException(status_code=422, detail="Production widget origins must use HTTPS.")
    return f"{parsed.scheme}://{parsed.netloc.lower()}"


async def _to_out(profile: AssistantProfile, session: AsyncSession) -> SettingsOut:
    repo = WidgetRepository(session)
    installation = await repo.get_for_profile(profile.id)
    if installation is None:
        raise HTTPException(status_code=500, detail="Widget installation is missing.")
    period, reset = _month()
    return SettingsOut(
        business_name=profile.name,
        assistant_name=profile.assistant_name,
        custom_instructions=profile.custom_instructions,
        public_key=installation.public_key,
        widget_origin=installation.allowed_origin,
        widget_enabled=installation.is_enabled,
        widget_monthly_limit=installation.monthly_limit,
        widget_monthly_usage=await repo.usage(installation.id, period),
        widget_resets_at=reset,
    )


@router.get("", response_model=SettingsOut)
async def get_settings(
    session: AsyncSession = Depends(get_session),
    profile: AssistantProfile = Depends(get_current_profile),
) -> SettingsOut:
    return await _to_out(profile, session)


@router.put("", response_model=SettingsOut)
async def update_settings(
    body: SettingsUpdate,
    session: AsyncSession = Depends(get_session),
    profile: AssistantProfile = Depends(get_current_profile),
) -> SettingsOut:
    await ProfileRepository(session).update_settings(
        profile,
        name=body.business_name,
        assistant_name=body.assistant_name,
        custom_instructions=body.custom_instructions,
    )
    installation = await WidgetRepository(session).get_for_profile(profile.id)
    if installation is None:
        raise HTTPException(status_code=500, detail="Widget installation is missing.")
    if "widget_origin" in body.model_fields_set:
        installation.allowed_origin = _normalize_origin(body.widget_origin)
    if body.widget_enabled is not None:
        installation.is_enabled = body.widget_enabled
    await session.commit()
    return await _to_out(profile, session)


@router.post("/widget-key/rotate", response_model=SettingsOut)
async def rotate_widget_key(
    session: AsyncSession = Depends(get_session),
    profile: AssistantProfile = Depends(get_current_profile),
) -> SettingsOut:
    repo = WidgetRepository(session)
    installation = await repo.get_for_profile(profile.id)
    if installation is None:
        raise HTTPException(status_code=500, detail="Widget installation is missing.")
    await repo.rotate(installation)
    await session.commit()
    return await _to_out(profile, session)

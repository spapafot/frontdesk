from datetime import date, datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import AdminUser, require_admin
from app.core.db import get_session
from app.core.origins import normalize_origin
from app.models.profile import AssistantProfile
from app.repositories.profile_repository import ProfileRepository
from app.repositories.team_repository import TeamRepository
from app.repositories.widget_repository import WidgetRepository
from app.schemas.site import SiteCreate, SiteSummaryOut, SiteUpdate
from app.services import billing

router = APIRouter(prefix="/sites", tags=["sites"])


def _period() -> date:
    now = datetime.now(timezone.utc)
    return date(now.year, now.month, 1)


async def _to_summary(
    profile: AssistantProfile,
    session: AsyncSession,
    period: date,
    role: str = "owner",
) -> SiteSummaryOut:
    repo = WidgetRepository(session)
    installation = await repo.get_for_profile(profile.id)
    return SiteSummaryOut(
        id=profile.id,
        name=profile.name,
        assistant_name=profile.assistant_name,
        type=profile.type,
        public_key=installation.public_key if installation else None,
        widget_origin=installation.allowed_origin if installation else None,
        widget_enabled=installation.is_enabled if installation else True,
        widget_monthly_usage=(
            await repo.usage(installation.id, period) if installation else 0
        ),
        role=role,
        created_at=profile.created_at,
    )


@router.get("", response_model=list[SiteSummaryOut])
async def list_sites(
    session: AsyncSession = Depends(get_session),
    user: AdminUser = Depends(require_admin),
) -> list[SiteSummaryOut]:
    repo = ProfileRepository(session)
    period = _period()
    summaries = [
        await _to_summary(p, session, period)
        for p in await repo.list_for_owner(user.id)
    ]
    # Team memberships expose every site of each team's owner as "member".
    for team in await TeamRepository(session).list_teams_for_user(
        user.id, user.email
    ):
        for profile in await repo.list_for_owner(team.owner_user_id):
            summaries.append(await _to_summary(profile, session, period, role="member"))
    # This is the app's first call after login, so it also persists any lazy
    # invite activation done by list_teams_for_user.
    await session.commit()
    return summaries


@router.post("", response_model=SiteSummaryOut, status_code=201)
async def create_site(
    body: SiteCreate,
    session: AsyncSession = Depends(get_session),
    user: AdminUser = Depends(require_admin),
) -> SiteSummaryOut:
    repo = ProfileRepository(session)
    entitlements = await billing.resolve_entitlements(session, user, user.id)
    if entitlements.sites is not None:
        existing = await repo.list_for_owner(user.id)
        if len(existing) >= entitlements.sites:
            raise HTTPException(
                status_code=402,
                detail="Your plan's website limit has been reached. Upgrade to add more websites.",
            )
    allowed_origin = normalize_origin(body.widget_origin)
    profile = await repo.create_site(
        user.id,
        name=body.name.strip(),
        type=body.type,
        assistant_name=body.assistant_name,
        allowed_origin=allowed_origin,
        notification_email=user.email,
    )
    await session.commit()
    return await _to_summary(profile, session, _period())


@router.patch("/{site_id}", response_model=SiteSummaryOut)
async def rename_site(
    site_id: int,
    body: SiteUpdate,
    session: AsyncSession = Depends(get_session),
    user: AdminUser = Depends(require_admin),
) -> SiteSummaryOut:
    repo = ProfileRepository(session)
    profile = await repo.get_owned(site_id, user.id)
    if profile is None:
        raise HTTPException(status_code=404, detail="Site not found.")
    await repo.update_settings(profile, name=body.name.strip())
    await session.commit()
    return await _to_summary(profile, session, _period())


@router.delete("/{site_id}", status_code=204)
async def delete_site(
    site_id: int,
    session: AsyncSession = Depends(get_session),
    user: AdminUser = Depends(require_admin),
) -> None:
    repo = ProfileRepository(session)
    profile = await repo.get_owned(site_id, user.id)
    if profile is None:
        raise HTTPException(status_code=404, detail="Site not found.")
    if len(await repo.list_for_owner(user.id)) <= 1:
        raise HTTPException(status_code=409, detail="Cannot delete your only site.")
    await repo.delete_site(profile)
    await session.commit()

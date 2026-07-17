from dataclasses import dataclass

from fastapi import Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import AdminUser, require_admin
from app.core.db import get_session
from app.models.profile import AssistantProfile
from app.repositories.profile_repository import ProfileRepository


@dataclass
class SiteAccess:
    profile: AssistantProfile
    role: str  # "owner" | "member"

    @property
    def is_owner(self) -> bool:
        return self.role == "owner"


async def get_site_access(
    site_id: int | None = Query(default=None),
    user: AdminUser = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
) -> SiteAccess:
    """Resolve which site a request targets and the caller's role on it.

    ``?site_id=`` omitted falls back to the caller's default site (an owner's
    first site - bootstrapping one on first login - else the first site of a
    team they belong to), so an un-updated client keeps working. A ``site_id``
    the caller cannot access yields 404 (don't leak existence). Team
    memberships pending on the caller's email are activated as a side effect
    of resolution (committed below)."""
    repo = ProfileRepository(session)
    if site_id is None:
        profile, role = await repo.resolve_default_access(user.id, user.email)
    else:
        result = await repo.get_accessible(site_id, user.id, user.email)
        if result is None:
            # No cross-tenant access, ever - not even for super-admins. The
            # super-admin role only lifts billing/plan limits on the caller's
            # OWN account (see app.services.billing.resolve_entitlements); it
            # never grants sight of another owner's sites or data.
            raise HTTPException(status_code=404, detail="Site not found.")
        profile, role = result
    if role == "owner" and profile.notification_email is None and user.email:
        # One-time backfill for sites created before migration 0020. Owner-only:
        # a member's login email must never become the site's ticket recipient.
        profile.notification_email = user.email
    await session.commit()
    return SiteAccess(profile=profile, role=role)


async def get_selected_site(
    access: SiteAccess = Depends(get_site_access),
) -> AssistantProfile:
    return access.profile


async def require_site_owner(
    access: SiteAccess = Depends(get_site_access),
) -> AssistantProfile:
    if not access.is_owner:
        raise HTTPException(
            status_code=403, detail="Only the site owner can manage settings."
        )
    return access.profile

"""``get_site_access`` backfills ``notification_email`` and resolves roles.

Sites created before migration 0020 (and any row cleared out-of-band) get the
owner's login email persisted the first time the owner touches the dashboard,
so ticket-notification emails work without any manual setup. The backfill is
owner-only: a team member's login email must never become the site's ticket
recipient. ``require_site_owner`` gates the settings surface to owners.
"""

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from fastapi import HTTPException

from app.api.dependencies import (
    SiteAccess,
    get_selected_site,
    get_site_access,
    require_site_owner,
)
from app.core.auth import AdminUser


def _user(email: str | None = "owner@acme.com") -> AdminUser:
    return AdminUser("user-1", email, {})


def _session() -> SimpleNamespace:
    return SimpleNamespace(commit=AsyncMock())


def _profile() -> SimpleNamespace:
    return SimpleNamespace(id=7, owner_user_id="user-1", notification_email=None)


@pytest.fixture
def profile_repo(monkeypatch):
    """Patch both resolution paths to a shared, mutable profile (role owner)."""
    profile = _profile()
    monkeypatch.setattr(
        "app.api.dependencies.ProfileRepository.resolve_default_access",
        AsyncMock(return_value=(profile, "owner")),
    )
    monkeypatch.setattr(
        "app.api.dependencies.ProfileRepository.get_accessible",
        AsyncMock(return_value=(profile, "owner")),
    )
    return profile


@pytest.fixture
def member_repo(monkeypatch):
    """Both resolution paths return the site with role member."""
    profile = SimpleNamespace(
        id=7, owner_user_id="other-owner", notification_email=None
    )
    monkeypatch.setattr(
        "app.api.dependencies.ProfileRepository.resolve_default_access",
        AsyncMock(return_value=(profile, "member")),
    )
    monkeypatch.setattr(
        "app.api.dependencies.ProfileRepository.get_accessible",
        AsyncMock(return_value=(profile, "member")),
    )
    return profile


async def test_backfills_default_site(profile_repo):
    session = _session()
    result = await get_selected_site(
        await get_site_access(site_id=None, user=_user(), session=session)
    )

    assert result.notification_email == "owner@acme.com"
    session.commit.assert_awaited()


async def test_backfills_selected_site(profile_repo):
    access = await get_site_access(site_id=7, user=_user(), session=_session())

    assert access.profile.notification_email == "owner@acme.com"
    assert access.role == "owner"


async def test_leaves_an_existing_email_alone(profile_repo):
    profile_repo.notification_email = "support@acme.com"

    access = await get_site_access(site_id=None, user=_user(), session=_session())

    assert access.profile.notification_email == "support@acme.com"


async def test_tolerates_a_jwt_without_email(profile_repo):
    access = await get_site_access(
        site_id=None, user=_user(email=None), session=_session()
    )

    assert access.profile.notification_email is None


async def test_member_access_never_backfills_notification_email(member_repo):
    access = await get_site_access(
        site_id=7, user=_user(email="member@acme.com"), session=_session()
    )

    assert access.role == "member"
    assert access.profile.notification_email is None


async def test_foreign_site_still_404s_before_any_backfill(monkeypatch):
    monkeypatch.setattr(
        "app.api.dependencies.ProfileRepository.get_accessible",
        AsyncMock(return_value=None),
    )

    with pytest.raises(HTTPException) as exc:
        await get_site_access(site_id=999, user=_user(), session=_session())
    assert exc.value.status_code == 404


async def test_require_site_owner_passes_owners():
    profile = _profile()
    result = await require_site_owner(SiteAccess(profile=profile, role="owner"))
    assert result is profile


async def test_require_site_owner_rejects_members():
    with pytest.raises(HTTPException) as exc:
        await require_site_owner(SiteAccess(profile=_profile(), role="member"))
    assert exc.value.status_code == 403

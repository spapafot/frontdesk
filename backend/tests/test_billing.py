"""Unit tests for billing plan/entitlement resolution (no HTTP, no DB).

The pure helpers (``is_superadmin``, ``effective_status``, ``limits_for``) and
the ``resolve_entitlements`` wrapper are imported directly, so the module-level
binding stays the real implementation even though ``conftest``'s autouse
``no_database_billing`` fixture patches the module attribute for route tests.
"""

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

from app.core.auth import AdminUser
from app.core.plans import LOCKED_LIMITS, PLANS, SUPERADMIN_LIMITS
from app.services import billing
from app.services.billing import resolve_entitlements

NOW = datetime.now(timezone.utc)


def _user(claims=None):
    return AdminUser(subject="user-1", email="a@b.co", claims=claims or {})


def test_is_superadmin_detects_app_metadata_role():
    assert billing.is_superadmin(_user({"app_metadata": {"role": "superadmin"}}))


def test_is_superadmin_false_without_role():
    assert not billing.is_superadmin(_user({}))
    assert not billing.is_superadmin(_user({"app_metadata": {"role": "member"}}))


def test_effective_status_locks_expired_trial():
    sub = SimpleNamespace(status="trialing", trial_ends_at=NOW - timedelta(days=1))
    assert billing.effective_status(sub) == "locked"


def test_effective_status_keeps_live_trial():
    sub = SimpleNamespace(status="trialing", trial_ends_at=NOW + timedelta(days=3))
    assert billing.effective_status(sub) == "trialing"


def test_limits_for_expired_trial_is_locked():
    sub = SimpleNamespace(
        plan="starter", status="trialing", trial_ends_at=NOW - timedelta(days=1)
    )
    assert billing.limits_for(sub) == LOCKED_LIMITS


def test_limits_for_canceled_is_locked():
    sub = SimpleNamespace(plan="pro", status="canceled", trial_ends_at=None)
    assert billing.limits_for(sub) == LOCKED_LIMITS


def test_limits_for_active_plan_maps_to_plan():
    sub = SimpleNamespace(plan="pro", status="active", trial_ends_at=None)
    assert billing.limits_for(sub) == PLANS["pro"]


async def test_resolve_entitlements_superadmin_is_unlimited_without_db():
    # Super-admin short-circuits before any repository/DB access (session unused).
    limits = await resolve_entitlements(
        None, _user({"app_metadata": {"role": "superadmin"}}), "owner-x"
    )
    assert limits == SUPERADMIN_LIMITS


async def test_resolve_entitlements_normal_user_uses_subscription():
    # get_or_create_trial is stubbed by the autouse fixture to a business plan.
    limits = await resolve_entitlements(None, _user(), "owner-1")
    assert limits == PLANS["business"]

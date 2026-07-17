"""MFA (aal2) enforcement in ``require_admin``: a user with a verified MFA
factor must present an aal2 token; everyone else is unaffected, and any
Supabase Admin API problem fails open (the primary JWT gate stays enforced)."""

import httpx
import pytest
from fastapi import HTTPException
from fastapi.security import HTTPAuthorizationCredentials

import app.core.auth as auth_module
from app.core.auth import MFA_REQUIRED_DETAIL, AdminUser, require_admin
from tests.conftest import make_jwt

JWT_SECRET = "supabase-jwt-secret"


def _creds(token: str) -> HTTPAuthorizationCredentials:
    return HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)


def _factor(status: str = "verified") -> dict:
    return {"id": "factor-1", "factor_type": "totp", "status": status}


@pytest.fixture
def mfa(settings, monkeypatch):
    """Enable enforcement, reset the cache, and stub the factor fetch.

    Returns a dict: set ``factors`` to control the Admin API answer (an
    exception instance means "raise it"); ``calls`` counts fetches.
    """
    monkeypatch.setattr(settings, "supabase_jwt_secret", JWT_SECRET)
    monkeypatch.setattr(settings, "supabase_url", "https://demo.supabase.co")
    monkeypatch.setattr(settings, "supabase_service_role_key", "service-role-key")
    monkeypatch.setattr(settings, "mfa_enforcement_enabled", True)
    monkeypatch.setattr(auth_module, "_mfa_cache", {})

    state = {"factors": [], "calls": 0}

    async def _fake_fetch(user_id):
        state["calls"] += 1
        if isinstance(state["factors"], Exception):
            raise state["factors"]
        return state["factors"]

    monkeypatch.setattr(auth_module, "_fetch_user_factors", _fake_fetch)
    return state


async def test_aal2_token_passes_without_factor_lookup(mfa):
    token = make_jwt(JWT_SECRET, claims={"aal": "aal2"})
    user = await require_admin(credentials=_creds(token))
    assert isinstance(user, AdminUser)
    assert mfa["calls"] == 0


async def test_aal1_token_with_verified_factor_rejected(mfa):
    mfa["factors"] = [_factor("verified")]
    token = make_jwt(JWT_SECRET, claims={"aal": "aal1"})
    with pytest.raises(HTTPException) as exc:
        await require_admin(credentials=_creds(token))
    assert exc.value.status_code == 401
    assert exc.value.detail == MFA_REQUIRED_DETAIL


async def test_token_without_aal_claim_is_treated_as_aal1(mfa):
    mfa["factors"] = [_factor("verified")]
    with pytest.raises(HTTPException) as exc:
        await require_admin(credentials=_creds(make_jwt(JWT_SECRET)))
    assert exc.value.detail == MFA_REQUIRED_DETAIL


async def test_aal1_token_without_factors_passes(mfa):
    mfa["factors"] = []
    user = await require_admin(credentials=_creds(make_jwt(JWT_SECRET)))
    assert isinstance(user, AdminUser)


async def test_unverified_factor_does_not_lock_out(mfa):
    # Abandoned enrollment: the factor exists but was never verified.
    mfa["factors"] = [_factor("unverified")]
    user = await require_admin(credentials=_creds(make_jwt(JWT_SECRET)))
    assert isinstance(user, AdminUser)


async def test_admin_api_error_fails_open(mfa):
    mfa["factors"] = httpx.ConnectError("boom")
    user = await require_admin(credentials=_creds(make_jwt(JWT_SECRET)))
    assert isinstance(user, AdminUser)
    # The fail-open answer is cached (briefly) so an outage doesn't add a
    # lookup to every request.
    await require_admin(credentials=_creds(make_jwt(JWT_SECRET)))
    assert mfa["calls"] == 1


async def test_skipped_when_service_role_key_unset(mfa, settings, monkeypatch):
    monkeypatch.setattr(settings, "supabase_service_role_key", "")
    mfa["factors"] = [_factor("verified")]
    user = await require_admin(credentials=_creds(make_jwt(JWT_SECRET)))
    assert isinstance(user, AdminUser)
    assert mfa["calls"] == 0


async def test_skipped_when_kill_switch_off(mfa, settings, monkeypatch):
    monkeypatch.setattr(settings, "mfa_enforcement_enabled", False)
    mfa["factors"] = [_factor("verified")]
    user = await require_admin(credentials=_creds(make_jwt(JWT_SECRET)))
    assert isinstance(user, AdminUser)
    assert mfa["calls"] == 0


async def test_factor_answer_is_cached_within_ttl(mfa):
    mfa["factors"] = [_factor("verified")]
    for _ in range(3):
        with pytest.raises(HTTPException):
            await require_admin(credentials=_creds(make_jwt(JWT_SECRET)))
    assert mfa["calls"] == 1


async def test_cache_is_per_user(mfa):
    mfa["factors"] = [_factor("verified")]
    with pytest.raises(HTTPException):
        await require_admin(credentials=_creds(make_jwt(JWT_SECRET, sub="user-1")))

    mfa["factors"] = []
    user = await require_admin(credentials=_creds(make_jwt(JWT_SECRET, sub="user-2")))
    assert isinstance(user, AdminUser)
    assert mfa["calls"] == 2


async def test_admin_route_rejects_aal1_with_verified_factor(
    client, mfa, settings, monkeypatch
):
    monkeypatch.setattr(settings, "edge_shared_secret", "")  # isolate from edge gate
    mfa["factors"] = [_factor("verified")]
    token = make_jwt(JWT_SECRET, claims={"aal": "aal1"})

    r = await client.get("/settings", headers={"Authorization": f"Bearer {token}"})

    assert r.status_code == 401
    assert r.json()["detail"] == MFA_REQUIRED_DETAIL


async def test_fetch_user_factors_parses_bare_array_and_wrapper(settings, monkeypatch):
    monkeypatch.setattr(settings, "supabase_url", "https://demo.supabase.co")
    monkeypatch.setattr(settings, "supabase_service_role_key", "service-role-key")

    captured = {}

    def _client_for(body):
        class _Client:
            def __init__(self, *args, **kwargs):
                pass

            async def __aenter__(self):
                return self

            async def __aexit__(self, *exc):
                return False

            async def get(self, url, headers=None):
                captured["url"] = url
                captured["headers"] = headers
                return httpx.Response(
                    200, json=body, request=httpx.Request("GET", url)
                )

        return _Client

    monkeypatch.setattr(auth_module.httpx, "AsyncClient", _client_for([_factor()]))
    factors = await auth_module._fetch_user_factors("user-1")
    assert factors == [_factor()]
    assert captured["url"].endswith("/auth/v1/admin/users/user-1/factors")
    assert captured["headers"]["Authorization"] == "Bearer service-role-key"

    monkeypatch.setattr(
        auth_module.httpx, "AsyncClient", _client_for({"factors": [_factor()]})
    )
    assert await auth_module._fetch_user_factors("user-1") == [_factor()]

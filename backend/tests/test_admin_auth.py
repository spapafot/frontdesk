"""Admin authentication: routes require a valid Supabase JWT, and the
``require_admin`` dependency validates tokens correctly."""

from datetime import timedelta

import pytest
from fastapi import HTTPException
from fastapi.security import HTTPAuthorizationCredentials

import app.core.auth as auth_module
from app.core.auth import AdminUser, require_admin
from tests.conftest import make_es256_jwt, make_es256_keypair, make_jwt

JWT_SECRET = "supabase-jwt-secret"
ADMIN_PATHS = [
    "/knowledge/documents",
    "/settings",
    "/conversations",
    "/analytics",
    "/sites",
    "/team/members",
]


def _creds(token: str) -> HTTPAuthorizationCredentials:
    return HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)


# --- Route-level: rejection paths short-circuit before any DB access --------


@pytest.mark.parametrize("path", ADMIN_PATHS)
async def test_admin_route_requires_token(client, settings, monkeypatch, path):
    monkeypatch.setattr(settings, "edge_shared_secret", "")  # isolate from edge gate
    monkeypatch.setattr(settings, "supabase_jwt_secret", JWT_SECRET)
    r = await client.get(path)
    assert r.status_code == 401


async def test_admin_route_rejects_garbage_token(client, settings, monkeypatch):
    monkeypatch.setattr(settings, "edge_shared_secret", "")
    monkeypatch.setattr(settings, "supabase_jwt_secret", JWT_SECRET)
    r = await client.get("/settings", headers={"Authorization": "Bearer not.a.jwt"})
    assert r.status_code == 401


# --- Unit tests on require_admin -------------------------------------------


async def test_valid_token_yields_admin_user(settings, monkeypatch):
    monkeypatch.setattr(settings, "supabase_jwt_secret", JWT_SECRET)
    user = await require_admin(credentials=_creds(make_jwt(JWT_SECRET)))
    assert isinstance(user, AdminUser)
    assert user.id == "user-1"
    assert user.email == "admin@example.com"


async def test_no_dev_bypass_when_auth_unconfigured(settings, monkeypatch):
    # There is no dev bypass: even with no signing config, a missing token is
    # rejected rather than yielding a synthetic dev user.
    monkeypatch.setattr(settings, "supabase_jwt_secret", "")
    monkeypatch.setattr(settings, "supabase_url", "")
    with pytest.raises(HTTPException) as exc:
        await require_admin(credentials=None)
    assert exc.value.status_code == 401


async def test_no_dev_bypass_rejects_token_when_unconfigured(settings, monkeypatch):
    # With no signing config a presented token can't be verified -> 401, never
    # a fabricated dev user.
    monkeypatch.setattr(settings, "supabase_jwt_secret", "")
    monkeypatch.setattr(settings, "supabase_url", "")
    with pytest.raises(HTTPException) as exc:
        await require_admin(credentials=_creds(make_jwt(JWT_SECRET)))
    assert exc.value.status_code == 401


async def test_expired_token_rejected(settings, monkeypatch):
    monkeypatch.setattr(settings, "supabase_jwt_secret", JWT_SECRET)
    token = make_jwt(JWT_SECRET, exp_delta=timedelta(hours=-1))
    with pytest.raises(HTTPException) as exc:
        await require_admin(credentials=_creds(token))
    assert exc.value.status_code == 401


async def test_token_signed_with_wrong_secret_rejected(settings, monkeypatch):
    monkeypatch.setattr(settings, "supabase_jwt_secret", JWT_SECRET)
    token = make_jwt("a-different-secret")
    with pytest.raises(HTTPException) as exc:
        await require_admin(credentials=_creds(token))
    assert exc.value.status_code == 401


async def test_wrong_audience_rejected(settings, monkeypatch):
    monkeypatch.setattr(settings, "supabase_jwt_secret", JWT_SECRET)
    token = make_jwt(JWT_SECRET, aud="some-other-audience")
    with pytest.raises(HTTPException) as exc:
        await require_admin(credentials=_creds(token))
    assert exc.value.status_code == 401


async def test_missing_token_rejected_when_enabled(settings, monkeypatch):
    monkeypatch.setattr(settings, "supabase_jwt_secret", JWT_SECRET)
    with pytest.raises(HTTPException) as exc:
        await require_admin(credentials=None)
    assert exc.value.status_code == 401


async def test_token_without_subject_is_rejected(settings, monkeypatch):
    monkeypatch.setattr(settings, "supabase_jwt_secret", JWT_SECRET)
    token = make_jwt(JWT_SECRET, sub="")
    with pytest.raises(HTTPException) as exc:
        await require_admin(credentials=_creds(token))
    assert exc.value.status_code == 401


# --- Asymmetric (ES256 / JWKS) path: Supabase's new signing keys ------------


@pytest.fixture
def es256(settings, monkeypatch):
    """Enable the asymmetric path and stub the JWKS fetch with a local keypair."""
    private_key, jwks = make_es256_keypair()
    monkeypatch.setattr(settings, "supabase_jwt_secret", "")  # force the JWKS path
    monkeypatch.setattr(settings, "supabase_url", "https://demo.supabase.co")
    # Reset the module-level JWKS cache so tests don't leak keys into each other.
    monkeypatch.setattr(auth_module, "_jwks_cache", {"set": None, "fetched_at": 0.0})

    async def _fake_fetch():
        import jwt as _jwt

        return _jwt.PyJWKSet.from_dict(jwks)

    monkeypatch.setattr(auth_module, "_fetch_jwks_set", _fake_fetch)
    return private_key


async def test_es256_token_verified_via_jwks(es256):
    user = await require_admin(credentials=_creds(make_es256_jwt(es256)))
    assert isinstance(user, AdminUser)
    assert user.id == "user-1"
    assert user.email == "admin@example.com"


async def test_es256_token_signed_with_wrong_key_rejected(es256):
    from tests.conftest import make_es256_keypair as _kp

    attacker_key, _ = _kp()  # not in the published JWKS
    with pytest.raises(HTTPException) as exc:
        await require_admin(credentials=_creds(make_es256_jwt(attacker_key)))
    assert exc.value.status_code == 401


async def test_es256_wrong_audience_rejected(es256):
    token = make_es256_jwt(es256, aud="some-other-audience")
    with pytest.raises(HTTPException) as exc:
        await require_admin(credentials=_creds(token))
    assert exc.value.status_code == 401


async def test_es256_unknown_kid_rejected(es256):
    token = make_es256_jwt(es256, kid="rotated-away-kid")
    with pytest.raises(HTTPException) as exc:
        await require_admin(credentials=_creds(token))
    assert exc.value.status_code == 401

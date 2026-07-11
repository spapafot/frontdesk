"""Admin authentication: routes require a valid Supabase JWT, and the
``require_admin`` dependency validates tokens correctly."""

from datetime import timedelta

import pytest
from fastapi import HTTPException
from fastapi.security import HTTPAuthorizationCredentials

from app.core.auth import AdminUser, require_admin
from tests.conftest import make_jwt

JWT_SECRET = "supabase-jwt-secret"
ADMIN_PATHS = ["/knowledge/documents", "/settings", "/conversations", "/analytics"]


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


async def test_disabled_auth_returns_dev_user(settings, monkeypatch):
    monkeypatch.setattr(settings, "supabase_jwt_secret", "")
    user = await require_admin(credentials=None)
    assert user.id == "dev"


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

"""Shared test fixtures.

These tests exercise the HTTP/auth layer without a real database: the chat
route's service call is monkeypatched, and admin routes are tested for their
*rejection* paths (which short-circuit before any DB access) plus direct unit
tests of ``require_admin``.
"""

import os
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

# Tests must never inherit credentials from backend/.env or the launching shell.
# These overrides are set before importing app settings, so pydantic-settings
# cannot load real provider, database, or signing secrets into the test process.
os.environ.update(
    {
        "DEEPSEEK_API_KEY": "",
        "OPENAI_API_KEY": "",
        "DATABASE_URL": "postgresql+asyncpg://postgres:postgres@localhost:5432/support",
        "WIDGET_SESSION_SECRET": "",
        "EDGE_SHARED_SECRET": "",
        "SUPABASE_URL": "",
        "SUPABASE_JWT_SECRET": "",
    }
)

import jwt
import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from app.core.config import settings as app_settings
from app.main import app


@pytest_asyncio.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest.fixture
def settings(monkeypatch):
    """The live settings singleton. Tests mutate it via ``monkeypatch.setattr``
    so changes are reverted automatically after each test."""
    return app_settings


@pytest.fixture(autouse=True)
def no_database_profile(monkeypatch):
    """HTTP/auth tests should not require a migrated local Postgres database."""
    async def _profile(self, owner_user_id, email=None):
        return SimpleNamespace(id=7, owner_user_id=owner_user_id)

    monkeypatch.setattr(
        "app.repositories.profile_repository.ProfileRepository.get_or_create_default",
        _profile,
    )


def make_jwt(
    secret: str,
    *,
    aud: str = "authenticated",
    sub: str = "user-1",
    email: str | None = "admin@example.com",
    exp_delta: timedelta = timedelta(hours=1),
) -> str:
    payload = {
        "sub": sub,
        "aud": aud,
        "exp": datetime.now(timezone.utc) + exp_delta,
    }
    if email is not None:
        payload["email"] = email
    return jwt.encode(payload, secret, algorithm="HS256")


def make_es256_keypair(kid: str = "test-kid"):
    """Return (private_key, jwks_dict) for signing/verifying ES256 tokens the
    way Supabase's asymmetric signing keys work."""
    from cryptography.hazmat.primitives.asymmetric import ec

    private_key = ec.generate_private_key(ec.SECP256R1())
    jwk = jwt.algorithms.ECAlgorithm(jwt.algorithms.ECAlgorithm.SHA256).to_jwk(
        private_key.public_key(), as_dict=True
    )
    jwk.update({"kid": kid, "alg": "ES256", "use": "sig"})
    return private_key, {"keys": [jwk]}


def make_es256_jwt(
    private_key,
    *,
    kid: str = "test-kid",
    aud: str = "authenticated",
    sub: str = "user-1",
    email: str | None = "admin@example.com",
    exp_delta: timedelta = timedelta(hours=1),
) -> str:
    payload = {
        "sub": sub,
        "aud": aud,
        "exp": datetime.now(timezone.utc) + exp_delta,
    }
    if email is not None:
        payload["email"] = email
    return jwt.encode(payload, private_key, algorithm="ES256", headers={"kid": kid})


def make_fake_stream(record: dict):
    """A stand-in for ``stream_chat`` that records its kwargs and yields one
    SSE frame, so the chat route runs without touching the database."""

    async def _fake(**kwargs):
        record.update(kwargs)
        yield 'data: {"type": "done"}\n\n'

    return _fake

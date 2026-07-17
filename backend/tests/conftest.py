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
        "CONVERSATION_SUMMARIES_ENABLED": "false",
        "OPENAI_API_KEY": "",
        "DATABASE_URL": "postgresql+asyncpg://postgres:postgres@localhost:5432/support",
        "WIDGET_SESSION_SECRET": "",
        "EDGE_SHARED_SECRET": "",
        "SUPABASE_URL": "",
        "SUPABASE_JWT_SECRET": "",
        "SUPABASE_SERVICE_ROLE_KEY": "",
        "STRIPE_SECRET_KEY": "",
        "STRIPE_WEBHOOK_SECRET": "",
        "STRIPE_PRICE_STARTER_MONTH": "",
        "STRIPE_PRICE_STARTER_YEAR": "",
        "STRIPE_PRICE_PRO_MONTH": "",
        "STRIPE_PRICE_PRO_YEAR": "",
        "STRIPE_PRICE_BUSINESS_MONTH": "",
        "STRIPE_PRICE_BUSINESS_YEAR": "",
        "STRIPE_PRICE_TOPUP": "",
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
        return SimpleNamespace(
            id=7,
            owner_user_id=owner_user_id,
            notification_email=email or "admin@example.com",
        )

    async def _default_access(self, user_id, email=None):
        return await _profile(self, user_id, email), "owner"

    monkeypatch.setattr(
        "app.repositories.profile_repository.ProfileRepository.get_or_create_default",
        _profile,
    )
    monkeypatch.setattr(
        "app.repositories.profile_repository.ProfileRepository.resolve_default_access",
        _default_access,
    )


@pytest.fixture(autouse=True)
def no_database_billing(monkeypatch):
    """Billing/plan resolution must not require a real database in HTTP tests.

    Defaults to unlimited entitlements so existing route tests exercise the
    happy path; the dedicated billing/gating tests override these stubs to
    assert 402s, quota 429s, and webhook handling."""
    from app.core.plans import SUPERADMIN_LIMITS

    async def _entitlements(session, user, owner_user_id):
        return SUPERADMIN_LIMITS

    async def _trial(self, owner_user_id):
        return SimpleNamespace(
            owner_user_id=owner_user_id,
            plan="business",
            status="active",
            trial_ends_at=None,
            current_period_end=None,
            stripe_customer_id=None,
            stripe_subscription_id=None,
            billing_interval=None,
        )

    async def _reserve(self, owner_user_id, period, base_limit):
        return True

    async def _usage(self, owner_user_id, period):
        return (0, 0)

    async def _increment(self, installation, period):
        return None

    async def _get_profile(self, profile_id):
        return SimpleNamespace(id=profile_id, owner_user_id="owner-1")

    async def _chunks_for_owner(self, owner_user_id):
        return 0

    monkeypatch.setattr("app.services.billing.resolve_entitlements", _entitlements)
    monkeypatch.setattr(
        "app.repositories.knowledge_repository.KnowledgeRepository.count_chunks_for_owner",
        _chunks_for_owner,
    )
    monkeypatch.setattr(
        "app.repositories.subscription_repository.SubscriptionRepository.get_or_create_trial",
        _trial,
    )
    monkeypatch.setattr(
        "app.repositories.subscription_repository.SubscriptionRepository.reserve_account_message",
        _reserve,
    )
    monkeypatch.setattr(
        "app.repositories.subscription_repository.SubscriptionRepository.usage",
        _usage,
    )
    monkeypatch.setattr(
        "app.repositories.widget_repository.WidgetRepository.increment_usage",
        _increment,
    )
    monkeypatch.setattr(
        "app.repositories.profile_repository.ProfileRepository.get",
        _get_profile,
    )


def make_jwt(
    secret: str,
    *,
    aud: str = "authenticated",
    sub: str = "user-1",
    email: str | None = "admin@example.com",
    claims: dict | None = None,
    exp_delta: timedelta = timedelta(hours=1),
) -> str:
    payload = {
        "sub": sub,
        "aud": aud,
        "exp": datetime.now(timezone.utc) + exp_delta,
    }
    if email is not None:
        payload["email"] = email
    if claims:
        payload.update(claims)
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

"""Shared test fixtures.

These tests exercise the HTTP/auth layer without a real database: the chat
route's service call is monkeypatched, and admin routes are tested for their
*rejection* paths (which short-circuit before any DB access) plus direct unit
tests of ``require_admin``.
"""

from datetime import datetime, timedelta, timezone

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


def make_fake_stream(record: dict):
    """A stand-in for ``stream_chat`` that records its kwargs and yields one
    SSE frame, so the chat route runs without touching the database."""

    async def _fake(**kwargs):
        record.update(kwargs)
        yield 'data: {"type": "done"}\n\n'

    return _fake

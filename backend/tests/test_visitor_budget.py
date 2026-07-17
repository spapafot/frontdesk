"""Daily per-IP widget message budget: over-budget visitors get 429 before any
subscription work, the check is skipped without the Worker-attested IP header
(local dev has no Worker), and only a hash of the IP ever reaches storage."""

import hashlib
from datetime import datetime, timezone
from types import SimpleNamespace

from tests.conftest import make_fake_stream

IP_HEADER = {"x-visitor-ip": "203.0.113.8"}


def _stub_widget(monkeypatch):
    """Make the widget-token and installation checks pass without a database."""
    installation = SimpleNamespace(
        id=17, profile_id=11, public_key="pk_live_test", is_enabled=True
    )

    async def _get_installation(_self, profile_id):
        return installation if profile_id == 11 else None

    monkeypatch.setattr(
        "app.api.routes.chat.decode_widget_token",
        lambda _token: (11, 17, "pk_live_test"),
    )
    monkeypatch.setattr(
        "app.repositories.widget_repository.WidgetRepository.get_for_profile",
        _get_installation,
    )


def _payload():
    return {"message": "hello", "widget_token": "signed-widget-token"}


def _reserve_trap_msg(reason):
    async def _trap(_self, installation_id, ip_hash, day, limit):
        raise AssertionError(reason)

    return _trap


async def test_over_daily_ip_budget_returns_429(client, monkeypatch):
    _stub_widget(monkeypatch)

    async def _reserve(_self, installation_id, ip_hash, day, limit):
        return False  # this IP is at its daily ceiling

    monkeypatch.setattr(
        "app.repositories.widget_repository.WidgetRepository.reserve_visitor_message",
        _reserve,
    )

    response = await client.post("/chat/stream", json=_payload(), headers=IP_HEADER)

    assert response.status_code == 429
    assert "Daily message limit" in response.json()["detail"]


async def test_rejection_happens_before_any_subscription_work(client, monkeypatch):
    """The budget is checked first, so a rejected visitor never creates a trial
    row or consumes the owner's monthly quota (the profile fetch precedes both)."""
    _stub_widget(monkeypatch)

    async def _reserve(_self, installation_id, ip_hash, day, limit):
        return False

    async def _profile_trap(_self, profile_id):
        raise AssertionError("a rejected visitor must not reach subscription work")

    monkeypatch.setattr(
        "app.repositories.widget_repository.WidgetRepository.reserve_visitor_message",
        _reserve,
    )
    monkeypatch.setattr(
        "app.repositories.profile_repository.ProfileRepository.get", _profile_trap
    )

    response = await client.post("/chat/stream", json=_payload(), headers=IP_HEADER)

    assert response.status_code == 429


async def test_missing_ip_header_skips_the_budget(client, monkeypatch):
    _stub_widget(monkeypatch)
    record = {}
    monkeypatch.setattr(
        "app.repositories.widget_repository.WidgetRepository.reserve_visitor_message",
        _reserve_trap_msg("no Worker-attested IP -> the budget must be skipped"),
    )
    monkeypatch.setattr("app.api.routes.chat.stream_chat", make_fake_stream(record))

    response = await client.post("/chat/stream", json=_payload())

    assert response.status_code == 200
    assert record["installation_id"] == 17


async def test_zero_limit_disables_the_budget(client, settings, monkeypatch):
    monkeypatch.setattr(settings, "chat_daily_ip_message_limit", 0)
    _stub_widget(monkeypatch)
    record = {}
    monkeypatch.setattr(
        "app.repositories.widget_repository.WidgetRepository.reserve_visitor_message",
        _reserve_trap_msg("a zero limit must disable the budget"),
    )
    monkeypatch.setattr("app.api.routes.chat.stream_chat", make_fake_stream(record))

    response = await client.post("/chat/stream", json=_payload(), headers=IP_HEADER)

    assert response.status_code == 200


async def test_ip_is_hashed_and_day_is_utc_today(client, monkeypatch):
    """Only the SHA-256 of the IP reaches the repository, bucketed by UTC day
    against the default 100/day limit."""
    _stub_widget(monkeypatch)
    record = {}
    calls = []

    async def _reserve(_self, installation_id, ip_hash, day, limit):
        calls.append(
            {
                "installation_id": installation_id,
                "ip_hash": ip_hash,
                "day": day,
                "limit": limit,
            }
        )
        return True

    monkeypatch.setattr(
        "app.repositories.widget_repository.WidgetRepository.reserve_visitor_message",
        _reserve,
    )
    monkeypatch.setattr("app.api.routes.chat.stream_chat", make_fake_stream(record))

    response = await client.post("/chat/stream", json=_payload(), headers=IP_HEADER)

    assert response.status_code == 200
    assert calls == [
        {
            "installation_id": 17,
            "ip_hash": hashlib.sha256(b"203.0.113.8").hexdigest(),
            "day": datetime.now(timezone.utc).date(),
            "limit": 100,
        }
    ]

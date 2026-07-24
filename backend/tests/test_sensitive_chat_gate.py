import json
from types import SimpleNamespace

import pytest

from app.core.db import get_session
from app.main import app
from app.services import chat_service
from app.services.chat_service import run_turn
from app.services.sensitive_data_policy import BLOCK_CODE, BLOCK_MESSAGES
from tests.conftest import make_jwt

JWT_SECRET = "sensitive-gate-test-secret"


class FakeSession:
    def __init__(self):
        self.commits = 0
        self.rollbacks = 0

    async def commit(self):
        self.commits += 1

    async def rollback(self):
        self.rollbacks += 1


@pytest.fixture
def fake_session():
    session = FakeSession()

    async def dependency():
        yield session

    app.dependency_overrides[get_session] = dependency
    yield session
    app.dependency_overrides.pop(get_session, None)


def _sse_event(response) -> dict:
    events = [
        json.loads(line.removeprefix("data: "))
        for line in response.text.splitlines()
        if line.startswith("data: ")
    ]
    assert len(events) == 1
    return events[0]


def _install_route_traps(monkeypatch):
    calls: list[str] = []

    async def get_installation(_self, profile_id):
        calls.append("installation")
        return SimpleNamespace(
            id=17,
            profile_id=profile_id,
            public_key="pk_live_test",
            is_enabled=True,
        )

    async def trap(*_args, **_kwargs):
        raise AssertionError("blocked input reached quota, persistence, or chat service")

    monkeypatch.setattr(
        "app.api.routes.chat.decode_widget_token",
        lambda _token: (11, 17, "pk_live_test"),
    )
    monkeypatch.setattr(
        "app.repositories.widget_repository.WidgetRepository.get_for_profile",
        get_installation,
    )
    monkeypatch.setattr(
        "app.repositories.widget_repository.WidgetRepository.reserve_visitor_message",
        trap,
    )
    monkeypatch.setattr(
        "app.repositories.widget_repository.WidgetRepository.increment_usage",
        trap,
    )
    monkeypatch.setattr(
        "app.repositories.subscription_repository.SubscriptionRepository.get_or_create_trial",
        trap,
    )
    monkeypatch.setattr(
        "app.repositories.subscription_repository.SubscriptionRepository.reserve_account_message",
        trap,
    )
    monkeypatch.setattr("app.api.routes.chat.stream_chat", trap)
    return calls


async def test_new_widget_secret_is_blocked_before_quota_or_chat(
    client, settings, monkeypatch, fake_session
):
    monkeypatch.setattr(settings, "edge_shared_secret", "")
    monkeypatch.setattr(settings, "chat_daily_ip_message_limit", 100)
    calls = _install_route_traps(monkeypatch)

    response = await client.post(
        "/chat/stream",
        headers={"x-visitor-ip": "203.0.113.8"},
        json={
            "message": "password=hunter2",
            "widget_token": "signed-widget-token",
        },
    )

    assert response.status_code == 200
    assert _sse_event(response) == {
        "type": "input_blocked",
        "code": BLOCK_CODE,
        "message": BLOCK_MESSAGES["en"],
    }
    assert calls == ["installation"]
    assert fake_session.commits == 0
    assert fake_session.rollbacks == 0


async def test_existing_widget_secret_checks_ownership_then_blocks_without_usage(
    client, settings, monkeypatch, fake_session
):
    monkeypatch.setattr(settings, "edge_shared_secret", "")
    monkeypatch.setattr(settings, "chat_daily_ip_message_limit", 100)
    _install_route_traps(monkeypatch)
    conversation = SimpleNamespace(
        id=42,
        profile_id=11,
        visitor_session_id_hash="stored-session-hash",
    )

    async def get_conversation(_self, conversation_id):
        assert conversation_id == 42
        return conversation

    monkeypatch.setattr(
        "app.repositories.conversation_repository.ConversationRepository.get",
        get_conversation,
    )
    monkeypatch.setattr(
        "app.api.routes.chat.conversation_token_matches",
        lambda *_args, **_kwargs: None,
    )

    response = await client.post(
        "/chat/stream",
        headers={"x-visitor-ip": "203.0.113.8"},
        json={
            "message": "otp: 123456",
            "widget_token": "signed-widget-token",
            "conversation_id": 42,
            "conversation_token": "conversation-session",
        },
    )

    assert response.status_code == 200
    assert _sse_event(response)["code"] == BLOCK_CODE
    assert fake_session.commits == 0


async def test_admin_secret_is_blocked_after_auth_without_chat_service(
    client, settings, monkeypatch, fake_session
):
    monkeypatch.setattr(settings, "edge_shared_secret", "")
    monkeypatch.setattr(settings, "supabase_jwt_secret", JWT_SECRET)

    async def trap(*_args, **_kwargs):
        raise AssertionError("blocked admin input reached the chat service")

    monkeypatch.setattr("app.api.routes.chat.stream_chat", trap)
    response = await client.post(
        "/chat/stream",
        headers={"Authorization": f"Bearer {make_jwt(JWT_SECRET)}"},
        json={"message": "Η κάρτα είναι 4111111111111111"},
    )

    assert response.status_code == 200
    assert _sse_event(response) == {
        "type": "input_blocked",
        "code": BLOCK_CODE,
        "message": BLOCK_MESSAGES["el"],
    }
    # The commit belongs to admin access resolution, not chat persistence.
    assert fake_session.commits == 1


async def test_direct_run_turn_blocks_before_database_moderation_and_rag(
    monkeypatch, caplog
):
    touched: list[str] = []

    def session_trap():
        touched.append("database")
        raise AssertionError("blocked direct turn opened a database session")

    async def provider_trap(*_args, **_kwargs):
        touched.append("provider")
        raise AssertionError("blocked direct turn called a provider")

    monkeypatch.setattr(chat_service, "SessionLocal", session_trap)
    monkeypatch.setattr(chat_service.moderation, "classify", provider_trap)
    monkeypatch.setattr(chat_service, "search_knowledge", provider_trap)

    events = [
        event
        async for event in run_turn(
            "You are awful; Authorization: Bearer abcdefghijklmnopqrstuvwxyz",
            profile_id=7,
            conversation_id=42,
            installation_id=17,
        )
    ]

    assert events == [
        {
            "type": "input_blocked",
            "code": BLOCK_CODE,
            "message": BLOCK_MESSAGES["en"],
        }
    ]
    assert touched == []
    assert "question" not in json.dumps(events)

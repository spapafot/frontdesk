import pytest
from fastapi import HTTPException
from types import SimpleNamespace
from unittest.mock import AsyncMock

from app.services.live_auth import (
    conversation_token_matches,
    create_conversation_token,
    create_socket_ticket,
    decode_conversation_token,
    decode_socket_ticket,
    visitor_session_hash,
)


def test_return_to_ai_is_not_a_valid_live_action():
    from pydantic import ValidationError

    from app.schemas.live import InternalActionRequest

    with pytest.raises(ValidationError):
        InternalActionRequest.model_validate(
            {
                "actor": {
                    "actor_type": "visitor",
                    "profile_id": 1,
                    "conversation_id": 11,
                    "channel": "conversation",
                },
                "action": "return_to_ai",
            }
        )


def test_conversation_token_is_scoped_and_hash_bound(settings, monkeypatch):
    monkeypatch.setattr(settings, "widget_session_secret", "live-test-secret")
    token = create_conversation_token(11, 17, 29, "visitor-random-value")

    claims = conversation_token_matches(
        token,
        profile_id=11,
        conversation_id=29,
        stored_hash=visitor_session_hash("visitor-random-value"),
    )

    assert claims["installation_id"] == 17
    assert decode_conversation_token(token)["conversation_id"] == 29


@pytest.mark.parametrize(
    ("profile_id", "conversation_id", "stored_hash"),
    [
        (12, 29, visitor_session_hash("visitor-random-value")),
        (11, 30, visitor_session_hash("visitor-random-value")),
        (11, 29, visitor_session_hash("another-visitor")),
        (11, 29, None),
    ],
)
def test_conversation_token_rejects_scope_or_visitor_mismatch(
    settings, monkeypatch, profile_id, conversation_id, stored_hash
):
    monkeypatch.setattr(settings, "widget_session_secret", "live-test-secret")
    token = create_conversation_token(11, 17, 29, "visitor-random-value")

    with pytest.raises(HTTPException) as exc:
        conversation_token_matches(
            token,
            profile_id=profile_id,
            conversation_id=conversation_id,
            stored_hash=stored_hash,
        )
    assert exc.value.status_code == 401


def test_socket_ticket_contains_only_short_lived_actor_scope(settings, monkeypatch):
    monkeypatch.setattr(settings, "widget_session_secret", "live-test-secret")
    monkeypatch.setattr(settings, "live_socket_ticket_ttl_seconds", 60)
    ticket = create_socket_ticket(
        {
            "actor_type": "visitor",
            "profile_id": 11,
            "conversation_id": 29,
            "channel": "conversation",
        }
    )

    claims = decode_socket_ticket(ticket)
    assert claims["actor_type"] == "visitor"
    assert claims["profile_id"] == 11
    assert claims["exp"] - claims["iat"] == 60
    assert "jti" in claims


async def test_visitor_live_endpoint_is_dark_when_global_flag_is_off(
    client, settings, monkeypatch
):
    monkeypatch.setattr(settings, "live_human_escalation_enabled", False)
    response = await client.post(
        "/live/visitor/socket-ticket",
        json={
            "widget_token": "not-even-decoded-while-dark",
            "conversation_id": 11,
            "conversation_token": "existing-conversation-token",
        },
    )
    assert response.status_code == 404


async def test_visitor_live_endpoint_requires_existing_conversation_credentials(
    client, settings, monkeypatch
):
    monkeypatch.setattr(settings, "live_human_escalation_enabled", True)
    response = await client.post(
        "/live/visitor/socket-ticket",
        json={"widget_token": "signed-widget-token"},
    )
    assert response.status_code == 422


async def test_stale_visitor_conversation_returns_404_without_creating_one(
    client, settings, monkeypatch
):
    monkeypatch.setattr(settings, "live_human_escalation_enabled", True)
    monkeypatch.setattr(
        "app.api.routes.live.decode_widget_token",
        lambda _token: (7, 17, "pk_live_test"),
    )
    monkeypatch.setattr(
        "app.repositories.widget_repository.WidgetRepository.get_for_profile",
        AsyncMock(return_value=SimpleNamespace(
            id=17,
            public_key="pk_live_test",
            is_enabled=True,
        )),
    )
    monkeypatch.setattr(
        "app.repositories.profile_repository.ProfileRepository.get",
        AsyncMock(return_value=SimpleNamespace(
            id=7,
            live_human_escalation_enabled=True,
        )),
    )
    monkeypatch.setattr(
        "app.repositories.conversation_repository.ConversationRepository.get",
        AsyncMock(return_value=None),
    )
    create = AsyncMock()
    monkeypatch.setattr(
        "app.repositories.conversation_repository.ConversationRepository.create",
        create,
    )

    response = await client.post(
        "/live/visitor/socket-ticket",
        json={
            "widget_token": "signed-widget-token",
            "conversation_id": 999,
            "conversation_token": "stale-conversation-token",
        },
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Conversation not found."
    create.assert_not_awaited()


def test_transition_state_omits_messages_but_snapshot_keeps_them():
    from types import SimpleNamespace

    from app.api.routes.live import _conversation_state

    conversation = SimpleNamespace(
        id=11,
        profile_id=7,
        mode="waiting",
        assigned_user_id=None,
        escalation_requested_at=None,
        escalation_expires_at=None,
        accepted_at=None,
        closed_at=None,
    )

    assert "messages" not in _conversation_state(conversation)
    assert _conversation_state(conversation, [])["messages"] == []

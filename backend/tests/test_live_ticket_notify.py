"""The ticket action's owner-only ``notify`` payload.

The Worker uses ``notify`` to send the ticket-notification email and strips it
before broadcasting to any socket; the backend contract is that ``notify``
appears only on the ticket action's response, and only when the profile has a
notification email configured.
"""

from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest


def _profile(**over):
    base = dict(
        id=7,
        name="Acme",
        owner_user_id="user-1",
        live_human_escalation_enabled=True,
        notification_email="owner@acme.com",
    )
    base.update(over)
    return SimpleNamespace(**base)


def _conversation(**over):
    base = dict(
        id=11,
        profile_id=7,
        mode="pending_ticket",
        assigned_user_id=None,
        escalation_requested_at=None,
        escalation_expires_at=None,
        accepted_at=None,
        closed_at=None,
    )
    base.update(over)
    return SimpleNamespace(**base)


def _ticket(**over):
    base = dict(
        id=1,
        conversation_id=11,
        profile_id=7,
        customer_name="Vis",
        customer_email="vis@example.com",
        customer_message="Please call me back.",
        reason="no_agent_available",
        status="pending",
        assignee_user_id=None,
        archived=False,
        created_at=datetime.now(timezone.utc),
        resolved_at=None,
    )
    base.update(over)
    return SimpleNamespace(**base)


@pytest.fixture
def live_action_setup(settings, monkeypatch):
    """Wire the internal action route to in-memory objects; returns the profile
    so tests can vary its notification email."""
    monkeypatch.setattr(settings, "live_human_escalation_enabled", True)
    profile = _profile()
    monkeypatch.setattr(
        "app.repositories.profile_repository.ProfileRepository.get",
        AsyncMock(return_value=profile),
    )
    monkeypatch.setattr(
        "app.repositories.conversation_repository.ConversationRepository.get",
        AsyncMock(return_value=_conversation()),
    )
    monkeypatch.setattr(
        "app.repositories.live_repository.LiveRepository.create_ticket",
        AsyncMock(return_value=_ticket()),
    )
    monkeypatch.setattr(
        "app.repositories.live_repository.LiveRepository.add_event",
        AsyncMock(),
    )
    return profile


def _ticket_request() -> dict:
    return {
        "actor": {
            "actor_type": "visitor",
            "profile_id": 7,
            "conversation_id": 11,
            "channel": "conversation",
        },
        "action": "ticket",
        "payload": {
            "customer_email": "vis@example.com",
            "customer_name": "Vis",
            "customer_message": "Please call me back.",
        },
    }


async def test_ticket_action_returns_owner_notify(client, live_action_setup):
    response = await client.post("/internal/live/action", json=_ticket_request())

    assert response.status_code == 200
    body = response.json()
    assert body["mode"] == "closed"
    assert body["ticket"]["customer_email"] == "vis@example.com"
    assert body["notify"] == {"email": "owner@acme.com", "site_name": "Acme"}


async def test_ticket_action_omits_notify_without_notification_email(
    client, live_action_setup
):
    live_action_setup.notification_email = None

    response = await client.post("/internal/live/action", json=_ticket_request())

    assert response.status_code == 200
    body = response.json()
    assert body["mode"] == "closed"
    assert "notify" not in body


async def test_state_action_never_carries_notify(client, live_action_setup, monkeypatch):
    monkeypatch.setattr(
        "app.repositories.conversation_repository.ConversationRepository.get_messages",
        AsyncMock(return_value=[]),
    )

    response = await client.post(
        "/internal/live/action",
        json={
            "actor": {
                "actor_type": "visitor",
                "profile_id": 7,
                "conversation_id": 11,
                "channel": "conversation",
            },
            "action": "state",
        },
    )

    assert response.status_code == 200
    assert "notify" not in response.json()

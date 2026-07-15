"""Team members can operate live escalations on their team's sites.

Covers the three (previously owner-only) live gates made team-aware:
``operator_socket_ticket``, ``internal_authorize``, and the shared
``_authorized_conversation`` check behind ``/internal/live/action`` — plus the
owner-only gate on settings writes.
"""

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from fastapi import HTTPException

from app.api.routes import live
from app.services.live_auth import create_socket_ticket
from tests.conftest import make_jwt

OWNER = "owner-1"
MEMBER = "member-2"
SECRET = "team-access-socket-secret"


def _profile(**over) -> SimpleNamespace:
    base = dict(id=7, owner_user_id=OWNER, live_human_escalation_enabled=True)
    base.update(over)
    return SimpleNamespace(**base)


def _session() -> SimpleNamespace:
    return SimpleNamespace(commit=AsyncMock())


@pytest.fixture
def live_enabled(monkeypatch, settings):
    monkeypatch.setattr(settings, "live_human_escalation_enabled", True)
    monkeypatch.setattr(settings, "widget_session_secret", SECRET)


def _patch_membership(monkeypatch, membership):
    monkeypatch.setattr(
        "app.repositories.team_repository.TeamRepository.get_membership",
        AsyncMock(return_value=membership),
    )


# --- _operator_can_access ----------------------------------------------------


async def test_owner_can_access_without_team_lookup(monkeypatch):
    lookup = AsyncMock()
    monkeypatch.setattr(
        "app.repositories.team_repository.TeamRepository.get_membership", lookup
    )

    assert await live._operator_can_access(_profile(), OWNER, _session()) is True
    lookup.assert_not_awaited()


async def test_active_member_can_access(monkeypatch):
    _patch_membership(monkeypatch, SimpleNamespace(id=1, status="active"))

    assert await live._operator_can_access(_profile(), MEMBER, _session()) is True


async def test_non_member_cannot_access(monkeypatch):
    _patch_membership(monkeypatch, None)

    assert await live._operator_can_access(_profile(), "stranger", _session()) is False


async def test_missing_user_id_cannot_access(monkeypatch):
    assert await live._operator_can_access(_profile(), None, _session()) is False


# --- operator_socket_ticket ---------------------------------------------------


async def test_member_gets_inbox_socket_ticket(monkeypatch, live_enabled):
    monkeypatch.setattr(
        "app.repositories.profile_repository.ProfileRepository.get_accessible",
        AsyncMock(return_value=(_profile(), "member")),
    )

    result = await live.operator_socket_ticket(
        body=SimpleNamespace(site_id=7, channel="inbox", conversation_id=None),
        user=SimpleNamespace(id=MEMBER, email="member@acme.com"),
        session=_session(),
    )

    assert result.websocket_path == "/live/inbox/7"
    assert result.ticket


async def test_stranger_socket_ticket_404s(monkeypatch, live_enabled):
    monkeypatch.setattr(
        "app.repositories.profile_repository.ProfileRepository.get_accessible",
        AsyncMock(return_value=None),
    )

    with pytest.raises(HTTPException) as exc:
        await live.operator_socket_ticket(
            body=SimpleNamespace(site_id=7, channel="inbox", conversation_id=None),
            user=SimpleNamespace(id="stranger", email=None),
            session=_session(),
        )
    assert exc.value.status_code == 404


# --- internal authorize / action gate ------------------------------------------


def _operator_ticket(user_id: str) -> str:
    return create_socket_ticket(
        {
            "actor_type": "operator",
            "profile_id": 7,
            "conversation_id": None,
            "user_id": user_id,
            "display_name": "agent@acme.com",
            "channel": "inbox",
        }
    )


async def test_authorize_accepts_team_member(monkeypatch, live_enabled):
    monkeypatch.setattr(
        "app.repositories.profile_repository.ProfileRepository.get",
        AsyncMock(return_value=_profile()),
    )
    _patch_membership(monkeypatch, SimpleNamespace(id=1, status="active"))

    actor = await live.internal_authorize(
        body=SimpleNamespace(ticket=_operator_ticket(MEMBER)), session=_session()
    )

    assert actor["actor_type"] == "operator"
    assert actor["user_id"] == MEMBER


async def test_authorize_rejects_removed_member(monkeypatch, live_enabled):
    monkeypatch.setattr(
        "app.repositories.profile_repository.ProfileRepository.get",
        AsyncMock(return_value=_profile()),
    )
    _patch_membership(monkeypatch, None)

    with pytest.raises(HTTPException) as exc:
        await live.internal_authorize(
            body=SimpleNamespace(ticket=_operator_ticket(MEMBER)), session=_session()
        )
    assert exc.value.status_code == 403


# --- settings owner gate --------------------------------------------------------


async def test_member_cannot_write_settings(client, settings, monkeypatch):
    monkeypatch.setattr(settings, "edge_shared_secret", "")
    monkeypatch.setattr(settings, "supabase_jwt_secret", "settings-gate-secret")
    monkeypatch.setattr(
        "app.api.dependencies.ProfileRepository.get_accessible",
        AsyncMock(
            return_value=(
                SimpleNamespace(
                    id=7, owner_user_id=OWNER, notification_email="x@y.com"
                ),
                "member",
            )
        ),
    )

    r = await client.put(
        "/settings?site_id=7",
        json={"business_name": "Hijacked"},
        headers={"Authorization": f"Bearer {make_jwt('settings-gate-secret')}"},
    )
    assert r.status_code == 403


async def test_action_gate_rejects_removed_member(monkeypatch, live_enabled):
    """A member removed mid-conversation 403s on their next action, even over
    an already-open socket."""
    monkeypatch.setattr(
        "app.repositories.profile_repository.ProfileRepository.get",
        AsyncMock(return_value=_profile()),
    )
    _patch_membership(monkeypatch, None)

    from app.schemas.live import LiveActor

    actor = LiveActor(
        actor_type="operator",
        profile_id=7,
        conversation_id=99,
        user_id=MEMBER,
        display_name="agent@acme.com",
        channel="conversation",
    )
    with pytest.raises(HTTPException) as exc:
        await live._authorized_conversation(actor, _session())
    assert exc.value.status_code == 403

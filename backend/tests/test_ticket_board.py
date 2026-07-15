"""Board endpoints for escalation tickets.

Covers the status workflow (any operator), assignee validation (owner or
activated member only), the owner-only archive gate, the operators list that
feeds the assignee picker, and the legacy resolve endpoint's delegation.
"""

from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from tests.conftest import make_jwt

SECRET = "ticket-board-secret"
OWNER = "user-1"  # matches make_jwt's default sub
MEMBER = "member-2"


def _profile(**over):
    base = dict(
        id=7,
        name="Acme",
        owner_user_id=OWNER,
        live_human_escalation_enabled=True,
        notification_email="owner@acme.com",
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
def board_setup(settings, monkeypatch):
    """Authenticated owner access to site 7 with live escalation on. Returns a
    ``grant(role)`` re-patcher so member-role tests can flip the caller."""
    monkeypatch.setattr(settings, "supabase_jwt_secret", SECRET)
    monkeypatch.setattr(settings, "live_human_escalation_enabled", True)

    def grant(role="owner"):
        monkeypatch.setattr(
            "app.api.dependencies.ProfileRepository.get_accessible",
            AsyncMock(return_value=(_profile(), role)),
        )

    grant()
    return grant


def _auth(sub: str = OWNER) -> dict:
    return {"Authorization": f"Bearer {make_jwt(SECRET, sub=sub)}"}


def _patch_repo(monkeypatch, method: str, mock: AsyncMock) -> AsyncMock:
    monkeypatch.setattr(
        f"app.repositories.live_repository.LiveRepository.{method}", mock
    )
    return mock


# --- status -------------------------------------------------------------------


async def test_status_passes_the_actor_and_returns_the_ticket(
    client, board_setup, monkeypatch
):
    set_status = _patch_repo(
        monkeypatch,
        "set_ticket_status",
        AsyncMock(return_value=_ticket(status="in_progress", assignee_user_id=OWNER)),
    )

    r = await client.post(
        "/live/callbacks/1/status?site_id=7",
        json={"status": "in_progress"},
        headers=_auth(),
    )

    assert r.status_code == 200
    set_status.assert_awaited_once_with(1, 7, "in_progress", actor_user_id=OWNER)
    body = r.json()
    assert body["status"] == "in_progress"
    assert body["assignee_user_id"] == OWNER


async def test_members_can_move_tickets(client, board_setup, monkeypatch):
    board_setup(role="member")
    set_status = _patch_repo(
        monkeypatch,
        "set_ticket_status",
        AsyncMock(return_value=_ticket(status="in_progress", assignee_user_id=MEMBER)),
    )

    r = await client.post(
        "/live/callbacks/1/status?site_id=7",
        json={"status": "in_progress"},
        headers=_auth(sub=MEMBER),
    )

    assert r.status_code == 200
    set_status.assert_awaited_once_with(1, 7, "in_progress", actor_user_id=MEMBER)


async def test_status_404s_on_a_foreign_ticket(client, board_setup, monkeypatch):
    _patch_repo(monkeypatch, "set_ticket_status", AsyncMock(return_value=None))

    r = await client.post(
        "/live/callbacks/99/status?site_id=7",
        json={"status": "resolved"},
        headers=_auth(),
    )

    assert r.status_code == 404


async def test_status_rejects_unknown_values(client, board_setup):
    r = await client.post(
        "/live/callbacks/1/status?site_id=7",
        json={"status": "archived"},
        headers=_auth(),
    )

    assert r.status_code == 422


async def test_board_is_dark_when_live_escalation_is_off(
    client, board_setup, settings, monkeypatch
):
    monkeypatch.setattr(settings, "live_human_escalation_enabled", False)

    r = await client.post(
        "/live/callbacks/1/status?site_id=7",
        json={"status": "resolved"},
        headers=_auth(),
    )

    assert r.status_code == 404


# --- assignee -----------------------------------------------------------------


async def test_assigning_a_stranger_422s(client, board_setup, monkeypatch):
    monkeypatch.setattr(
        "app.repositories.team_repository.TeamRepository.get_membership",
        AsyncMock(return_value=None),
    )
    assign = _patch_repo(monkeypatch, "assign_ticket", AsyncMock())

    r = await client.post(
        "/live/callbacks/1/assignee?site_id=7",
        json={"assignee_user_id": "stranger"},
        headers=_auth(),
    )

    assert r.status_code == 422
    assign.assert_not_awaited()


async def test_assigning_the_owner_skips_the_membership_lookup(
    client, board_setup, monkeypatch
):
    lookup = AsyncMock()
    monkeypatch.setattr(
        "app.repositories.team_repository.TeamRepository.get_membership", lookup
    )
    _patch_repo(
        monkeypatch,
        "assign_ticket",
        AsyncMock(return_value=_ticket(assignee_user_id=OWNER)),
    )

    r = await client.post(
        "/live/callbacks/1/assignee?site_id=7",
        json={"assignee_user_id": OWNER},
        headers=_auth(),
    )

    assert r.status_code == 200
    assert r.json()["assignee_user_id"] == OWNER
    lookup.assert_not_awaited()


async def test_unassigning_skips_validation(client, board_setup, monkeypatch):
    lookup = AsyncMock()
    monkeypatch.setattr(
        "app.repositories.team_repository.TeamRepository.get_membership", lookup
    )
    assign = _patch_repo(
        monkeypatch, "assign_ticket", AsyncMock(return_value=_ticket())
    )

    r = await client.post(
        "/live/callbacks/1/assignee?site_id=7",
        json={"assignee_user_id": None},
        headers=_auth(),
    )

    assert r.status_code == 200
    lookup.assert_not_awaited()
    assign.assert_awaited_once_with(1, 7, None)


# --- archive (owner-only) -------------------------------------------------------


async def test_members_cannot_archive(client, board_setup, monkeypatch):
    board_setup(role="member")
    set_archived = _patch_repo(monkeypatch, "set_ticket_archived", AsyncMock())

    r = await client.post(
        "/live/callbacks/1/archive?site_id=7",
        json={"archived": True},
        headers=_auth(sub=MEMBER),
    )

    assert r.status_code == 403
    set_archived.assert_not_awaited()


async def test_only_resolved_tickets_can_be_archived(client, board_setup, monkeypatch):
    _patch_repo(
        monkeypatch, "get_ticket", AsyncMock(return_value=_ticket(status="pending"))
    )
    set_archived = _patch_repo(monkeypatch, "set_ticket_archived", AsyncMock())

    r = await client.post(
        "/live/callbacks/1/archive?site_id=7",
        json={"archived": True},
        headers=_auth(),
    )

    assert r.status_code == 409
    set_archived.assert_not_awaited()


async def test_owner_archives_and_unarchives_a_resolved_ticket(
    client, board_setup, monkeypatch
):
    resolved = _ticket(status="resolved", resolved_at=datetime.now(timezone.utc))
    _patch_repo(monkeypatch, "get_ticket", AsyncMock(return_value=resolved))
    set_archived = _patch_repo(
        monkeypatch,
        "set_ticket_archived",
        AsyncMock(return_value=_ticket(status="resolved", archived=True)),
    )

    r = await client.post(
        "/live/callbacks/1/archive?site_id=7",
        json={"archived": True},
        headers=_auth(),
    )
    assert r.status_code == 200
    assert r.json()["archived"] is True
    set_archived.assert_awaited_once_with(1, 7, True)

    resolved.archived = True
    set_archived.return_value = _ticket(status="resolved", archived=False)
    r = await client.post(
        "/live/callbacks/1/archive?site_id=7",
        json={"archived": False},
        headers=_auth(),
    )
    assert r.status_code == 200
    assert r.json()["archived"] is False


# --- operators ------------------------------------------------------------------


async def test_operators_lists_the_owner_and_activated_members_only(
    client, board_setup, monkeypatch
):
    monkeypatch.setattr(
        "app.repositories.team_repository.TeamRepository.list_members",
        AsyncMock(
            return_value=[
                SimpleNamespace(
                    invited_email="invited@acme.com", member_user_id=None, status="invited"
                ),
                SimpleNamespace(
                    invited_email="member@acme.com", member_user_id=MEMBER, status="active"
                ),
                SimpleNamespace(
                    invited_email="unbound@acme.com", member_user_id=None, status="active"
                ),
            ]
        ),
    )

    r = await client.get("/live/operators?site_id=7", headers=_auth())

    assert r.status_code == 200
    assert r.json() == [
        {"user_id": OWNER, "email": "owner@acme.com", "is_owner": True},
        {"user_id": MEMBER, "email": "member@acme.com", "is_owner": False},
    ]


# --- legacy resolve ---------------------------------------------------------------


async def test_resolve_delegates_to_the_status_workflow(
    client, board_setup, monkeypatch
):
    set_status = _patch_repo(
        monkeypatch,
        "set_ticket_status",
        AsyncMock(
            return_value=_ticket(
                status="resolved", resolved_at=datetime.now(timezone.utc)
            )
        ),
    )

    r = await client.post("/live/callbacks/1/resolve?site_id=7", headers=_auth())

    assert r.status_code == 200
    assert r.json()["status"] == "resolved"
    set_status.assert_awaited_once_with(1, 7, "resolved", actor_user_id=OWNER)

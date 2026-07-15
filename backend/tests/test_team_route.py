"""The /team router lets an account owner invite, list, and remove members.

Routes are keyed by the caller's own user id (structurally own-team-only). The
invite response carries the ``invite_notify`` payload for the edge Worker's
Cloudflare email send, including the one-time set-password action link.
"""

from datetime import datetime, timezone
from types import SimpleNamespace

from sqlalchemy.exc import IntegrityError

from app.services.supabase_admin import InviteLinkResult
from tests.conftest import make_jwt

JWT_SECRET = "team-route-jwt-secret"
LINK = "https://project.supabase.co/auth/v1/verify?token=abc&type=invite"


def _auth(token: str | None = None) -> dict:
    return {"Authorization": f"Bearer {token or make_jwt(JWT_SECRET)}"}


def _member(**over) -> SimpleNamespace:
    base = dict(
        id=11,
        owner_user_id="user-1",
        invited_email="member@acme.com",
        member_user_id=None,
        status="invited",
        created_at=datetime.now(timezone.utc),
        activated_at=None,
    )
    base.update(over)
    return SimpleNamespace(**base)


def _configure(
    monkeypatch,
    settings,
    calls,
    *,
    add_raises=None,
    link=InviteLinkResult(LINK, False, None),
    members=None,
    removed=True,
):
    monkeypatch.setattr(settings, "edge_shared_secret", "")
    monkeypatch.setattr(settings, "supabase_jwt_secret", JWT_SECRET)

    async def _add_member(_self, owner, email):
        calls["add"] = (owner, email)
        if add_raises is not None:
            raise add_raises
        return _member(owner_user_id=owner, invited_email=email)

    async def _list_members(_self, owner):
        return members or []

    async def _remove_member(_self, owner, member_id):
        calls["remove"] = (owner, member_id)
        return removed

    async def _generate(email):
        calls["generate"] = email
        return link

    async def _list_for_owner(_self, owner):
        return [SimpleNamespace(name="Acme Store")]

    monkeypatch.setattr(
        "app.repositories.team_repository.TeamRepository.add_member", _add_member
    )
    monkeypatch.setattr(
        "app.repositories.team_repository.TeamRepository.list_members", _list_members
    )
    monkeypatch.setattr(
        "app.repositories.team_repository.TeamRepository.remove_member", _remove_member
    )
    monkeypatch.setattr(
        "app.api.routes.team.supabase_admin.generate_invite_link", _generate
    )
    monkeypatch.setattr(
        "app.repositories.profile_repository.ProfileRepository.list_for_owner",
        _list_for_owner,
    )


async def test_invite_creates_member_and_notify_payload(client, settings, monkeypatch):
    calls: dict = {}
    _configure(monkeypatch, settings, calls)

    r = await client.post(
        "/team/members", json={"email": "Member@Acme.com "}, headers=_auth()
    )

    assert r.status_code == 201
    body = r.json()
    # Emails are normalized to lowercase before storage and account creation.
    assert calls["add"] == ("user-1", "member@acme.com")
    assert calls["generate"] == "member@acme.com"
    assert body["member"]["email"] == "member@acme.com"
    assert body["member"]["status"] == "invited"
    assert body["already_registered"] is False
    assert body["detail"] is None
    # The edge payload the Worker strips and turns into the invitation email.
    assert body["invite_notify"] == {
        "email": "member@acme.com",
        "team_name": "Acme Store",
        "invited_by": "admin@example.com",
        "action_link": LINK,
        "already_registered": False,
    }


async def test_invite_rejects_self(client, settings, monkeypatch):
    calls: dict = {}
    _configure(monkeypatch, settings, calls)

    r = await client.post(
        "/team/members", json={"email": "admin@example.com"}, headers=_auth()
    )

    assert r.status_code == 409
    assert "add" not in calls


async def test_invite_rejects_duplicate(client, settings, monkeypatch):
    calls: dict = {}
    _configure(
        monkeypatch,
        settings,
        calls,
        add_raises=IntegrityError("stmt", {}, Exception("dup")),
    )

    r = await client.post(
        "/team/members", json={"email": "member@acme.com"}, headers=_auth()
    )

    assert r.status_code == 409
    assert "generate" not in calls


async def test_invite_rejects_invalid_email(client, settings, monkeypatch):
    calls: dict = {}
    _configure(monkeypatch, settings, calls)

    for bad in ["not-an-email", "@acme.com", "member@", "member@nodot"]:
        r = await client.post("/team/members", json={"email": bad}, headers=_auth())
        assert r.status_code == 422, bad
    assert "add" not in calls


async def test_invite_degrades_without_service_key(client, settings, monkeypatch):
    calls: dict = {}
    _configure(
        monkeypatch,
        settings,
        calls,
        link=InviteLinkResult(None, False, "Invite saved, but no signup email..."),
    )

    r = await client.post(
        "/team/members", json={"email": "member@acme.com"}, headers=_auth()
    )

    # The membership row still lands; the caller sees the degradation notice.
    assert r.status_code == 201
    body = r.json()
    assert body["detail"].startswith("Invite saved")
    assert body["invite_notify"]["action_link"] is None


async def test_invite_reports_existing_account(client, settings, monkeypatch):
    calls: dict = {}
    _configure(monkeypatch, settings, calls, link=InviteLinkResult(None, True, None))

    r = await client.post(
        "/team/members", json={"email": "member@acme.com"}, headers=_auth()
    )

    assert r.status_code == 201
    body = r.json()
    assert body["already_registered"] is True
    assert "already has an account" in body["detail"]
    assert body["invite_notify"]["already_registered"] is True
    assert body["invite_notify"]["action_link"] is None


async def test_list_members(client, settings, monkeypatch):
    calls: dict = {}
    _configure(
        monkeypatch,
        settings,
        calls,
        members=[_member(), _member(id=12, status="active", member_user_id="user-9")],
    )

    r = await client.get("/team/members", headers=_auth())

    assert r.status_code == 200
    assert [(m["id"], m["status"]) for m in r.json()] == [
        (11, "invited"),
        (12, "active"),
    ]


async def test_remove_member(client, settings, monkeypatch):
    calls: dict = {}
    _configure(monkeypatch, settings, calls)

    r = await client.delete("/team/members/11", headers=_auth())

    assert r.status_code == 204
    assert calls["remove"] == ("user-1", 11)


async def test_remove_missing_member_404(client, settings, monkeypatch):
    calls: dict = {}
    _configure(monkeypatch, settings, calls, removed=False)

    r = await client.delete("/team/members/999", headers=_auth())

    assert r.status_code == 404

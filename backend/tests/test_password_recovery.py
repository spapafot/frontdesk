"""The public password-recovery endpoint must be indistinguishable for
existing and unknown accounts: same status, same body shape, and the reset
link confined to ``recovery_notify`` (which the Worker strips at the edge)."""

import pytest

from app.services import supabase_admin

_LINK = "https://project.supabase.co/auth/v1/verify?token=xyz&type=recovery"


@pytest.fixture
def recovery_link(monkeypatch):
    """Stub the Supabase Admin call; ``value['link']`` controls the outcome."""
    value = {"link": None, "emails": []}

    async def _generate(email):
        value["emails"].append(email)
        return value["link"]

    monkeypatch.setattr(supabase_admin, "generate_recovery_link", _generate)
    return value


async def test_known_account_returns_link_in_notify_only(client, recovery_link):
    recovery_link["link"] = _LINK

    response = await client.post(
        "/auth/password-recovery", json={"email": "Admin@Example.com "}
    )

    assert response.status_code == 200
    body = response.json()
    assert body["recovery_notify"] == {
        "email": "admin@example.com",
        "action_link": _LINK,
    }
    # The link must never leak outside the notify payload.
    assert _LINK not in body["detail"]
    # Normalized (trimmed + lowercased) email reaches the service.
    assert recovery_link["emails"] == ["admin@example.com"]


async def test_unknown_account_has_identical_shape(client, recovery_link):
    recovery_link["link"] = _LINK
    known = await client.post(
        "/auth/password-recovery", json={"email": "admin@example.com"}
    )

    recovery_link["link"] = None
    unknown = await client.post(
        "/auth/password-recovery", json={"email": "nobody@example.com"}
    )

    assert unknown.status_code == known.status_code == 200
    known_body = known.json()
    unknown_body = unknown.json()
    assert unknown_body["detail"] == known_body["detail"]
    assert set(unknown_body) == set(known_body)
    assert set(unknown_body["recovery_notify"]) == set(known_body["recovery_notify"])
    assert unknown_body["recovery_notify"]["action_link"] is None


async def test_requires_no_authorization_header(client, recovery_link):
    # Public route: no bearer token, no edge secret (scrubbed in conftest).
    response = await client.post(
        "/auth/password-recovery", json={"email": "admin@example.com"}
    )
    assert response.status_code == 200


@pytest.mark.parametrize("email", ["", "no-at-sign", "user@", "@domain.com", "user@nodot"])
async def test_malformed_email_is_rejected(client, recovery_link, email):
    response = await client.post("/auth/password-recovery", json={"email": email})

    assert response.status_code == 422
    # Rejection happens before the Supabase call - reveals format only.
    assert recovery_link["emails"] == []

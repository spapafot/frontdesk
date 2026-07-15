"""``generate_invite_link`` is best-effort: it must never raise (the invite
row alone grants access at the invitee's next sign-in) and must never leak the
action link into warnings."""

import httpx

from app.services import supabase_admin

_EMAIL = "member@acme.com"
_LINK = "https://project.supabase.co/auth/v1/verify?token=abc&type=invite"


def _install_client(monkeypatch, *, response=None, raises=None, capture=None):
    class _Client:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *exc):
            return False

        async def post(self, url, headers=None, json=None):
            if capture is not None:
                capture["url"] = url
                capture["headers"] = headers
                capture["json"] = json
            if raises is not None:
                raise raises
            return response

    monkeypatch.setattr(supabase_admin.httpx, "AsyncClient", _Client)


def _response(status_code=200, body=None):
    return httpx.Response(
        status_code,
        json=body,
        request=httpx.Request("POST", "https://project.supabase.co"),
    )


def _configure(monkeypatch, settings, *, app_base_url=""):
    monkeypatch.setattr(settings, "supabase_url", "https://project.supabase.co")
    monkeypatch.setattr(settings, "supabase_service_role_key", "service-role-key")
    monkeypatch.setattr(settings, "app_base_url", app_base_url)


async def test_generates_action_link(monkeypatch, settings):
    _configure(monkeypatch, settings, app_base_url="https://app.example.com")
    capture: dict = {}
    _install_client(
        monkeypatch, response=_response(body={"action_link": _LINK}), capture=capture
    )

    result = await supabase_admin.generate_invite_link(_EMAIL)

    assert result.action_link == _LINK
    assert result.already_registered is False
    assert result.warning is None
    assert capture["url"].endswith("/auth/v1/admin/generate_link")
    assert capture["headers"]["Authorization"] == "Bearer service-role-key"
    assert capture["json"] == {
        "type": "invite",
        "email": _EMAIL,
        "redirect_to": "https://app.example.com",
    }


async def test_reports_existing_account(monkeypatch, settings):
    _configure(monkeypatch, settings)
    _install_client(
        monkeypatch,
        response=_response(422, body={"error_code": "email_exists", "msg": "..."}),
    )

    result = await supabase_admin.generate_invite_link(_EMAIL)

    assert result.action_link is None
    assert result.already_registered is True
    assert result.warning is None


async def test_network_error_degrades_to_warning(monkeypatch, settings):
    _configure(monkeypatch, settings)
    _install_client(monkeypatch, raises=httpx.ConnectError("boom"))

    result = await supabase_admin.generate_invite_link(_EMAIL)

    assert result.action_link is None
    assert result.already_registered is False
    assert result.warning is not None


async def test_unconfigured_key_degrades_to_warning(monkeypatch, settings):
    monkeypatch.setattr(settings, "supabase_url", "https://project.supabase.co")
    monkeypatch.setattr(settings, "supabase_service_role_key", "")

    result = await supabase_admin.generate_invite_link(_EMAIL)

    assert result.action_link is None
    assert "SUPABASE_SERVICE_ROLE_KEY" in (result.warning or "")


async def test_unexpected_error_status_degrades_to_warning(monkeypatch, settings):
    _configure(monkeypatch, settings)
    _install_client(monkeypatch, response=_response(500, body={"msg": "boom"}))

    result = await supabase_admin.generate_invite_link(_EMAIL)

    assert result.action_link is None
    assert result.already_registered is False
    assert result.warning is not None

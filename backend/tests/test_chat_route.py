"""Admin chat derives its profile from the authenticated user and validates input."""

from types import SimpleNamespace

from tests.conftest import make_fake_stream, make_jwt

JWT_SECRET = "chat-route-jwt-secret"


async def test_admin_chat_uses_authenticated_profile(client, settings, monkeypatch):
    monkeypatch.setattr(settings, "edge_shared_secret", "")
    monkeypatch.setattr(settings, "supabase_jwt_secret", JWT_SECRET)
    record: dict = {}
    monkeypatch.setattr("app.api.routes.chat.stream_chat", make_fake_stream(record))

    response = await client.post(
        "/chat/stream",
        json={"message": "hello"},
        headers={"Authorization": f"Bearer {make_jwt(JWT_SECRET)}"},
    )
    assert response.status_code == 200
    _ = response.text
    assert record["profile_id"] == 7
    assert record["include_sources"] is True


async def test_admin_chat_honors_site_id(client, settings, monkeypatch):
    monkeypatch.setattr(settings, "edge_shared_secret", "")
    monkeypatch.setattr(settings, "supabase_jwt_secret", JWT_SECRET)
    record: dict = {}
    monkeypatch.setattr("app.api.routes.chat.stream_chat", make_fake_stream(record))

    async def _get_accessible(_self, site_id, _user_id, _email=None):
        return (SimpleNamespace(id=site_id), "owner") if site_id == 42 else None

    monkeypatch.setattr(
        "app.repositories.profile_repository.ProfileRepository.get_accessible",
        _get_accessible,
    )

    response = await client.post(
        "/chat/stream",
        json={"message": "hello", "site_id": 42},
        headers={"Authorization": f"Bearer {make_jwt(JWT_SECRET)}"},
    )
    assert response.status_code == 200
    _ = response.text
    assert record["profile_id"] == 42


async def test_admin_chat_rejects_foreign_site_id(client, settings, monkeypatch):
    monkeypatch.setattr(settings, "edge_shared_secret", "")
    monkeypatch.setattr(settings, "supabase_jwt_secret", JWT_SECRET)

    async def _get_accessible(_self, _site_id, _user_id, _email=None):
        return None

    monkeypatch.setattr(
        "app.repositories.profile_repository.ProfileRepository.get_accessible",
        _get_accessible,
    )

    response = await client.post(
        "/chat/stream",
        json={"message": "hello", "site_id": 999},
        headers={"Authorization": f"Bearer {make_jwt(JWT_SECRET)}"},
    )
    assert response.status_code == 404


async def test_widget_chat_never_requests_source_metadata(
    client, settings, monkeypatch
):
    monkeypatch.setattr(settings, "edge_shared_secret", "")
    installation = SimpleNamespace(
        id=17,
        profile_id=11,
        public_key="pk_live_test",
        is_enabled=True,
    )
    record: dict = {}

    async def get_installation(_self, profile_id):
        return installation if profile_id == 11 else None

    async def reserve_message(_self, _installation, _period):
        return True

    monkeypatch.setattr(
        "app.api.routes.chat.decode_widget_token",
        lambda _token: (11, 17, "pk_live_test"),
    )
    monkeypatch.setattr(
        "app.repositories.widget_repository.WidgetRepository.get_for_profile",
        get_installation,
    )
    monkeypatch.setattr(
        "app.repositories.widget_repository.WidgetRepository.reserve_message",
        reserve_message,
    )
    monkeypatch.setattr("app.api.routes.chat.stream_chat", make_fake_stream(record))

    response = await client.post(
        "/chat/stream",
        json={"message": "hello", "widget_token": "signed-widget-token"},
    )

    assert response.status_code == 200
    _ = response.text
    assert record["profile_id"] == 11
    assert record["include_sources"] is False


async def test_chat_message_has_hard_limit(client, settings, monkeypatch):
    monkeypatch.setattr(settings, "edge_shared_secret", "")
    record: dict = {}
    monkeypatch.setattr("app.api.routes.chat.stream_chat", make_fake_stream(record))

    response = await client.post("/chat/stream", json={"message": "x" * 4001})
    assert response.status_code == 422
    assert record == {}

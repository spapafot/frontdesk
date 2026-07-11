"""Admin chat derives its profile from the authenticated user and validates input."""

from tests.conftest import make_fake_stream


async def test_admin_chat_uses_authenticated_profile(client, settings, monkeypatch):
    monkeypatch.setattr(settings, "edge_shared_secret", "")
    record: dict = {}
    monkeypatch.setattr("app.api.routes.chat.stream_chat", make_fake_stream(record))

    response = await client.post("/chat/stream", json={"message": "hello"})
    assert response.status_code == 200
    _ = response.text
    assert record["profile_id"] == 7


async def test_chat_message_has_hard_limit(client, settings, monkeypatch):
    monkeypatch.setattr(settings, "edge_shared_secret", "")
    record: dict = {}
    monkeypatch.setattr("app.api.routes.chat.stream_chat", make_fake_stream(record))

    response = await client.post("/chat/stream", json={"message": "x" * 4001})
    assert response.status_code == 422
    assert record == {}

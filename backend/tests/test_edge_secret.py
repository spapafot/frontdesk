"""EdgeSecretMiddleware: only requests carrying the shared secret (injected by
the Cloudflare Worker) reach the app; /health and CORS preflight are exempt."""

from tests.conftest import make_fake_stream

SECRET = "s3cr3t-edge-value"


async def test_health_is_exempt_even_when_secret_enabled(client, settings, monkeypatch):
    monkeypatch.setattr(settings, "edge_shared_secret", SECRET)
    r = await client.get("/health")
    assert r.status_code == 200


async def test_missing_secret_is_rejected(client, settings, monkeypatch):
    monkeypatch.setattr(settings, "edge_shared_secret", SECRET)
    r = await client.post("/chat/stream", json={"message": "hi"})
    assert r.status_code == 403


async def test_wrong_secret_is_rejected(client, settings, monkeypatch):
    monkeypatch.setattr(settings, "edge_shared_secret", SECRET)
    r = await client.post(
        "/chat/stream", json={"message": "hi"}, headers={"x-edge-secret": "nope"}
    )
    assert r.status_code == 403


async def test_correct_secret_passes_through(client, settings, monkeypatch):
    monkeypatch.setattr(settings, "edge_shared_secret", SECRET)
    monkeypatch.setattr("app.api.routes.chat.stream_chat", make_fake_stream({}))
    r = await client.post(
        "/chat/stream", json={"message": "hi"}, headers={"x-edge-secret": SECRET}
    )
    assert r.status_code == 200


async def test_check_disabled_when_secret_empty(client, settings, monkeypatch):
    monkeypatch.setattr(settings, "edge_shared_secret", "")
    monkeypatch.setattr("app.api.routes.chat.stream_chat", make_fake_stream({}))
    r = await client.post("/chat/stream", json={"message": "hi"})
    assert r.status_code == 200


async def test_options_preflight_is_exempt(client, settings, monkeypatch):
    monkeypatch.setattr(settings, "edge_shared_secret", SECRET)
    r = await client.options(
        "/chat/stream",
        headers={
            "Origin": settings.frontend_origin,
            "Access-Control-Request-Method": "POST",
        },
    )
    # CORS middleware answers the preflight; the edge gate must not block it.
    assert r.status_code == 200

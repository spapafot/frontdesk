"""Public chat route hardening: the tenant is resolved from ``site_key`` only;
a ``business_id`` in the request body must be ignored (no tenant spoofing)."""

from tests.conftest import make_fake_stream


async def test_body_business_id_is_ignored(client, settings, monkeypatch):
    monkeypatch.setattr(settings, "edge_shared_secret", "")  # isolate from edge gate
    record: dict = {}
    monkeypatch.setattr("app.api.routes.chat.stream_chat", make_fake_stream(record))

    r = await client.post(
        "/chat/stream",
        json={"message": "hello", "business_id": 999, "site_key": "pk_live_abc"},
    )
    assert r.status_code == 200
    _ = r.text  # drain the streaming body so the generator runs

    # The route forces business_id=None regardless of the body...
    assert record["business_id"] is None
    # ...and passes the site_key through for tenant resolution.
    assert record["site_key"] == "pk_live_abc"


async def test_site_key_forwarded_when_no_business_id(client, settings, monkeypatch):
    monkeypatch.setattr(settings, "edge_shared_secret", "")
    record: dict = {}
    monkeypatch.setattr("app.api.routes.chat.stream_chat", make_fake_stream(record))

    r = await client.post(
        "/chat/stream", json={"message": "hi", "site_key": "pk_live_xyz"}
    )
    assert r.status_code == 200
    _ = r.text
    assert record["site_key"] == "pk_live_xyz"
    assert record["business_id"] is None

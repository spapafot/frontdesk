from types import SimpleNamespace


async def test_turnstile_required_rejects_missing_edge_marker(
    client, settings, monkeypatch
):
    monkeypatch.setattr(settings, "edge_shared_secret", "edge-secret")
    monkeypatch.setattr(settings, "turnstile_required", True)

    response = await client.post(
        "/widget/session",
        data={"key": "pk_live_test", "turnstile_token": "token"},
        headers={"origin": "https://customer.example", "x-edge-secret": "edge-secret"},
    )

    assert response.status_code == 403
    assert response.json()["detail"] == "Widget verification is required."


async def test_turnstile_enforcement_requires_edge_secret(client, settings, monkeypatch):
    monkeypatch.setattr(settings, "edge_shared_secret", "")
    monkeypatch.setattr(settings, "turnstile_required", True)

    response = await client.post(
        "/widget/session",
        data={"key": "pk_live_test", "turnstile_token": "token"},
        headers={"origin": "https://customer.example", "x-turnstile-verified": "1"},
    )

    assert response.status_code == 503


async def test_verified_request_keeps_existing_origin_and_session_checks(
    client, settings, monkeypatch
):
    installation = SimpleNamespace(
        id=17,
        profile_id=11,
        public_key="pk_live_test",
        allowed_origin="https://customer.example",
        is_enabled=True,
    )
    profile = SimpleNamespace(id=11, assistant_name="Helper", name="Acme")

    async def get_installation(_self, key):
        return installation if key == installation.public_key else None

    async def get_profile(_self, profile_id):
        return profile if profile_id == profile.id else None

    monkeypatch.setattr(
        "app.repositories.widget_repository.WidgetRepository.get_by_key",
        get_installation,
    )
    monkeypatch.setattr(
        "app.repositories.profile_repository.ProfileRepository.get", get_profile
    )
    monkeypatch.setattr(settings, "edge_shared_secret", "edge-secret")
    monkeypatch.setattr(settings, "turnstile_required", True)
    monkeypatch.setattr(settings, "widget_session_secret", "widget-secret")

    response = await client.post(
        "/widget/session",
        data={"key": "pk_live_test", "turnstile_token": "valid-token"},
        headers={
            "origin": "https://customer.example",
            "x-edge-secret": "edge-secret",
            "x-turnstile-verified": "1",
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["installation_id"] == 17
    assert body["origin"] == "https://customer.example"
    assert body["assistant_name"] == "Helper"


async def test_local_session_can_skip_turnstile_when_disabled(
    client, settings, monkeypatch
):
    installation = SimpleNamespace(
        id=17,
        profile_id=11,
        public_key="pk_live_test",
        allowed_origin="http://localhost:5173",
        is_enabled=True,
    )
    profile = SimpleNamespace(id=11, assistant_name="Helper", name="Local")

    async def get_installation(_self, _key):
        return installation

    async def get_profile(_self, _profile_id):
        return profile

    monkeypatch.setattr(
        "app.repositories.widget_repository.WidgetRepository.get_by_key",
        get_installation,
    )
    monkeypatch.setattr(
        "app.repositories.profile_repository.ProfileRepository.get", get_profile
    )
    monkeypatch.setattr(settings, "edge_shared_secret", "")
    monkeypatch.setattr(settings, "turnstile_required", False)
    monkeypatch.setattr(settings, "widget_session_secret", "widget-secret")

    response = await client.post(
        "/widget/session",
        data={"key": "pk_live_test"},
        headers={"origin": "http://localhost:5173"},
    )

    assert response.status_code == 200

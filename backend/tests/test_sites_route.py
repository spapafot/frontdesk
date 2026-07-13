"""The /sites router lists, creates, and deletes an owner's sites.

Like the other backend tests these avoid a real database by monkeypatching the
repository methods; the request still exercises auth, routing, ownership, and
response serialization.
"""

from datetime import datetime, timezone
from types import SimpleNamespace

from tests.conftest import make_jwt

JWT_SECRET = "sites-route-jwt-secret"


def _auth(token: str | None = None) -> dict:
    return {"Authorization": f"Bearer {token or make_jwt(JWT_SECRET)}"}


def _installation(**over) -> SimpleNamespace:
    base = dict(
        id=17,
        public_key="pk_live_abc",
        allowed_origin="https://acme.example",
        is_enabled=True,
        monthly_limit=5000,
    )
    base.update(over)
    return SimpleNamespace(**base)


def _patch_widget(monkeypatch, installation=None, usage=0):
    async def _get_for_profile(_self, _profile_id):
        return installation

    async def _usage(_self, _installation_id, _period):
        return usage

    monkeypatch.setattr(
        "app.repositories.widget_repository.WidgetRepository.get_for_profile",
        _get_for_profile,
    )
    monkeypatch.setattr(
        "app.repositories.widget_repository.WidgetRepository.usage", _usage
    )


async def test_create_site_returns_summary(client, settings, monkeypatch):
    monkeypatch.setattr(settings, "edge_shared_secret", "")
    monkeypatch.setattr(settings, "supabase_jwt_secret", JWT_SECRET)

    profile = SimpleNamespace(
        id=42,
        name="Acme",
        assistant_name="Aria",
        type="general",
        created_at=datetime.now(timezone.utc),
    )

    captured: dict = {}

    async def _create_site(
        _self, owner_user_id, name, type="general", assistant_name=None, allowed_origin=None
    ):
        captured["allowed_origin"] = allowed_origin
        return profile

    monkeypatch.setattr(
        "app.repositories.profile_repository.ProfileRepository.create_site", _create_site
    )
    _patch_widget(monkeypatch, _installation(), usage=3)

    r = await client.post(
        "/sites",
        json={"name": "Acme", "widget_origin": "https://acme.example"},
        headers=_auth(),
    )
    assert r.status_code == 201
    body = r.json()
    assert body["id"] == 42
    assert body["public_key"] == "pk_live_abc"
    assert body["widget_monthly_usage"] == 3
    # The submitted URL is normalized and handed to the repository.
    assert captured["allowed_origin"] == "https://acme.example"


async def test_create_site_rejects_invalid_origin(client, settings, monkeypatch):
    monkeypatch.setattr(settings, "edge_shared_secret", "")
    monkeypatch.setattr(settings, "supabase_jwt_secret", JWT_SECRET)

    r = await client.post(
        "/sites",
        json={"name": "Acme", "widget_origin": "not a url"},
        headers=_auth(),
    )
    assert r.status_code == 422


async def test_list_sites_returns_summaries(client, settings, monkeypatch):
    monkeypatch.setattr(settings, "edge_shared_secret", "")
    monkeypatch.setattr(settings, "supabase_jwt_secret", JWT_SECRET)

    profiles = [
        SimpleNamespace(
            id=1, name="A", assistant_name="Aria", type="general",
            created_at=datetime.now(timezone.utc),
        ),
        SimpleNamespace(
            id=2, name="B", assistant_name="Bo", type="general",
            created_at=datetime.now(timezone.utc),
        ),
    ]

    async def _list(_self, _owner):
        return profiles

    monkeypatch.setattr(
        "app.repositories.profile_repository.ProfileRepository.list_for_owner", _list
    )
    _patch_widget(monkeypatch, _installation())

    r = await client.get("/sites", headers=_auth())
    assert r.status_code == 200
    assert [s["id"] for s in r.json()] == [1, 2]


async def test_rename_site_updates_name(client, settings, monkeypatch):
    monkeypatch.setattr(settings, "edge_shared_secret", "")
    monkeypatch.setattr(settings, "supabase_jwt_secret", JWT_SECRET)

    profile = SimpleNamespace(
        id=5,
        name="Old name",
        assistant_name="Aria",
        type="general",
        created_at=datetime.now(timezone.utc),
    )

    async def _get_owned(_self, site_id, _owner):
        return profile if site_id == 5 else None

    monkeypatch.setattr(
        "app.repositories.profile_repository.ProfileRepository.get_owned", _get_owned
    )
    _patch_widget(monkeypatch, _installation())

    r = await client.patch("/sites/5", json={"name": "New name"}, headers=_auth())
    assert r.status_code == 200
    assert r.json()["name"] == "New name"
    assert profile.name == "New name"


async def test_rename_foreign_site_404(client, settings, monkeypatch):
    monkeypatch.setattr(settings, "edge_shared_secret", "")
    monkeypatch.setattr(settings, "supabase_jwt_secret", JWT_SECRET)

    async def _get_owned(_self, _site_id, _owner):
        return None

    monkeypatch.setattr(
        "app.repositories.profile_repository.ProfileRepository.get_owned", _get_owned
    )

    r = await client.patch("/sites/999", json={"name": "X"}, headers=_auth())
    assert r.status_code == 404


async def test_delete_only_site_conflicts(client, settings, monkeypatch):
    monkeypatch.setattr(settings, "edge_shared_secret", "")
    monkeypatch.setattr(settings, "supabase_jwt_secret", JWT_SECRET)

    async def _get_owned(_self, site_id, _owner):
        return SimpleNamespace(id=site_id)

    async def _list(_self, _owner):
        return [SimpleNamespace(id=5)]

    monkeypatch.setattr(
        "app.repositories.profile_repository.ProfileRepository.get_owned", _get_owned
    )
    monkeypatch.setattr(
        "app.repositories.profile_repository.ProfileRepository.list_for_owner", _list
    )

    r = await client.delete("/sites/5", headers=_auth())
    assert r.status_code == 409


async def test_delete_foreign_site_404(client, settings, monkeypatch):
    monkeypatch.setattr(settings, "edge_shared_secret", "")
    monkeypatch.setattr(settings, "supabase_jwt_secret", JWT_SECRET)

    async def _get_owned(_self, _site_id, _owner):
        return None

    monkeypatch.setattr(
        "app.repositories.profile_repository.ProfileRepository.get_owned", _get_owned
    )

    r = await client.delete("/sites/999", headers=_auth())
    assert r.status_code == 404


async def test_create_site_requires_auth(client, settings, monkeypatch):
    monkeypatch.setattr(settings, "edge_shared_secret", "")
    monkeypatch.setattr(settings, "supabase_jwt_secret", JWT_SECRET)
    r = await client.post("/sites", json={"name": "Acme"})
    assert r.status_code == 401


async def test_get_selected_site_rejects_foreign_site_id(client, settings, monkeypatch):
    # get_selected_site (used by every admin router) 404s on a site the caller
    # does not own, before any downstream work.
    monkeypatch.setattr(settings, "edge_shared_secret", "")
    monkeypatch.setattr(settings, "supabase_jwt_secret", JWT_SECRET)

    async def _get_owned(_self, _site_id, _owner):
        return None

    monkeypatch.setattr(
        "app.repositories.profile_repository.ProfileRepository.get_owned", _get_owned
    )

    r = await client.get("/analytics?site_id=999", headers=_auth())
    assert r.status_code == 404

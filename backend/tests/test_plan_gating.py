"""Plan-limit enforcement across the gated routes: over-limit actions return
402, and the pooled message quota returns 429. Entitlements and counts are
stubbed (the autouse fixture defaults to unlimited; these tests override it)."""

from types import SimpleNamespace

from app.core.plans import PlanLimits
from tests.conftest import make_jwt

JWT_SECRET = "gating-jwt-secret"


def _auth():
    return {"Authorization": f"Bearer {make_jwt(JWT_SECRET)}"}


def _limits(**overrides) -> PlanLimits:
    base = dict(
        sites=1,
        messages=500,
        seats=1,
        knowledge_chunks=5_000,
        live_handoff=False,
        remove_branding=False,
    )
    base.update(overrides)
    return PlanLimits(**base)


def _entitlements(monkeypatch, limits: PlanLimits):
    async def _resolve(session, user, owner_user_id):
        return limits

    monkeypatch.setattr("app.services.billing.resolve_entitlements", _resolve)


async def test_create_site_over_limit_returns_402(client, settings, monkeypatch):
    monkeypatch.setattr(settings, "edge_shared_secret", "")
    monkeypatch.setattr(settings, "supabase_jwt_secret", JWT_SECRET)
    _entitlements(monkeypatch, _limits(sites=1))

    async def _list(_self, _owner):
        return [SimpleNamespace(id=1)]  # already at the 1-site cap

    monkeypatch.setattr(
        "app.repositories.profile_repository.ProfileRepository.list_for_owner", _list
    )

    response = await client.post("/sites", json={"name": "Second site"}, headers=_auth())
    assert response.status_code == 402


async def test_invite_over_seat_limit_returns_402(client, settings, monkeypatch):
    monkeypatch.setattr(settings, "edge_shared_secret", "")
    monkeypatch.setattr(settings, "supabase_jwt_secret", JWT_SECRET)
    _entitlements(monkeypatch, _limits(seats=1))  # solo plan: no invitable seats

    async def _members(_self, _owner):
        return []

    monkeypatch.setattr(
        "app.repositories.team_repository.TeamRepository.list_members", _members
    )

    response = await client.post(
        "/team/members", json={"email": "teammate@example.com"}, headers=_auth()
    )
    assert response.status_code == 402


async def test_add_faq_over_knowledge_limit_returns_402(client, settings, monkeypatch):
    monkeypatch.setattr(settings, "edge_shared_secret", "")
    monkeypatch.setattr(settings, "supabase_jwt_secret", JWT_SECRET)
    _entitlements(monkeypatch, _limits(knowledge_chunks=5_000))

    async def _count(_self, _owner_user_id):
        return 5_000  # already at the chunk cap

    monkeypatch.setattr(
        "app.repositories.knowledge_repository.KnowledgeRepository.count_chunks_for_owner",
        _count,
    )

    response = await client.post(
        "/knowledge/faqs",
        json={"question": "What is this?", "answer": "This is the answer text."},
        headers=_auth(),
    )
    assert response.status_code == 402


async def test_enable_live_handoff_without_entitlement_returns_402(
    client, settings, monkeypatch
):
    monkeypatch.setattr(settings, "edge_shared_secret", "")
    monkeypatch.setattr(settings, "supabase_jwt_secret", JWT_SECRET)
    _entitlements(monkeypatch, _limits(live_handoff=False))

    response = await client.put(
        "/settings", json={"live_human_escalation_enabled": True}, headers=_auth()
    )
    assert response.status_code == 402


async def test_remove_branding_without_entitlement_returns_402(
    client, settings, monkeypatch
):
    monkeypatch.setattr(settings, "edge_shared_secret", "")
    monkeypatch.setattr(settings, "supabase_jwt_secret", JWT_SECRET)
    _entitlements(monkeypatch, _limits(remove_branding=False))

    response = await client.put(
        "/settings", json={"show_branding": False}, headers=_auth()
    )
    assert response.status_code == 402


async def test_widget_chat_over_pooled_quota_returns_429(client, settings, monkeypatch):
    monkeypatch.setattr(settings, "edge_shared_secret", "")
    installation = SimpleNamespace(
        id=17, profile_id=11, public_key="pk_live_test", is_enabled=True
    )

    async def _get_installation(_self, profile_id):
        return installation if profile_id == 11 else None

    async def _reserve(_self, _owner, _period, _base_limit):
        return False  # account is at its pooled monthly ceiling

    monkeypatch.setattr(
        "app.api.routes.chat.decode_widget_token",
        lambda _token: (11, 17, "pk_live_test"),
    )
    monkeypatch.setattr(
        "app.repositories.widget_repository.WidgetRepository.get_for_profile",
        _get_installation,
    )
    monkeypatch.setattr(
        "app.repositories.subscription_repository.SubscriptionRepository.reserve_account_message",
        _reserve,
    )

    response = await client.post(
        "/chat/stream",
        json={"message": "hello", "widget_token": "signed-widget-token"},
    )
    assert response.status_code == 429

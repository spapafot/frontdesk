from types import SimpleNamespace

import pytest

from app.api.routes.widget import _origin_allowed
from app.core.db import get_session
from app.main import app
from app.services.chat_service import _resolve_conversation
from app.services.live_auth import create_conversation_token, visitor_session_hash
from app.services.widget_auth import create_widget_token, decode_widget_token


class FakeConversations:
    def __init__(self, existing=None):
        self.existing = existing
        self.created_for = None

    async def get(self, conversation_id):
        return self.existing

    async def create(self, profile_id):
        self.created_for = profile_id
        return SimpleNamespace(id=99, profile_id=profile_id)


@pytest.mark.parametrize("existing_profile", [None, 22])
async def test_missing_or_foreign_conversation_starts_new(existing_profile):
    existing = (
        SimpleNamespace(id=5, profile_id=existing_profile)
        if existing_profile is not None
        else None
    )
    repo = FakeConversations(existing)
    conversation = await _resolve_conversation(repo, 11, 5)
    assert conversation.id == 99
    assert repo.created_for == 11


async def test_owned_conversation_is_reused():
    existing = SimpleNamespace(id=5, profile_id=11)
    repo = FakeConversations(existing)
    conversation = await _resolve_conversation(repo, 11, 5)
    assert conversation is existing
    assert repo.created_for is None


def test_widget_token_is_scoped_to_profile_installation_and_key(settings, monkeypatch):
    monkeypatch.setattr(settings, "widget_session_secret", "test-secret")
    token = create_widget_token(11, 17, "pk_live_current")
    assert decode_widget_token(token) == (11, 17, "pk_live_current")


def test_invalid_widget_token_is_rejected(settings, monkeypatch):
    monkeypatch.setattr(settings, "widget_session_secret", "test-secret")
    with pytest.raises(Exception) as exc:
        decode_widget_token("not-a-token")
    assert getattr(exc.value, "status_code", None) == 401


@pytest.mark.parametrize(
    "allowed, origin",
    [
        ("https://angelsfashion.gr", "https://angelsfashion.gr"),
        ("https://angelsfashion.gr", "https://www.angelsfashion.gr"),
        ("https://www.angelsfashion.gr", "https://angelsfashion.gr"),
        ("https://www.angelsfashion.gr", "https://www.angelsfashion.gr"),
    ],
)
def test_origin_allowed_treats_apex_and_www_as_same_site(allowed, origin):
    assert _origin_allowed(allowed, origin) is True


@pytest.mark.parametrize(
    "allowed, origin",
    [
        (None, "https://angelsfashion.gr"),
        ("https://angelsfashion.gr", "https://evil.gr"),
        ("https://angelsfashion.gr", "http://angelsfashion.gr"),  # scheme must match
        ("https://angelsfashion.gr", "https://shop.angelsfashion.gr"),  # other subdomain
        ("https://angelsfashion.gr", "https://wwwangelsfashion.gr"),
    ],
)
def test_origin_allowed_rejects_foreign_origins(allowed, origin):
    assert _origin_allowed(allowed, origin) is False


# --- POST /widget/rating -------------------------------------------------- #


@pytest.fixture
def override_session():
    """Yield a no-op session so the rating endpoint's ``session.commit()`` never
    touches a real database (the repositories are monkeypatched per-test)."""

    class _FakeSession:
        async def commit(self):
            pass

        async def rollback(self):
            pass

    async def _dep():
        yield _FakeSession()

    app.dependency_overrides[get_session] = _dep
    yield
    app.dependency_overrides.pop(get_session, None)


def _stub_rating_repos(monkeypatch, *, conversation, installation, recorded):
    async def _get_for_profile(self, profile_id):
        return installation

    async def _get(self, conversation_id):
        return conversation

    async def _set_rating(self, conv, rating):
        recorded["rating"] = rating
        conv.rating = rating
        return conv

    monkeypatch.setattr(
        "app.repositories.widget_repository.WidgetRepository.get_for_profile",
        _get_for_profile,
    )
    monkeypatch.setattr(
        "app.repositories.conversation_repository.ConversationRepository.get",
        _get,
    )
    monkeypatch.setattr(
        "app.repositories.conversation_repository.ConversationRepository.set_rating",
        _set_rating,
    )


async def test_widget_rating_accepts_owned_conversation(
    client, settings, monkeypatch, override_session
):
    monkeypatch.setattr(settings, "widget_session_secret", "test-secret")
    installation = SimpleNamespace(id=17, public_key="pk_live_current", is_enabled=True)
    conversation = SimpleNamespace(
        id=5,
        profile_id=11,
        visitor_session_id_hash=visitor_session_hash("visitor-abc"),
        rating=None,
    )
    recorded: dict = {}
    _stub_rating_repos(
        monkeypatch, conversation=conversation, installation=installation, recorded=recorded
    )

    response = await client.post(
        "/widget/rating",
        json={
            "widget_token": create_widget_token(11, 17, "pk_live_current"),
            "conversation_id": 5,
            "conversation_token": create_conversation_token(11, 17, 5, "visitor-abc"),
            "rating": "up",
        },
    )

    assert response.status_code == 204
    assert recorded["rating"] == "up"


async def test_widget_rating_rejects_foreign_visitor_session(
    client, settings, monkeypatch, override_session
):
    # A conversation token minted for a different visitor session must not be
    # able to rate someone else's conversation.
    monkeypatch.setattr(settings, "widget_session_secret", "test-secret")
    installation = SimpleNamespace(id=17, public_key="pk_live_current", is_enabled=True)
    conversation = SimpleNamespace(
        id=5,
        profile_id=11,
        visitor_session_id_hash=visitor_session_hash("visitor-abc"),
        rating=None,
    )
    recorded: dict = {}
    _stub_rating_repos(
        monkeypatch, conversation=conversation, installation=installation, recorded=recorded
    )

    response = await client.post(
        "/widget/rating",
        json={
            "widget_token": create_widget_token(11, 17, "pk_live_current"),
            "conversation_id": 5,
            "conversation_token": create_conversation_token(11, 17, 5, "attacker-session"),
            "rating": "up",
        },
    )

    assert response.status_code == 401
    assert "rating" not in recorded


async def test_widget_rating_404_for_conversation_of_other_profile(
    client, settings, monkeypatch, override_session
):
    monkeypatch.setattr(settings, "widget_session_secret", "test-secret")
    installation = SimpleNamespace(id=17, public_key="pk_live_current", is_enabled=True)
    conversation = SimpleNamespace(
        id=5,
        profile_id=22,  # owned by a different profile than the widget token (11)
        visitor_session_id_hash=visitor_session_hash("visitor-abc"),
        rating=None,
    )
    recorded: dict = {}
    _stub_rating_repos(
        monkeypatch, conversation=conversation, installation=installation, recorded=recorded
    )

    response = await client.post(
        "/widget/rating",
        json={
            "widget_token": create_widget_token(11, 17, "pk_live_current"),
            "conversation_id": 5,
            "conversation_token": create_conversation_token(11, 17, 5, "visitor-abc"),
            "rating": "up",
        },
    )

    assert response.status_code == 404
    assert "rating" not in recorded


async def test_widget_rating_rejects_invalid_rating_value(client, settings, monkeypatch):
    monkeypatch.setattr(settings, "widget_session_secret", "test-secret")
    response = await client.post(
        "/widget/rating",
        json={
            "widget_token": create_widget_token(11, 17, "pk_live_current"),
            "conversation_id": 5,
            "conversation_token": "irrelevant",
            "rating": "maybe",
        },
    )
    assert response.status_code == 422

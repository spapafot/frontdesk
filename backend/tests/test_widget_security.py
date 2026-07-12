from types import SimpleNamespace

import pytest

from app.api.routes.widget import _origin_allowed
from app.services.chat_service import _resolve_conversation
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

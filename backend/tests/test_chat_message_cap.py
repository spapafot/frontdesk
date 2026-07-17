"""run_turn per-conversation message cap: a widget conversation at the cap is
auto-closed with a canned reply and never reaches moderation, retrieval, or
the model; admin test chat and a disabled (0) limit are exempt."""

from types import SimpleNamespace

from app.services import chat_service
from app.services.chat_service import LIMIT_CLOSED, run_turn


def _setup(
    monkeypatch,
    *,
    count=0,
    count_trap=False,
    close_result=None,
    refresh_mode=None,
    allow_moderation=False,
    allow_search=False,
):
    """Monkeypatch every seam run_turn touches; return the recorder dict."""
    record = {
        "messages": [],
        "events": [],
        "count_calls": [],
        "close_calls": [],
        "search_calls": [],
        "session": None,
    }
    profile = SimpleNamespace(
        id=7,
        name="Acme",
        assistant_name="Aria",
        timezone="Europe/Athens",
        custom_instructions=None,
        moderation_enabled=True,
    )
    conversation = SimpleNamespace(id=42, profile_id=7, mode="ai", title=None)

    class FakeSession:
        def __init__(self):
            record["session"] = self
            self.commits = 0

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return False

        async def commit(self):
            self.commits += 1

        async def refresh(self, obj, attribute_names=None):
            if refresh_mode is not None:
                obj.mode = refresh_mode

    class FakeProfileRepo:
        def __init__(self, session):
            pass

        async def get(self, profile_id):
            return profile

    class FakeConversationRepo:
        def __init__(self, session):
            pass

        async def get(self, conversation_id):
            return conversation

        async def create(self, profile_id, **kwargs):
            return conversation

        async def add_message(self, conversation_id, role, content="", **kwargs):
            record["messages"].append(
                {"role": role, "content": content, "meta": kwargs.get("meta")}
            )

        async def count_user_messages(self, conversation_id):
            if count_trap:
                raise AssertionError("the cap must not be checked for this turn")
            record["count_calls"].append(conversation_id)
            return count

        async def get_messages(self, conversation_id):
            return []

    class FakeLiveRepo:
        def __init__(self, session):
            pass

        async def close_flagged(self, conversation_id, closed_at):
            record["close_calls"].append(conversation_id)
            return close_result

        async def add_event(
            self, conversation_id, type, actor_type, actor_id=None, meta=None
        ):
            record["events"].append(
                {"type": type, "actor_type": actor_type, "meta": meta or {}}
            )

    async def fake_classify(text):
        if not allow_moderation:
            raise AssertionError("a capped turn must not reach moderation")
        return None

    async def fake_search(session, profile_id, message, history=None):
        if not allow_search:
            raise AssertionError("a capped turn must not reach retrieval")
        record["search_calls"].append(message)
        return []

    def trap_client():
        raise AssertionError("a capped turn must not reach the model")

    monkeypatch.setattr(chat_service, "SessionLocal", FakeSession)
    monkeypatch.setattr(chat_service, "ProfileRepository", FakeProfileRepo)
    monkeypatch.setattr(chat_service, "ConversationRepository", FakeConversationRepo)
    monkeypatch.setattr(chat_service, "LiveRepository", FakeLiveRepo)
    monkeypatch.setattr(chat_service.moderation, "classify", fake_classify)
    monkeypatch.setattr(chat_service, "search_knowledge", fake_search)
    monkeypatch.setattr(chat_service, "get_client", trap_client)
    return record


async def _events(message="one more question", **kwargs):
    return [event async for event in run_turn(message, 7, 42, **kwargs)]


async def test_cap_reached_closes_with_canned_reply(monkeypatch):
    closed_conversation = SimpleNamespace(id=42, mode="closed")
    record = _setup(monkeypatch, count=30, close_result=closed_conversation)

    events = await _events(installation_id=17)

    assert [e["type"] for e in events] == ["conversation", "token", "mode_changed"]
    assert events[1]["content"] == LIMIT_CLOSED["en"]
    assert events[2]["mode"] == "closed"
    assert events[2]["conversation_id"] == 42
    # Only the canned reply is stored - the over-cap user message is rejected.
    assert [m["role"] for m in record["messages"]] == ["assistant"]
    assert record["messages"][0]["meta"]["limit_closed"] is True
    assert record["messages"][0]["meta"]["searched"] is False
    assert [e["type"] for e in record["events"]] == ["auto_closed"]
    assert record["events"][0]["actor_type"] == "system"
    assert record["events"][0]["meta"] == {"reason": "message_limit", "limit": 30}
    assert record["close_calls"] == [42]
    # Everything durable before the first post-cap yield: title + close block.
    assert record["session"].commits == 2


async def test_under_cap_proceeds_normally(monkeypatch):
    record = _setup(monkeypatch, count=29, allow_moderation=True, allow_search=True)

    events = await _events(installation_id=17)

    assert [e["type"] for e in events] == ["conversation", "token", "done"]
    assert record["count_calls"] == [42]
    assert record["close_calls"] == []


async def test_admin_test_chat_is_exempt(monkeypatch):
    _setup(monkeypatch, count_trap=True, allow_moderation=True, allow_search=True)

    events = await _events(installation_id=None)

    assert [e["type"] for e in events] == ["conversation", "token", "done"]


async def test_zero_limit_disables_the_cap(monkeypatch, settings):
    monkeypatch.setattr(settings, "chat_conversation_message_limit", 0)
    _setup(monkeypatch, count_trap=True, allow_moderation=True, allow_search=True)

    events = await _events(installation_id=17)

    assert [e["type"] for e in events] == ["conversation", "token", "done"]


async def test_greek_visitor_gets_greek_close_reply(monkeypatch):
    closed_conversation = SimpleNamespace(id=42, mode="closed")
    _setup(monkeypatch, count=30, close_result=closed_conversation)

    events = await _events(message="έχω άλλη μία ερώτηση", installation_id=17)

    assert events[1]["content"] == LIMIT_CLOSED["el"]


async def test_lost_close_race_reports_current_mode(monkeypatch):
    record = _setup(monkeypatch, count=30, close_result=None, refresh_mode="waiting")

    events = await _events(installation_id=17)

    assert [e["type"] for e in events] == ["conversation", "mode_changed"]
    assert events[1]["mode"] == "waiting"
    assert events[1]["conversation_id"] == 42
    # A lost race records nothing: no canned reply, no auto_closed event.
    assert record["messages"] == []
    assert record["events"] == []

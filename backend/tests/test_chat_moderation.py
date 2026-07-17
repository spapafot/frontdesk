"""run_turn moderation branch: warn on flagged visitor messages, auto-close on
repeated flags, and never let flagged turns reach retrieval or the model."""

from types import SimpleNamespace

from app.services import chat_service
from app.services.chat_service import (
    MODERATION_CLOSED,
    MODERATION_WARNINGS,
    _load_history,
    run_turn,
)
from app.services.moderation import ModerationVerdict

FLAGGED = ModerationVerdict(flagged=True, categories=("harassment",))


def _setup(
    monkeypatch,
    *,
    moderation_enabled=True,
    verdict=None,
    classify_trap=False,
    strikes=1,
    close_result=None,
    allow_search=False,
):
    """Monkeypatch every seam run_turn touches; return the recorder dict."""
    record = {
        "messages": [],
        "events": [],
        "classify_calls": [],
        "search_calls": [],
        "close_calls": [],
        "session": None,
    }
    profile = SimpleNamespace(
        id=7,
        name="Acme",
        assistant_name="Aria",
        timezone="Europe/Athens",
        custom_instructions=None,
        moderation_enabled=moderation_enabled,
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
            return None

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
            return 0

        async def get_messages(self, conversation_id):
            return []

    class FakeLiveRepo:
        def __init__(self, session):
            pass

        async def add_strike(self, conversation_id):
            return strikes

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
        if classify_trap:
            raise AssertionError("moderation must not run for this turn")
        record["classify_calls"].append(text)
        return verdict

    async def fake_search(session, profile_id, message, history=None):
        if not allow_search:
            raise AssertionError("a flagged turn must not reach retrieval")
        record["search_calls"].append(message)
        return []

    def trap_client():
        raise AssertionError("a flagged turn must not reach the model")

    monkeypatch.setattr(chat_service, "SessionLocal", FakeSession)
    monkeypatch.setattr(chat_service, "ProfileRepository", FakeProfileRepo)
    monkeypatch.setattr(chat_service, "ConversationRepository", FakeConversationRepo)
    monkeypatch.setattr(chat_service, "LiveRepository", FakeLiveRepo)
    monkeypatch.setattr(chat_service.moderation, "classify", fake_classify)
    monkeypatch.setattr(chat_service, "search_knowledge", fake_search)
    monkeypatch.setattr(chat_service, "get_client", trap_client)
    return record


async def _events(message="you are garbage", **kwargs):
    return [event async for event in run_turn(message, 7, 42, **kwargs)]


async def test_first_strike_warns_and_skips_rag_and_llm(monkeypatch):
    record = _setup(monkeypatch, verdict=FLAGGED, strikes=1)

    events = await _events(installation_id=17)

    assert [e["type"] for e in events] == ["conversation", "token", "done"]
    assert events[1]["content"] == MODERATION_WARNINGS["en"]
    # A moderation warning must not carry the "answered" flag: the widget only
    # treats an explicit answered=False as its talk-to-a-person signal.
    assert "answered" not in events[2]
    # Both the abusive message and the canned reply are stored, marked flagged.
    roles = [(m["role"], m["meta"].get("flagged")) for m in record["messages"]]
    assert roles == [("user", True), ("assistant", True)]
    assert record["messages"][0]["meta"]["categories"] == ["harassment"]
    assert record["messages"][1]["meta"]["searched"] is False
    assert [e["type"] for e in record["events"]] == ["message_flagged"]
    assert record["events"][0]["actor_type"] == "visitor"
    assert record["close_calls"] == []
    # Everything durable before the first post-moderation yield: title + block.
    assert record["session"].commits == 2


async def test_strike_limit_closes_the_conversation(monkeypatch):
    closed_conversation = SimpleNamespace(id=42, mode="closed")
    record = _setup(
        monkeypatch, verdict=FLAGGED, strikes=3, close_result=closed_conversation
    )

    events = await _events(installation_id=17)

    assert [e["type"] for e in events] == ["conversation", "token", "mode_changed"]
    assert events[1]["content"] == MODERATION_CLOSED["en"]
    assert events[2]["mode"] == "closed"
    assert events[2]["conversation_id"] == 42
    assert [e["type"] for e in record["events"]] == ["message_flagged", "auto_closed"]
    auto_closed = record["events"][1]
    assert auto_closed["actor_type"] == "system"
    assert auto_closed["meta"] == {"reason": "moderation", "strikes": 3}


async def test_lost_close_race_falls_back_to_a_warning(monkeypatch):
    record = _setup(monkeypatch, verdict=FLAGGED, strikes=3, close_result=None)

    events = await _events(installation_id=17)

    assert [e["type"] for e in events] == ["conversation", "token", "done"]
    assert events[1]["content"] == MODERATION_WARNINGS["en"]
    assert record["close_calls"] == [42]
    assert [e["type"] for e in record["events"]] == ["message_flagged"]


async def test_greek_visitors_get_greek_canned_replies(monkeypatch):
    _setup(monkeypatch, verdict=FLAGGED, strikes=1)
    warned = await _events(message="είσαι άχρηστος", installation_id=17)
    assert warned[1]["content"] == MODERATION_WARNINGS["el"]

    closed_conversation = SimpleNamespace(id=42, mode="closed")
    _setup(monkeypatch, verdict=FLAGGED, strikes=3, close_result=closed_conversation)
    closed = await _events(message="είσαι άχρηστος", installation_id=17)
    assert closed[1]["content"] == MODERATION_CLOSED["el"]


async def test_no_verdict_fails_open_to_a_normal_answer(monkeypatch):
    record = _setup(monkeypatch, verdict=None, allow_search=True)

    events = await _events(installation_id=17)

    # Moderation ran but returned no verdict; the turn proceeds through
    # retrieval to the safe fallback (no knowledge configured in this fake).
    assert record["classify_calls"] == ["you are garbage"]
    assert record["search_calls"] == ["you are garbage"]
    assert [e["type"] for e in events] == ["conversation", "token", "done"]
    assert events[1]["content"] == chat_service.safe_fallback("you are garbage")
    # No sources -> the done event marks the turn unanswered so the widget can
    # offer a human right away.
    assert events[2]["answered"] is False


async def test_admin_test_chat_is_never_moderated(monkeypatch):
    _setup(monkeypatch, classify_trap=True, allow_search=True)

    events = await _events(installation_id=None)

    assert [e["type"] for e in events] == ["conversation", "token", "done"]


async def test_per_site_toggle_disables_moderation(monkeypatch):
    _setup(
        monkeypatch, moderation_enabled=False, classify_trap=True, allow_search=True
    )

    events = await _events(installation_id=17)

    assert [e["type"] for e in events] == ["conversation", "token", "done"]


async def test_load_history_skips_flagged_messages():
    stored = [
        SimpleNamespace(role="user", content="abusive text", meta={"flagged": True}),
        SimpleNamespace(
            role="assistant",
            content=MODERATION_WARNINGS["en"],
            meta={"flagged": True, "moderation_warning": True},
        ),
        SimpleNamespace(role="user", content="what are your opening hours?", meta={}),
        SimpleNamespace(role="assistant", content="We open at 9.", meta=None),
    ]

    class FakeRepo:
        async def get_messages(self, conversation_id):
            return stored

    history = await _load_history(FakeRepo(), 42)

    assert history == [
        {"role": "user", "content": "what are your opening hours?"},
        {"role": "assistant", "content": "We open at 9."},
    ]

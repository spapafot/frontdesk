"""Conversation summaries are optional because generating one adds an LLM call
to an otherwise cheap history-detail request."""

from datetime import datetime, timezone
from types import SimpleNamespace

from app.api.routes import conversations


def _conversation(summary=None):
    return SimpleNamespace(
        id=11,
        profile_id=7,
        title="Question about shipping",
        started_at=datetime.now(timezone.utc),
        rating=None,
        summary=summary,
        mode="ai",
        assigned_user_id=None,
        escalation_requested_at=None,
        accepted_at=None,
        closed_at=None,
        last_message_at=None,
        visitor_session_id_hash="visitor-hash",
    )


class _Session:
    def __init__(self):
        self.committed = False

    async def commit(self):
        self.committed = True


def _install_repo(monkeypatch, conversation, calls):
    class _Repo:
        def __init__(self, _session):
            pass

        async def get(self, conversation_id):
            assert conversation_id == conversation.id
            return conversation

        async def get_messages(self, conversation_id):
            calls["messages"] = conversation_id
            return [
                SimpleNamespace(role="user", content="When will it arrive?"),
                SimpleNamespace(role="assistant", content="Usually in 2 days."),
            ]

        async def set_summary(self, item, summary):
            calls["stored"] = summary
            item.summary = summary

    monkeypatch.setattr(conversations, "ConversationRepository", _Repo)


async def test_summary_generation_is_disabled_by_default(settings, monkeypatch):
    monkeypatch.setattr(settings, "conversation_summaries_enabled", False)
    item = _conversation()
    calls = {}
    session = _Session()
    _install_repo(monkeypatch, item, calls)

    async def _summarize(_history):
        calls["summarized"] = True
        return "A generated summary."

    monkeypatch.setattr(conversations, "summarize_conversation", _summarize)

    result = await conversations.get_conversation(
        item.id, session=session, profile=SimpleNamespace(id=7)
    )

    assert result.summary is None
    assert calls == {}
    assert session.committed is False


async def test_summary_generation_can_be_enabled(settings, monkeypatch):
    monkeypatch.setattr(settings, "conversation_summaries_enabled", True)
    item = _conversation()
    calls = {}
    session = _Session()
    _install_repo(monkeypatch, item, calls)

    async def _summarize(history):
        calls["history"] = history
        return "The customer asked about shipping."

    monkeypatch.setattr(conversations, "summarize_conversation", _summarize)

    result = await conversations.get_conversation(
        item.id, session=session, profile=SimpleNamespace(id=7)
    )

    assert calls["messages"] == item.id
    assert calls["history"] == [
        {"role": "user", "content": "When will it arrive?"},
        {"role": "assistant", "content": "Usually in 2 days."},
    ]
    assert calls["stored"] == "The customer asked about shipping."
    assert result.summary == "The customer asked about shipping."
    assert session.committed is True

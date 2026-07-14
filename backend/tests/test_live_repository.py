from datetime import datetime, timezone
from unittest.mock import AsyncMock, Mock

import pytest

from app.models.conversation import Conversation, ConversationMessage
from app.repositories.live_repository import LiveRepository


def _session_returning(conversation: Conversation | None) -> Mock:
    result = Mock()
    result.scalar_one_or_none.return_value = conversation
    session = Mock()
    session.execute = AsyncMock(return_value=result)
    return session


def _executed_sql(session: Mock) -> str:
    return str(session.execute.await_args.args[0])


@pytest.mark.asyncio
async def test_add_message_uses_the_mapped_json_metadata_attribute():
    message = ConversationMessage(
        conversation_id=11,
        client_message_id="message-1",
        role="assistant",
        content="Hello",
        sender_type="operator",
        sender_user_id="owner-1",
        sender_display_name="Owner",
        meta={},
    )
    result = Mock()
    result.scalar_one_or_none.return_value = message
    session = Mock()
    session.execute = AsyncMock(return_value=result)
    session.get = AsyncMock(return_value=None)

    inserted, created = await LiveRepository(session).add_message_idempotent(
        conversation_id=11,
        client_message_id="message-1",
        role="assistant",
        content="Hello",
        sender_type="operator",
        sender_user_id="owner-1",
        sender_display_name="Owner",
    )

    assert inserted is message
    assert created is True
    session.execute.assert_awaited_once()


@pytest.mark.asyncio
async def test_escalate_is_an_atomic_ai_to_waiting_transition():
    conversation = Conversation(id=11, profile_id=7, mode="waiting")
    result = Mock()
    result.scalar_one_or_none.return_value = conversation
    session = Mock()
    session.execute = AsyncMock(return_value=result)

    transitioned = await LiveRepository(session).escalate(
        11,
        requested_at=Mock(),
        expires_at=Mock(),
    )

    assert transitioned is conversation
    statement = session.execute.await_args.args[0]
    sql = str(statement)
    assert "conversations.mode" in sql
    assert "UPDATE conversations" in sql


@pytest.mark.asyncio
async def test_cancel_is_conditional_on_the_waiting_mode():
    conversation = Conversation(id=11, profile_id=7, mode="ai")
    session = _session_returning(conversation)

    cancelled = await LiveRepository(session).cancel(11)

    assert cancelled is conversation
    sql = _executed_sql(session)
    assert "UPDATE conversations" in sql
    assert "conversations.mode = " in sql


@pytest.mark.asyncio
async def test_cancel_reports_a_lost_race_instead_of_writing_blindly():
    session = _session_returning(None)

    assert await LiveRepository(session).cancel(11) is None


@pytest.mark.asyncio
async def test_close_requires_human_mode_and_the_assigned_operator():
    session = _session_returning(None)

    closed = await LiveRepository(session).close(
        11, "owner-1", datetime.now(timezone.utc)
    )

    assert closed is None
    sql = _executed_sql(session)
    assert "UPDATE conversations" in sql
    assert "conversations.mode = " in sql
    assert "conversations.assigned_user_id = " in sql


@pytest.mark.asyncio
async def test_timeout_only_expires_a_passed_deadline():
    conversation = Conversation(id=11, profile_id=7, mode="pending_ticket")
    session = _session_returning(conversation)

    timed_out = await LiveRepository(session).timeout(
        11, datetime.now(timezone.utc)
    )

    assert timed_out is conversation
    sql = _executed_sql(session)
    assert "conversations.mode = " in sql
    assert "conversations.escalation_expires_at <= " in sql


@pytest.mark.asyncio
async def test_mark_unavailable_is_conditional_on_the_waiting_mode():
    session = _session_returning(None)

    assert (
        await LiveRepository(session).mark_unavailable(
            11, datetime.now(timezone.utc)
        )
        is None
    )
    sql = _executed_sql(session)
    assert "conversations.mode = " in sql

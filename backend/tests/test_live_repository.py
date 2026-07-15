from datetime import datetime, timezone
from unittest.mock import AsyncMock, Mock

import pytest
from sqlalchemy.dialects import postgresql

from app.models.conversation import Conversation, ConversationMessage, EscalationTicket
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


# --- escalation tickets ---------------------------------------------------------


def _board_ticket(**over) -> EscalationTicket:
    base = dict(
        id=1,
        conversation_id=11,
        profile_id=7,
        customer_email="vis@example.com",
        status="pending",
        assignee_user_id=None,
        archived=False,
        resolved_at=None,
    )
    base.update(over)
    return EscalationTicket(**base)


def _ticket_session(ticket: EscalationTicket | None) -> Mock:
    session = Mock()
    session.get = AsyncMock(return_value=ticket)
    session.flush = AsyncMock()
    return session


@pytest.mark.asyncio
async def test_resolving_stamps_resolved_at():
    ticket = _board_ticket()
    session = _ticket_session(ticket)

    updated = await LiveRepository(session).set_ticket_status(
        1, 7, "resolved", actor_user_id="owner-1"
    )

    assert updated is ticket
    assert ticket.status == "resolved"
    assert ticket.resolved_at is not None
    assert ticket.assignee_user_id is None  # resolve never auto-assigns


@pytest.mark.asyncio
async def test_reopening_clears_resolved_at():
    ticket = _board_ticket(
        status="resolved", resolved_at=datetime.now(timezone.utc)
    )
    session = _ticket_session(ticket)

    await LiveRepository(session).set_ticket_status(
        1, 7, "pending", actor_user_id="owner-1"
    )

    assert ticket.status == "pending"
    assert ticket.resolved_at is None


@pytest.mark.asyncio
async def test_in_progress_auto_assigns_only_when_unassigned():
    unassigned = _board_ticket()
    await LiveRepository(_ticket_session(unassigned)).set_ticket_status(
        1, 7, "in_progress", actor_user_id="member-2"
    )
    assert unassigned.assignee_user_id == "member-2"

    assigned = _board_ticket(assignee_user_id="owner-1")
    await LiveRepository(_ticket_session(assigned)).set_ticket_status(
        1, 7, "in_progress", actor_user_id="member-2"
    )
    assert assigned.assignee_user_id == "owner-1"


@pytest.mark.asyncio
async def test_ticket_mutators_hide_foreign_profiles():
    repo = LiveRepository(_ticket_session(_board_ticket(profile_id=999)))

    assert await repo.set_ticket_status(1, 7, "resolved", actor_user_id="x") is None
    assert await repo.assign_ticket(1, 7, "owner-1") is None
    assert await repo.set_ticket_archived(1, 7, True) is None


@pytest.mark.asyncio
async def test_set_ticket_archived_flips_the_flag():
    ticket = _board_ticket(status="resolved")
    session = _ticket_session(ticket)
    repo = LiveRepository(session)

    await repo.set_ticket_archived(1, 7, True)
    assert ticket.archived is True

    await repo.set_ticket_archived(1, 7, False)
    assert ticket.archived is False


@pytest.mark.asyncio
async def test_create_ticket_upsert_resurfaces_archived_tickets():
    result = Mock()
    result.scalar_one.return_value = _board_ticket()
    session = Mock()
    session.execute = AsyncMock(return_value=result)

    await LiveRepository(session).create_ticket(
        conversation_id=11,
        profile_id=7,
        customer_email="vis@example.com",
        customer_name=None,
        customer_message=None,
    )

    statement = session.execute.await_args.args[0]
    sql = str(statement.compile(dialect=postgresql.dialect()))
    on_conflict = sql.split("ON CONFLICT")[1]
    assert "archived" in on_conflict
    assert "assignee_user_id" in on_conflict


@pytest.mark.asyncio
async def test_list_tickets_orders_by_creation_time_only():
    result = Mock()
    result.scalars.return_value = []
    session = Mock()
    session.execute = AsyncMock(return_value=result)

    await LiveRepository(session).list_tickets(7)

    sql = _executed_sql(session)
    order_by = sql.split("ORDER BY")[1]
    assert "escalation_tickets.created_at DESC" in order_by
    assert "status" not in order_by

from unittest.mock import AsyncMock, Mock

import pytest

from app.models.conversation import Conversation, ConversationMessage
from app.repositories.conversation_repository import ConversationRepository
from app.repositories.live_repository import LiveRepository


def _session_for(conversation: Conversation | None) -> Mock:
    session = Mock()
    session.add = Mock()
    session.flush = AsyncMock()
    session.get = AsyncMock(return_value=conversation)
    return session


@pytest.mark.asyncio
async def test_set_archived_stamps_and_clears_archived_at():
    conversation = Conversation(id=11, profile_id=7)
    repo = ConversationRepository(_session_for(conversation))

    await repo.set_archived(conversation, True)
    assert conversation.archived_at is not None

    await repo.set_archived(conversation, False)
    assert conversation.archived_at is None


@pytest.mark.asyncio
async def test_add_message_unarchives_the_conversation():
    """New activity must resurface an archived conversation in History -
    otherwise a returning visitor's messages would be invisible to the owner."""
    conversation = Conversation(id=11, profile_id=7)
    conversation.archived_at = Mock()
    repo = ConversationRepository(_session_for(conversation))

    await repo.add_message(11, "user", "hello again")

    assert conversation.archived_at is None
    assert conversation.last_message_at is not None


@pytest.mark.asyncio
async def test_live_message_insert_unarchives_the_conversation():
    conversation = Conversation(id=11, profile_id=7)
    conversation.archived_at = Mock()
    message = ConversationMessage(
        conversation_id=11,
        client_message_id="message-1",
        role="user",
        content="hello again",
        sender_type="visitor",
        meta={},
    )
    result = Mock()
    result.scalar_one_or_none.return_value = message
    session = _session_for(conversation)
    session.execute = AsyncMock(return_value=result)

    inserted, created = await LiveRepository(session).add_message_idempotent(
        conversation_id=11,
        client_message_id="message-1",
        role="user",
        content="hello again",
        sender_type="visitor",
        sender_user_id=None,
        sender_display_name=None,
    )

    assert created is True
    assert conversation.archived_at is None
    assert conversation.last_message_at is not None

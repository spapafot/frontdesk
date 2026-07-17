from typing import Any

from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.conversation import Conversation, ConversationMessage


class ConversationRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get(self, conversation_id: int) -> Conversation | None:
        return await self.session.get(Conversation, conversation_id)

    async def list_conversations(self, profile_id: int) -> list[Conversation]:
        stmt = (
            select(Conversation)
            .where(Conversation.profile_id == profile_id)
            .order_by(Conversation.id.desc())
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def create(
        self,
        profile_id: int,
        channel: str = "chat",
        visitor_session_id_hash: str | None = None,
    ) -> Conversation:
        conversation = Conversation(
            profile_id=profile_id,
            channel=channel,
            visitor_session_id_hash=visitor_session_id_hash,
        )
        self.session.add(conversation)
        await self.session.flush()
        return conversation

    async def rename(self, conversation: Conversation, title: str) -> Conversation:
        conversation.title = title
        await self.session.flush()
        return conversation

    async def set_rating(self, conversation: Conversation, rating: str) -> Conversation:
        conversation.rating = rating
        await self.session.flush()
        return conversation

    async def set_summary(self, conversation: Conversation, summary: str) -> Conversation:
        conversation.summary = summary
        await self.session.flush()
        return conversation

    async def delete(self, conversation: Conversation) -> None:
        await self.session.delete(conversation)
        await self.session.flush()

    async def add_message(
        self,
        conversation_id: int,
        role: str,
        content: str = "",
        tool_name: str | None = None,
        meta: dict[str, Any] | None = None,
        client_message_id: str | None = None,
        sender_type: str | None = None,
        sender_user_id: str | None = None,
        sender_display_name: str | None = None,
    ) -> ConversationMessage:
        message = ConversationMessage(
            conversation_id=conversation_id,
            role=role,
            content=content,
            tool_name=tool_name,
            meta=meta or {},
            client_message_id=client_message_id,
            sender_type=sender_type or ("visitor" if role == "user" else "ai"),
            sender_user_id=sender_user_id,
            sender_display_name=sender_display_name,
        )
        self.session.add(message)
        conversation = await self.get(conversation_id)
        if conversation is not None:
            conversation.last_message_at = datetime.now(timezone.utc)
        await self.session.flush()
        return message

    async def count_user_messages(self, conversation_id: int) -> int:
        """All persisted visitor turns, including moderation-flagged ones."""
        result = await self.session.execute(
            select(func.count())
            .select_from(ConversationMessage)
            .where(
                ConversationMessage.conversation_id == conversation_id,
                ConversationMessage.role == "user",
            )
        )
        return int(result.scalar_one())

    async def get_messages(self, conversation_id: int) -> list[ConversationMessage]:
        stmt = (
            select(ConversationMessage)
            .where(ConversationMessage.conversation_id == conversation_id)
            .order_by(ConversationMessage.id)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

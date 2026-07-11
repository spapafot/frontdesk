from typing import Any

from sqlalchemy import select
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

    async def create(self, profile_id: int, channel: str = "chat") -> Conversation:
        conversation = Conversation(profile_id=profile_id, channel=channel)
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
    ) -> ConversationMessage:
        message = ConversationMessage(
            conversation_id=conversation_id,
            role=role,
            content=content,
            tool_name=tool_name,
            meta=meta or {},
        )
        self.session.add(message)
        await self.session.flush()
        return message

    async def get_messages(self, conversation_id: int) -> list[ConversationMessage]:
        stmt = (
            select(ConversationMessage)
            .where(ConversationMessage.conversation_id == conversation_id)
            .order_by(ConversationMessage.id)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

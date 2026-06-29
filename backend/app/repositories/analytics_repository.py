from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.conversation import Conversation, ConversationMessage


class AnalyticsRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def overview(self, business_id: int) -> dict:
        total = await self.session.scalar(
            select(func.count(Conversation.id)).where(
                Conversation.business_id == business_id
            )
        )

        week_ago = datetime.now(timezone.utc) - timedelta(days=7)
        last_7_days = await self.session.scalar(
            select(func.count(Conversation.id)).where(
                Conversation.business_id == business_id,
                Conversation.started_at >= week_ago,
            )
        )

        rating_rows = await self.session.execute(
            select(Conversation.rating, func.count(Conversation.id))
            .where(Conversation.business_id == business_id)
            .group_by(Conversation.rating)
        )
        ratings = {"up": 0, "down": 0, "none": 0}
        for rating, count in rating_rows.all():
            if rating == "up":
                ratings["up"] = count
            elif rating == "down":
                ratings["down"] = count
            else:
                ratings["none"] += count

        return {
            "total_conversations": total or 0,
            "last_7_days": last_7_days or 0,
            "ratings": ratings,
        }

    async def unanswered(self, business_id: int, limit: int = 100) -> list[dict]:
        """Assistant turns that searched the knowledge base but found nothing."""
        stmt = (
            select(
                ConversationMessage.conversation_id,
                ConversationMessage.meta["question"].astext.label("question"),
                ConversationMessage.created_at,
            )
            .join(Conversation, Conversation.id == ConversationMessage.conversation_id)
            .where(
                Conversation.business_id == business_id,
                ConversationMessage.role == "assistant",
                ConversationMessage.meta["searched"].astext == "true",
                ConversationMessage.meta["had_sources"].astext == "false",
            )
            .order_by(ConversationMessage.id.desc())
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        return [
            {
                "conversation_id": row.conversation_id,
                "question": row.question,
                "created_at": row.created_at,
            }
            for row in result.all()
            if row.question
        ]

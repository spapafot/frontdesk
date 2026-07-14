from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.conversation import (
    Conversation,
    ConversationEvent,
    ConversationMessage,
    EscalationTicket,
)


class LiveRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def add_event(
        self,
        conversation_id: int,
        type: str,
        actor_type: str,
        actor_id: str | None = None,
        meta: dict[str, Any] | None = None,
    ) -> ConversationEvent:
        event = ConversationEvent(
            conversation_id=conversation_id,
            type=type,
            actor_type=actor_type,
            actor_id=actor_id,
            meta=meta or {},
        )
        self.session.add(event)
        await self.session.flush()
        return event

    async def accept(
        self, conversation_id: int, user_id: str
    ) -> Conversation | None:
        now = datetime.now(timezone.utc)
        result = await self.session.execute(
            update(Conversation)
            .where(
                Conversation.id == conversation_id,
                Conversation.mode == "waiting",
                Conversation.assigned_user_id.is_(None),
                Conversation.escalation_expires_at > now,
            )
            .values(
                mode="human",
                assigned_user_id=user_id,
                accepted_at=now,
                closed_at=None,
            )
            .returning(Conversation)
        )
        return result.scalar_one_or_none()

    async def escalate(
        self,
        conversation_id: int,
        *,
        requested_at: datetime,
        expires_at: datetime,
    ) -> Conversation | None:
        """Atomically perform the one permitted AI-to-waiting transition."""
        result = await self.session.execute(
            update(Conversation)
            .where(
                Conversation.id == conversation_id,
                Conversation.mode == "ai",
            )
            .values(
                mode="waiting",
                assigned_user_id=None,
                escalation_requested_at=requested_at,
                escalation_expires_at=expires_at,
                accepted_at=None,
                closed_at=None,
            )
            .returning(Conversation)
        )
        return result.scalar_one_or_none()

    async def cancel(self, conversation_id: int) -> Conversation | None:
        """Atomically revert waiting to AI; a no-op if an operator already won."""
        result = await self.session.execute(
            update(Conversation)
            .where(
                Conversation.id == conversation_id,
                Conversation.mode == "waiting",
            )
            .values(
                mode="ai",
                assigned_user_id=None,
                escalation_expires_at=None,
            )
            .returning(Conversation)
        )
        return result.scalar_one_or_none()

    async def close(
        self, conversation_id: int, user_id: str, closed_at: datetime
    ) -> Conversation | None:
        """Atomically close a human conversation still assigned to ``user_id``."""
        result = await self.session.execute(
            update(Conversation)
            .where(
                Conversation.id == conversation_id,
                Conversation.mode == "human",
                Conversation.assigned_user_id == user_id,
            )
            .values(mode="closed", closed_at=closed_at)
            .returning(Conversation)
        )
        return result.scalar_one_or_none()

    async def timeout(self, conversation_id: int, now: datetime) -> Conversation | None:
        """Atomically expire a waiting escalation whose deadline has passed."""
        result = await self.session.execute(
            update(Conversation)
            .where(
                Conversation.id == conversation_id,
                Conversation.mode == "waiting",
                Conversation.escalation_expires_at.is_not(None),
                Conversation.escalation_expires_at <= now,
            )
            .values(mode="pending_ticket")
            .returning(Conversation)
        )
        return result.scalar_one_or_none()

    async def mark_unavailable(
        self, conversation_id: int, now: datetime
    ) -> Conversation | None:
        """Atomically move a waiting escalation to pending_ticket (nobody online)."""
        result = await self.session.execute(
            update(Conversation)
            .where(
                Conversation.id == conversation_id,
                Conversation.mode == "waiting",
            )
            .values(mode="pending_ticket", escalation_expires_at=now)
            .returning(Conversation)
        )
        return result.scalar_one_or_none()

    async def add_message_idempotent(
        self,
        *,
        conversation_id: int,
        client_message_id: str,
        role: str,
        content: str,
        sender_type: str,
        sender_user_id: str | None,
        sender_display_name: str | None,
    ) -> tuple[ConversationMessage, bool]:
        stmt = (
            insert(ConversationMessage)
            .values(
                conversation_id=conversation_id,
                client_message_id=client_message_id,
                role=role,
                content=content,
                sender_type=sender_type,
                sender_user_id=sender_user_id,
                sender_display_name=sender_display_name,
                meta={},
            )
            .on_conflict_do_nothing(
                constraint="uq_conversation_messages_client_id"
            )
            .returning(ConversationMessage)
        )
        inserted = (await self.session.execute(stmt)).scalar_one_or_none()
        if inserted is not None:
            conversation = await self.session.get(Conversation, conversation_id)
            if conversation is not None:
                conversation.last_message_at = datetime.now(timezone.utc)
            return inserted, True
        existing = (
            await self.session.execute(
                select(ConversationMessage).where(
                    ConversationMessage.conversation_id == conversation_id,
                    ConversationMessage.client_message_id == client_message_id,
                )
            )
        ).scalar_one()
        return existing, False

    async def create_ticket(
        self,
        *,
        conversation_id: int,
        profile_id: int,
        customer_email: str,
        customer_name: str | None,
        customer_message: str | None,
    ) -> EscalationTicket:
        stmt = (
            insert(EscalationTicket)
            .values(
                conversation_id=conversation_id,
                profile_id=profile_id,
                customer_email=customer_email,
                customer_name=customer_name,
                customer_message=customer_message,
                reason="no_agent_available",
                status="pending",
            )
            .on_conflict_do_update(
                index_elements=[EscalationTicket.conversation_id],
                set_={
                    "customer_email": customer_email,
                    "customer_name": customer_name,
                    "customer_message": customer_message,
                    "status": "pending",
                    "resolved_at": None,
                },
            )
            .returning(EscalationTicket)
        )
        return (await self.session.execute(stmt)).scalar_one()

    async def list_tickets(self, profile_id: int) -> list[EscalationTicket]:
        result = await self.session.execute(
            select(EscalationTicket)
            .where(EscalationTicket.profile_id == profile_id)
            .order_by(EscalationTicket.status, EscalationTicket.created_at.desc())
        )
        return list(result.scalars())

    async def resolve_ticket(
        self, ticket_id: int, profile_id: int
    ) -> EscalationTicket | None:
        ticket = await self.session.get(EscalationTicket, ticket_id)
        if ticket is None or ticket.profile_id != profile_id:
            return None
        ticket.status = "resolved"
        ticket.resolved_at = datetime.now(timezone.utc)
        await self.session.flush()
        return ticket

from datetime import datetime
from typing import Any

from sqlalchemy import Boolean, DateTime, ForeignKey, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


class Conversation(Base):
    __tablename__ = "conversations"

    id: Mapped[int] = mapped_column(primary_key=True)
    profile_id: Mapped[int] = mapped_column(
        ForeignKey("assistant_profiles.id", ondelete="CASCADE"), index=True
    )
    channel: Mapped[str] = mapped_column(String(16), default="chat")
    title: Mapped[str | None] = mapped_column(String(160), nullable=True)
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    ended_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    rating: Mapped[str | None] = mapped_column(String(8), nullable=True)  # up / down
    mode: Mapped[str] = mapped_column(String(24), default="ai", server_default="ai")
    assigned_user_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    visitor_session_id_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    escalation_requested_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    escalation_expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    accepted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_message_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )


class ConversationMessage(Base):
    __tablename__ = "conversation_messages"
    __table_args__ = (
        UniqueConstraint(
            "conversation_id",
            "client_message_id",
            name="uq_conversation_messages_client_id",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    conversation_id: Mapped[int] = mapped_column(
        ForeignKey("conversations.id", ondelete="CASCADE"), index=True
    )
    role: Mapped[str] = mapped_column(String(16))  # user, assistant, tool
    content: Mapped[str] = mapped_column(Text, default="")
    tool_name: Mapped[str | None] = mapped_column(String(64), nullable=True)
    meta: Mapped[dict[str, Any]] = mapped_column("metadata", JSONB, default=dict)
    client_message_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    sender_type: Mapped[str] = mapped_column(
        String(16), default="system", server_default="system"
    )
    sender_user_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    sender_display_name: Mapped[str | None] = mapped_column(String(120), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class ConversationEvent(Base):
    __tablename__ = "conversation_events"

    id: Mapped[int] = mapped_column(primary_key=True)
    conversation_id: Mapped[int] = mapped_column(
        ForeignKey("conversations.id", ondelete="CASCADE"), index=True
    )
    type: Mapped[str] = mapped_column(String(32))
    actor_type: Mapped[str] = mapped_column(String(16))
    actor_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    meta: Mapped[dict[str, Any]] = mapped_column("metadata", JSONB, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class EscalationTicket(Base):
    __tablename__ = "escalation_tickets"

    id: Mapped[int] = mapped_column(primary_key=True)
    conversation_id: Mapped[int] = mapped_column(
        ForeignKey("conversations.id", ondelete="CASCADE"), unique=True
    )
    profile_id: Mapped[int] = mapped_column(
        ForeignKey("assistant_profiles.id", ondelete="CASCADE"), index=True
    )
    customer_name: Mapped[str | None] = mapped_column(String(120), nullable=True)
    customer_email: Mapped[str] = mapped_column(String(254))
    customer_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    reason: Mapped[str] = mapped_column(String(64), default="no_agent_available")
    status: Mapped[str] = mapped_column(String(16), default="pending", server_default="pending")
    assignee_user_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    archived: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

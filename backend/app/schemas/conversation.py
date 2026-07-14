from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class ConversationOut(BaseModel):
    id: int
    title: str | None = None
    started_at: datetime
    rating: str | None = None
    summary: str | None = None
    mode: str = "ai"
    assigned_user_id: str | None = None
    escalation_requested_at: datetime | None = None
    accepted_at: datetime | None = None
    closed_at: datetime | None = None
    last_message_at: datetime | None = None


class MessageOut(BaseModel):
    id: int
    role: str
    content: str
    sender_type: str
    sender_display_name: str | None = None
    created_at: datetime


class RenameRequest(BaseModel):
    title: str = Field(..., min_length=1, max_length=160)


class RatingRequest(BaseModel):
    rating: Literal["up", "down"]


class WidgetRatingRequest(BaseModel):
    widget_token: str = Field(..., min_length=1)
    conversation_id: int
    conversation_token: str = Field(..., min_length=1)
    rating: Literal["up", "down"]

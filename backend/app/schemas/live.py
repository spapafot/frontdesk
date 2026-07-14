from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


class VisitorSocketTicketRequest(BaseModel):
    widget_token: str
    conversation_id: int = Field(gt=0)
    conversation_token: str = Field(min_length=1)


class OperatorSocketTicketRequest(BaseModel):
    site_id: int
    channel: Literal["inbox", "conversation"]
    conversation_id: int | None = None


class SocketTicketOut(BaseModel):
    ticket: str
    websocket_path: str
    conversation_id: int | None = None
    conversation_token: str | None = None
    expires_in: int


class InternalAuthorizeRequest(BaseModel):
    ticket: str


class LiveActor(BaseModel):
    actor_type: Literal["visitor", "operator", "system"]
    profile_id: int
    conversation_id: int | None = None
    user_id: str | None = None
    display_name: str | None = None
    channel: Literal["inbox", "conversation"]


class InternalActionRequest(BaseModel):
    actor: LiveActor
    action: Literal[
        "state",
        "escalate",
        "cancel",
        "accept",
        "message",
        "close",
        "timeout",
        "unavailable",
        "ticket",
    ]
    payload: dict[str, Any] = Field(default_factory=dict)


class CallbackTicketRequest(BaseModel):
    customer_email: str = Field(min_length=3, max_length=254)
    customer_name: str | None = Field(default=None, max_length=120)
    customer_message: str | None = Field(default=None, max_length=4000)


class CallbackTicketOut(BaseModel):
    id: int
    conversation_id: int
    profile_id: int
    customer_name: str | None
    customer_email: str
    customer_message: str | None
    reason: str
    status: str
    created_at: datetime
    resolved_at: datetime | None

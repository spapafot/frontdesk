from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class ConversationOut(BaseModel):
    id: int
    title: str | None = None
    started_at: datetime
    rating: str | None = None
    summary: str | None = None


class MessageOut(BaseModel):
    role: str
    content: str


class RenameRequest(BaseModel):
    title: str = Field(..., min_length=1, max_length=160)


class RatingRequest(BaseModel):
    rating: Literal["up", "down"]

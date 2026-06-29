from datetime import datetime

from pydantic import BaseModel


class RatingBreakdown(BaseModel):
    up: int
    down: int
    none: int


class UnansweredQuestion(BaseModel):
    conversation_id: int
    question: str
    created_at: datetime


class AnalyticsOut(BaseModel):
    total_conversations: int
    last_7_days: int
    ratings: RatingBreakdown
    unanswered: list[UnansweredQuestion]

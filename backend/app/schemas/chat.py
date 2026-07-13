from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=4000)
    conversation_id: int | None = None
    widget_token: str | None = None
    site_id: int | None = None

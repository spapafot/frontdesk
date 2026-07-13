from datetime import datetime
from typing import Literal

from pydantic import BaseModel, HttpUrl


class DocumentOut(BaseModel):
    id: int
    title: str
    type: str
    source_url: str | None = None
    is_active: bool
    processing_status: Literal["queued", "processing", "ready", "failed"]
    chunk_count: int
    created_at: datetime
    processed_at: datetime | None = None


class ChunkOut(BaseModel):
    id: int
    content: str


class ToggleRequest(BaseModel):
    is_active: bool


class LinkRequest(BaseModel):
    url: HttpUrl

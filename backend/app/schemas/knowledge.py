from datetime import datetime

from pydantic import BaseModel


class DocumentOut(BaseModel):
    id: int
    title: str
    type: str
    is_active: bool
    chunk_count: int
    created_at: datetime


class ChunkOut(BaseModel):
    id: int
    content: str


class ToggleRequest(BaseModel):
    is_active: bool

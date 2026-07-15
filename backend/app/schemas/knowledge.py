from datetime import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, HttpUrl, StringConstraints


class DocumentOut(BaseModel):
    id: int
    title: str
    type: str
    source_url: str | None = None
    # FAQ answer text (type == "faq") so the edit dialog can prefill; None for
    # every other type — file/page full text must not leak into list responses.
    content: str | None = None
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


class FaqRequest(BaseModel):
    # Minimums keep entries above the chunker's junk filter; the answer cap
    # keeps FAQ entries concise and list payloads small (content is echoed in
    # DocumentOut for prefilling the edit dialog).
    question: Annotated[
        str, StringConstraints(strip_whitespace=True, min_length=5, max_length=255)
    ]
    answer: Annotated[
        str, StringConstraints(strip_whitespace=True, min_length=10, max_length=4000)
    ]

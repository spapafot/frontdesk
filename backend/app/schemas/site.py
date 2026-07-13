from datetime import datetime

from pydantic import BaseModel, Field


class SiteCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    type: str = Field(default="general", max_length=64)
    assistant_name: str | None = Field(default=None, min_length=1, max_length=120)
    widget_origin: str | None = Field(default=None, max_length=255)


class SiteUpdate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)


class SiteSummaryOut(BaseModel):
    id: int
    name: str
    assistant_name: str
    type: str
    public_key: str | None = None
    widget_origin: str | None = None
    widget_enabled: bool = True
    widget_monthly_limit: int = 5000
    widget_monthly_usage: int = 0
    created_at: datetime

from pydantic import BaseModel, Field


class SettingsOut(BaseModel):
    business_name: str
    assistant_name: str
    custom_instructions: str | None = None
    public_key: str | None = None
    widget_origin: str | None = None
    widget_enabled: bool = True
    widget_monthly_limit: int = 5000
    widget_monthly_usage: int = 0
    widget_resets_at: str


class SettingsUpdate(BaseModel):
    business_name: str | None = Field(default=None, min_length=1, max_length=255)
    assistant_name: str | None = Field(default=None, min_length=1, max_length=120)
    custom_instructions: str | None = Field(default=None, max_length=4000)
    widget_origin: str | None = Field(default=None, max_length=255)
    widget_enabled: bool | None = None

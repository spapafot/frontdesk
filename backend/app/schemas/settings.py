from pydantic import BaseModel, Field


class SettingsOut(BaseModel):
    business_name: str
    assistant_name: str
    custom_instructions: str | None = None


class SettingsUpdate(BaseModel):
    business_name: str | None = Field(default=None, min_length=1, max_length=255)
    assistant_name: str | None = Field(default=None, min_length=1, max_length=120)
    custom_instructions: str | None = Field(default=None, max_length=4000)

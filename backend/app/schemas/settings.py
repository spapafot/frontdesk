from typing import Literal

from pydantic import BaseModel, Field

# Supported OpenAI TTS voices, grouped loosely by perceived gender.
TTSVoice = Literal[
    "nova",
    "shimmer",
    "coral",
    "sage",
    "alloy",
    "echo",
    "onyx",
    "ash",
]


class SettingsOut(BaseModel):
    business_name: str
    assistant_name: str
    custom_instructions: str | None = None
    tts_voice: str
    tts_speed: float


class SettingsUpdate(BaseModel):
    business_name: str | None = Field(default=None, min_length=1, max_length=255)
    assistant_name: str | None = Field(default=None, min_length=1, max_length=120)
    custom_instructions: str | None = Field(default=None, max_length=4000)
    tts_voice: TTSVoice | None = None
    tts_speed: float | None = Field(default=None, ge=0.5, le=2.0)

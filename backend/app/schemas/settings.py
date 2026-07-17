from pydantic import BaseModel, Field, field_validator

# Preset launcher-icon keys. Kept in sync with the frontend source of truth,
# frontend/widget/icons.ts.
LAUNCHER_ICONS = frozenset(
    {"chat", "chat-dots", "help", "headset", "sparkles", "smile"}
)
LAUNCHER_POSITIONS = frozenset({"bottom-right", "bottom-left"})
_HEX_COLOR = r"^#(?:[0-9a-fA-F]{3}|[0-9a-fA-F]{6})$"


class SettingsOut(BaseModel):
    business_name: str
    assistant_name: str
    custom_instructions: str | None = None
    public_key: str | None = None
    widget_origin: str | None = None
    widget_enabled: bool = True
    widget_monthly_usage: int = 0
    widget_resets_at: str
    # Appearance
    accent_color: str = "#0284c7"
    launcher_icon: str = "chat"
    launcher_position: str = "bottom-right"
    greeting: str = "Hi! How can I help you today?"
    launcher_label: str | None = None
    show_branding: bool = True
    live_human_escalation_enabled: bool = False
    live_human_escalation_available: bool = False
    moderation_enabled: bool = True
    moderation_available: bool = False
    notification_email: str | None = None


class SettingsUpdate(BaseModel):
    business_name: str | None = Field(default=None, min_length=1, max_length=255)
    assistant_name: str | None = Field(default=None, min_length=1, max_length=120)
    custom_instructions: str | None = Field(default=None, max_length=4000)
    widget_origin: str | None = Field(default=None, max_length=255)
    widget_enabled: bool | None = None
    live_human_escalation_enabled: bool | None = None
    moderation_enabled: bool | None = None
    notification_email: str | None = Field(default=None, max_length=254)
    # Appearance
    accent_color: str | None = Field(default=None, pattern=_HEX_COLOR)
    launcher_icon: str | None = Field(default=None, max_length=32)
    launcher_position: str | None = Field(default=None)
    greeting: str | None = Field(default=None, min_length=1, max_length=500)
    launcher_label: str | None = Field(default=None, max_length=60)
    show_branding: bool | None = None

    @field_validator("notification_email")
    @classmethod
    def _valid_notification_email(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip()
        if "@" not in value or " " in value or len(value) < 3:
            raise ValueError("notification_email must be a valid email address")
        return value

    @field_validator("launcher_icon")
    @classmethod
    def _valid_icon(cls, value: str | None) -> str | None:
        if value is not None and value not in LAUNCHER_ICONS:
            raise ValueError(f"launcher_icon must be one of {sorted(LAUNCHER_ICONS)}")
        return value

    @field_validator("launcher_position")
    @classmethod
    def _valid_position(cls, value: str | None) -> str | None:
        if value is not None and value not in LAUNCHER_POSITIONS:
            raise ValueError(f"launcher_position must be one of {sorted(LAUNCHER_POSITIONS)}")
        return value

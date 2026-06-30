from datetime import datetime

from sqlalchemy import DateTime, Float, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


class Business(Base):
    __tablename__ = "businesses"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(255))
    type: Mapped[str] = mapped_column(String(64))
    # Public, non-secret key the embeddable widget sends to identify this tenant.
    public_key: Mapped[str | None] = mapped_column(String(48), unique=True, nullable=True)
    assistant_name: Mapped[str] = mapped_column(String(120), default="Assistant")
    custom_instructions: Mapped[str | None] = mapped_column(Text, nullable=True)
    tts_voice: Mapped[str] = mapped_column(String(32), default="nova")
    tts_speed: Mapped[float] = mapped_column(Float, default=1.1)
    timezone: Mapped[str] = mapped_column(String(64), default="Europe/Athens")
    default_language: Mapped[str] = mapped_column(String(8), default="en")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

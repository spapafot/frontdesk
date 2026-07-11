from datetime import date, datetime

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Integer, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


class WidgetInstallation(Base):
    __tablename__ = "widget_installations"

    id: Mapped[int] = mapped_column(primary_key=True)
    profile_id: Mapped[int] = mapped_column(
        ForeignKey("assistant_profiles.id", ondelete="CASCADE"), unique=True, index=True
    )
    public_key: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    allowed_origin: Mapped[str | None] = mapped_column(String(255), nullable=True)
    is_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    monthly_limit: Mapped[int] = mapped_column(Integer, default=5000)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class WidgetUsage(Base):
    __tablename__ = "widget_usage"
    __table_args__ = (UniqueConstraint("installation_id", "period", name="uq_widget_usage_period"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    installation_id: Mapped[int] = mapped_column(
        ForeignKey("widget_installations.id", ondelete="CASCADE"), index=True
    )
    period: Mapped[date] = mapped_column(Date)
    message_count: Mapped[int] = mapped_column(Integer, default=0)

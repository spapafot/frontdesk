from datetime import datetime
from typing import Any

from sqlalchemy import Boolean, DateTime, ForeignKey, String, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


class CatalogIntegration(Base):
    """One public, read-only commerce catalog connected to a site."""

    __tablename__ = "catalog_integrations"

    id: Mapped[int] = mapped_column(primary_key=True)
    profile_id: Mapped[int] = mapped_column(
        ForeignKey("assistant_profiles.id", ondelete="CASCADE"),
        unique=True,
        index=True,
    )
    store_url: Mapped[str] = mapped_column(String(2048))
    provider: Mapped[str] = mapped_column(
        String(32), default="woocommerce", server_default="woocommerce"
    )
    enabled: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    catalog_metadata: Mapped[dict[str, Any]] = mapped_column(
        JSONB, default=dict, server_default="{}"
    )
    verified_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    metadata_refreshed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


# One-release import compatibility for code deployed alongside migration 0031.
WooCommerceCatalogIntegration = CatalogIntegration

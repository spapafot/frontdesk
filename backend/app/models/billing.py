from datetime import date, datetime

from sqlalchemy import Date, DateTime, Integer, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


class Subscription(Base):
    """One billing account, keyed by the owner's Supabase ``sub``.

    Billing is per-account (per ``owner_user_id``), the same value that scopes
    ``assistant_profiles`` and ``team_members``. Stripe owns payment state; this
    row is the local mirror written by the webhook. Plan *limits* live in code
    (``app.core.plans``) - only the plan name and payment status are stored here.

    A row is created lazily on first login as a 7-day ``trialing`` trial; there
    is no Stripe object until the owner subscribes.
    """

    __tablename__ = "subscriptions"
    __table_args__ = (
        UniqueConstraint("owner_user_id", name="uq_subscriptions_owner"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    owner_user_id: Mapped[str] = mapped_column(String(128), index=True)
    # trial | starter | pro | business
    plan: Mapped[str] = mapped_column(String(16), default="trial", server_default="trial")
    # trialing | active | past_due | canceled | locked
    status: Mapped[str] = mapped_column(
        String(24), default="trialing", server_default="trialing"
    )
    stripe_customer_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    stripe_subscription_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    # month | year
    billing_interval: Mapped[str | None] = mapped_column(String(8), nullable=True)
    trial_ends_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    current_period_end: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class AccountUsage(Base):
    """Pooled monthly message counter for one account.

    The quota is enforced account-wide (across all the owner's sites), not
    per-installation. One row per ``(owner_user_id, period)`` where ``period``
    is the first day of the calendar month (UTC). ``message_count`` is bumped
    atomically before any model work; ``bonus_messages`` holds top-up packs that
    lift the current month's ceiling and reset with it (a new month = a new row).
    """

    __tablename__ = "account_usage"
    __table_args__ = (
        UniqueConstraint("owner_user_id", "period", name="uq_account_usage_period"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    owner_user_id: Mapped[str] = mapped_column(String(128), index=True)
    period: Mapped[date] = mapped_column(Date)
    message_count: Mapped[int] = mapped_column(Integer, default=0)
    bonus_messages: Mapped[int] = mapped_column(
        Integer, default=0, server_default="0"
    )


class BillingEvent(Base):
    """Processed Stripe webhook events, for idempotency.

    Stripe delivers at-least-once, so each event id is recorded on first receipt;
    a duplicate delivery hits the unique constraint and is skipped. This matters
    for non-idempotent handlers such as top-up ``bonus_messages`` increments.
    """

    __tablename__ = "billing_events"
    __table_args__ = (
        UniqueConstraint("stripe_event_id", name="uq_billing_events_event_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    stripe_event_id: Mapped[str] = mapped_column(String(64), index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

from typing import Literal

from pydantic import BaseModel, Field


class Entitlements(BaseModel):
    """Plan limits surfaced to the client. ``None`` means unlimited."""

    sites: int | None
    messages: int | None
    seats: int | None
    knowledge_chunks: int | None
    live_handoff: bool
    remove_branding: bool


class UsageOut(BaseModel):
    messages_used: int
    messages_limit: int | None
    bonus_messages: int = 0
    resets_at: str


class KnowledgeUsageOut(BaseModel):
    # Chunks are the enforced unit; ~100 chunks ≈ 1 MB (see plans.CHUNKS_PER_MB).
    chunks_used: int
    chunks_limit: int | None


class BillingOut(BaseModel):
    plan: str
    status: str
    manageable: bool
    has_stripe_customer: bool = False
    # month | year; None until the first Stripe subscription exists.
    billing_interval: str | None = None
    trial_ends_at: str | None = None
    current_period_end: str | None = None
    entitlements: Entitlements
    usage: UsageOut
    knowledge: KnowledgeUsageOut


class CheckoutRequest(BaseModel):
    plan: Literal["starter", "pro", "business"]
    interval: Literal["month", "year"] = "month"


class CheckoutResponse(BaseModel):
    url: str


class PortalResponse(BaseModel):
    url: str


class TopupRequest(BaseModel):
    # Reserved for Phase 2; number of 1,000-message packs.
    packs: int = Field(default=1, ge=1, le=50)

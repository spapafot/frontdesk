"""Subscription plans and their entitlements.

Plan *limits* live here in code (not in the database or Stripe): Stripe only
owns payment state, which the webhook mirrors into a ``subscriptions`` row as a
plan name + status. Resolving a plan name to concrete limits happens here.

Both quota-bearing limits are enforced **account-wide** (pooled across all of an
owner's sites): ``messages`` is the whole account's monthly allowance, and
``knowledge_chunks`` is the total number of stored knowledge chunks (files +
scanned pages + FAQs). ``None`` means "unlimited" for a countable limit.

Knowledge is priced to customers in **MB** but enforced in **chunks**, because a
chunk (≈ one pgvector row) is our real cost unit: ~``CHUNKS_PER_MB`` chunks fit
in 1 MB of database. So a plan's MB headline × ``CHUNKS_PER_MB`` = its chunk cap.

``seats`` counts the whole team including the owner (invited members are capped
at ``seats - 1``).

Keep these in sync with the marketing pricing table (``site/src/data/pricing.ts``)
and the Stripe Prices referenced by ``config.stripe_price_*``.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.core.config import settings

# Approx chunks per MB of database (a 1536-dim vector ≈ 6 KB + text + index
# ≈ ~10 KB/chunk). Used to convert the MB pricing headline to a chunk cap and to
# show an MB estimate next to the chunk usage meter.
CHUNKS_PER_MB = 100


@dataclass(frozen=True)
class PlanLimits:
    sites: int | None
    messages: int | None  # pooled, per account, per calendar month
    seats: int | None  # includes the owner; invited members capped at seats - 1
    knowledge_chunks: int | None  # pooled per account; ~100 chunks ≈ 1 MB
    live_handoff: bool
    remove_branding: bool


# Trial grants Starter-level entitlements for 7 days (see subscription resolution).
PLANS: dict[str, PlanLimits] = {
    "trial": PlanLimits(
        sites=1, messages=500, seats=1, knowledge_chunks=5_000,
        live_handoff=False, remove_branding=False,
    ),
    "starter": PlanLimits(
        sites=1, messages=500, seats=1, knowledge_chunks=5_000,
        live_handoff=False, remove_branding=False,
    ),
    "pro": PlanLimits(
        sites=3, messages=5_000, seats=5, knowledge_chunks=50_000,
        live_handoff=True, remove_branding=True,
    ),
    "business": PlanLimits(
        sites=20, messages=50_000, seats=None, knowledge_chunks=200_000,
        live_handoff=True, remove_branding=True,
    ),
}

# A locked account (expired trial / canceled with no active plan) can do nothing
# quota-bearing: the widget is dark and new resources cannot be created. Existing
# data stays readable in the admin (enforced in the API/UI, not here).
LOCKED_LIMITS = PlanLimits(
    sites=0, messages=0, seats=0, knowledge_chunks=0,
    live_handoff=False, remove_branding=False,
)

# Super-admins (manual Supabase role) bypass every gate.
SUPERADMIN_LIMITS = PlanLimits(
    sites=None,
    messages=None,
    seats=None,
    knowledge_chunks=None,
    live_handoff=True,
    remove_branding=True,
)

TRIAL_DAYS = 7


def _price_map() -> dict[str, tuple[str, str]]:
    """Map each configured Stripe Price id to ``(plan, interval)``."""
    pairs = {
        settings.stripe_price_starter_month: ("starter", "month"),
        settings.stripe_price_starter_year: ("starter", "year"),
        settings.stripe_price_pro_month: ("pro", "month"),
        settings.stripe_price_pro_year: ("pro", "year"),
        settings.stripe_price_business_month: ("business", "month"),
        settings.stripe_price_business_year: ("business", "year"),
    }
    # Drop unconfigured (empty) price ids so "" never matches.
    return {price_id: value for price_id, value in pairs.items() if price_id}


def price_id_to_plan(price_id: str) -> tuple[str, str] | None:
    """Return ``(plan, interval)`` for a Stripe Price id, or ``None`` if unknown."""
    return _price_map().get(price_id)


def plan_price_id(plan: str, interval: str) -> str | None:
    """Return the configured Stripe Price id for ``plan``/``interval`` (checkout)."""
    for price_id, (mapped_plan, mapped_interval) in _price_map().items():
        if mapped_plan == plan and mapped_interval == interval:
            return price_id
    return None

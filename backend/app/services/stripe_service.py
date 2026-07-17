"""Stripe integration: Checkout, Billing Portal, and webhook verification.

Vendor-isolated (swapping Stripe is a change to this module alone) and
config-driven: with ``stripe_secret_key`` empty the whole billing feature is
off, so local dev and self-hosting run without payments. Secrets are never
logged. The ``stripe`` SDK is imported lazily inside functions so the module
loads even where the package is absent (mirrors the lazy ``openai`` import in
``chat_service``), and its synchronous network calls run in a worker thread to
avoid blocking the event loop.
"""

import asyncio
import logging

from app.core.config import settings

logger = logging.getLogger(__name__)


class BillingError(RuntimeError):
    """Raised when a Stripe operation fails or billing is not configured."""


def billing_configured() -> bool:
    return bool(settings.stripe_secret_key)


def _client():
    import stripe

    stripe.api_key = settings.stripe_secret_key
    return stripe


async def create_checkout_session(
    *,
    owner_user_id: str,
    price_id: str,
    mode: str,
    success_url: str,
    cancel_url: str,
    quantity: int = 1,
    customer_id: str | None = None,
    customer_email: str | None = None,
    metadata: dict[str, str] | None = None,
) -> str:
    """Create a Checkout session and return its hosted URL.

    ``mode`` is ``"subscription"`` for a plan or ``"payment"`` for a one-time
    top-up (``quantity`` = number of packs). ``client_reference_id`` carries the
    account id so the webhook can map the completed session back to the owner.
    """
    if not billing_configured():
        raise BillingError("Billing is not configured.")
    if not price_id:
        raise BillingError("No Stripe price is configured for that plan.")

    stripe = _client()
    params: dict = {
        "mode": mode,
        "line_items": [{"price": price_id, "quantity": quantity}],
        "success_url": success_url,
        "cancel_url": cancel_url,
        "client_reference_id": owner_user_id,
        "metadata": {"owner_user_id": owner_user_id, **(metadata or {})},
    }
    if customer_id:
        params["customer"] = customer_id
    elif customer_email:
        params["customer_email"] = customer_email
    if mode == "subscription":
        # Stamp the account id onto the subscription so every later
        # customer.subscription.* webhook can attribute the owner directly,
        # without depending on the checkout event landing first.
        params["subscription_data"] = {"metadata": {"owner_user_id": owner_user_id}}
    try:
        session = await asyncio.to_thread(stripe.checkout.Session.create, **params)
    except Exception as exc:  # noqa: BLE001 - surface a clean error to the caller
        logger.warning("Stripe checkout session creation failed", exc_info=True)
        raise BillingError("Could not start checkout.") from exc
    if not session.url:
        raise BillingError("Stripe returned no checkout URL.")
    return session.url


async def create_portal_session(*, customer_id: str, return_url: str) -> str:
    """Create a Billing Portal session and return its hosted URL."""
    if not billing_configured():
        raise BillingError("Billing is not configured.")
    if not customer_id:
        raise BillingError("No Stripe customer on this account yet.")
    stripe = _client()
    try:
        session = await asyncio.to_thread(
            stripe.billing_portal.Session.create,
            customer=customer_id,
            return_url=return_url,
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("Stripe portal session creation failed", exc_info=True)
        raise BillingError("Could not open the billing portal.") from exc
    if not session.url:
        raise BillingError("Stripe returned no portal URL.")
    return session.url


async def create_plan_change_session(
    *,
    customer_id: str,
    subscription_id: str,
    price_id: str,
    return_url: str,
    confirm_url: str,
) -> str | None:
    """Portal deep-link that switches an existing subscription to ``price_id``.

    An already-subscribed account changes plan by UPDATING its subscription
    (the Billing Portal's ``subscription_update_confirm`` flow, prorated per the
    saved portal configuration) - running Checkout again would create a second
    live subscription and bill the account twice. ``return_url`` is where the
    portal's back link lands; ``confirm_url`` is reached only after the switch
    is actually confirmed.

    Returns ``None`` when the subscription no longer exists or is already
    canceled on Stripe's side (a stale local mirror) - the caller should fall
    back to a fresh Checkout in that case.
    """
    if not billing_configured():
        raise BillingError("Billing is not configured.")
    if not price_id:
        raise BillingError("No Stripe price is configured for that plan.")
    stripe = _client()
    try:
        subscription = await asyncio.to_thread(
            stripe.Subscription.retrieve, subscription_id
        )
    except stripe.InvalidRequestError:
        # Gone on Stripe's side (stale mirror): a new Checkout is correct.
        return None
    except Exception as exc:  # noqa: BLE001
        logger.warning("Stripe subscription retrieve failed", exc_info=True)
        raise BillingError("Could not start the plan change.") from exc
    if subscription.get("status") in ("canceled", "incomplete_expired"):
        return None
    items = (subscription.get("items") or {}).get("data") or []
    if not items:
        return None
    try:
        session = await asyncio.to_thread(
            stripe.billing_portal.Session.create,
            customer=customer_id,
            return_url=return_url,
            flow_data={
                "type": "subscription_update_confirm",
                "subscription_update_confirm": {
                    "subscription": subscription_id,
                    "items": [
                        {"id": items[0]["id"], "price": price_id, "quantity": 1}
                    ],
                },
                "after_completion": {
                    "type": "redirect",
                    "redirect": {"return_url": confirm_url},
                },
            },
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("Stripe plan-change session creation failed", exc_info=True)
        raise BillingError("Could not start the plan change.") from exc
    if not session.url:
        raise BillingError("Stripe returned no portal URL.")
    return session.url


def verify_event(payload: bytes, sig_header: str) -> dict:
    """Verify a webhook payload's signature and return the parsed event.

    Raises ``BillingError`` on a missing secret or an invalid signature; the
    route maps that to HTTP 400 so Stripe retries only genuine failures. This is
    CPU-only (HMAC), so it is safe to call synchronously.
    """
    if not settings.stripe_webhook_secret:
        raise BillingError("Stripe webhook secret is not configured.")
    stripe = _client()
    try:
        return stripe.Webhook.construct_event(
            payload, sig_header, settings.stripe_webhook_secret
        )
    except Exception as exc:  # noqa: BLE001 - bad signature or malformed payload
        raise BillingError("Invalid Stripe signature.") from exc

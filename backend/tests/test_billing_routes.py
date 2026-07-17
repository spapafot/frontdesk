"""HTTP tests for the billing routes: current-plan read, Checkout, and the
public Stripe webhook (signature + idempotency). No real DB or Stripe calls -
repositories and the Stripe service are stubbed."""

from types import SimpleNamespace

from app.services.stripe_service import BillingError
from tests.conftest import make_jwt

JWT_SECRET = "billing-routes-jwt-secret"


def _auth():
    return {"Authorization": f"Bearer {make_jwt(JWT_SECRET)}"}


def _owns_a_site(monkeypatch):
    async def _list(_self, _owner):
        return [SimpleNamespace(id=1)]

    monkeypatch.setattr(
        "app.repositories.profile_repository.ProfileRepository.list_for_owner", _list
    )


async def test_get_billing_returns_plan_usage_and_entitlements(
    client, settings, monkeypatch
):
    monkeypatch.setattr(settings, "edge_shared_secret", "")
    monkeypatch.setattr(settings, "supabase_jwt_secret", JWT_SECRET)
    _owns_a_site(monkeypatch)

    response = await client.get("/billing", headers=_auth())
    assert response.status_code == 200
    body = response.json()
    # Autouse fixture resolves the account to an active business subscription.
    assert body["plan"] == "business"
    assert body["manageable"] is True
    assert body["entitlements"]["messages"] == 50000
    assert body["usage"]["messages_used"] == 0
    assert body["usage"]["resets_at"]


async def test_checkout_returns_hosted_stripe_url(client, settings, monkeypatch):
    monkeypatch.setattr(settings, "edge_shared_secret", "")
    monkeypatch.setattr(settings, "supabase_jwt_secret", JWT_SECRET)
    monkeypatch.setattr(settings, "app_base_url", "https://app.example.com")
    monkeypatch.setattr(settings, "stripe_price_pro_month", "price_pro_m")
    _owns_a_site(monkeypatch)

    captured: dict = {}

    async def _create(**kwargs):
        captured.update(kwargs)
        return "https://checkout.stripe.com/c/pay/session_123"

    monkeypatch.setattr(
        "app.services.stripe_service.create_checkout_session", _create
    )

    response = await client.post(
        "/billing/checkout",
        json={"plan": "pro", "interval": "month"},
        headers=_auth(),
    )
    assert response.status_code == 200
    assert response.json()["url"].startswith("https://checkout.stripe.com/")
    assert captured["price_id"] == "price_pro_m"
    assert captured["mode"] == "subscription"
    assert captured["metadata"] == {"plan": "pro", "interval": "month"}
    # The account id is passed so the service can stamp subscription_data.metadata
    # (see stripe_service.create_checkout_session), making webhook attribution
    # independent of event ordering.
    assert captured["owner_user_id"]


async def test_webhook_applies_plan_on_checkout_completed(
    client, settings, monkeypatch
):
    monkeypatch.setattr(settings, "edge_shared_secret", "")
    event = {
        "id": "evt_1",
        "type": "checkout.session.completed",
        "data": {
            "object": {
                "client_reference_id": "owner-1",
                "customer": "cus_1",
                "subscription": "sub_1",
                "metadata": {
                    "owner_user_id": "owner-1",
                    "plan": "pro",
                    "interval": "month",
                },
            }
        },
    }
    monkeypatch.setattr(
        "app.services.stripe_service.verify_event", lambda payload, sig: event
    )

    async def _mark(_self, _event_id):
        return True

    captured: dict = {}

    async def _apply(_self, owner, **kwargs):
        captured.update(owner=owner, **kwargs)
        return SimpleNamespace()

    monkeypatch.setattr(
        "app.repositories.subscription_repository.SubscriptionRepository.mark_event_processed",
        _mark,
    )
    monkeypatch.setattr(
        "app.repositories.subscription_repository.SubscriptionRepository.apply_stripe_state",
        _apply,
    )

    response = await client.post(
        "/billing/webhook", content=b"{}", headers={"stripe-signature": "sig"}
    )
    assert response.status_code == 200
    assert captured["owner"] == "owner-1"
    assert captured["plan"] == "pro"
    assert captured["status"] == "active"


async def test_webhook_rejects_bad_signature(client, settings, monkeypatch):
    monkeypatch.setattr(settings, "edge_shared_secret", "")

    def _raise(payload, sig):
        raise BillingError("Invalid Stripe signature.")

    monkeypatch.setattr("app.services.stripe_service.verify_event", _raise)

    response = await client.post(
        "/billing/webhook", content=b"{}", headers={"stripe-signature": "bad"}
    )
    assert response.status_code == 400


async def test_webhook_skips_duplicate_event(client, settings, monkeypatch):
    monkeypatch.setattr(settings, "edge_shared_secret", "")
    event = {
        "id": "evt_dup",
        "type": "checkout.session.completed",
        "data": {"object": {}},
    }
    monkeypatch.setattr(
        "app.services.stripe_service.verify_event", lambda payload, sig: event
    )

    async def _mark(_self, _event_id):
        return False  # already processed

    called = {"apply": False}

    async def _apply(_self, owner, **kwargs):
        called["apply"] = True

    monkeypatch.setattr(
        "app.repositories.subscription_repository.SubscriptionRepository.mark_event_processed",
        _mark,
    )
    monkeypatch.setattr(
        "app.repositories.subscription_repository.SubscriptionRepository.apply_stripe_state",
        _apply,
    )

    response = await client.post(
        "/billing/webhook", content=b"{}", headers={"stripe-signature": "sig"}
    )
    assert response.status_code == 200
    assert response.json().get("duplicate") is True
    assert called["apply"] is False


def _live_subscription(monkeypatch, **overrides):
    """Stub the account onto a live Stripe subscription (sub_current)."""
    fields = dict(
        plan="starter",
        status="active",
        trial_ends_at=None,
        current_period_end=None,
        stripe_customer_id="cus_1",
        stripe_subscription_id="sub_current",
        billing_interval="month",
    )
    fields.update(overrides)

    async def _get_or_create(_self, owner):
        return SimpleNamespace(owner_user_id=owner, **fields)

    monkeypatch.setattr(
        "app.repositories.subscription_repository.SubscriptionRepository.get_or_create_trial",
        _get_or_create,
    )


async def test_checkout_switches_live_subscription_via_portal(
    client, settings, monkeypatch
):
    """An account with a live subscription changes plan by UPDATING it through
    the portal confirm flow - never via a second Checkout subscription, which
    Stripe would add alongside the first (double billing)."""
    monkeypatch.setattr(settings, "edge_shared_secret", "")
    monkeypatch.setattr(settings, "supabase_jwt_secret", JWT_SECRET)
    monkeypatch.setattr(settings, "app_base_url", "https://app.example.com")
    monkeypatch.setattr(settings, "stripe_price_pro_month", "price_pro_m")
    _owns_a_site(monkeypatch)
    _live_subscription(monkeypatch)

    captured: dict = {}

    async def _change(**kwargs):
        captured.update(kwargs)
        return "https://billing.stripe.com/session/flow_123"

    async def _checkout(**kwargs):
        raise AssertionError("a live account must never get a second Checkout")

    monkeypatch.setattr(
        "app.services.stripe_service.create_plan_change_session", _change
    )
    monkeypatch.setattr(
        "app.services.stripe_service.create_checkout_session", _checkout
    )

    response = await client.post(
        "/billing/checkout",
        json={"plan": "pro", "interval": "month"},
        headers=_auth(),
    )
    assert response.status_code == 200
    assert response.json()["url"].startswith("https://billing.stripe.com/")
    assert captured["subscription_id"] == "sub_current"
    assert captured["price_id"] == "price_pro_m"
    # Only a confirmed switch returns to the ?checkout=updated handler.
    assert captured["confirm_url"].endswith("/billing?checkout=updated")


async def test_checkout_falls_back_when_tracked_subscription_is_gone(
    client, settings, monkeypatch
):
    """A stale local mirror (subscription canceled/deleted on Stripe's side)
    falls back to a fresh Checkout instead of failing."""
    monkeypatch.setattr(settings, "edge_shared_secret", "")
    monkeypatch.setattr(settings, "supabase_jwt_secret", JWT_SECRET)
    monkeypatch.setattr(settings, "app_base_url", "https://app.example.com")
    monkeypatch.setattr(settings, "stripe_price_pro_month", "price_pro_m")
    _owns_a_site(monkeypatch)
    _live_subscription(monkeypatch)

    async def _change(**kwargs):
        return None  # subscription gone on Stripe's side

    async def _checkout(**kwargs):
        return "https://checkout.stripe.com/c/pay/session_456"

    monkeypatch.setattr(
        "app.services.stripe_service.create_plan_change_session", _change
    )
    monkeypatch.setattr(
        "app.services.stripe_service.create_checkout_session", _checkout
    )

    response = await client.post(
        "/billing/checkout",
        json={"plan": "pro", "interval": "month"},
        headers=_auth(),
    )
    assert response.status_code == 200
    assert response.json()["url"].startswith("https://checkout.stripe.com/")


def _webhook_event(monkeypatch, event: dict):
    monkeypatch.setattr(
        "app.services.stripe_service.verify_event", lambda payload, sig: event
    )

    async def _mark(_self, _event_id):
        return True

    monkeypatch.setattr(
        "app.repositories.subscription_repository.SubscriptionRepository.mark_event_processed",
        _mark,
    )


def _tracked_subscription(monkeypatch, subscription):
    async def _get(_self, _owner):
        return subscription

    monkeypatch.setattr(
        "app.repositories.subscription_repository.SubscriptionRepository.get", _get
    )


async def test_webhook_deleted_cancels_only_the_tracked_subscription(
    client, settings, monkeypatch
):
    monkeypatch.setattr(settings, "edge_shared_secret", "")
    _webhook_event(
        monkeypatch,
        {
            "id": "evt_del_1",
            "type": "customer.subscription.deleted",
            "data": {
                "object": {
                    "id": "sub_current",
                    "customer": "cus_1",
                    "metadata": {"owner_user_id": "owner-1"},
                }
            },
        },
    )
    _tracked_subscription(
        monkeypatch,
        SimpleNamespace(
            owner_user_id="owner-1",
            stripe_subscription_id="sub_current",
            status="active",
        ),
    )

    captured: dict = {}

    async def _apply(_self, owner, **kwargs):
        captured.update(owner=owner, **kwargs)
        return SimpleNamespace()

    monkeypatch.setattr(
        "app.repositories.subscription_repository.SubscriptionRepository.apply_stripe_state",
        _apply,
    )

    response = await client.post(
        "/billing/webhook", content=b"{}", headers={"stripe-signature": "sig"}
    )
    assert response.status_code == 200
    assert captured == {"owner": "owner-1", "status": "canceled"}


async def test_webhook_deleted_ignores_a_stale_subscription(
    client, settings, monkeypatch
):
    """Deleting an old/duplicate subscription must not dark the account that is
    live on a different one (e.g. after a re-subscribe)."""
    monkeypatch.setattr(settings, "edge_shared_secret", "")
    _webhook_event(
        monkeypatch,
        {
            "id": "evt_del_2",
            "type": "customer.subscription.deleted",
            "data": {
                "object": {
                    "id": "sub_old",
                    "customer": "cus_1",
                    "metadata": {"owner_user_id": "owner-1"},
                }
            },
        },
    )
    _tracked_subscription(
        monkeypatch,
        SimpleNamespace(
            owner_user_id="owner-1",
            stripe_subscription_id="sub_current",
            status="active",
        ),
    )

    called = {"apply": False}

    async def _apply(_self, owner, **kwargs):
        called["apply"] = True

    monkeypatch.setattr(
        "app.repositories.subscription_repository.SubscriptionRepository.apply_stripe_state",
        _apply,
    )

    response = await client.post(
        "/billing/webhook", content=b"{}", headers={"stripe-signature": "sig"}
    )
    assert response.status_code == 200
    assert called["apply"] is False


async def test_webhook_update_ignores_other_subscription_while_live(
    client, settings, monkeypatch
):
    monkeypatch.setattr(settings, "edge_shared_secret", "")
    monkeypatch.setattr(settings, "stripe_price_business_month", "price_biz_m")
    _webhook_event(
        monkeypatch,
        {
            "id": "evt_upd_1",
            "type": "customer.subscription.updated",
            "data": {
                "object": {
                    "id": "sub_old",
                    "customer": "cus_1",
                    "status": "active",
                    "metadata": {"owner_user_id": "owner-1"},
                    "items": {"data": [{"price": {"id": "price_biz_m"}}]},
                }
            },
        },
    )
    _tracked_subscription(
        monkeypatch,
        SimpleNamespace(
            owner_user_id="owner-1",
            stripe_subscription_id="sub_current",
            status="active",
        ),
    )

    called = {"apply": False}

    async def _apply(_self, owner, **kwargs):
        called["apply"] = True

    monkeypatch.setattr(
        "app.repositories.subscription_repository.SubscriptionRepository.apply_stripe_state",
        _apply,
    )

    response = await client.post(
        "/billing/webhook", content=b"{}", headers={"stripe-signature": "sig"}
    )
    assert response.status_code == 200
    assert called["apply"] is False


async def test_webhook_update_adopts_subscription_when_none_tracked(
    client, settings, monkeypatch
):
    """The first subscription event for an account (or one arriving before
    checkout.session.completed) is adopted, incl. the price -> plan mapping and
    the items-level current_period_end used by newer Stripe API versions."""
    monkeypatch.setattr(settings, "edge_shared_secret", "")
    monkeypatch.setattr(settings, "stripe_price_pro_month", "price_pro_m")
    _webhook_event(
        monkeypatch,
        {
            "id": "evt_upd_2",
            "type": "customer.subscription.created",
            "data": {
                "object": {
                    "id": "sub_new",
                    "customer": "cus_1",
                    "status": "active",
                    "metadata": {"owner_user_id": "owner-1"},
                    "items": {
                        "data": [
                            {
                                "price": {"id": "price_pro_m"},
                                "current_period_end": 1767225600,
                            }
                        ]
                    },
                }
            },
        },
    )
    _tracked_subscription(monkeypatch, None)

    captured: dict = {}

    async def _apply(_self, owner, **kwargs):
        captured.update(owner=owner, **kwargs)
        return SimpleNamespace()

    monkeypatch.setattr(
        "app.repositories.subscription_repository.SubscriptionRepository.apply_stripe_state",
        _apply,
    )

    response = await client.post(
        "/billing/webhook", content=b"{}", headers={"stripe-signature": "sig"}
    )
    assert response.status_code == 200
    assert captured["owner"] == "owner-1"
    assert captured["plan"] == "pro"
    assert captured["billing_interval"] == "month"
    assert captured["stripe_subscription_id"] == "sub_new"
    assert captured["current_period_end"] is not None


# --- Top-up packs (Phase 2) ------------------------------------------------

async def test_topup_returns_hosted_stripe_url(client, settings, monkeypatch):
    monkeypatch.setattr(settings, "edge_shared_secret", "")
    monkeypatch.setattr(settings, "supabase_jwt_secret", JWT_SECRET)
    monkeypatch.setattr(settings, "app_base_url", "https://app.example.com")
    monkeypatch.setattr(settings, "stripe_price_topup", "price_topup")
    _owns_a_site(monkeypatch)  # autouse trial stub resolves to an active business plan

    captured: dict = {}

    async def _create(**kwargs):
        captured.update(kwargs)
        return "https://checkout.stripe.com/c/pay/topup_123"

    monkeypatch.setattr(
        "app.services.stripe_service.create_checkout_session", _create
    )

    response = await client.post("/billing/topup", json={"packs": 3}, headers=_auth())
    assert response.status_code == 200
    assert response.json()["url"].startswith("https://checkout.stripe.com/")
    assert captured["mode"] == "payment"
    assert captured["quantity"] == 3
    assert captured["metadata"] == {"kind": "topup", "packs": "3"}


async def test_topup_rejected_on_starter_plan(client, settings, monkeypatch):
    monkeypatch.setattr(settings, "edge_shared_secret", "")
    monkeypatch.setattr(settings, "supabase_jwt_secret", JWT_SECRET)
    monkeypatch.setattr(settings, "app_base_url", "https://app.example.com")
    monkeypatch.setattr(settings, "stripe_price_topup", "price_topup")
    _owns_a_site(monkeypatch)

    async def _starter(_self, owner):
        return SimpleNamespace(
            owner_user_id=owner,
            plan="starter",
            status="active",
            trial_ends_at=None,
            current_period_end=None,
            stripe_customer_id=None,
            stripe_subscription_id=None,
        )

    monkeypatch.setattr(
        "app.repositories.subscription_repository.SubscriptionRepository.get_or_create_trial",
        _starter,
    )

    response = await client.post("/billing/topup", json={"packs": 1}, headers=_auth())
    assert response.status_code == 402


async def test_webhook_topup_credits_bonus_messages(client, settings, monkeypatch):
    monkeypatch.setattr(settings, "edge_shared_secret", "")
    event = {
        "id": "evt_topup",
        "type": "checkout.session.completed",
        "data": {
            "object": {
                "client_reference_id": "owner-1",
                "metadata": {
                    "owner_user_id": "owner-1",
                    "kind": "topup",
                    "packs": "3",
                },
            }
        },
    }
    monkeypatch.setattr(
        "app.services.stripe_service.verify_event", lambda payload, sig: event
    )

    async def _mark(_self, _event_id):
        return True

    captured: dict = {}

    async def _add_bonus(_self, owner, period, quantity):
        captured.update(owner=owner, quantity=quantity)

    monkeypatch.setattr(
        "app.repositories.subscription_repository.SubscriptionRepository.mark_event_processed",
        _mark,
    )
    monkeypatch.setattr(
        "app.repositories.subscription_repository.SubscriptionRepository.add_bonus",
        _add_bonus,
    )

    response = await client.post(
        "/billing/webhook", content=b"{}", headers={"stripe-signature": "sig"}
    )
    assert response.status_code == 200
    assert captured["owner"] == "owner-1"
    assert captured["quantity"] == 3000  # 3 packs × 1,000

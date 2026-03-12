"""Stripe billing integration.

Wraps the Stripe API for checkout sessions, customer portal,
subscription management, and webhook event handling.
"""

from __future__ import annotations

import logging
from typing import Any

import stripe

from core.config import settings

logger = logging.getLogger("agentic_governance.billing")

TIER_FREE = "free"
TIER_PRO = "pro"
TIER_ENTERPRISE = "enterprise"

VALID_TIERS = {TIER_FREE, TIER_PRO, TIER_ENTERPRISE}

STRIPE_STATUS_MAP = {
    "active": "active",
    "trialing": "trialing",
    "past_due": "past_due",
    "canceled": "canceled",
    "unpaid": "unpaid",
    "incomplete": "incomplete",
    "incomplete_expired": "canceled",
    "paused": "paused",
}


def _init_stripe() -> None:
    if not settings.stripe_configured:
        raise RuntimeError("Stripe is not configured. Set STRIPE_SECRET_KEY and STRIPE_WEBHOOK_SECRET.")
    stripe.api_key = settings.stripe_secret_key


def get_or_create_customer(tenant_id: str, tenant_name: str, admin_email: str) -> str:
    """Return the Stripe customer ID for a tenant, creating one if needed."""
    _init_stripe()
    from core.database import SessionLocal
    from models.tenant import Tenant

    db = SessionLocal()
    try:
        tenant = db.query(Tenant).filter(Tenant.id == tenant_id).first()
        if not tenant:
            raise ValueError(f"Tenant {tenant_id} not found")

        if tenant.stripe_customer_id:
            return tenant.stripe_customer_id

        customer = stripe.Customer.create(
            email=admin_email,
            name=tenant_name,
            metadata={"tenant_id": tenant_id},
        )

        tenant.stripe_customer_id = customer.id
        db.commit()
        logger.info("Created Stripe customer %s for tenant %s", customer.id, tenant_id)
        return customer.id
    finally:
        db.close()


def create_checkout_session(
    tenant_id: str,
    tenant_name: str,
    admin_email: str,
    price_id: str,
    success_url: str,
    cancel_url: str,
) -> str:
    """Create a Stripe Checkout session and return the URL."""
    _init_stripe()
    customer_id = get_or_create_customer(tenant_id, tenant_name, admin_email)

    session = stripe.checkout.Session.create(
        customer=customer_id,
        mode="subscription",
        line_items=[{"price": price_id, "quantity": 1}],
        success_url=success_url,
        cancel_url=cancel_url,
        metadata={"tenant_id": tenant_id},
        allow_promotion_codes=True,
    )
    return session.url


def create_portal_session(tenant_id: str, return_url: str) -> str:
    """Create a Stripe Customer Portal session for subscription management."""
    _init_stripe()
    from core.database import SessionLocal
    from models.tenant import Tenant

    db = SessionLocal()
    try:
        tenant = db.query(Tenant).filter(Tenant.id == tenant_id).first()
        if not tenant or not tenant.stripe_customer_id:
            raise ValueError("Tenant has no Stripe customer")

        session = stripe.billing_portal.Session.create(
            customer=tenant.stripe_customer_id,
            return_url=return_url,
        )
        return session.url
    finally:
        db.close()


def handle_webhook_event(payload: bytes, sig_header: str) -> dict[str, Any]:
    """Verify and process a Stripe webhook event.

    Returns a dict with keys: event_type, tenant_id, and any relevant updates.
    """
    _init_stripe()
    event = stripe.Webhook.construct_event(
        payload, sig_header, settings.stripe_webhook_secret
    )

    result: dict[str, Any] = {"event_type": event.type, "stripe_event_id": event.id}

    if event.type == "checkout.session.completed":
        session = event.data.object
        tenant_id = session.get("metadata", {}).get("tenant_id")
        subscription_id = session.get("subscription")
        if tenant_id and subscription_id:
            _activate_subscription(tenant_id, subscription_id)
            result["tenant_id"] = tenant_id
            result["subscription_id"] = subscription_id

    elif event.type in (
        "customer.subscription.updated",
        "customer.subscription.deleted",
    ):
        subscription = event.data.object
        _sync_subscription(subscription)
        result["subscription_id"] = subscription.id

    elif event.type == "invoice.payment_failed":
        invoice = event.data.object
        customer_id = invoice.get("customer")
        if customer_id:
            _mark_payment_failed(customer_id)
            result["customer_id"] = customer_id

    return result


def _activate_subscription(tenant_id: str, subscription_id: str) -> None:
    """Set tenant to pro tier after successful checkout."""
    from core.database import SessionLocal
    from models.tenant import Tenant

    db = SessionLocal()
    try:
        tenant = db.query(Tenant).filter(Tenant.id == tenant_id).first()
        if not tenant:
            logger.warning("Webhook: tenant %s not found", tenant_id)
            return

        sub = stripe.Subscription.retrieve(subscription_id)
        price_id = sub["items"]["data"][0]["price"]["id"] if sub["items"]["data"] else ""

        tier = _price_to_tier(price_id)
        tenant.subscription_tier = tier
        tenant.subscription_status = STRIPE_STATUS_MAP.get(sub.status, sub.status)
        tenant.stripe_subscription_id = subscription_id
        tenant.trial_ends_at = None
        db.commit()
        logger.info("Tenant %s activated: tier=%s, sub=%s", tenant_id, tier, subscription_id)
    finally:
        db.close()


def _sync_subscription(subscription: Any) -> None:
    """Sync subscription state from Stripe to the local tenant."""
    from core.database import SessionLocal
    from models.tenant import Tenant

    customer_id = subscription.get("customer")
    if not customer_id:
        return

    db = SessionLocal()
    try:
        tenant = db.query(Tenant).filter(Tenant.stripe_customer_id == customer_id).first()
        if not tenant:
            logger.warning("Webhook: no tenant for customer %s", customer_id)
            return

        status = STRIPE_STATUS_MAP.get(subscription.status, subscription.status)
        tenant.subscription_status = status
        tenant.stripe_subscription_id = subscription.id

        if status == "canceled":
            tenant.subscription_tier = TIER_FREE
            tenant.stripe_subscription_id = None

        price_id = ""
        if subscription.get("items", {}).get("data"):
            price_id = subscription["items"]["data"][0]["price"]["id"]
        if price_id and status != "canceled":
            tenant.subscription_tier = _price_to_tier(price_id)

        db.commit()
        logger.info("Tenant %s synced: tier=%s, status=%s", tenant.id, tenant.subscription_tier, status)
    finally:
        db.close()


def _mark_payment_failed(customer_id: str) -> None:
    """Mark tenant subscription as past_due on payment failure."""
    from core.database import SessionLocal
    from models.tenant import Tenant

    db = SessionLocal()
    try:
        tenant = db.query(Tenant).filter(Tenant.stripe_customer_id == customer_id).first()
        if tenant:
            tenant.subscription_status = "past_due"
            db.commit()
            logger.warning("Tenant %s marked past_due after payment failure", tenant.id)
    finally:
        db.close()


def _price_to_tier(price_id: str) -> str:
    """Map a Stripe price ID to a subscription tier."""
    if price_id == settings.stripe_price_id_pro:
        return TIER_PRO
    if price_id == settings.stripe_price_id_enterprise:
        return TIER_ENTERPRISE
    logger.warning("Unknown Stripe price ID %r, defaulting to free tier", price_id)
    return TIER_FREE

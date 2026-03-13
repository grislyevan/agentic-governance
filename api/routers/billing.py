"""Billing router: checkout, portal, webhook, and subscription status."""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy.orm import Session

from core.config import settings
from core.database import get_db
from core.tenant import AuthContext, resolve_auth, require_role
from core.tier_limits import TIER_LIMITS, get_limits
from models.tenant import Tenant
from models.user import User

logger = logging.getLogger("agentic_governance.billing")

router = APIRouter(prefix="/billing", tags=["billing"])


def _require_stripe():
    if not settings.stripe_configured:
        raise HTTPException(503, "Billing is not configured. Set STRIPE_SECRET_KEY and STRIPE_WEBHOOK_SECRET.")


class CheckoutRequest(BaseModel):
    tier: str
    success_url: str
    cancel_url: str


class PortalRequest(BaseModel):
    return_url: str


@router.get("/status")
def billing_status(
    authorization: str | None = Header(default=None),
    x_api_key: str | None = Header(default=None),
    db: Session = Depends(get_db),
):
    """Get current billing status for the tenant."""
    auth = resolve_auth(authorization, x_api_key, db)
    tenant = db.query(Tenant).filter(Tenant.id == auth.tenant_id).first()
    if not tenant:
        raise HTTPException(404, "Tenant not found")

    limits = get_limits(tenant.subscription_tier)
    return {
        "tier": tenant.subscription_tier,
        "status": tenant.subscription_status,
        "stripe_configured": settings.stripe_configured,
        "is_trial": tenant.is_trial,
        "trial_ends_at": tenant.trial_ends_at.isoformat() if tenant.trial_ends_at else None,
        "stripe_customer_id": tenant.stripe_customer_id,
        "limits": {
            "max_endpoints": limits.max_endpoints,
            "max_events_per_day": limits.max_events_per_day,
            "max_users": limits.max_users,
            "webhook_enabled": limits.webhook_enabled,
            "sso_enabled": limits.sso_enabled,
            "siem_export": limits.siem_export,
            "retention_days": limits.retention_days,
        },
    }


@router.get("/tiers")
def list_tiers():
    """List available subscription tiers and their limits."""
    result = {}
    for tier_name, limits in TIER_LIMITS.items():
        result[tier_name] = {
            "max_endpoints": limits.max_endpoints,
            "max_events_per_day": limits.max_events_per_day,
            "max_users": limits.max_users,
            "webhook_enabled": limits.webhook_enabled,
            "sso_enabled": limits.sso_enabled,
            "siem_export": limits.siem_export,
            "retention_days": limits.retention_days,
            "price_id": _tier_price_id(tier_name),
        }
    return result


@router.post("/checkout")
def create_checkout(
    body: CheckoutRequest,
    authorization: str | None = Header(default=None),
    x_api_key: str | None = Header(default=None),
    db: Session = Depends(get_db),
):
    """Create a Stripe Checkout session to upgrade the subscription."""
    _require_stripe()
    auth = resolve_auth(authorization, x_api_key, db)
    require_role(auth, "owner", "admin")

    if body.tier not in ("pro", "enterprise"):
        raise HTTPException(400, "Can only checkout for 'pro' or 'enterprise' tier")

    price_id = _tier_price_id(body.tier)
    if not price_id:
        raise HTTPException(400, f"No Stripe price configured for tier '{body.tier}'")

    tenant = db.query(Tenant).filter(Tenant.id == auth.tenant_id).first()
    if not tenant:
        raise HTTPException(404, "Tenant not found")

    user = db.query(User).filter(User.id == auth.user_id).first()
    admin_email = user.email if user else "unknown@example.com"

    from core.billing import create_checkout_session
    url = create_checkout_session(
        tenant_id=tenant.id,
        tenant_name=tenant.name,
        admin_email=admin_email,
        price_id=price_id,
        success_url=body.success_url,
        cancel_url=body.cancel_url,
    )
    return {"checkout_url": url}


@router.post("/portal")
def create_portal(
    body: PortalRequest,
    authorization: str | None = Header(default=None),
    x_api_key: str | None = Header(default=None),
    db: Session = Depends(get_db),
):
    """Create a Stripe Customer Portal session for managing the subscription."""
    _require_stripe()
    auth = resolve_auth(authorization, x_api_key, db)
    require_role(auth, "owner", "admin")

    from core.billing import create_portal_session
    url = create_portal_session(
        tenant_id=auth.tenant_id,
        return_url=body.return_url,
    )
    return {"portal_url": url}


@router.post("/webhook")
async def stripe_webhook(request: Request):
    """Handle incoming Stripe webhook events.

    This endpoint is unauthenticated (Stripe sends events directly).
    Verification is done via the webhook signature.
    """
    _require_stripe()

    payload = await request.body()
    sig_header = request.headers.get("stripe-signature", "")

    if not sig_header:
        raise HTTPException(400, "Missing Stripe signature header")

    try:
        from core.billing import handle_webhook_event
        result = handle_webhook_event(payload, sig_header)
        logger.info("Processed Stripe webhook: %s", result.get("event_type"))
        return {"received": True, "event_type": result.get("event_type")}
    except Exception as e:
        logger.error("Stripe webhook error: %s", str(e))
        from core.config import settings
        detail = f"Webhook error: {str(e)}" if settings.debug else "Webhook processing failed."
        raise HTTPException(400, detail)


def _tier_price_id(tier: str) -> str:
    if tier == "pro":
        return settings.stripe_price_id_pro
    if tier == "enterprise":
        return settings.stripe_price_id_enterprise
    return ""

"""Tier-based usage limits for Detec billing.

Free:       3 endpoints, 1000 events/day, 1 user
Pro:        25 endpoints, unlimited events, 10 users
Enterprise: unlimited endpoints, unlimited events, unlimited users
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone


@dataclass(frozen=True)
class TierLimits:
    max_endpoints: int | None
    max_events_per_day: int | None
    max_users: int | None
    webhook_enabled: bool
    sso_enabled: bool
    siem_export: bool
    retention_days: int


TIER_LIMITS: dict[str, TierLimits] = {
    "free": TierLimits(
        max_endpoints=3,
        max_events_per_day=1000,
        max_users=1,
        webhook_enabled=False,
        sso_enabled=False,
        siem_export=False,
        retention_days=7,
    ),
    "pro": TierLimits(
        max_endpoints=25,
        max_events_per_day=None,
        max_users=10,
        webhook_enabled=True,
        sso_enabled=False,
        siem_export=False,
        retention_days=90,
    ),
    "enterprise": TierLimits(
        max_endpoints=None,
        max_events_per_day=None,
        max_users=None,
        webhook_enabled=True,
        sso_enabled=True,
        siem_export=True,
        retention_days=365,
    ),
}


def get_limits(tier: str) -> TierLimits:
    return TIER_LIMITS.get(tier, TIER_LIMITS["free"])


def check_endpoint_limit(tier: str, current_count: int) -> tuple[bool, str | None]:
    """Return (allowed, reason) for adding a new endpoint."""
    limits = get_limits(tier)
    if limits.max_endpoints is None:
        return True, None
    if current_count >= limits.max_endpoints:
        return False, f"Endpoint limit reached ({limits.max_endpoints} for {tier} tier). Upgrade to add more."
    return True, None


def check_event_limit(tier: str, events_today: int) -> tuple[bool, str | None]:
    """Return (allowed, reason) for ingesting a new event."""
    limits = get_limits(tier)
    if limits.max_events_per_day is None:
        return True, None
    if events_today >= limits.max_events_per_day:
        return False, f"Daily event limit reached ({limits.max_events_per_day} for {tier} tier). Upgrade for unlimited."
    return True, None


def check_user_limit(tier: str, current_count: int) -> tuple[bool, str | None]:
    """Return (allowed, reason) for adding a new user."""
    limits = get_limits(tier)
    if limits.max_users is None:
        return True, None
    if current_count >= limits.max_users:
        return False, f"User limit reached ({limits.max_users} for {tier} tier). Upgrade to add more."
    return True, None


def check_feature(tier: str, feature: str) -> tuple[bool, str | None]:
    """Check if a feature is available for the given tier."""
    limits = get_limits(tier)
    feature_map = {
        "webhooks": limits.webhook_enabled,
        "sso": limits.sso_enabled,
        "siem_export": limits.siem_export,
    }
    available = feature_map.get(feature, True)
    if not available:
        return False, f"Feature '{feature}' requires a higher tier. Current: {tier}."
    return True, None


def count_events_today(db, tenant_id: str) -> int:
    """Count events ingested today for a tenant."""
    from models.event import Event
    from sqlalchemy import func

    start_of_day = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    return (
        db.query(func.count(Event.id))
        .filter(Event.tenant_id == tenant_id, Event.observed_at >= start_of_day)
        .scalar()
        or 0
    )

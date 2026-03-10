"""Event-to-webhook matching and dispatch.

When an event is ingested, call ``dispatch_event`` to check if the tenant
has any active webhooks that subscribe to the event's decision_state.
If so, deliveries are scheduled as background tasks.
"""

from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session

from models.webhook import Webhook
from webhooks.sender import deliver

logger = logging.getLogger(__name__)


def _matches(webhook_events: str, decision_state: str | None) -> bool:
    """Check if a webhook's event subscription list matches the event."""
    try:
        subscribed = json.loads(webhook_events)
    except (json.JSONDecodeError, TypeError):
        return False
    if not subscribed:
        return True
    if decision_state and decision_state in subscribed:
        return True
    return False


def _build_payload(event_data: dict[str, Any], tenant_id: str) -> dict[str, Any]:
    """Build the webhook payload from the ingested event."""
    tool = event_data.get("tool", {})
    policy = event_data.get("policy", {})
    severity = event_data.get("severity", {})
    endpoint = event_data.get("endpoint", {})

    return {
        "event_id": event_data.get("event_id"),
        "event_type": event_data.get("event_type"),
        "observed_at": str(event_data.get("observed_at", "")),
        "tenant_id": tenant_id,
        "tool": {
            "name": tool.get("name"),
            "class": tool.get("class"),
            "version": tool.get("version"),
        },
        "policy": {
            "decision_state": policy.get("decision_state"),
            "rule_id": policy.get("rule_id"),
        },
        "severity": {
            "level": severity.get("level"),
        },
        "endpoint": {
            "hostname": endpoint.get("hostname") or endpoint.get("id"),
        },
        "delivered_at": datetime.now(timezone.utc).isoformat(),
    }


def dispatch_event(
    db: Session,
    tenant_id: str,
    event_data: dict[str, Any],
) -> int:
    """Find matching webhooks and schedule async deliveries.

    Returns the number of webhooks matched. Deliveries run as
    fire-and-forget background tasks on the running event loop.
    """
    decision_state = None
    policy = event_data.get("policy", {})
    if isinstance(policy, dict):
        decision_state = policy.get("decision_state")

    webhooks = (
        db.query(Webhook)
        .filter(
            Webhook.tenant_id == tenant_id,
            Webhook.is_active.is_(True),
        )
        .all()
    )

    matched = 0
    payload = None

    for wh in webhooks:
        if _matches(wh.events, decision_state):
            if payload is None:
                payload = _build_payload(event_data, tenant_id)

            try:
                loop = asyncio.get_running_loop()
                loop.create_task(deliver(wh.url, wh.secret, payload))
            except RuntimeError:
                logger.debug("No running event loop; skipping async webhook delivery")
            matched += 1

    if matched:
        logger.info(
            "Dispatched event %s to %d webhook(s) for tenant %s",
            event_data.get("event_id"), matched, tenant_id,
        )

    return matched

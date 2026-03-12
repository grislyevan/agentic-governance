"""Event-to-webhook matching and dispatch.

When an event is ingested, call ``dispatch_event`` to check if the tenant
has any active webhooks that subscribe to the event's event_type or
decision_state. Subscriptions may include enforcement event types
(enforcement.applied, enforcement.failed, posture.changed, etc.) or
policy decision states (block, warn, etc.). Empty subscription list matches
all events. Deliveries are scheduled as background tasks.
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


def _matches(
    webhook_events: str,
    event_type: str | None,
    decision_state: str | None,
) -> bool:
    try:
        subscribed = json.loads(webhook_events)
    except (json.JSONDecodeError, TypeError):
        return False
    if not subscribed:
        return True
    if event_type and event_type in subscribed:
        return True
    if decision_state and decision_state in subscribed:
        return True
    return False


_SECRET_PATTERNS = (
    "--api-key", "--api_key", "--secret", "--password", "--token",
    "API_KEY=", "SECRET=", "PASSWORD=", "TOKEN=",
)
_MAX_CMDLINE_LEN = 256


def _sanitize_cmdline(snippet: str | None) -> str | None:
    if not snippet:
        return snippet
    if len(snippet) > _MAX_CMDLINE_LEN:
        snippet = snippet[:_MAX_CMDLINE_LEN] + "..."
    for pat in _SECRET_PATTERNS:
        if pat.lower() in snippet.lower():
            snippet = "[redacted: may contain secrets]"
            break
    return snippet


def _build_payload(event_data: dict[str, Any], tenant_id: str) -> dict[str, Any]:
    tool = event_data.get("tool", {})
    policy = event_data.get("policy", {})
    severity = event_data.get("severity", {})
    endpoint = event_data.get("endpoint", {})
    enforcement = event_data.get("enforcement")
    posture = event_data.get("posture")

    payload: dict[str, Any] = {
        "event_id": event_data.get("event_id"),
        "event_type": event_data.get("event_type"),
        "observed_at": str(event_data.get("observed_at", "")),
        "tenant_id": tenant_id,
        "tool": {
            "name": tool.get("name"),
            "class": tool.get("class"),
            "version": tool.get("version"),
            "attribution_confidence": tool.get("attribution_confidence"),
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
            "posture": endpoint.get("posture"),
        },
        "delivered_at": datetime.now(timezone.utc).isoformat(),
    }

    if enforcement and isinstance(enforcement, dict):
        payload["enforcement"] = {
            "tactic": enforcement.get("tactic"),
            "success": enforcement.get("success"),
            "pids_killed": enforcement.get("pids_killed"),
            "process_name": enforcement.get("process_name"),
            "cmdline_snippet": _sanitize_cmdline(enforcement.get("cmdline_snippet")),
            "rate_limited": enforcement.get("rate_limited"),
            "simulated": enforcement.get("simulated"),
            "allow_listed": enforcement.get("allow_listed"),
            "provider": enforcement.get("provider"),
            "detail": enforcement.get("detail"),
        }

    if posture and isinstance(posture, dict):
        payload["posture"] = {
            "old_posture": posture.get("old_posture"),
            "new_posture": posture.get("new_posture"),
            "changed_by": posture.get("changed_by"),
            "auto_enforce_threshold": posture.get("auto_enforce_threshold"),
        }

    return payload


def dispatch_event(
    db: Session,
    tenant_id: str,
    event_data: dict[str, Any],
) -> int:
    """Find matching webhooks and schedule async deliveries.

    Returns the number of webhooks matched. Deliveries run as
    fire-and-forget background tasks on the running event loop.
    """
    event_type = event_data.get("event_type")
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
        if _matches(wh.events, event_type, decision_state):
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

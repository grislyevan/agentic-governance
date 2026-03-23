"""Webhook subscription matching (stdlib only; safe without API DB deps)."""

from __future__ import annotations

import json


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

"""Structured incident-response playbook definitions.

Playbooks define trigger conditions and action chains. The response
orchestrator matches ingested events against triggers and runs the
configured actions (enforcement push, webhook, audit log). Escalation
runs after N failures of the primary action.
"""

from __future__ import annotations

from typing import Any

# Trigger keys that can be matched against event payload (decision_state, confidence, event_type).
# Confidence is taken from event payload or severity; decision_state from policy block.
TRIGGER_KEYS = ("decision_state", "confidence", "event_type")

# Action types the orchestrator can execute.
ACTION_ENFORCEMENT = "enforcement"
ACTION_WEBHOOK = "webhook"
ACTION_AUDIT_LOG = "audit_log"

# Default playbook definitions (id -> definition). Tenants can override or add custom playbooks.
PLAYBOOK_DEFINITIONS: dict[str, dict[str, Any]] = {
    "high_confidence_block": {
        "name": "High confidence block",
        "description": "On block decision with High confidence: log, notify, and record critical audit.",
        "trigger": {
            "decision_state": "block",
            "confidence": "High",
        },
        "actions": [
            {"type": ACTION_WEBHOOK, "template": "pagerduty", "payload_key": "default"},
            {"type": ACTION_AUDIT_LOG, "severity": "critical"},
        ],
        "escalation": None,
    },
    "block_with_escalation": {
        "name": "Block with escalation",
        "description": "On block: notify and audit; after 3 failures escalate to network block.",
        "trigger": {
            "decision_state": "block",
        },
        "actions": [
            {"type": ACTION_WEBHOOK, "template": "slack", "payload_key": "default"},
            {"type": ACTION_AUDIT_LOG, "severity": "high"},
        ],
        "escalation": {
            "after_failures": 3,
            "action": {"type": ACTION_ENFORCEMENT, "tactic": "network_null_route"},
        },
    },
    "enforcement_applied": {
        "name": "Enforcement applied",
        "description": "When enforcement.applied is emitted: send to SIEM and audit.",
        "trigger": {
            "event_type": "enforcement.applied",
        },
        "actions": [
            {"type": ACTION_WEBHOOK, "template": "splunk", "payload_key": "default"},
            {"type": ACTION_AUDIT_LOG, "severity": "high"},
        ],
        "escalation": None,
    },
    "warn_notify": {
        "name": "Warn notify",
        "description": "On warn decision: audit and optional webhook.",
        "trigger": {
            "decision_state": "warn",
        },
        "actions": [
            {"type": ACTION_AUDIT_LOG, "severity": "medium"},
        ],
        "escalation": None,
    },
}


def match_trigger(trigger: dict[str, Any], event_payload: dict[str, Any]) -> bool:
    """Return True if the event payload matches the playbook trigger.

    All keys present in trigger must match the event. Confidence can come
    from event payload severity or a top-level confidence field.
    """
    if not trigger:
        return True
    for key, want in trigger.items():
        if key == "decision_state":
            policy = event_payload.get("policy") or {}
            got = policy.get("decision_state")
            if got != want:
                return False
        elif key == "event_type":
            got = event_payload.get("event_type")
            if got != want:
                return False
        elif key == "confidence":
            got = _event_confidence(event_payload)
            if got != want:
                return False
        else:
            got = event_payload.get(key)
            if got != want:
                return False
    return True


def _event_confidence(event_payload: dict[str, Any]) -> str | None:
    """Derive confidence from event (severity or explicit confidence)."""
    if event_payload.get("confidence"):
        return event_payload.get("confidence")
    severity = event_payload.get("severity") or {}
    level = severity.get("level") or ""
    if level in ("P1", "critical", "Critical"):
        return "High"
    if level in ("P2", "high", "High"):
        return "High"
    if level in ("P3", "medium", "Medium"):
        return "Medium"
    if level in ("P4", "low", "Low"):
        return "Low"
    return None


def get_default_playbooks() -> dict[str, dict[str, Any]]:
    """Return a copy of default playbook definitions."""
    return dict(PLAYBOOK_DEFINITIONS)

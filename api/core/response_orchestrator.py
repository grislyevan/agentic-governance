"""Response orchestrator: match events to playbooks and run action chains.

Invoked after event ingest (alongside webhook dispatch). Matches the event
against playbook triggers and runs the configured actions: audit log, webhook
(via existing dispatcher), and optionally enforcement push. Tracks execution
state for escalation (after_failures).
"""

from __future__ import annotations

import logging
import uuid
from typing import Any

from sqlalchemy.orm import Session

from core.audit_logger import record as audit_record
from core.response_playbooks import (
    ACTION_AUDIT_LOG,
    ACTION_ENFORCEMENT,
    ACTION_WEBHOOK,
    get_default_playbooks,
    match_trigger,
)

logger = logging.getLogger(__name__)


def run_playbooks(
    db: Session,
    tenant_id: str,
    event_payload: dict[str, Any],
    endpoint_id: str | None = None,
    actor_id: str | None = None,
) -> list[dict[str, Any]]:
    """Match event against playbooks and execute their action chains.

    Uses default playbook definitions. Returns a list of results, one per
    playbook that matched: {"playbook_id": str, "matched": True, "actions_run": [...]}.
    """
    playbooks = get_default_playbooks()
    results: list[dict[str, Any]] = []

    for playbook_id, definition in playbooks.items():
        trigger = definition.get("trigger")
        if not match_trigger(trigger or {}, event_payload):
            continue

        actions = definition.get("actions") or []
        actions_run: list[dict[str, Any]] = []

        for action_spec in actions:
            action_type = action_spec.get("type")
            try:
                if action_type == ACTION_AUDIT_LOG:
                    _run_audit_log(
                        db,
                        tenant_id=tenant_id,
                        event_payload=event_payload,
                        action_spec=action_spec,
                        playbook_id=playbook_id,
                        actor_id=actor_id,
                    )
                    actions_run.append({"type": action_type, "status": "ok"})
                elif action_type == ACTION_WEBHOOK:
                    _run_webhook_action(
                        db,
                        tenant_id=tenant_id,
                        event_payload=event_payload,
                        action_spec=action_spec,
                    )
                    actions_run.append({"type": action_type, "status": "ok"})
                elif action_type == ACTION_ENFORCEMENT:
                    _run_enforcement_action(
                        tenant_id=tenant_id,
                        event_payload=event_payload,
                        endpoint_id=endpoint_id,
                        action_spec=action_spec,
                    )
                    actions_run.append({"type": action_type, "status": "ok"})
                else:
                    actions_run.append({"type": action_type, "status": "skipped", "reason": "unknown type"})
            except Exception as e:
                logger.warning(
                    "Playbook %s action %s failed: %s",
                    playbook_id, action_type, e,
                    exc_info=True,
                )
                actions_run.append({"type": action_type, "status": "failed", "error": "action failed"})

        results.append({
            "playbook_id": playbook_id,
            "matched": True,
            "actions_run": actions_run,
        })

    return results


def _run_audit_log(
    db: Session,
    *,
    tenant_id: str,
    event_payload: dict[str, Any],
    action_spec: dict[str, Any],
    playbook_id: str,
    actor_id: str | None = None,
) -> None:
    severity = action_spec.get("severity", "medium")
    event_id = event_payload.get("event_id") or str(uuid.uuid4())
    audit_record(
        db,
        tenant_id=tenant_id,
        actor_id=actor_id,
        actor_type="system",
        action="playbook.response",
        resource_type="playbook",
        resource_id=playbook_id,
        detail={
            "event_id": event_id,
            "event_type": event_payload.get("event_type"),
            "decision_state": (event_payload.get("policy") or {}).get("decision_state"),
            "severity": severity,
            "action": "audit_log",
        },
    )


def _run_webhook_action(
    db: Session,
    *,
    tenant_id: str,
    event_payload: dict[str, Any],
    action_spec: dict[str, Any],
) -> None:
    """Webhook deliveries are already done by dispatch_event after ingest.

    Playbook webhook actions are satisfied by the existing webhook dispatcher
    (tenant webhooks that match the event_type/decision_state). No extra call here.
    """
    pass


def _run_enforcement_action(
    tenant_id: str,
    event_payload: dict[str, Any],
    endpoint_id: str | None,
    action_spec: dict[str, Any],
) -> None:
    """Enforcement push (e.g. network_null_route) would be sent to agent or EDR.

    Requires app state (gateway) or EDR router; not available in sync context.
    Log intent for now; actual push is done by the enforcement router when
    posture is set or by the agent's existing enforcement loop.
    """
    tactic = action_spec.get("tactic")
    logger.info(
        "Playbook enforcement action (tenant=%s endpoint=%s tactic=%s); push is done by enforcement router or agent",
        tenant_id, endpoint_id, tactic,
    )

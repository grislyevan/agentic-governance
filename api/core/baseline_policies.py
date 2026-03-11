"""Baseline policy definitions that ship with every tenant.

Maps 1:1 to the deterministic rules in collector/engine/policy.py (RULE_VERSION 0.4.0)
and Playbook Section 6.3. Each entry becomes a row in the ``policies`` table on
tenant creation.

To add or modify baseline rules:
  1. Update the collector's policy.py
  2. Mirror the change here
  3. Bump BASELINE_VERSION
  4. Existing tenants get updates via the "restore defaults" endpoint
"""

from __future__ import annotations

BASELINE_VERSION = "0.4.0"

BASELINE_POLICIES: list[dict] = [
    # ── Core Enforcement Rules ────────────────────────────────────────
    {
        "rule_id": "ENFORCE-001",
        "rule_version": BASELINE_VERSION,
        "category": "enforcement",
        "is_active": True,
        "description": (
            "Low confidence detection on non-sensitive assets with read-only actions. "
            "Records and monitors without user disruption."
        ),
        "parameters": {
            "decision_state": "detect",
            "conditions": {
                "confidence_band": ["Low"],
                "tool_classes": ["A", "B", "C"],
                "sensitivity_tiers": ["Tier0", "Tier1"],
                "action_risk_max": "R1",
            },
            "precedence": 100,
        },
    },
    {
        "rule_id": "ENFORCE-002",
        "rule_version": BASELINE_VERSION,
        "category": "enforcement",
        "is_active": True,
        "description": (
            "Medium confidence detection with scoped write actions. "
            "Warns operator and creates policy awareness."
        ),
        "parameters": {
            "decision_state": "warn",
            "conditions": {
                "confidence_band": ["Medium"],
                "tool_classes": ["A", "B", "C"],
                "sensitivity_tiers": ["Tier1", "Tier2"],
                "action_risk_min": "R2",
            },
            "precedence": 200,
        },
    },
    {
        "rule_id": "ENFORCE-003",
        "rule_version": BASELINE_VERSION,
        "category": "enforcement",
        "is_active": True,
        "description": (
            "Medium confidence detection on sensitive assets with broad actions. "
            "Holds action pending authorized sign-off."
        ),
        "parameters": {
            "decision_state": "approval_required",
            "conditions": {
                "confidence_band": ["Medium"],
                "tool_classes": ["A", "B", "C"],
                "sensitivity_tiers": ["Tier2", "Tier3"],
                "action_risk_min": "R3",
            },
            "precedence": 300,
        },
    },
    {
        "rule_id": "ENFORCE-004",
        "rule_version": BASELINE_VERSION,
        "category": "enforcement",
        "is_active": True,
        "description": (
            "High confidence detection with privileged or prohibited actions. "
            "Blocks the action to enforce policy boundary."
        ),
        "parameters": {
            "decision_state": "block",
            "conditions": {
                "confidence_band": ["High"],
                "tool_classes": ["A", "B", "C"],
                "action_risk_min": "R4",
            },
            "precedence": 400,
        },
    },
    {
        "rule_id": "ENFORCE-005",
        "rule_version": BASELINE_VERSION,
        "category": "enforcement",
        "is_active": True,
        "description": (
            "Explicit deny on crown-jewel or regulated assets. "
            "Blocks regardless of confidence level."
        ),
        "parameters": {
            "decision_state": "block",
            "conditions": {
                "confidence_band": ["Low", "Medium", "High"],
                "tool_classes": ["A", "B", "C"],
                "sensitivity_tiers": ["Tier3"],
                "explicit_deny": True,
            },
            "precedence": 500,
        },
    },
    {
        "rule_id": "ENFORCE-006",
        "rule_version": BASELINE_VERSION,
        "category": "enforcement",
        "is_active": True,
        "description": (
            "Autonomous executors (Class C) at medium or high confidence with broad actions. "
            "Requires approval before execution proceeds."
        ),
        "parameters": {
            "decision_state": "approval_required",
            "conditions": {
                "confidence_band": ["Medium", "High"],
                "tool_classes": ["C"],
                "action_risk_min": "R3",
            },
            "precedence": 350,
        },
    },

    # ── Class D Override Rules ────────────────────────────────────────
    {
        "rule_id": "ENFORCE-D01",
        "rule_version": BASELINE_VERSION,
        "category": "class_d",
        "is_active": True,
        "description": (
            "Persistent autonomous agents (Class D) with broad or privileged actions. "
            "Always blocked: self-modifying daemons must not perform high-risk operations."
        ),
        "parameters": {
            "decision_state": "block",
            "conditions": {
                "confidence_band": ["Low", "Medium", "High"],
                "tool_classes": ["D"],
                "action_risk_min": "R3",
            },
            "precedence": 50,
            "rationale": "Class D tools have daemon persistence and self-modification capability.",
        },
    },
    {
        "rule_id": "ENFORCE-D02",
        "rule_version": BASELINE_VERSION,
        "category": "class_d",
        "is_active": True,
        "description": (
            "Persistent autonomous agents at medium or high confidence with scoped writes. "
            "Requires approval: even routine writes need sign-off for always-on agents."
        ),
        "parameters": {
            "decision_state": "approval_required",
            "conditions": {
                "confidence_band": ["Medium", "High"],
                "tool_classes": ["D"],
                "action_risk_min": "R2",
            },
            "precedence": 51,
            "rationale": "Scoped writes from persistent agents carry elevated risk.",
        },
    },
    {
        "rule_id": "ENFORCE-D03",
        "rule_version": BASELINE_VERSION,
        "category": "class_d",
        "is_active": True,
        "description": (
            "Warn floor for all Class D detections regardless of confidence or risk. "
            "No safe baseline exists for always-on autonomous agents."
        ),
        "parameters": {
            "decision_state": "warn",
            "conditions": {
                "confidence_band": ["Low", "Medium", "High"],
                "tool_classes": ["D"],
                "action_risk_min": "R1",
            },
            "precedence": 52,
            "rationale": "An always-on agent has no safe baseline; operator awareness is mandatory.",
        },
    },

    # ── Overlay Rules ─────────────────────────────────────────────────
    {
        "rule_id": "NET-001",
        "rule_version": BASELINE_VERSION,
        "category": "overlay",
        "is_active": True,
        "description": (
            "Autonomous tools (Class C/D) with unknown outbound network connections. "
            "Escalates to approval required for unrecognized destinations."
        ),
        "parameters": {
            "decision_state": "approval_required",
            "conditions": {
                "tool_classes": ["C", "D"],
                "unknown_outbound_min": 1,
            },
            "precedence": 600,
            "overlay": True,
        },
    },
    {
        "rule_id": "NET-002",
        "rule_version": BASELINE_VERSION,
        "category": "overlay",
        "is_active": True,
        "description": (
            "Autonomous tools (Class C/D) with high-volume unknown outbound connections. "
            "Blocks to mitigate data exfiltration risk."
        ),
        "parameters": {
            "decision_state": "block",
            "conditions": {
                "tool_classes": ["C", "D"],
                "unknown_outbound_min": 3,
            },
            "precedence": 601,
            "overlay": True,
            "rationale": "Three or more unknown destinations indicates potential exfiltration.",
        },
    },
    {
        "rule_id": "ISO-001",
        "rule_version": BASELINE_VERSION,
        "category": "overlay",
        "is_active": False,
        "description": (
            "Container isolation requirement for Class C autonomous executors. "
            "Blocks when not running inside a container. Disabled by default; "
            "enable for environments that mandate sandboxed execution."
        ),
        "parameters": {
            "decision_state": "block",
            "conditions": {
                "tool_classes": ["C"],
                "requires_container": True,
            },
            "precedence": 602,
            "overlay": True,
            "rationale": "Container isolation prevents host-level side effects from autonomous code execution.",
        },
    },

    # ── Fallback Rules ────────────────────────────────────────────────
    {
        "rule_id": "ENFORCE-001-F",
        "rule_version": BASELINE_VERSION,
        "category": "fallback",
        "is_active": True,
        "description": (
            "Fallback for low-confidence detections that don't match a specific rule. "
            "Defaults to detect-only."
        ),
        "parameters": {
            "decision_state": "detect",
            "conditions": {
                "confidence_band": ["Low"],
            },
            "precedence": 900,
            "is_fallback": True,
        },
    },
    {
        "rule_id": "ENFORCE-002-F",
        "rule_version": BASELINE_VERSION,
        "category": "fallback",
        "is_active": True,
        "description": (
            "Fallback for medium or high confidence detections with no specific rule match. "
            "Defaults to warn."
        ),
        "parameters": {
            "decision_state": "warn",
            "conditions": {
                "confidence_band": ["Medium", "High"],
            },
            "precedence": 901,
            "is_fallback": True,
        },
    },
    {
        "rule_id": "ENFORCE-003-F",
        "rule_version": BASELINE_VERSION,
        "category": "fallback",
        "is_active": True,
        "description": (
            "Fallback for high confidence detections with broad actions and no specific rule match. "
            "Defaults to approval required."
        ),
        "parameters": {
            "decision_state": "approval_required",
            "conditions": {
                "confidence_band": ["High"],
                "action_risk_min": "R3",
            },
            "precedence": 902,
            "is_fallback": True,
        },
    },
]


def get_baseline_rule_ids() -> set[str]:
    """Return the set of rule_id values that are baseline."""
    return {p["rule_id"] for p in BASELINE_POLICIES}


def seed_baseline_policies(
    db: "Session",
    tenant_id: str,
    *,
    restore: bool = False,
) -> int:
    """Insert baseline policies for a tenant. Returns count of rows created.

    When ``restore=True``, missing rules are re-created and existing baseline
    rules are reset to their default state (is_active, parameters, description,
    rule_version).  Non-baseline (custom) policies are never touched.
    """
    from models.policy import Policy
    import uuid as _uuid

    existing = {
        p.rule_id: p
        for p in db.query(Policy).filter(
            Policy.tenant_id == tenant_id,
            Policy.is_baseline.is_(True),
        ).all()
    }

    created = 0
    for defn in BASELINE_POLICIES:
        rule_id = defn["rule_id"]

        if rule_id in existing:
            if restore:
                row = existing[rule_id]
                row.rule_version = defn["rule_version"]
                row.description = defn["description"]
                row.is_active = defn["is_active"]
                row.parameters = defn["parameters"]
                row.category = defn["category"]
            continue

        db.add(Policy(
            id=str(_uuid.uuid4()),
            tenant_id=tenant_id,
            rule_id=rule_id,
            rule_version=defn["rule_version"],
            description=defn["description"],
            is_active=defn["is_active"],
            is_baseline=True,
            category=defn["category"],
            parameters=defn["parameters"],
        ))
        created += 1

    return created

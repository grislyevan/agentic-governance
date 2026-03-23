"""Code-defined policy presets for tenant baseline rules.

Presets are applied via POST /api/policies/apply-preset. Only baseline
rule_ids from baseline_policies.py are used. Null parameters mean use
baseline default.
"""

from __future__ import annotations

import copy
from typing import Any

from sqlalchemy.orm import Session

from core.baseline_policies import BASELINE_POLICIES, get_baseline_rule_ids
from models.policy import Policy

_BASELINE_BY_RULE_ID: dict[str, dict[str, Any]] = {
    p["rule_id"]: {
        "is_active": p["is_active"],
        "parameters": copy.deepcopy(p["parameters"]),
    }
    for p in BASELINE_POLICIES
}


def _baseline_state(rule_id: str) -> dict[str, Any]:
    """Return default is_active and parameters for a baseline rule_id."""
    if rule_id not in _BASELINE_BY_RULE_ID:
        return {"is_active": True, "parameters": {}}
    return copy.deepcopy(_BASELINE_BY_RULE_ID[rule_id])


def _audit_only_params(baseline_params: dict) -> dict:
    """Downgrade block/approval_required to warn for audit-only preset."""
    out = copy.deepcopy(baseline_params)
    if out.get("decision_state") in ("block", "approval_required"):
        out["decision_state"] = "warn"
    return out


# All 15 baseline rule IDs for building full rule_states.
_BASELINE_IDS = get_baseline_rule_ids()

# Preset 1: Block all AI coding tools (block and approval_required rules on; others per baseline).
_BLOCK_ALL_STATES = {}
for rid in _BASELINE_IDS:
    default = _baseline_state(rid)
    _BLOCK_ALL_STATES[rid] = {
        "is_active": True if rid != "ISO-001" else False,
        "parameters": None,
    }

# Preset 2: Audit only (no block, no approval_required; warn/detect only).
_AUDIT_ONLY_STATES = {}
for rid in _BASELINE_IDS:
    default = _baseline_state(rid)
    params = default["parameters"]
    if params.get("decision_state") in ("block", "approval_required"):
        _AUDIT_ONLY_STATES[rid] = {
            "is_active": True,
            "parameters": _audit_only_params(params),
        }
    else:
        _AUDIT_ONLY_STATES[rid] = {"is_active": default["is_active"], "parameters": None}

# Preset 3: Allow local, block cloud (local = detect/warn; cloud/autonomous = block/approval).
# Toggle: 001/002 on; 003 off so no approval for medium Tier2/3 on A,B,C; 004,005,006,D01,D02,D03,NET-001,NET-002 on.
_ALLOW_LOCAL_STATES = {}
for rid in _BASELINE_IDS:
    default = _baseline_state(rid)
    if rid == "ENFORCE-003":
        _ALLOW_LOCAL_STATES[rid] = {"is_active": False, "parameters": None}
    else:
        _ALLOW_LOCAL_STATES[rid] = {
            "is_active": True if rid != "ISO-001" else False,
            "parameters": None,
        }

# Preset 4: High security (all block rules on, NET-001/002 on, including ISO-001).
_HIGH_SECURITY_STATES = {}
for rid in _BASELINE_IDS:
    _HIGH_SECURITY_STATES[rid] = {"is_active": True, "parameters": None}


POLICY_PRESETS: list[dict[str, Any]] = [
    {
        "id": "block_all_ai_coding",
        "name": "Block all AI coding tools",
        "description": "Block and approval-required rules on; detect/warn kept. No blocking on container (ISO-001 off).",
        "rule_states": _BLOCK_ALL_STATES,
    },
    {
        "id": "audit_only",
        "name": "Audit only",
        "description": "No block or approval required; all actions recorded or warned, none blocked.",
        "rule_states": _AUDIT_ONLY_STATES,
    },
    {
        "id": "allow_local_block_cloud",
        "name": "Allow local, block cloud",
        "description": "Local tools (A/B) detect/warn; autonomous/cloud (C/D) use block and approval. Medium Tier2/3 approval off.",
        "rule_states": _ALLOW_LOCAL_STATES,
    },
    {
        "id": "high_security",
        "name": "High security",
        "description": "All baseline rules on including container isolation (ISO-001) and network overlays (NET-001, NET-002).",
        "rule_states": _HIGH_SECURITY_STATES,
    },
]


def get_presets_list() -> list[dict[str, Any]]:
    """Return list of presets for API (id, name, description only)."""
    return [
        {"id": p["id"], "name": p["name"], "description": p["description"]}
        for p in POLICY_PRESETS
    ]


def get_preset_by_id(preset_id: str) -> dict[str, Any] | None:
    """Return full preset by id or None."""
    for p in POLICY_PRESETS:
        if p["id"] == preset_id:
            return p
    return None


def apply_preset_to_tenant(db: Session, tenant_id: str, preset_id: str) -> int:
    """Update every baseline Policy row for the tenant to match the preset.

    Non-baseline policies are unchanged. Returns the number of baseline
    policies updated. Raises ValueError if preset_id is unknown.
    """
    preset = get_preset_by_id(preset_id)
    if not preset:
        raise ValueError(f"Unknown preset_id: {preset_id}")

    rule_states = preset["rule_states"]
    baseline_rows = (
        db.query(Policy)
        .filter(Policy.tenant_id == tenant_id, Policy.is_baseline.is_(True))
        .all()
    )
    updated = 0
    for row in baseline_rows:
        state = rule_states.get(row.rule_id)
        if not state:
            continue
        params = state.get("parameters")
        if params is None:
            baseline_def = _BASELINE_BY_RULE_ID.get(row.rule_id)
            params = copy.deepcopy(baseline_def["parameters"]) if baseline_def else {}
        else:
            params = copy.deepcopy(params)
        row.is_active = state.get("is_active", row.is_active)
        row.parameters = params
        updated += 1
    return updated

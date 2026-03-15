# Policy Mapping for DETEC-BEH-CORE-01/02/03

This document maps the three core behavioral detections to default policy actions. The collector does not evaluate rules by detection code; it uses confidence band, tool class, sensitivity tier, and action risk. The mapping below describes how existing ENFORCE-* and NET-* rules produce the desired defaults when these patterns fire.

## Detection to risk and rules

| Detection | Pattern | Default action intent | How it is achieved |
|-----------|---------|------------------------|---------------------|
| **DETEC-BEH-CORE-01** (Autonomous shell fan-out) | BEH-001 | warn or approval_required by class/risk | BEH-001 often pairs with BEH-002 (LLM cadence); `_determine_risk()` returns R3 when BEH-001 and BEH-002 both match. Resulting confidence band (Medium/High) plus action_risk R2 or R3 drives ENFORCE-002 (warn) or ENFORCE-003 (approval_required) per sensitivity. |
| **DETEC-BEH-CORE-02** (Read-modify-write loop) | BEH-004 | detect / warn / approval_required depending on repo sensitivity | action_risk R2 or R3 from pattern set; sensitivity_tier (Tier0–Tier3) is applied in policy evaluation. ENFORCE-001 (detect), ENFORCE-002 (warn), or ENFORCE-003 (approval_required) apply by condition. |
| **DETEC-BEH-CORE-03** (Sensitive access + outbound) | BEH-006 | approval_required or block | BEH-006 sets action_risk to R3 in `_determine_risk()`. For Unknown Agent (Class C), ENFORCE-003 or ENFORCE-004 can apply. If outbound is unknown (not on allowlist), NET-001 (approval_required) or NET-002 (block for high volume) is evaluated in addition. |

## Rule references

- **ENFORCE-001 to ENFORCE-007:** [api/core/baseline_policies.py](../api/core/baseline_policies.py), [collector/engine/policy.py](../collector/engine/policy.py).
- **NET-001, NET-002:** Network rules for unknown outbound; evaluated when `NetworkContext.unknown_connections > 0`.
- **Risk (R1–R4):** Set in behavioral scanner by `_determine_risk(matches)`; BEH-006 or BEH-008 imply R3.

## Optional: rules keyed by detection code

The current design uses (confidence_band, tool_class, sensitivity_tier, action_risk). If product requirements later need rule-by-detection overrides (e.g. "always block when DETEC-BEH-CORE-03 fires"), add baseline rules that reference `detection_codes` in the event payload and prescribe `decision_state`. The event already includes `evidence_details.detection_codes` (DETEC-BEH-CORE-01/02/03) when the corresponding BEH pattern matches.

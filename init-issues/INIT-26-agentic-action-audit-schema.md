# INIT-26 — Agentic Action Audit Schema (Full Deep Revision)

## Scope
Issue: **INIT-26**
Objective: define an audit schema that captures agentic AI actions with enough fidelity to support:
- incident response,
- policy explainability,
- compliance/audit demands,
- buyer technical due diligence.

This schema must be operationally useful (fast triage) and evidentially defensible (forensic integrity).

---

## 1) Why This Schema Matters
Without a strict audit schema, governance claims are weak because teams cannot reliably answer:
- who performed the action,
- what tool/class was involved,
- what action occurred,
- what target was affected,
- why policy allowed/blocked it,
- what evidence proves that decision.

Schema quality directly determines trustworthiness of the product’s enforcement story.

---

## 2) Design Principles
1. **Immutable event lineage** — preserve original event IDs and processing chain.
2. **Deterministic explainability** — decisions must reference rule IDs and evidence IDs.
3. **Context completeness** — actor, asset, action, policy, and confidence captured together.
4. **Forensic readiness** — include timestamps, hashes, and provenance metadata.
5. **Privacy-aware minimization** — capture enough to audit, avoid unnecessary sensitive payload storage.

---

## 3) Canonical Event Envelope
Every audit record should contain:

### A) Event Identity
- `event_id` (globally unique)
- `parent_event_id` (for correlated chains)
- `session_id`
- `trace_id` / `span_id` (if distributed pipeline)
- `event_version`

### B) Time Metadata
- `observed_at` (source observation time)
- `ingested_at` (pipeline receipt time)
- `decided_at` (policy decision time)
- `clock_skew_ms` (if measured)

### C) Actor Context
- `actor_id`
- `actor_type` (human/service/automation)
- `actor_trust_tier`
- `identity_confidence`
- `endpoint_id` / `host_id`
- `endpoint_posture` (managed/unmanaged, risk score)

### D) Tool Attribution
- `tool_name` (if known)
- `tool_class` (A/B/C per policy model)
- `tool_confidence`
- `tool_attribution_sources` (process/file/network/identity/behavior)

### E) Action Context
- `action_type` (read/write/exec/network/repo/privileged)
- `action_risk_class` (R1-R4)
- `action_summary` (normalized)
- `action_raw_ref` (pointer to redacted raw details)

### F) Target Context
- `target_type` (path/repo/host/destination)
- `target_id`
- `target_sensitivity_tier`
- `target_scope` (path prefix, repo branch, network destination)

### G) Policy Decision
- `decision_state` (detect/warn/approval_required/block)
- `decision_rule_id`
- `decision_rule_version`
- `decision_reason_codes[]`
- `decision_confidence`

### H) Approval/Exception Linkage
- `approval_id` (nullable)
- `approval_scope_id` (nullable)
- `exception_id` (nullable)
- `exception_expiry` (nullable)

### I) Evidence and Integrity
- `evidence_ids[]`
- `artifact_hashes[]`
- `provenance_collector_id`
- `integrity_status`

### J) Outcome Metadata
- `enforcement_outcome` (allowed/held/denied)
- `user_visible_message_id` (if shown)
- `incident_flag` (bool)
- `incident_id` (nullable)

---

## 4) Evidence Object Model (Linked)
Audit schema should reference evidence objects, not bloat event payloads.

Evidence object fields:
- `evidence_id`
- `evidence_type` (process_tree, file_diff, netflow, policy_eval, approval_record)
- `captured_at`
- `storage_uri`
- `hash`
- `redaction_level`
- `chain_of_custody`

Benefits:
- scalable storage,
- integrity and tamper detection,
- privacy-aware retrieval by role.

---

## 5) Normalization and Enumerations
Use strict enums to avoid analyst ambiguity:
- action_type enum,
- decision_state enum,
- trust tier enum,
- sensitivity tier enum,
- tool_class enum,
- risk class enum.

All free-text fields should be supplemental, not canonical.

---

## 6) Explainability Requirements
Every enforcement event must be reconstructible via:
1. what triggered policy (signals),
2. which rule fired,
3. why alternatives were not chosen,
4. what evidence supports the final state.

Minimum explainability payload:
- top contributing signals,
- confidence penalties,
- competing rule evaluation summary,
- final rule precedence result.

---

## 7) Data Retention and Privacy Guardrails

### Retention tiers
- hot retention for triage (short-term indexed)
- warm retention for investigations
- cold retention for compliance archive

### Privacy controls
- redact sensitive command/content payloads by policy,
- tokenize identities where required by region,
- role-based evidence access,
- audit every evidence retrieval.

---

## 8) Failure Modes and Hardening

### Failure: Missing actor attribution
Action: mark identity_confidence low, prevent high-trust decisions, escalate for review.

### Failure: Rule ID missing in decision event
Action: reject event as non-compliant, emit schema integrity alert.

### Failure: Evidence hash mismatch
Action: mark integrity_status failed, trigger incident workflow.

### Failure: Time inconsistency across pipeline
Action: store skew metadata and prevent strict sequence assumptions until corrected.

---

## 9) Query and Reporting Requirements
Schema must support fast answers to:
- "Show all blocked R4 actions in Tier3 assets this week."
- "Which events were allowed under exceptions nearing expiry?"
- "What percentage of Class C actions required approval?"
- "Which decisions had low evidence integrity confidence?"

These queries power both SOC operations and buyer proof narratives.

---

## 10) Validation Plan

### Schema validity tests
- required fields enforced,
- enum constraints enforced,
- backward-compatible version parsing.

### Pipeline integrity tests
- evidence linkage completeness,
- hash integrity verification,
- rule trace completeness.

### Operational tests
- end-to-end incident reconstruction from event + evidence chain,
- explainability payload completeness scoring,
- performance checks under high event throughput.

Required outputs:
- schema conformance report,
- evidence linkage coverage report,
- incident replay reconstruction sample.

---

## 11) Buyer-Credibility Statement
"Our audit schema captures who did what, where, why it was allowed or blocked, and what evidence proves that decision. It is structured for both real-time operations and forensic-grade accountability."

---

## 12) Acceptance Checklist
- [x] Canonical event envelope defined.
- [x] Evidence linkage model defined.
- [x] Explainability, privacy, and retention requirements documented.
- [x] Failure modes and hardening behaviors specified.
- [x] Validation and reporting requirements documented.
- [ ] Empirical schema replay evidence attached.

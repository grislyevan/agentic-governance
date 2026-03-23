# INIT-39 — Canonical Agentic AI Event Schema (Full Deep Revision)

## Scope
Issue: **INIT-39**
Objective: define a canonical event schema that unifies detection, policy, enforcement, and audit data for agentic AI activity across heterogeneous tools and environments.

The schema must support:
- cross-tool comparability,
- policy determinism,
- explainable decisions,
- forensic reconstruction,
- benchmark/report generation.

---

## 1) Why Canonical Schema Is Critical
Without a canonical schema, each tool integration emits different semantics, causing:
- inconsistent policy behavior,
- fragile analytics,
- unreliable benchmarks,
- weak audit defensibility.

Canonical schema creates a single source of truth for what an “agentic event” means and how it should be interpreted.

---

## 2) Schema Design Principles
1. **Semantics over raw logs**
   - store normalized meaning, not only source-specific details.
2. **Deterministic policy compatibility**
   - fields required for decision logic must be explicit and typed.
3. **Evidence linkability**
   - every meaningful event must be traceable to evidence objects.
4. **Versioned evolution**
   - schema changes must preserve backward compatibility rules.
5. **Privacy-aware minimization**
   - retain what is needed for security and audit, not indiscriminate payloads.

---

## 3) Event Envelope (Top-Level)

Required top-level fields:
- `event_id` (UUID)
- `event_type` (enum)
- `event_version` (semver string)
- `observed_at` (RFC3339)
- `ingested_at` (RFC3339)
- `source_system`
- `schema_namespace`
- `trace_id`
- `session_id`

Optional but recommended:
- `parent_event_id`
- `correlation_id`

---

## 4) Canonical Field Groups

### A) Actor Context
- `actor.id`
- `actor.type` (human/service/automation)
- `actor.trust_tier`
- `actor.identity_confidence`
- `actor.org_context` (org/personal/unknown)

### B) Endpoint Context
- `endpoint.id`
- `endpoint.os`
- `endpoint.posture` (managed/unmanaged/risk score)
- `endpoint.location_context` (optional)

### C) Tool Attribution Context
- `tool.name` (if known)
- `tool.class` (A/B/C)
- `tool.version` (if known)
- `tool.attribution_confidence`
- `tool.attribution_sources[]`

### D) Action Context
- `action.type` (read/write/exec/network/repo/privileged)
- `action.risk_class` (R1-R4)
- `action.summary`
- `action.raw_ref` (pointer, not full raw payload)

### E) Target Context
- `target.type` (path/repo/host/destination/resource)
- `target.id`
- `target.scope`
- `target.sensitivity_tier`

### F) Policy Context
- `policy.decision_state` (detect/warn/approval_required/block)
- `policy.rule_id`
- `policy.rule_version`
- `policy.reason_codes[]`
- `policy.decision_confidence`

### G) Approval/Exception Context
- `approval.id` (nullable)
- `approval.scope_id` (nullable)
- `exception.id` (nullable)
- `exception.status` (nullable)

### H) Evidence Context
- `evidence.ids[]`
- `evidence.integrity_status`
- `evidence.hash_refs[]`

### I) Outcome Context
- `outcome.enforcement_result` (allowed/held/denied)
- `outcome.incident_flag`
- `outcome.incident_id` (nullable)

---

## 5) Event Type Taxonomy
Minimum event type families:
- `detection.observed`
- `attribution.updated`
- `policy.evaluated`
- `enforcement.applied`
- `approval.requested`
- `approval.resolved`
- `exception.lifecycle`
- `evidence.linked`
- `incident.flagged`

Each type may define required subfields but must preserve core envelope compatibility.

---

## 6) Required vs Optional Fields

### Required for policy-evaluable events
- actor, endpoint, tool class/confidence,
- action type/risk,
- target sensitivity,
- decision state and rule reference,
- event/evidence IDs.

### Optional with fallback behavior
- precise tool name if unresolved,
- full target identity in partial telemetry contexts,
- rich raw refs where privacy constraints apply.

Missing required fields should trigger schema conformance failure.

---

## 7) Enumeration and Typing Rules
Use strict enums for:
- event_type,
- action.type,
- action.risk_class,
- tool.class,
- decision_state,
- sensitivity_tier,
- enforcement_result.

Avoid free-text for canonical decision-critical semantics.

All numeric confidence values should define explicit range [0,1].

---

## 8) Versioning and Compatibility Strategy

### Version model
- MAJOR for breaking changes,
- MINOR for additive compatible fields,
- PATCH for documentation/validation clarifications.

### Compatibility guarantees
- consumers must tolerate unknown additive fields,
- deprecated fields require sunset period and migration guidance,
- transformations between versions must be deterministic and logged.

### Schema registry
- maintain versioned schema artifacts,
- include effective dates and migration notes.

---

## 9) Validation Rules
Schema validators must enforce:
- required field presence,
- enum value correctness,
- type correctness,
- timestamp sanity,
- confidence range constraints,
- rule/evidence linkage requirements for policy events.

Validation outcomes:
- pass,
- pass-with-warnings (optional field issues),
- fail (required field or semantic violations).

---

## 10) Privacy and Data Handling Controls

### Minimization
- store summaries and references over raw sensitive content when possible.

### Redaction
- policy-driven redaction for command content, file paths, and identities where required.

### Access control
- role-based retrieval,
- audit logging for schema data access,
- separation between raw evidence stores and normalized event views.

### Retention
- tiered retention aligned to compliance and operational needs.

---

## 11) Failure Modes and Safeguards

### Failure Mode: Schema drift between producers
Safeguard:
- central schema registry + strict producer conformance checks.

### Failure Mode: Policy engine receives semantically incomplete events
Safeguard:
- reject or downgrade events with missing decision-critical fields.

### Failure Mode: Incompatible version rollouts
Safeguard:
- staged rollout with dual-write/dual-parse validation.

### Failure Mode: Overcollection of sensitive raw payloads
Safeguard:
- minimize by default and enforce redaction policies.

---

## 12) Query and Analytics Requirements
Schema must support efficient queries for:
- decision quality by tool class,
- severity/escalation patterns,
- exception-mediated actions,
- evidence integrity failures,
- trend analysis by release.

Canonical schema should map cleanly to reporting views used by benchmark and buyer-facing outputs.

---

## 13) Validation Plan
1. implement JSON schema (and optional protobuf/Avro mapping if needed).
2. run conformance tests against representative event producers.
3. test backward compatibility parser behavior.
4. run policy replay to verify deterministic field consumption.

Required artifacts:
- canonical schema v1 file,
- conformance test results,
- migration guidance template.

---

## 14) Buyer-Credibility Statement
"Our canonical event schema standardizes how agentic AI actions are represented across tools and environments, enabling consistent policy decisions, reliable benchmarking, and evidence-linked auditability."

---

## 15) Acceptance Checklist
- [x] canonical envelope and field groups defined.
- [x] event taxonomy and typing rules specified.
- [x] required/optional semantics and validation rules documented.
- [x] versioning, privacy, and failure safeguards defined.
- [x] analytics and validation requirements specified.
- [ ] formal schema artifact and conformance run evidence attached.

# INIT-24 — Enforcement Ladder (Full Deep Revision)

## Scope
Issue: **INIT-24**
Objective: define a deterministic, confidence-aware enforcement ladder that converts detection signals into safe, explainable controls with minimal ambiguity for users, analysts, and auditors.

This ladder is the decision spine connecting:
- detection confidence,
- policy class,
- asset sensitivity,
- actor trust posture,
- final action (detect/warn/approve/block).

---

## 1) Design Principles

1. **Safety over certainty theater**
   - hard blocks should require strong evidence or explicit policy mandates.
2. **Determinism over analyst guesswork**
   - same input conditions should produce same decision.
3. **Explainability by default**
   - every enforcement outcome must include reason codes and evidence references.
4. **Progressive friction**
   - low-risk events get low-friction handling; high-risk events escalate quickly.
5. **Reversibility for uncertain contexts**
   - medium-confidence paths prefer controlled approvals before irreversible blocks.

---

## 2) Enforcement States (Canonical)

### State 0 — Observe (optional internal pre-state)
Purpose: collect/normalize telemetry before user-facing action.
Output: enriched event candidate with confidence and context scores.

### State 1 — Detect
Purpose: record and monitor without interrupting user workflow.
Use when:
- confidence is low,
- asset sensitivity is low,
- no explicit policy violation.

Required output:
- event captured with class, confidence, context, and trace metadata.

### State 2 — Warn
Purpose: notify user and create explicit policy awareness.
Use when:
- confidence is medium,
- context indicates policy drift,
- risk is non-trivial but not yet block-threshold.

Required output:
- warning reason,
- remediation guidance,
- acknowledgment/log marker where supported.

### State 3 — Approval Required
Purpose: hold potentially risky action pending authorized decision.
Use when:
- action touches sensitive assets,
- privilege-impacting operations are requested,
- confidence is medium/high but block certainty is not absolute.

Required output:
- approval ticket with scope + expiration + approver,
- explicit action envelope (what is allowed, where, for how long).

### State 4 — Block
Purpose: deny action to enforce policy boundaries.
Use when:
- high-confidence prohibited behavior,
- repeated bypass attempts,
- explicit disallowed command/scope policy hit.

Required output:
- deny reason code,
- evidence trace,
- incident routing metadata if severity threshold met.

---

## 3) Decision Inputs (Scoring Dimensions)

### A) Detection Confidence
- Low (<0.45)
- Medium (0.45–0.74)
- High (>=0.75)

### B) Asset Sensitivity Tier
- Tier 0: non-sensitive
- Tier 1: business-sensitive
- Tier 2: high-value engineering/security assets
- Tier 3: crown-jewel/regulated assets

### C) Actor Trust Tier
- T0 unmanaged/unknown
- T1 known user on partially managed endpoint
- T2 managed identity + managed endpoint
- T3 privileged/admin actor

### D) Action Risk Class
- R1 read-only low impact
- R2 write/modify scoped
- R3 broad write or outbound transfer
- R4 privileged/system-impacting or policy-prohibited pattern

### E) Historical Context
- prior warnings in session,
- active exceptions,
- repeat policy violations.

---

## 4) Deterministic Escalation Rules (Core)

Rule examples:
1. Low confidence + Tier0/1 asset + R1 action => Detect
2. Medium confidence + Tier1/2 + R2 => Warn
3. Medium confidence + Tier2/3 + R3 => Approval Required
4. High confidence + disallowed R4 => Block
5. Any confidence + explicit deny policy + Tier3 => Block
6. Repeated Warn in same session (N threshold) => step-up to Approval Required
7. Approval denied + retry same action => Block

Implementation requirement: each rule has stable `rule_id`, version, and explainability payload.

---

## 5) Explainability Contract
Every decision must emit:
- `decision_state` (Detect/Warn/Approval/Block)
- `rule_id` and `rule_version`
- top contributing signals
- penalties/uncertainty notes
- target asset + action summary
- actor and context snapshot
- evidence IDs

Without this, enforcement is not enterprise-defensible.

---

## 6) Approval Workflow Semantics

Approval object fields:
- request_id
- requester
- requested_action
- target_scope (paths/repos/resources)
- validity window
- approver identity
- compensating controls
- revocation capability

Rules:
- approvals are not global; scope-limited only.
- expired approvals auto-revoke.
- approval decisions are immutable events.
- critical assets can require dual approval.

---

## 7) Failure Modes and Safeguards

### Failure Mode 1: Overblocking from noisy signals
Safeguard:
- confidence penalties,
- require corroborating layers before Block unless explicit deny policy applies.

### Failure Mode 2: Underblocking for high-risk autonomous actions
Safeguard:
- Class C stricter default escalation,
- lower threshold for Approval/Block on privileged actions.

### Failure Mode 3: Policy contradiction across sources
Safeguard:
- precedence model: explicit deny > scoped approval > default allow.
- conflict resolver emits policy-conflict event.

### Failure Mode 4: Telemetry partial loss
Safeguard:
- downgrade confidence,
- route to Warn/Approval instead of silent pass.

---

## 8) Session-Level Escalation Behavior
Ladder should be stateful within session context:
- first medium-risk event => Warn
- repeated medium-risk events => Approval Required
- repeated denied attempts => Block + incident flag

This prevents repetitive low-grade abuse while avoiding immediate harsh enforcement for first uncertain events.

---

## 9) Integration Requirements
Ladder engine must integrate with:
- policy class model (INIT-23),
- risky action controls (INIT-25),
- audit schema (INIT-26),
- exception workflow (INIT-27),
- metrics pipeline (INIT-30).

Expected outputs feed:
- analyst console,
- SIEM export,
- buyer-facing benchmark/report pipeline.

---

## 10) Validation Plan

### Positive tests
1. deterministic decisions for known input vectors.
2. correct step-up behavior across repeated events.
3. approval scope enforcement and expiry behavior.

### Adversarial tests
1. attempt replay after denied approval.
2. attempt action outside approved scope.
3. partial telemetry scenarios to verify safe fallback.

### Evidence required
- rule evaluation traces,
- decision distribution by confidence tier,
- false-positive/false-block review sample,
- approval lifecycle logs.

---

## 11) Buyer-Credibility Statement
"Our enforcement ladder is deterministic, confidence-aware, and explainable. We do not rely on opaque one-shot blocks; we escalate responsibly from detect to block based on risk, sensitivity, and evidence quality."

---

## 12) Acceptance Checklist
- [x] Ladder states and semantics fully specified.
- [x] Decision inputs and deterministic rules documented.
- [x] Explainability contract defined.
- [x] Approval model and failure safeguards documented.
- [x] Validation plan and evidence requirements defined.
- [ ] Replay evidence attached.

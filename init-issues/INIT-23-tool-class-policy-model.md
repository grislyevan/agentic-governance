# INIT-23 — Tool Class Policy Model (Full Deep Revision)

## Scope
Issue: **INIT-23**
Objective: build a rigorous, enforcement-ready policy model that governs agentic AI tools by **operational behavior class** rather than product name, while preserving explainability, auditability, and buyer credibility.

This document is intended to function as:
1. implementation guidance for policy engine design,
2. security architecture reference,
3. buyer-facing proof that governance is robust against tool churn and evasions.

---

## 1) Why Class-Based Policy Is Required
Name-based controls fail quickly in real environments because:
- tools are renamed, forked, wrapped, or embedded,
- behavior overlaps across products,
- backend endpoints are often shared,
- enterprise environments introduce proxies, containers, and remote dev contexts.

A class-based model remains stable by governing **what the tool can do** and **where it does it**, not just what it is called.

Design principle:
> "Classify by capability + risk surface + execution context; then enforce with confidence-scored controls."

---

## 2) Policy Class Taxonomy (Canonical)

### Class A — SaaS Copilots / Assistive IDE Features
Representative tools: Copilot/Cursor cloud-assist patterns.

**Core behavior profile**
- suggestion/chat assistance,
- typically bounded to IDE context,
- lower direct autonomous command execution by default (but may escalate with integrated actions).

**Primary risks**
- code/data leakage to unsanctioned accounts,
- sensitive context exposure,
- uncontrolled usage in restricted repositories.

**Default controls**
- org-account requirement,
- repo/path sensitivity restrictions,
- DLP content controls,
- logging + explainable event capture.

**Default enforcement posture**
- Detect/Warn baseline,
- Approval Required for sensitive scope crossings,
- Block for explicit account/scope violations.

---

### Class B — Local Model Runtimes
Representative tools: Ollama, LM Studio.

**Core behavior profile**
- local inference and model storage,
- localhost/service-based operation,
- potentially minimal external telemetry during inference.

**Primary risks**
- perimeter-control blind spots,
- unapproved local models,
- sensitive data processed locally outside expected controls.

**Default controls**
- model allowlist + source/checksum policy,
- endpoint posture requirements,
- local data boundary controls,
- model inventory and drift monitoring.

**Default enforcement posture**
- Detect for first-seen runtime/model,
- Warn for unapproved model source or policy drift,
- Approval Required for sensitive data scope,
- Block for disallowed model use in restricted contexts.

---

### Class C — Autonomous Executors / Agentic Operators
Representative tools: Open Interpreter, Aider, GPT-Pilot, Cline tool-calling modes.

**Core behavior profile**
- command execution,
- broad file/process/network interaction,
- iterative autonomous loops (plan → execute → revise).

**Primary risks**
- privileged or destructive command paths,
- rapid high-fan-out code/data mutation,
- boundary crossing and exfiltration behavior.

**Default controls**
- command class allow/deny policies,
- privileged action step-up approvals,
- protected path restrictions,
- immutable audit evidence requirements,
- branch/protected-repo governance integration.

**Default enforcement posture**
- Warn/Approval Required sooner than Class A/B,
- Block thresholds stricter for high-sensitivity targets.

---

## 3) Classification Inputs and Resolution Logic
Classification is derived from multi-signal evidence and should be explicit.

### Input dimensions
1. **Execution capability** (assistive vs local inference vs autonomous command execution)
2. **Action surface** (read/write/exec/network/privilege)
3. **Autonomy level** (suggestion-only vs tool-calling loop)
4. **Scope of impact** (single file vs repo-wide/system-wide)
5. **Context sensitivity** (asset tier, identity trust tier, endpoint posture)

### Resolution policy
- If signals indicate multiple classes, choose **highest-risk applicable class**.
- If class confidence is low, apply conservative controls with lower-impact enforcement (Warn/Approval) until confidence improves.
- Class assignment must include reason codes for analyst traceability.

---

## 4) Confidence-Coupled Class Policy Matrix

### Confidence bands
- High: >=0.75
- Medium: 0.45–0.74
- Low: <0.45

### Decision matrix (simplified)
- **Class A + Low confidence + Low sensitivity** → Detect
- **Class A + Medium confidence + Medium sensitivity** → Warn
- **Class A + High confidence + High sensitivity** → Approval Required/Block by policy

- **Class B + Medium confidence + Medium sensitivity** → Warn + model/source verification
- **Class B + High confidence + High sensitivity** → Approval Required
- **Class B + High confidence + restricted context violation** → Block

- **Class C + Medium confidence + sensitive action** → Approval Required
- **Class C + High confidence + disallowed command/scope** → Block
- **Class C + repeated warning bypass patterns** → Block escalation

Implementation note: every row must map to deterministic rule IDs and traceable evidence references.

---

## 5) Enforcement Semantics by Class

### Detect
- capture event with class assignment and confidence,
- enrich with actor/asset context,
- no user disruption.

### Warn
- notify user with policy reason and remediation path,
- record acknowledgment where platform supports it,
- increase session scrutiny.

### Approval Required
- hold action pending approver decision,
- approval token must encode scope + expiration + owner,
- auto-expire with fallback to baseline controls.

### Block
- deny action and provide explicit rationale,
- emit high-priority audit event,
- optionally trigger incident workflow based on severity.

---

## 6) Exception Design (Class-Aware)
Exceptions are often where governance fails if poorly designed.

Required exception fields:
- class,
- requester,
- approver,
- scope (tool/action/asset),
- expiration,
- justification,
- compensating controls,
- evidence references.

Rules:
- exceptions cannot silently widen across classes,
- Class C exceptions require stricter approval tier,
- expired exceptions automatically revert to baseline policy,
- every exception is reportable for compliance and periodic review.

---

## 7) Policy Drift and Change Management
A class model still degrades without governance hygiene.

Drift vectors:
- stale allowlists,
- emergency exceptions never retired,
- mismatch between stated and enforced class mappings,
- tool capability expansion without policy updates.

Controls:
- versioned policy artifacts,
- change approval workflow,
- replay validation before release,
- rollback path for broken policy updates.

---

## 8) Failure Modes and Hardening Strategy

### Failure Mode 1: Misclassification due to partial telemetry
Mitigation:
- confidence penalties,
- conservative step-up controls,
- explicit low-confidence tagging.

### Failure Mode 2: Overblocking due to coarse class rules
Mitigation:
- add sensitivity + context gates,
- use Approval Required before Block in medium-confidence scenarios.

### Failure Mode 3: Underblocking in autonomous execution paths
Mitigation:
- Class C default strictness,
- command class deny policies,
- privilege-aware escalation.

### Failure Mode 4: Analyst confusion from opaque decisions
Mitigation:
- mandatory reason codes,
- evidence-linked decision trace,
- per-event explainability payload.

---

## 9) Data Model Requirements
Minimum policy event schema must include:
- event id, timestamp,
- actor/endpoint identity confidence,
- tool class + class confidence,
- attempted action summary,
- asset sensitivity,
- decision and rule IDs,
- evidence reference IDs,
- exception linkage (if any).

Without this, policy cannot be audited or defended in enterprise review.

---

## 10) Validation Plan (for this model)

### Positive validation
1. representative Class A/B/C events classify correctly under baseline telemetry.
2. decision matrix returns expected enforcement outcomes.
3. explainability payloads contain sufficient analyst detail.

### Adversarial validation
1. renamed/forked tool retains correct class assignment.
2. partial telemetry yields confidence downgrade + safe enforcement behavior.
3. exception misuse attempts are denied or constrained.

### Evidence outputs required
- classification confusion matrix,
- enforcement decision audit samples,
- exception lifecycle traces,
- residual risk statements.

---

## 11) Buyer-Facing Credibility Statement
"Our governance model classifies AI tools by behavior and risk surface, not just brand names. That makes controls resilient to forks, wrappers, and endpoint variability. Every enforcement decision is confidence-scored, explainable, and auditable."

---

## 12) Acceptance Checklist
- [x] Class taxonomy defined with concrete control bundles.
- [x] Classification inputs and resolution logic documented.
- [x] Confidence-coupled decision matrix defined.
- [x] Enforcement semantics and exception model specified.
- [x] Failure modes and hardening strategy documented.
- [x] Validation plan and required evidence outputs defined.
- [ ] Empirical replay evidence attached.

# INIT-37 — Demo Script + Evidence Pack (Full Deep Revision)

## Scope
Issue: **INIT-37**
Objective: define a repeatable demo and evidence package that proves product capability under realistic conditions, with traceable artifacts that withstand technical buyer scrutiny.

This deliverable must support both:
- short executive demos,
- deep technical validation sessions.

---

## 1) Why Demo + Evidence Is a Distinct Workstream
A polished demo without evidence looks like theater.
Evidence without narrative fails to persuade.

This workstream combines both:
- a deterministic story flow,
- and verifiable proof points linked to underlying telemetry, policy decisions, and audit records.

---

## 2) Demo Objectives
The demo must prove, in order:
1. detection of AI-agentic activity,
2. confidence-aware policy decisioning,
3. enforcement behavior (warn/approve/block),
4. audit and explainability output,
5. known limitation transparency.

If any step is missing, the demo is incomplete.

---

## 3) Demo Track Variants

### Track A — 10-Minute Executive Demo
Goal: business confidence and control narrative.

Sequence:
1. one risky AI action detected,
2. step-up enforcement shown,
3. audit trail and summary dashboard shown,
4. known-gap transparency statement,
5. pilot success criteria call-to-action.

### Track B — 30-Minute Technical Deep Demo
Goal: architecture and control credibility.

Sequence:
1. signal-layer visibility walkthrough,
2. confidence and rule trace details,
3. approval/exception behavior,
4. evasion scenario handling,
5. evidence package retrieval and validation.

Both tracks must use the same underlying validated scenario data.

---

## 4) Canonical Demo Scenario Set

### Scenario 1: Baseline allowed behavior
- approved tool in approved scope,
- demonstrates detect/allow with audit capture.

### Scenario 2: Policy drift warning
- medium-confidence risky context,
- demonstrates Warn behavior and user guidance.

### Scenario 3: Approval-required sensitive action
- sensitive repo/path access,
- demonstrates hold-for-approval and scoped token behavior.

### Scenario 4: Hard block prohibited action
- high-confidence disallowed action,
- demonstrates deterministic block + reason codes.

### Scenario 5: Evasion-resilience check
- known evasion tactic,
- demonstrates confidence penalty and safe fallback.

Optional Scenario 6:
- known limitation scenario with transparent caveat handling.

---

## 5) Demo Script Structure
Each scenario script block should include:
- `scenario_id`
- objective
- preconditions
- operator steps (exact)
- expected observables
- expected policy decision
- expected evidence outputs
- fallback notes if scenario deviates

Script must avoid improvisational dependencies whenever possible.

---

## 6) Evidence Pack Specification

### Core package contents
1. **Run manifest**
   - version, environment, scenario IDs, timestamps.
2. **Event timeline export**
   - ordered detection/policy/enforcement events.
3. **Decision trace bundle**
   - rule IDs, confidence rationale, reason codes.
4. **Evidence index**
   - process/file/network/artifact references with hashes.
5. **Scenario result summary**
   - expected vs observed outcomes.
6. **Known limitations snapshot**
   - relevant caveats for demonstrated scope.

### Packaging format
- machine-readable bundle + human-readable summary.
- immutable manifest hash for integrity.

---

## 7) Demo Readiness Criteria
A scenario is “demo-ready” only if:
- replay has passed within tolerance,
- expected decision outcomes are stable,
- evidence references resolve and pass integrity checks,
- script timing fits target track duration,
- caveat text is current.

No live demo should rely on unvalidated scenario variants.

---

## 8) Presenter Guidance

### Do
- narrate decisions with evidence references,
- explain confidence and caveats clearly,
- show both strengths and current limits.

### Don’t
- claim universal coverage,
- hide partial-visibility contexts,
- improvise unsupported technical claims.

Presenter should always map statements back to report/evidence IDs.

---

## 9) Objection Handling in Demo Context
Prepare scripted responses for:
- "How do you handle local models?"
- "What about renamed/forked tools?"
- "How do you avoid false blocks?"
- "Can we audit every decision?"
- "What are your current blind spots?"

Each response must have:
- capability statement,
- caveat,
- mitigation path.

---

## 10) Failure Modes and Safeguards

### Failure Mode: Demo passes but evidence pack incomplete
Safeguard:
- pre-demo evidence completeness gate.

### Failure Mode: Scenario drift breaks live reliability
Safeguard:
- require recent replay validation and environment checksum.

### Failure Mode: Presenter overstates capability
Safeguard:
- approved script language and claim-lint checklist.

### Failure Mode: Technical audience cannot verify claims
Safeguard:
- include direct evidence retrieval path and rule trace references.

---

## 11) Versioning and Governance
Each demo/evidence package must include:
- package version,
- source release version,
- input run IDs,
- approver signatures (security + product),
- expiration/revalidation date.

Retire stale demo packages automatically when source validation ages out.

---

## 12) Validation Plan

### Functional validation
- script executes within planned runtime,
- expected outputs appear at each checkpoint.

### Integrity validation
- all evidence links resolve,
- manifest hash verification succeeds.

### Communication validation
- message clarity tested with executive and technical audiences.

### Regression validation
- rerun demo scenarios on release candidate builds.

Required artifacts:
- approved demo script (10-min and 30-min variants),
- evidence pack template,
- completed sample evidence pack.

---

## 13) Buyer-Credibility Statement
"Our demos are replay-backed and evidence-linked. What we show live maps to validated scenarios, rule-traceable decisions, and auditable artifacts—so buyers can verify capability instead of relying on polished narrative alone."

---

## 14) Acceptance Checklist
- [x] Demo objectives, tracks, and canonical scenarios defined.
- [x] Script structure and evidence pack schema specified.
- [x] Readiness criteria, presenter guardrails, and objection handling documented.
- [x] Failure safeguards and version governance defined.
- [x] Validation workflow and required artifacts listed.
- [ ] Final approved demo script + evidence package produced.

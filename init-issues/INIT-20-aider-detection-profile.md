# INIT-20 — Aider Detection Profile (Deep Revision)

## Scope
Tool: **Aider**
Class: **CLI coding assistant with direct repository modification workflows**
Primary risk posture: **Medium-High** (high-impact code changes + git operations at speed)

Objective: provide a high-fidelity detection and governance profile for Aider that separates normal developer git activity from AI-assisted repo mutation behavior and supports enforceable policy outcomes.

---

## 1) Why Aider Needs Its Own Detection Logic
Aider is not just another terminal chatbot. Its value proposition is:
- repo-aware editing,
- targeted file mutation,
- fast iterative patch generation,
- tight git integration.

This means threat and governance focus should be on **change control integrity**:
- where changes occurred,
- how quickly and broadly they propagated,
- whether workflow guardrails (review/branch policy) were respected.

---

## 2) Risk-Relevant Activity Surface
Aider can influence:
- source files across one or many directories,
- commit creation and commit-message quality,
- branch and PR hygiene,
- downstream CI behavior through generated changes.

It can accelerate delivery, but also accelerate mistakes, policy violations, or unreviewed risky diffs if unmanaged.

---

## 3) Detection Model by Telemetry Layer

### A) Process / Execution Telemetry
**High-value detections**
- Aider CLI invocation from terminal/scripting environments.
- Parent-child lineage linking terminal → aider → git/tool subprocesses.
- Session loops showing repeated prompt-edit-diff cycles.

**Collection requirements**
- process path/hash, command-line digest, parent lineage
- session duration and command cadence
- child execution trace (git, shell helpers, formatting/test tools)

**What works**
- Process lineage strongly differentiates Aider sessions from generic git automation.

**What fails**
- Static binary-name matching without lineage (aliases/wrappers bypass).

---

### B) File / Artifact Telemetry
**High-value detections**
- concentrated source-file edit bursts in narrow time windows.
- repeated patch/rewrite behavior across related modules.
- temporary/session artifacts where present.

**Collection requirements**
- file fan-out count per session
- churn intensity metrics (LOC touched, file type distribution)
- timing relationship to aider process windows

**What works**
- File mutation shape is strong corroboration for AI-assisted repo workflows.

**What fails**
- Treating raw file-change volume as definitive (humans/scripts can also spike).

---

### C) Network Telemetry
**High-value detections**
- model endpoint traffic aligned with active aider sessions.
- burst cadence around prompt/diff iteration windows.

**Limitations**
- endpoint overlap with other AI tools reduces standalone attribution reliability.
- network-only data does not prove repo mutation provenance.

**Confidence guidance**
- Medium as corroborative signal only.

---

### D) Identity / Access Telemetry
**High-value detections**
- OS user session + git author identity correlation.
- credential source and repo ownership context.
- branch protection applicability to actor/repo.

**Policy checks**
- was actor authorized for target repo/branch?
- were review requirements expected but bypassed?
- is commit identity compliant (signed/verified where required)?

**Confidence guidance**
- High when identity and repo policy context are complete.

---

### E) Behavioral Telemetry
**High-value detections**
- prompt-edit-commit loops with short latency.
- rapid iterative diff generation before commit.
- repeated staging/unstaging/refactor cycles suggestive of assistant-led edits.

**High-risk markers**
- broad file fan-out in critical services,
- direct writes to protected branches,
- high-velocity commits with weak review linkage.

**What works**
- Behavioral sequencing plus repo controls gives strong governance signal quality.

---

## 4) Detection Confidence Rubric (Operational)

### High (>=0.75)
Requires:
- aider process lineage,
- repo mutation behavior pattern,
- identity + branch/repo policy context.

Actionability:
- approval/block decisions in sensitive repos,
- incident-grade audit readiness.

### Medium (0.45–0.74)
Typical conditions:
- two aligned layers but incomplete identity/policy context.

Actionability:
- warn + step-up review gate.

### Low (<0.45)
Typical conditions:
- isolated process or network indicators without repo context.

Actionability:
- detect-only telemetry enrichment.

---

## 5) What Works Reliably (Today)
1. Process lineage + git/repo behavior correlation.
2. Identity-aware branch policy enforcement.
3. Audit-grade reconstruction using process + file + git event timelines.

---

## 6) What Does Not Work Reliably
1. Git-only heuristics without process attribution.
2. Name-based signatures in aliased/wrapped environments.
3. Network-only classification of Aider vs other assistants.

---

## 7) Evasion Paths and Coverage Gaps
1. wrapper scripts invoking aider indirectly.
2. renamed aliases and shell functions.
3. remote dev containers with reduced host visibility.
4. post-processing scripts that obscure original edit source.

Mitigations:
- enforce lineage requirements for high-confidence decisions,
- tie governance to branch protection and review workflows,
- apply stricter controls where telemetry visibility is degraded.

---

## 8) Governance Mapping (Aider-Specific)

### Detect
- first-seen aider usage in repository.

### Warn
- medium-confidence AI-assisted edits in sensitive components.

### Approval Required
- protected branch targets,
- critical service directories,
- high fan-out code changes exceeding policy thresholds.

### Block
- direct protected-branch writes without required controls,
- repeated bypass patterns,
- high-confidence policy violations tied to AI-assisted session evidence.

---

## 9) Validation Plan (Detailed)

### Positive Scenarios (minimum 3)
1. normal aider-assisted single-module change + compliant PR flow.
2. multi-file refactor with expected telemetry + review gate adherence.
3. aider session with formatting/tests and policy-compliant commit path.

### Evasion/Failure Scenarios (minimum 2)
1. alias/wrapper invocation path to mask binary attribution.
2. devcontainer-based execution with reduced endpoint visibility.

### Recommended adversarial scenarios
3. attempt direct push to protected branch.
4. broad critical-path rewrite without review metadata.

### Required outputs
- confidence and rationale,
- process tree + repo diff evidence,
- policy decision trace,
- residual risk statement.

---

## 10) Data Quality Requirements
Minimum fields:
- actor + host + session ID,
- process lineage,
- repo/branch targets,
- diff fan-out and churn metadata,
- policy state (expected vs observed),
- evidence references with timestamps.

Without these, governance claims are hard to defend in customer security reviews.

---

## 11) Buyer-Credibility Positioning
"Aider is governed as a high-velocity code mutation workflow, not just a chat tool. We correlate execution lineage, repository behavior, and branch policy context to enforce confidence-scored controls and preserve auditability."

---

## 12) Acceptance Checklist
- [x] Aider-specific five-layer profile documented.
- [x] Repo mutation and branch-policy risk model explicit.
- [x] Confidence rubric tied to actionable controls.
- [x] Evasion paths and mitigations detailed.
- [x] Validation plan with required evidence outputs defined.
- [ ] Empirical lab evidence attached (pending runs).

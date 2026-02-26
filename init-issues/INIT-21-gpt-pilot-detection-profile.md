# INIT-21 — GPT-Pilot Detection Profile (Deep Revision)

## Scope
Tool: **GPT-Pilot**
Class: **Autonomous project-generation/orchestration tool**
Primary risk posture: **High** (large-scale code generation and workflow automation)

Objective: define a deep, tool-specific detection/governance profile for GPT-Pilot with emphasis on high-fan-out generation behavior, orchestration traceability, and policy-safe execution boundaries.

---

## 1) Why GPT-Pilot Requires Distinct Controls
GPT-Pilot differs from incremental assistants because it often drives:
- project scaffolding from minimal prompts,
- iterative generation across many files/modules,
- scripted execution loops (generate, run, revise, repeat).

Core risk is not just model usage—it is **scope and speed of automated change**.

---

## 2) Risk-Relevant Activity Surface
GPT-Pilot can impact:
- repository structure creation and overwrite,
- build/test/dependency flows,
- environment configuration files,
- downstream deployment behavior if generated changes are promoted.

Security concern: broad code generation can bypass normal review intuition if not governed with strict boundaries.

---

## 3) Detection Model by Telemetry Layer

### A) Process / Execution Telemetry
**High-value detections**
- orchestrator runtime invocation (python/node/tool-specific launcher patterns).
- long-lived parent process driving iterative child command execution.
- repeated generation-run-correction cycles visible in process timeline.

**Collection requirements**
- process lineage and invocation context
- loop timing and execution cadence metrics
- child process categories (build/test/package/file ops)

**What works**
- Orchestration process shape strongly differentiates GPT-Pilot from ad hoc scripting.

**What fails**
- static binary/signature assumptions across forks/custom launchers.

---

### B) File / Artifact Telemetry
**High-value detections**
- sudden project tree creation from sparse baseline.
- high fan-out file generation bursts in short windows.
- scaffold/template residues and run-state artifacts.

**Collection requirements**
- file creation vs modification ratio,
- module spread and directory coverage,
- overwrite indicators for existing assets.

**What works**
- Artifact fan-out provides strong evidence of autonomous generation behavior.

**What fails**
- path-only heuristics without temporal behavior context.

---

### C) Network Telemetry
**High-value detections**
- API burst cycles aligned with generation phases.
- dependency download/network actions triggered by generated setup flows.

**Limitations**
- endpoint overlap with other tools lowers standalone attribution confidence.
- local/self-hosted model backends may reduce external signal value.

**Confidence guidance**
- Medium standalone; primarily corroborative.

---

### D) Identity / Access Telemetry
**High-value detections**
- actor/session tied to orchestrator process and workspace target.
- endpoint trust tier and credential source context.
- policy scope for allowed generation domains (repo/path/project).

**Policy checks**
- is actor approved for high-fan-out generation in this workspace?
- are generation targets inside allowed boundaries?
- is environment managed and auditable?

---

### E) Behavioral Telemetry
**High-value detections**
- generate-validate-regenerate loops.
- broad write patterns with high file churn velocity.
- build/test command chains immediately following generation passes.

**High-risk markers**
- mass overwrite of pre-existing code,
- generation in protected monorepo roots,
- repeated failed iterations with escalating scope.

**What works**
- Behavior sequencing + file fan-out metrics are strongest indicators of GPT-Pilot risk posture.

---

## 4) Detection Confidence Rubric (Operational)

### High (>=0.75)
Requires:
- orchestrator process lineage,
- high-fan-out generation behavior,
- artifact evidence + identity/context completeness.

Actionability:
- enforce approval/block for sensitive scopes,
- trigger high-priority review workflows.

### Medium (0.45–0.74)
Typical conditions:
- two layers align but identity/scope context partially missing.

Actionability:
- warn + scoped execution restriction.

### Low (<0.45)
Typical conditions:
- isolated signal without orchestration trace.

Actionability:
- detect-only and telemetry enrichment.

---

## 5) What Works Reliably (Today)
1. Process orchestration + file fan-out correlation.
2. Scope-aware governance boundaries (repo/path project limits).
3. Timeline reconstruction of autonomous generation cycles.

---

## 6) What Does Not Work Reliably
1. Signature-only detection in fork-heavy ecosystem patterns.
2. network-only attribution for generation behavior.
3. static artifact assumptions without sequencing context.

---

## 7) Evasion Paths and Coverage Gaps
1. custom forks and renamed launch wrappers.
2. containerized isolated runs with partial endpoint telemetry.
3. artifact relocation/cleanup post-run.
4. shared model gateways reducing direct attribution.

Mitigations:
- enforce orchestration-trace requirements,
- constrain generation scope by policy,
- preserve hashed evidence snapshots for large generation runs.

---

## 8) Governance Mapping (GPT-Pilot-Specific)

### Detect
- first-seen autonomous generation patterns.

### Warn
- medium-confidence broad generation in non-critical but unmanaged contexts.

### Approval Required
- high-fan-out generation in sensitive repositories,
- overwrite risk in established codebases,
- environment/config generation touching protected paths.

### Block
- high-confidence disallowed autonomous overwrite/exfil-risk behavior,
- repeated scope-boundary violations.

---

## 9) Validation Plan (Detailed)

### Positive Scenarios (minimum 3)
1. sanctioned greenfield scaffold generation in approved workspace.
2. iterative generation + test loop with policy-compliant boundaries.
3. controlled module expansion with expected telemetry coherence.

### Evasion/Failure Scenarios (minimum 2)
1. forked/renamed launcher path.
2. containerized execution with reduced host visibility.

### Recommended adversarial scenarios
3. attempted generation into protected monorepo directories.
4. mass overwrite against pre-existing critical modules.

### Required outputs
- confidence and rationale,
- orchestration timeline,
- file fan-out and overwrite metrics,
- policy decision trace,
- residual risk statement.

---

## 10) Data Quality Requirements
Minimum fields:
- actor + host + session ID,
- orchestrator lineage,
- target repo/path scope,
- file generation/overwrite metrics,
- policy expectation vs observed action,
- evidence references.

These are required for defensible customer-facing claims.

---

## 11) Buyer-Credibility Positioning
"GPT-Pilot is governed as an autonomous generation system, not a simple assistant. We correlate orchestration lineage, fan-out behavior, and scope policy context to enforce confidence-scored controls and preserve explainable audit trails."

---

## 12) Acceptance Checklist
- [x] GPT-Pilot-specific five-layer profile documented.
- [x] High-fan-out generation risk model explicit.
- [x] Confidence rubric tied to enforceable controls.
- [x] Evasion paths and mitigations detailed.
- [x] Validation scenarios and evidence requirements defined.
- [ ] Empirical lab evidence attached (pending runs).

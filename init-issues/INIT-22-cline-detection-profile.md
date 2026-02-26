# INIT-22 — Cline Detection Profile (Deep Revision)

## Scope
Tool: **Cline** (agentic IDE extension with tool-calling workflows)
Class: **IDE-embedded autonomous assistant**
Primary risk posture: **High** in sensitive repos due to external tool calls + broad context access.

Objective: deliver an enforcement-ready detection profile for Cline that handles extension forks, backend flexibility, and tool-calling behavior with confidence-scored attribution.

---

## 1) Tool Anatomy and Risk Signature
Cline is extension-native and can:
- read broad code context,
- propose/perform multi-file edits,
- invoke tools/commands depending on integration mode,
- route to different model backends.

The key risk is **agentic tool use inside trusted developer environments** where actions can look like normal IDE activity unless sequence-aware telemetry is used.

---

## 2) Detection Model by Telemetry Layer

### A) Process / Execution
High-value detections:
- IDE + extension host process activity tied to Cline interactions.
- Parent-child lineage from extension host to shell/tool subprocesses.
- sustained session patterns with iterative action loops.

What works:
- execution lineage + extension context correlation.

What fails:
- app-name-only process signatures.

### B) File / Artifact
High-value detections:
- extension manifests/version fingerprints,
- workspace config/state files indicating tool-calling settings,
- session-window file fan-out tied to assistant actions.

What works:
- config + artifact evidence for attribution and governance intent.

What fails:
- fixed-path assumptions with forked/portable builds.

### C) Network
High-value detections:
- backend model endpoint traffic aligned with extension activity,
- tool-call side traffic where external integrations are used.

What works:
- corroboration and timing reconstruction.

What fails:
- network-only attribution in shared gateway environments.

### D) Identity / Access
High-value detections:
- actor-session mapping to IDE process and extension use,
- backend credential/account ownership context,
- managed endpoint posture.

What works:
- policy enforceability when identity + repo scope are present.

What fails:
- weak identity hygiene on shared/dev endpoints.

### E) Behavior
High-value detections:
- prompt→plan→edit/tool-call loop sequencing,
- broad context reads followed by focused multi-file writes,
- tool execution patterns near sensitive paths.

High-risk markers:
- external tool calls from sensitive repositories,
- repeated boundary-crossing actions after warnings,
- high-volume changes without review linkage.

---

## 3) Confidence Rubric
- **High (>=0.75):** extension/process lineage + behavior sequence + repo/identity context.
- **Medium (0.45–0.74):** two aligned layers without complete backend/identity certainty.
- **Low (<0.45):** isolated indicator only.

---

## 4) What Works / What Fails / Gaps

### Works reliably
1. Extension host lineage + behavior sequencing.
2. Config-state analysis for backend/tool-call policy context.
3. Scope-aware governance in managed repos.

### Fails reliably
1. Domain-only detection where backends vary.
2. Static extension-name signatures for forked builds.
3. Single-signal enforcement without sequence context.

### Known gaps/evasions
1. forked/renamed extension builds,
2. custom backend routing through shared proxies,
3. remote/containerized dev reducing host visibility,
4. config drift to unsanctioned tool-call settings.

Mitigations:
- config drift monitoring,
- multi-signal confidence requirements for hard blocks,
- stricter defaults in low-visibility environments.

---

## 5) Governance Mapping (Cline-Specific)
- **Detect:** first-seen Cline use or config drift event.
- **Warn:** medium-confidence tool-calling in sensitive scope.
- **Approval Required:** external tool calls, privileged commands, or sensitive path targets.
- **Block:** high-confidence policy breach (disallowed backend/tool-call behavior with strong evidence chain).

---

## 6) Validation Plan
Positive scenarios (>=3):
1. approved backend + normal code-assist workflow,
2. multi-file edit with expected telemetry coherence,
3. controlled tool-calling in approved scope.

Evasion/failure scenarios (>=2):
1. forked/renamed extension build path,
2. shared proxy route obscuring backend attribution.

Required outputs:
- confidence and rationale,
- process/extension timeline,
- config snapshot evidence,
- policy decision trace,
- residual risk statement.

---

## 7) Acceptance Checklist
- [x] Cline-specific five-layer profile documented.
- [x] Tool-calling risk model and governance mapping explicit.
- [x] Confidence rubric tied to enforceable actions.
- [x] Evasion paths and mitigation strategy documented.
- [ ] Empirical evidence artifacts attached (pending lab execution).

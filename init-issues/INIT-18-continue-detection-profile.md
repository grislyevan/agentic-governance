# INIT-18 — Continue Detection Profile

## Scope
Tool: **Continue** (IDE extension framework that can route to many model backends)
Goal: define detection/governance that remains reliable even when backend models/endpoints are user-configurable.

---

## 1) Tool Anatomy
Continue is extension-first and backend-agnostic:
- runs inside IDE extension host context,
- supports multiple providers (cloud/self-hosted/local),
- behavior depends heavily on user config.

Implication: detection must combine extension identity + config target analysis + behavior, not endpoint names alone.

---

## 2) 5-Layer Detection Model

### A) Process / Execution
Reliable indicators:
- IDE process + extension host activity associated with Continue.
- Extension-triggered actions leading to file edits/terminal usage.
- Session patterns where prompts and code-change bursts are temporally coupled.

Collection targets:
- IDE/extension host process lineage,
- child-process invocations from extension workflows,
- runtime session durations.

Confidence:
- Medium with process presence only.
- High with extension-host + behavior correlation.

---

### B) File / Artifact
Reliable indicators:
- Continue extension install manifests and version data.
- Continue configuration files specifying model backends/providers.
- Workspace/local cache artifacts showing interaction windows.

Key challenge:
- backend target flexibility means artifacts are central for attribution.

Confidence:
- High for tool presence and configuration intent.
- Medium for active usage unless behavior/process corroborate.

---

### C) Network
Reliable indicators:
- outbound calls to configured model targets (cloud or self-hosted).
- traffic bursts synchronized with extension activity.

Limitations:
- endpoint targets vary per user config; domain allowlists are brittle.
- local/self-hosted endpoints may resemble normal internal traffic.

Confidence:
- Medium network-only.
- High when tied to extension config + process lineage.

---

### D) Identity / Access
Reliable indicators:
- endpoint user identity mapped to IDE session.
- credential source and backend ownership context.
- org-approved vs personal backend account usage.

Policy checks:
- Is backend target approved?
- Is credential source managed?
- Is user using sanctioned workspace/account configuration?

Confidence:
- Medium alone, high when correlated with config and behavior.

---

### E) Behavior
Reliable indicators:
- prompt-to-edit loops in IDE files,
- extension-driven multi-file modifications,
- command/tool invocation sequences from assistant workflows.

High-risk markers:
- use of unapproved backend with sensitive repo context,
- high-volume generated changes without review controls.

Confidence:
- High for assistant/agentic activity classification when sequence is preserved.

---

## 3) What Works Well
1. Extension + config artifact analysis gives strong Continue-specific attribution.
2. Process/behavior correlation differentiates active use from installed-but-idle extension states.
3. Backend-target governance is practical when config and identity are captured.

---

## 4) What Doesn’t Work Reliably
1. Static endpoint/domain detection (Continue backends are user-defined).
2. Extension-presence-only policy enforcement.
3. Network-only controls in self-hosted/internal backend scenarios.

---

## 5) Gaps / Evasion Paths
1. custom/forked extension builds,
2. hidden/templated config routing to unsanctioned endpoints,
3. shared internal gateways obscuring backend differentiation,
4. remote-dev environments with partial host telemetry.

Mitigations:
- enforce backend allowlist at config/policy level,
- hash and monitor config drift,
- confidence penalties for unresolved backend identity.

---

## 6) Confidence Rubric
- **High (>=0.75):** extension/process lineage + config target evidence + behavior sequence.
- **Medium (0.45–0.74):** two aligned layers without full target/identity certainty.
- **Low (<0.45):** isolated indicator only.

---

## 7) Governance Mapping
- **Detect:** first-seen Continue usage or config target changes.
- **Warn:** medium-confidence usage with non-approved backend target.
- **Approval Required:** sensitive repo context + nonstandard backend path.
- **Block:** disallowed backend target use, repeated config bypass, or high-confidence policy breach.

---

## 8) Validation Plan
Positive scenarios (>=3):
1. approved backend target with normal coding workflow,
2. config-defined backend switch within approved list,
3. extension-driven multi-file edit with expected telemetry.

Evasion/failure scenarios (>=2):
1. modified/forked config targeting unsanctioned endpoint,
2. internal proxy/gateway route reducing backend attribution clarity.

Required outputs:
- confidence + rationale per scenario,
- evidence links (config snapshots, process traces, network metadata),
- residual risk statements for unresolved backend attribution.

---

## 9) Acceptance Checklist
- [x] Continue-specific five-layer profile documented.
- [x] Backend-agnostic attribution limitations clearly captured.
- [x] Config-governance controls and enforcement mapping defined.
- [x] Validation scenarios and evidence outputs defined.
- [ ] Empirical lab evidence attached.

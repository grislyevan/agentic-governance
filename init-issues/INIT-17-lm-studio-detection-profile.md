# INIT-17 — LM Studio Detection Profile

## Scope
Tool: **LM Studio** (local desktop LLM runtime/UI with optional local inference server)
Goal: establish enterprise-ready detection/governance for local model usage where cloud-only controls are insufficient.

---

## 1) Tool Anatomy
LM Studio typically runs as a desktop app with local model files and can expose local inference endpoints.
Key implications:
- heavy endpoint-local artifacts,
- variable network footprint (may be mostly local),
- strong overlap with normal desktop/dev workflows unless correlated signals are used.

---

## 2) 5-Layer Detection Model

### A) Process / Execution
Reliable indicators:
- LM Studio app process launch and sustained runtime.
- Child process activity associated with model loading/inference orchestration.
- Session timing aligned with local generation bursts.

Collection targets:
- process hash/path/signer,
- parent-child chain,
- uptime and restart cadence.

Confidence:
- High with stable process lineage + corroborating behavior.
- Medium with top-level process only.

---

### B) File / Artifact
Reliable indicators:
- local model storage artifacts (downloads, metadata, manifests).
- configuration/workspace files showing model selections and runtime options.
- cache growth and model-switching traces.

Limitations:
- model files can be moved/renamed from defaults.

Confidence:
- High for model presence, medium for active usage unless behavior/process-linked.

---

### C) Network
Reliable indicators:
- local loopback API traffic where local server mode is enabled.
- outbound model-download/update traffic (when pulling models).

Limitations:
- local-only sessions may generate minimal useful perimeter network telemetry.
- network-only controls miss local inference operation.

Confidence:
- Medium standalone, high only when tied to process + actor context.

---

### D) Identity / Access
Reliable indicators:
- endpoint user session performing LM Studio actions.
- managed device context and user policy scope.

Policy checks:
- approved users for local model runtime,
- approved endpoint classes,
- approved model families/sources.

Confidence:
- Medium alone, high with process + artifact linkage.

---

### E) Behavior
Reliable indicators:
- repeated local inference loops,
- model switching patterns,
- data-access-to-generation sequences indicating sensitive local analysis.

High-risk markers:
- inference sessions immediately after sensitive file reads,
- unapproved model usage in restricted environments.

Confidence:
- High for local AI activity class when sequencing is captured.

---

## 3) What Works Well
1. Endpoint process + artifact telemetry gives strong LM Studio presence and usage visibility.
2. Model inventory tracking enables actionable governance (approved/disallowed model control).
3. Host-level controls are effective where network controls are blind.

---

## 4) What Doesn’t Work Reliably
1. Perimeter-only detection strategies.
2. Endpoint-domain signatures without local process correlation.
3. One-signal attribution in environments with multiple local AI tools.

---

## 5) Gaps / Evasion Paths
1. custom model paths and renamed artifacts,
2. local server on non-default ports,
3. containerized/packaged execution outside default monitoring scope,
4. offline usage after initial model acquisition.

Mitigations:
- enforce model source + checksum policies,
- monitor non-default local inference service creation,
- apply confidence penalties on missing lineage.

---

## 6) Confidence Rubric
- **High (>=0.75):** process lineage + model artifacts + behavior sequence.
- **Medium (0.45–0.74):** any two layers align without full actor/session certainty.
- **Low (<0.45):** single weak signal only.

---

## 7) Governance Mapping
- **Detect:** first-seen LM Studio runtime/model artifact.
- **Warn:** medium-confidence usage in unapproved endpoint/model context.
- **Approval Required:** local inference on sensitive datasets/repositories.
- **Block:** disallowed model source/use in restricted environment or repeat policy bypass.

---

## 8) Validation Plan
Positive scenarios (>=3):
1. approved model load + local generation session,
2. model switch and repeated local prompts with expected telemetry,
3. policy-compliant endpoint usage with identity mapping.

Evasion/failure scenarios (>=2):
1. non-default model path + renamed artifacts,
2. non-default local server port/service mode.

Required outputs:
- confidence + rationale per scenario,
- evidence links (process snapshots, model inventory logs, local endpoint traces),
- residual risk statements where coverage is partial.

---

## 9) Acceptance Checklist
- [x] LM Studio-specific five-layer profile documented.
- [x] Local inference/perimeter blind-spot caveats documented.
- [x] Model governance and enforcement mapping defined.
- [x] Validation scenarios and evidence outputs defined.
- [ ] Empirical lab evidence attached.

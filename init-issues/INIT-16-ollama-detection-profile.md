# INIT-16 — Ollama Detection Profile

## Scope
Tool: **Ollama** (local LLM runtime + model management daemon)
Goal: define robust endpoint detection/governance for local AI inference where cloud/network controls are insufficient.

---

## 1) Tool Anatomy (why Ollama is special)
Ollama is fundamentally different from SaaS AI tools:
- inference is local, often over localhost APIs,
- models are pulled/stored on-device,
- endpoint traffic may never hit external AI domains during inference.

So network perimeter tooling alone is weak here; endpoint telemetry is primary.

---

## 2) 5-Layer Detection Model

### A) Process / Execution
Reliable indicators:
- Ollama daemon/service process running on host.
- CLI/client invocations (`ollama run`, `pull`, `serve`) tied to user sessions.
- Parent-child lineage from terminal/scripting environments to Ollama calls.

Collection targets:
- process path/hash/signer
- service lifecycle events (start/stop/restart)
- command lineage and execution frequency

Confidence:
- High when daemon + invocation lineage are present.
- Medium when daemon seen but no user/session linkage.

---

### B) File / Artifact
Reliable indicators:
- Model storage directories and pulled model manifests.
- Local metadata for model versions/tags and pull timestamps.
- Cache/artifact growth patterns indicating active local inference usage.

Collection targets:
- model inventory snapshots
- first-seen / last-used metadata
- artifact hash and path consistency checks

Confidence:
- High for proving local model presence.
- Medium for proving active use unless paired with process/behavior signals.

---

### C) Network
Reliable indicators:
- Localhost inference API traffic (commonly loopback ports).
- External model pull/update traffic when fetching models.

Limitations:
- Localhost traffic can be invisible to network perimeter tools.
- Endpoint-only network traces cannot always identify user intent.

Confidence:
- Medium for local-only flows.
- High when process correlation ties local API calls to actor/session.

---

### D) Identity / Access
Reliable indicators:
- OS user/session tied to Ollama CLI and daemon interactions.
- Host ownership and managed/unmanaged endpoint context.

Policy checks:
- approved users for local model runtime,
- approved endpoint class (corp-managed vs personal),
- local model inventory compliance.

Confidence:
- Medium alone, high with process + model artifact ties.

---

### E) Behavior
Reliable indicators:
- Repeated prompt/inference cycles via local API and CLI loops.
- Automation scripts invoking local generation against repos/data.
- High-volume inference patterns linked to sensitive file access.

High-risk markers:
- sensitive data reads preceding local summarization/generation workflows,
- unsanctioned model pulls and rapid model switching.

Confidence:
- High for local AI activity class when sequence/timing is preserved.

---

## 3) What Works Well
1. Process + file artifacts provide strong proof of local AI runtime usage.
2. Model inventory visibility enables direct governance (approved vs unapproved models).
3. Host-level controls can enforce policy where network controls cannot.

---

## 4) What Doesn’t Work Reliably
1. CASB/SWG-only controls (localhost inference bypasses perimeter).
2. Domain-based detection for runtime usage when no external calls occur.
3. One-signal detections without actor/session and model context.

---

## 5) Gaps / Evasion Paths
1. Custom ports or wrapped execution paths.
2. Containerized Ollama instances outside default host telemetry coverage.
3. Side-loaded model files with renamed tags.
4. Offline model use after one-time pull, minimizing external signals.

Mitigations:
- endpoint-first telemetry,
- model allowlist + hash/checksum policy,
- confidence penalties for missing lineage.

---

## 6) Confidence Rubric
- **High (>=0.75):** daemon/process lineage + local model artifacts + behavioral sequence.
- **Medium (0.45–0.74):** two aligned layers without strong actor/session tie.
- **Low (<0.45):** isolated signal (e.g., network pull only or stale artifact only).

---

## 7) Governance Mapping
- **Detect:** first-seen local runtime or new model artifact.
- **Warn:** medium-confidence use on unapproved endpoint or model source.
- **Approval Required:** local inference over sensitive datasets/repos.
- **Block:** unapproved model pulls/runs in restricted environments or repeated policy bypass.

---

## 8) Validation Plan
Positive scenarios (>=3):
1. Standard approved model pull + run flow.
2. Existing approved model inference session with expected telemetry.
3. Local API-based inference automation with policy-compliant context.

Evasion/failure scenarios (>=2):
1. Custom port/containerized runtime path.
2. Side-loaded/renamed model artifacts.

Required outputs:
- confidence score + rationale per scenario,
- evidence links (process logs, model inventory snapshots, local API traces),
- residual risk statement where coverage is partial.

---

## 9) Acceptance Checklist
- [x] Ollama-specific 5-layer profile documented.
- [x] Localhost/perimeter-control limitation explicitly captured.
- [x] Model governance controls mapped to enforcement.
- [x] Validation scenarios and evidence requirements defined.
- [ ] Empirical lab evidence attached.

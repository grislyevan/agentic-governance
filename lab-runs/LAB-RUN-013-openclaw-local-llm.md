# Lab Run Protocol: OpenClaw with Local LLM (Qwen 3.5 via Ollama)

**Run ID:** LAB-RUN-013  
**Tool:** OpenClaw (`openclaw`) v2026.3.1  
**Model Backend:** Qwen 3.5 0.8B via Ollama (`ollama/qwen3.5:0.8b`, localhost:11434)  
**Class:** C (Autonomous Executor) with persistent daemon characteristics (Class B overlay)  
**Playbook Reference:** Section 4.11 (IOCs), Section 12 (Lab Validation), Appendix B (Confidence Scoring)  
**Target Scenario:** Positive — Same protocol as OC-POS-01 with local LLM backend  
**Scenario ID:** OC-POS-05  
**Base Protocol:** LAB-RUN-007 (OC-POS-01) — identical phases, different model backend  
**Status:** `COMPLETE`

---

## Protocol Basis

This run follows the **exact same protocol** as [LAB-RUN-007](LAB-RUN-007-openclaw-install-and-runtime.md) (OC-POS-01), with one parameter change:

| Parameter | LAB-RUN-007 | LAB-RUN-013 |
|---|---|---|
| Model backend | `gpt-5.3-codex` (OpenAI, cloud API) | `ollama/qwen3.5:0.8b` (Ollama, localhost:11434) |
| Model provider | OpenAI (outbound :443) | Ollama (localhost:11434, local inference) |
| Model size | Large (cloud-hosted, unknown params) | Small (0.8B parameters, local) |
| `openclaw.json` config | `agents.defaults.model.primary: "openai-codex/gpt-5.3-codex"` | `agents.defaults.model.primary: "ollama/qwen3.5:0.8b"` |
| `models.providers` | Multiple (Anthropic, Google, OpenAI-Codex) | Single (`ollama` with `baseUrl: http://localhost:11434`) |

All other parameters — environment, phases, evidence capture methodology, workspace isolation, evidence hashing — are identical to LAB-RUN-007.

## Phases Executed

| Phase | Description | Outcome |
|---|---|---|
| Baseline | File, process, network, env, persistence capture | 17 evidence files |
| Phase 1 | Installation verification (already installed) | Confirmed: v2026.3.1, npm global |
| Phase 2 | Gateway/config state capture (already running) | Confirmed: gateway PID 67171, Ollama PID 26237 |
| Phase 3A | Basic interaction (simple Q&A) | **PASSED** — "Paris is the capital of France" |
| Phase 3B | Agentic execution (shell + file creation) | **FAILED** — 0.8B model could not complete tool-use tasks |
| Phase 3C | Self-modification (skill authoring) | **FAILED** — 0.8B model could not create new skill |
| Phase 3D | Proactive/scheduled behavior assessment | Architecture confirmed, model failed to describe capabilities |
| Phase 4 | Teardown (gateway stop, persistence check) | Confirmed: port released, plist persists, no auto-restart |

## Additional Capture (vs LAB-RUN-007)

- **Port 11434 monitoring** added to baseline, Phase 2, Phase 3A, and Phase 4 — captures the Ollama local model server state alongside the OpenClaw gateway.
- **Ollama process entries** captured in Phase 2 process listing (PID 26237 + inference worker PID 97338).
- **Gateway outbound :443 traffic** captured even with local model — demonstrates that local inference does not eliminate all outbound network connections.

## Results

Full results: [LAB-RUN-013-RESULTS.md](LAB-RUN-013-RESULTS.md)

**Confidence:** 0.725 (Medium) — down from 0.80 (High) in LAB-RUN-007  
**Delta:** −0.075, driven by behavior layer (0.40 vs 0.80)  
**Policy:** Approval Required (same as LAB-RUN-007)  
**Key finding:** Infrastructure IOCs (process, file, identity, persistence) are model-independent. Behavioral IOCs are model-capability-dependent.

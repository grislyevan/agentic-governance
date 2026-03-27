# Claims → Evidence Map (Week 4 Reconciliation)

Purpose: map externally used claims to concrete in-repo evidence and qualification status.

**Status labels**
- **accurate**: claim is directly supported by current code/docs evidence.
- **qualified**: directionally true, but must be scoped (live vs protocol-expected, caveat, or point-in-time).
- **experimental**: capability exists partially, is provider-limited, or is not baseline-active.

| External claim | Evidence artifact(s) | Status | Qualification / wording guardrail |
|---|---|---|---|
| Detec uses deterministic policy decisions with stable rule IDs. | [collector/engine/policy.py](../collector/engine/policy.py), [api/core/baseline_policies.py](../api/core/baseline_policies.py) | accurate | Keep language deterministic/versioned; no probabilistic policy inference claims. |
| Four-state ladder: Detect / Warn / Approval Required / Block. | [collector/engine/policy.py](../collector/engine/policy.py), [api/core/baseline_policies.py](../api/core/baseline_policies.py) | accurate | None. |
| 15 baseline rules are seeded per tenant. | [api/core/baseline_policies.py](../api/core/baseline_policies.py) | accurate | Include composition (6 enforcement, 3 Class D, 3 overlay, 3 fallback). |
| Overlay rules only escalate, never downgrade. | [collector/engine/policy.py](../collector/engine/policy.py) (`_higher_severity`) | accurate | None. |
| ISO-001 enforces container isolation for Class C. | [api/core/baseline_policies.py](../api/core/baseline_policies.py), [collector/engine/policy.py](../collector/engine/policy.py) | qualified | Defined in policy logic but baseline rule is inactive (`is_active: false`); phrase as advisory/inactive by default. |
| EDR delegate enforcement is available across OSs. | [docs/product-status.md](product-status.md), [api/tests/test_crowdstrike.py](../api/tests/test_crowdstrike.py), [api/tests/test_crowdstrike_rtr.py](../api/tests/test_crowdstrike_rtr.py) | experimental | Provider maturity varies; currently partial/experimental path. |
| Confidence is scored across five evidence layers. | [branding/whitepaper.md](../branding/whitepaper.md), [docs/ENGINE-TECHNICAL-REPORT.md](ENGINE-TECHNICAL-REPORT.md) | accurate | Fifth-layer model is active; hash verification remains future/planned. |
| Hard enforcement requires multi-layer corroboration. | [branding/whitepaper.md](../branding/whitepaper.md), [playbook/PLAYBOOK-v0.4.1-agentic-ai-endpoint-detection-governance.md](../playbook/PLAYBOOK-v0.4.1-agentic-ai-endpoint-detection-governance.md) | qualified | Phrase as model/policy requirement; avoid implying universal perfect visibility in all environments. |
| Detec has 16 completed lab runs with protocol + RESULTS entries. | [docs/lab-runs-and-results.md](lab-runs-and-results.md), [PROGRESS.md](../PROGRESS.md) | accurate | Distinguish entries that are protocol-expected from full live runs. |
| Aider scanner is live-validated. | `collector/tests/fixtures/lab_runs/LAB-RUN-008.json`, [docs/lab-runs-and-results.md](lab-runs-and-results.md) | accurate | Note live run location/evidence policy in run index. |
| Cline / Continue / LM Studio / GPT-Pilot are validated equivalently to live runs. | [docs/lab-runs-and-results.md](lab-runs-and-results.md), calibration fixtures `LAB-RUN-009.json` through `LAB-RUN-012.json` in `collector/tests/fixtures/lab_runs/` | qualified | These are protocol-expected fixture-backed scenarios unless explicitly live-run. |
| Class D is broadly validated across multiple persistent-agent tools. | [docs/SECURITY-TECHNICAL-REPORT.md](SECURITY-TECHNICAL-REPORT.md), [branding/whitepaper.md](../branding/whitepaper.md) | qualified | Empirical Class D coverage is currently anchored to OpenClaw reference implementation. |
| Process kill tactic is available on Linux/macOS/Windows. | [docs/product-status.md](product-status.md), [collector/enforcement/process_kill.py](../collector/enforcement/process_kill.py) | accurate | Keep OS-specific caveats documented. |
| Network null-route tactic is available on Linux/macOS/Windows. | [docs/product-status.md](product-status.md), [collector/enforcement/network_block.py](../collector/enforcement/network_block.py) | accurate | Linux UID fallback caveat should stay explicit. |
| Proxy injection tactic is available on Linux/macOS/Windows. | [docs/product-status.md](product-status.md), [collector/enforcement/proxy_inject.py](../collector/enforcement/proxy_inject.py) | qualified | Works when proxy target/config and process model support env-proxy control. |
| Event payloads are SIEM-ready JSON. | [branding/whitepaper.md](../branding/whitepaper.md), [collector/schema/validator.py](../collector/schema/validator.py), [api/tests/test_schema_telemetry.py](../api/tests/test_schema_telemetry.py) | accurate | Avoid claiming zero mapping effort for all SIEMs; field mapping may still be organizational. |
| Evasion testing includes six validated vectors for Claude Code trailer suppression. | `collector/tests/fixtures/lab_runs/LAB-RUN-EVASION-001.json`, [docs/SECURITY-TECHNICAL-REPORT.md](SECURITY-TECHNICAL-REPORT.md) | accurate | Scope to tested vector family (trailer/attribution suppression). |
| Automated test volume is "700+". | `.venv/bin/pytest ... --collect-only -q` snapshot 2026-03-21, [docs/SECURITY-TECHNICAL-REPORT.md](SECURITY-TECHNICAL-REPORT.md) | qualified | Use rolling point-in-time method. Current snapshot: 1,318 collected (849 collector + 421 API + 48 protocol). |
| Native ESF/ETW/eBPF telemetry is production-ready. | [docs/product-status.md](product-status.md), [collector/tests/test_esf_provider.py](../collector/tests/test_esf_provider.py), [collector/tests/test_etw_provider.py](../collector/tests/test_etw_provider.py), [collector/tests/test_ebpf_provider.py](../collector/tests/test_ebpf_provider.py) | experimental | Phrase as experimental/provider scaffolding and roadmap maturation. |
| CrowdStrike enrichment is a pilot dependency. | [docs/product-status.md](product-status.md), [docs/pilot-runbook.md](pilot-runbook.md) | qualified | Explicitly state it is not required pilot dependency; optional/experimental enrichment. |

## Method note for marketing + sales docs

When publishing external-facing claims, pair each claim with:
1. Validation label (**live-validated** vs **protocol-expected**),
2. caveat if tactic/provider is not baseline-active,
3. timestamped evidence reference when using rolling metrics (especially test counts).

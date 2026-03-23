# Validation Expansion — Technical Architecture and Foundation

**Purpose:** Technical and UX foundation for the seven workstreams in the Detec Validation Expansion plan. Use this when implementing tasks from [project-tasks/detec-validation-expansion-tasklist.md](../project-tasks/detec-validation-expansion-tasklist.md). References INIT-30, INIT-31, INIT-32 and existing code paths.

---

## 1. Benchmark report format (Workstream 4, INIT-32)

The benchmark report generator (INIT-32) consumes metrics pipeline (INIT-30), evasion suite (INIT-31), and test/replay outputs. Each report build includes:

| Field | Description |
|-------|-------------|
| `report_id` | Unique run identifier |
| `report_type` | internal_technical \| internal_executive \| external_buyer_safe |
| `build_timestamp` | ISO UTC |
| `source_release_version` | Detec version or git ref |
| `input_run_set_ids[]` | Lab run IDs, benchmark run IDs, evasion scenario IDs |
| `coverage_snapshot` | Matrix dimensions, scenario distribution |
| `metric_snapshot` | Detection quality, confidence, enforcement, operational |
| `decision_quality_snapshot` | Policy correctness, escalation behavior |
| `evasion_resilience_snapshot` | Categories tested, R0–R3 outcomes |
| `known_gaps[]` | Explicit limitations and impact |
| `mitigation_plan[]` | Remediation backlog with owners |
| `evidence_manifest_id` | Link to evidence index |
| `sanitization_profile` | internal \| external |

**Section blueprint (canonical):** Executive Summary; Coverage & Methodology; Detection Quality; Governance Quality; Evasion Resilience; Known Gaps and Limitations; Evidence Index; Action Plan. External reports sanitize host/user identifiers and preserve truthfulness (no hiding limitations).

**Implementation note:** API/dashboard/large-fleet benchmarks should emit or write outputs that fit this data model (e.g. metric_snapshot, coverage_snapshot) so a future INIT-32 generator can consume them without rework.

---

## 2. Evasion suite layout (Workstream 5, INIT-31)

### Scenario definition schema

Each evasion scenario must include:

- `evasion_scenario_id` — stable ID (e.g. E1-001, E2-001, E4-CoAuthoredBy)
- `matrix_cell_id` — link to test matrix (INIT-28) if applicable
- `tool_id` + `tool_class` — tool and class (A/B/C/D)
- `evasion_category` — E1 (binary/entry-point), E2 (environment isolation), E3 (network attribution), E4 (artifact), E5 (policy boundary)
- `attack_technique_description` — short description
- `preconditions` — env, tool state
- `action_sequence` — steps to perform
- `expected_degradation_profile` — R0–R3 (see below)
- `expected_policy_behavior` — safe fallback behavior
- `required_evidence_outputs` — minimum evidence set
- `pass_fail_criteria` — assertions

### Degradation outcome model (R0–R3)

| Code | Meaning |
|------|---------|
| R0 | Resilient: detection/decision within expected tolerance |
| R1 | Partial degradation: confidence drops, policy remains safe |
| R2 | Material degradation: confidence/explainability impaired; decision still defensible but risky |
| R3 | Control failure: incorrect decision, missed detection, or unsafe allow |

### Required assertions per run

1. **Detection** — system still detects or explicitly classifies uncertainty  
2. **Confidence** — score reflects degraded certainty  
3. **Decision** — enforcement remains safe for risk context  
4. **Explainability** — reason codes and uncertainty notes present  
5. **Evidence** — minimum evidence set preserved  

### Suite layout (recommended)

- **Location:** `collector/tests/evasion_suite/` or `collector/tests/test_evasion_suite.py` plus scenario data (e.g. YAML/JSON).
- **Runner:** One entry point (e.g. `pytest collector/tests/test_evasion_suite.py`) that loads scenarios by ID, runs them (or replays fixtures), and records outcome (R0–R3) and assertion pass/fail.
- **CI:** Optional job or pytest marker (e.g. `@pytest.mark.evasion`) so suite runs on demand or in nightly CI; document in docs/ci-security.md.
- **Baseline scenarios:** At least E4-CoAuthoredBy (LAB-RUN-EVASION-001) and one E1 (e.g. binary rename) or E2 (container) scenario for regression.

---

## 3. Cross-agent detection design (Workstream 3)

### Current flow (reference code paths)

- **Detection entry:** [collector/main.py](collector/main.py) `run_scan()` builds a list of scanners (named tools + behavioral), calls `_collect_scan_results()`, then for each detection `_process_detection()`.
- **Per-detection pipeline:** `_process_detection()` in main.py: `compute_confidence(scan)`, `classify_confidence()`, `evaluate_policy()`, state_differ, enforcer, emitter. One event per tool detection; no explicit "agent A called agent B" event.
- **Behavioral scanner:** [collector/scanner/behavioral.py](collector/scanner/behavioral.py) builds process trees from the event store, filters out PIDs already detected by named scanners, scores candidate trees with [collector/scanner/behavioral_patterns.py](collector/scanner/behavioral_patterns.py) (e.g. BEH-005 session duration). Output is a single `ScanResult` for "Unknown Agent" (Class C).
- **Event payload:** Events carry `tool_name`, `tool_class`, `confidence`, `signals`, policy decision, etc. No field today for "primary_agent" / "secondary_agent" or "multi_agent_workflow_id".

### Extension points for multi-agent / cross-agent

1. **Correlation layer:** After named + behavioral scans, add a step that inspects all detected tools and process trees in this cycle (or over a short time window). If two or more known tools (or one known + behavioral "Unknown Agent") appear in the same tree or same time window, compute a cross-agent signal.
2. **Signals:** Possible signals: same process tree (parent/child or sibling), same session/time window, shared network egress, or MCP-like invocation (one process spawning another known agent). Data already available: `detected_scans`, `event_store` (process events with PIDs, timestamps), and process tree helpers in [collector/scanner/process_tree.py](collector/scanner/process_tree.py).
3. **Event shape:** Option A: add optional `correlation_context` to existing event (e.g. `multi_agent: true`, `related_tool_names: ["Cursor", "Open Interpreter"]`). Option B: emit a separate "cross_agent_observation" event type. Design doc in `docs/cross-agent-detection-design.md` should decide and reference these paths.
4. **Tests:** Unit tests for correlation logic (e.g. two ScanResults in same tree → correlation flag set); integration test that runs scan with two tools present and asserts event shape.

### UX / SOC impact

- Dashboard and API today show one row per detection. If cross-agent events are first-class, list/detail views may need to group or link "related" detections. Phase 2 foundation: define the minimal event field set; dashboard changes can follow in a later task.

---

## 4. Container and remote-dev detection (Workstream 2)

- **Existing:** [collector/engine/container.py](collector/engine/container.py) — `is_containerized(pid)`, `is_child_of_docker(pid)`. Linux: cgroup, mountinfo, /.dockerenv. macOS: Docker parent chain, /var/run/docker.sock.
- **Extension:** Add `is_devcontainer(pid)` and/or `is_remote_dev_context()` using documented env vars (e.g. `DEVCONTAINER`, VS Code remote env), or metadata paths. Keep existing functions unchanged; new helpers used for reporting and playbook "host weakens here" documentation.
- **Policy:** ISO-001 already uses `is_containerized` for Class C. DevContainer/remote-dev can be reported as context in events (e.g. `container_context: devcontainer`) without changing policy until explicitly required.

---

## 5. Endpoint footprint measurement (Workstream 7)

- **Scan latency:** Instrument [collector/main.py](collector/main.py) `run_scan()`: record wall-clock time for full scan (after provider.start, through _collect_scan_results and _process_detection). Optional: per-scanner timing. Benchmark test or script should run `run_scan` (e.g. dry-run) N times and record mean/p95.
- **CPU / memory:** Use standard library or psutil: sample process CPU and RSS before/after a short daemon loop (e.g. 2–3 scan cycles) or during one run_scan. Report in docs (e.g. SECURITY-TECHNICAL-REPORT or docs/endpoint-footprint.md). Repeatable script (e.g. in `collector/tests/` or `scripts/`) preferred so CI or release process can regenerate numbers.

---

## 6. Enterprise integrations (Workstream 6)

- **OIDC / Okta:** Dashboard already uses OIDC (see dashboard Settings, api auth). Document Okta-specific issuer/claims and test flow in docs/enterprise-oidc-okta.md (or equivalent).
- **SentinelOne:** Add provider in [api/integrations/](api/integrations/) following [api/integrations/crowdstrike.py](api/integrations/crowdstrike.py) and [api/integrations/base.py](api/integrations/base.py). Same interfaces: EDRProvider (enrichment), EnforcementProvider (if applicable).
- **SIEM:** Schema is SIEM-friendly; add doc and optionally a small export path (Splunk HEC or syslog) with config example and proof run. Reference [docs/enforcement-roadmap.md](docs/enforcement-roadmap.md) for Splunk HEC.

---

*This document is the architecture foundation for the validation expansion. Implement tasks from the task list in project-tasks/detec-validation-expansion-tasklist.md; update this doc if the architecture evolves.*

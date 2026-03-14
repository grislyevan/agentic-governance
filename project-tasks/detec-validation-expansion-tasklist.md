# Detec Validation Expansion — Consolidated Task List

**Source:** Orchestrator plan (seven workstreams). Requirements quoted from spec; no luxury scope.

**Output of:** Phase 1 (project-manager-senior equivalent). Use this list for Phase 2 foundation and Phase 3 Dev–QA loops.

---

## Spec (quoted)

1. **More real-world lab runs:** "Right now only ~7 tools were tested live. I'd want: 20–30 real tools tested."
2. **Better container coverage:** "Modern dev environments run in: Docker, DevContainers, remote dev. Host-based detection weakens there."
3. **Cross-agent behavior detection:** "Right now detection focuses on individual tools. Future threats involve: agents calling other agents, multi-agent workflows."
4. **Real performance benchmarks:** "They only tested the local event store. I'd want benchmarks for: API throughput, dashboard performance, large fleets."
5. **Evasion automation:** "They tested one evasion vector. I'd want a continuous evasion test suite. Attackers will absolutely target agent detection systems."
6. **Enterprise integrations:** "Before adoption I'd want proof of working integrations with: Okta / identity, CrowdStrike / SentinelOne, major SIEMs."
7. **Endpoint footprint:** "I'd want to see: CPU impact, memory usage, scan latency. Endpoint agents can become very heavy."

---

## Workstream 1: More real-world lab runs (20–30 tools)

**Current state:** ~10 completed runs (7–8 tools with full RESULTS); 5 tools with templates only (Aider, LM Studio, Continue, GPT-Pilot, Cline). Calibration fixtures: LAB-RUN-001, 003, 004, 005, 006, 007, 013, 014 + 2 behavioral. Scanners: Claude Code, Cursor, Copilot, Ollama, Open Interpreter, OpenClaw, Claude Cowork, Aider, LM Studio, Continue, Cline, GPT-Pilot, MCP, AI Extensions, Evasion, Behavioral.

### [x] Task 1.1 — Prioritize tool list for 20–30 coverage

- Document which tools to add next: complete live runs for LAB-RUN-008 (Aider), 009 (LM Studio), 010 (Continue), 011 (GPT-Pilot), 012 (Cline) first; then identify additional tools from playbook Section 4 / init-issues to reach 20–30.
- Deliverable: `project-tasks/detec-validation-expansion-lab-priority.md` or equivalent section in this file with ordered list and rationale.
- Reference: [docs/lab-runs-and-results.md](docs/lab-runs-and-results.md), playbook Section 4, INIT-13 through INIT-22.

### [ ] Task 1.2 — Add one new live lab run (protocol + results + fixture)

- Pick one tool from the priority list (e.g. Aider). Create or complete protocol in `lab-runs/`, execute run, produce RESULTS, add calibration fixture in `collector/tests/fixtures/lab_runs/`, update playbook Section 12.5 and [docs/lab-runs-and-results.md](docs/lab-runs-and-results.md).
- Acceptance: One new LAB-RUN-XXX with protocol, RESULTS, and fixture; calibration test passes.
- Note: Reaching 20–30 tools requires many such runs; this task is one concrete instance. Repeat for other tools as separate tasks.

**Blocked (as of 2026-03-14):** Requires a lab machine with the tool under test installed (e.g. Aider). Execution is human-driven. No code or doc edits until a run is executed.

**When lab is available:** Spawn Backend Architect or engineering-senior-developer with: (1) Task: Complete one live lab run for one Priority 1 tool (e.g. Aider, LAB-RUN-008). (2) Inputs: [lab-runs/LAB-RUN-008-TEMPLATE-aider.md](lab-runs/LAB-RUN-008-TEMPLATE-aider.md) (or chosen template), [docs/architecture-calibration-pipeline.md](docs/architecture-calibration-pipeline.md), [docs/lab-runs-and-results.md](docs/lab-runs-and-results.md). (3) Deliverables: Convert template to full protocol if needed, execute run, produce `LAB-RUN-XXX-RESULTS.md`, add calibration fixture under `collector/tests/fixtures/lab_runs/` (schema matches existing fixtures, e.g. LAB-RUN-014.json), run `pytest collector/tests/test_calibration.py -v` and ensure it passes. Then spawn EvidenceQA to validate RESULTS file present, fixture present, calibration test passes. Then run Task 1.3 (index + playbook Section 12.5 update).

### [x] Task 1.3 — Update lab index and playbook lab log

- Ensure [docs/lab-runs-and-results.md](docs/lab-runs-and-results.md) and playbook Section 12.5 reflect any new runs from Task 1.2 (or batch of runs). Single source of truth for run IDs and links.

---

## Workstream 2: Better container coverage (Docker, DevContainers, remote dev)

**Current state:** [collector/engine/container.py](collector/engine/container.py) handles Linux cgroup/dockerenv and macOS Docker parent chain. No DevContainer or remote-dev-specific detection.

### [x] Task 2.1 — Extend container detection for DevContainer and remote-dev hints

- Extend [collector/engine/container.py](collector/engine/container.py) (or add a small module) to detect DevContainer and remote-dev hints (e.g. VS Code devcontainer metadata, SSH remote session indicators, or documented env vars).
- Deliverable: Functions or flags such as `is_devcontainer(pid)`, `is_remote_dev_context()` where feasible; unit tests; no breaking change to existing `is_containerized` / `is_child_of_docker`.
- Reference: INIT-31 E2 (Environment Isolation), INIT-13/14/15/18/20.

### [x] Task 2.2 — Document container/remote-dev detection expectations

- Add or update playbook/INIT text for "host weakens here" and what detection can and cannot do in Docker, DevContainers, and remote dev. Link to container.py and new helpers from Task 2.1.
- Deliverable: Short section in playbook or [docs/](docs/) plus any INIT updates.

### [x] Task 2.3 — One lab or evasion scenario in container/remote-dev

- At least one lab run or evasion scenario that runs a tool (or detector) in a container or remote-dev context; document results and any confidence/visibility impact.
- Deliverable: Protocol + RESULTS or evasion scenario doc in `lab-runs/` or evasion suite.

---

## Workstream 3: Cross-agent behavior detection

**Current state:** [collector/scanner/behavioral.py](collector/scanner/behavioral.py) detects "Unknown Agent" by process-tree behavior; no explicit "agent A calls agent B" or multi-agent workflow detection.

### [x] Task 3.1 — Design doc for multi-agent / cross-agent signals

- Write a design doc (in `docs/` or init-issues) for "agent A calls agent B" and multi-agent workflow signals: data sources, correlation approach, and how it plugs into [collector/main.py](collector/main.py) and event payload.
- Deliverable: `docs/cross-agent-detection-design.md` (or init-issues INIT-XXX) with real code path references.
- Reference: [collector/main.py](collector/main.py) `_process_detection`, [collector/scanner/behavioral.py](collector/scanner/behavioral.py), [collector/scanner/process_tree.py](collector/scanner/process_tree.py), [collector/scanner/behavioral_patterns.py](collector/scanner/behavioral_patterns.py).

### [x] Task 3.2 — Implement cross-agent correlation (minimal viable)

- Implement a minimal cross-agent correlation layer or extension to the behavioral scanner: e.g. detect two known tools in the same process tree or same time window and emit a distinct signal or event field. Add tests.
- Deliverable: Code in collector + tests; optional playbook subsection on multi-agent threats.

---

## Workstream 4: Real performance benchmarks (API, dashboard, large fleets)

**Current state:** Only EventStore benchmarks in [collector/tests/test_latency_benchmarks.py](collector/tests/test_latency_benchmarks.py). No API/gateway/dashboard/large-fleet benchmarks.

### [x] Task 4.1 — API throughput and gateway benchmarks

- Add benchmarks for API: e.g. events ingest throughput (events/sec), gateway connection limits and message throughput. Runnable via pytest or a small script; results documentable.
- Deliverable: New test module (e.g. `api/tests/test_benchmarks.py` or `tests/benchmarks/`) and/or script; align with INIT-30/32 where applicable.
- Reference: [api/main.py](api/main.py), gateway, [init-issues/INIT-30-metrics-pipeline.md](init-issues/INIT-30-metrics-pipeline.md), [init-issues/INIT-32-benchmark-report-generator.md](init-issues/INIT-32-benchmark-report-generator.md).

### [x] Task 4.2 — Dashboard performance benchmarks

- Add benchmarks or measurable criteria for dashboard: e.g. load time, list view with many endpoints, detail view. Can be Lighthouse, pytest-playwright, or script; results documentable.
- Deliverable: Script or test suite plus short doc of baseline numbers.

### [x] Task 4.3 — Large-fleet scenario (many agents)

- Define and implement a large-fleet scenario: many simulated agents heartbeating and emitting events; measure API/gateway behavior and document limits or recommendations.
- Deliverable: Script or test + doc (e.g. in [docs/](docs/) or SECURITY-TECHNICAL-REPORT).

---

## Workstream 5: Evasion automation (continuous evasion test suite)

**Current state:** One evasion run (LAB-RUN-EVASION-001, Co-Authored-By). [init-issues/INIT-31-evasion-suite.md](init-issues/INIT-31-evasion-suite.md) defines E1–E5; no automated continuous suite.

### [x] Task 5.1 — Evasion suite structure and scenario IDs

- Implement evasion suite structure per INIT-31: scenario IDs, category (E1–E5), and runner that can execute scenarios and record outcomes (degrade mode, pass/fail). At least Co-Authored-By (existing) and one more vector (e.g. binary rename or container) as regression.
- Deliverable: Test module or suite in `collector/tests/` (e.g. `test_evasion_suite.py` or `evasion_suite/`) runnable in CI or on demand; deterministic scenarios.
- Reference: [lab-runs/LAB-RUN-EVASION-001-RESULTS.md](lab-runs/LAB-RUN-EVASION-001-RESULTS.md), [init-issues/INIT-31-evasion-suite.md](init-issues/INIT-31-evasion-suite.md), [collector/tests/test_evasion_scanner.py](collector/tests/test_evasion_scanner.py).

### [x] Task 5.2 — Wire evasion suite into CI (optional job)

- Add CI job or optional pytest marker to run evasion suite so regressions are caught. Document in [docs/ci-security.md](docs/ci-security.md) or main CI workflow if added.

---

## Workstream 6: Enterprise integrations (Okta, CrowdStrike/SentinelOne, SIEMs)

**Current state:** CrowdStrike in [api/integrations/](api/integrations/); dashboard OIDC SSO; no Okta-specific doc; no SentinelOne; schema SIEM-friendly but no certified SIEM export proof.

### [x] Task 6.1 — Okta / OIDC identity integration doc and test

- Document Okta (or generic OIDC) setup for dashboard SSO; add or extend test for OIDC auth flow so there is proof-of-working integration.
- Deliverable: Doc in [docs/](docs/) (e.g. `docs/enterprise-oidc-okta.md`) and test or runbook.

### [x] Task 6.2 — SentinelOne provider stub or implementation

- Add SentinelOne EDR provider stub (or real implementation) in [api/integrations/](api/integrations/) following existing CrowdStrike pattern. Interface alignment with [api/integrations/base.py](api/integrations/base.py) and enforcement provider if applicable.
- Deliverable: `api/integrations/sentinelone.py` (or equivalent) with tests; doc update.

### [x] Task 6.3 — SIEM export path and proof

- Implement or document at least one SIEM export path (e.g. Splunk HEC or syslog). Provide a small proof run and doc (e.g. how to forward events to SIEM, schema mapping).
- Deliverable: Code or config plus [docs/](docs/) section; reference [docs/enforcement-roadmap.md](docs/enforcement-roadmap.md) (Splunk HEC).

---

## Workstream 7: Endpoint footprint (CPU, memory, scan latency)

**Current state:** No systematic CPU/memory/scan-latency benchmarks or docs.

### [x] Task 7.1 — Scan latency and run_scan timing

- Instrument or benchmark scan latency (e.g. per `run_scan` or daemon cycle). Add test or script that records and asserts on timing; document baseline.
- Deliverable: Benchmark or test in collector (e.g. in [collector/tests/](collector/tests/)) and short doc (e.g. in [docs/SECURITY-TECHNICAL-REPORT.md](docs/SECURITY-TECHNICAL-REPORT.md) or [docs/](docs/)).

### [x] Task 7.2 — CPU and memory footprint measurement

- Add measurement or benchmark for CPU impact and memory usage of the endpoint agent (e.g. during steady-state scan loop). Produce repeatable numbers and document.
- Deliverable: Script or test plus doc section (e.g. endpoint footprint in SECURITY-TECHNICAL-REPORT or [docs/](docs/)).

---

## Task summary

| Workstream | Task IDs   | Count |
|------------|------------|-------|
| 1. Lab runs | 1.1–1.3   | 3     |
| 2. Container | 2.1–2.3   | 3     |
| 3. Cross-agent | 3.1–3.2 | 2     |
| 4. Benchmarks | 4.1–4.3   | 3     |
| 5. Evasion | 5.1–5.2    | 2     |
| 6. Enterprise | 6.1–6.3  | 3     |
| 7. Endpoint footprint | 7.1–7.2 | 2     |
| **Total** |            | **18** |

---

## Execution notes

- **Phase 2:** ArchitectUX should use this task list to produce technical/UX foundation only where applicable (benchmark report format, evasion suite layout, cross-agent design). Skip or shorten for purely lab/protocol or doc-only tasks.
- **Phase 3:** For each task, spawn the appropriate developer agent then EvidenceQA; loop until PASS or retry limit (3). Use shell subagent for running benchmarks or calibration.
- **Phase 4:** When all tasks pass QA, run testing-reality-checker for final integration report.
- One logical change per commit; playbook version bump per [.cursor/rules/git-and-versioning.mdc](.cursor/rules/git-and-versioning.mdc) when playbook is edited.

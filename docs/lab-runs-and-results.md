# Lab Runs, Results, and Related Documentation

**Purpose:** Index of lab validation runs, results, capture scripts, and how they link to the playbook, INIT-43, and calibration. Use this when running or extending lab validation, adding new tool profiles, or tracing evidence back to playbook sections.

---

## 1. Lab run layout

| Path | Contents |
|------|----------|
| **lab-runs/** (removed) | Lab run protocols and results were previously stored here. Protocols and results have been consolidated; calibration fixtures remain in `collector/tests/fixtures/lab_runs/`. |
| **lab-runs/scripts/** (removed) | Capture scripts were previously stored here. |

---

## 2. Protocol vs results

- **Protocol** = step-by-step procedure: prerequisites, baseline capture, phases (install, launch, behavior, teardown), Phase 5 analysis template, evidence inventory, INIT-43 validation mapping. Stored as `LAB-RUN-XXX-<tool-or-scenario>.md`.
- **Results** = filled-in analysis for a completed run: Signal Observation Matrix, confidence score, policy decision, findings, playbook feedback. Stored as `LAB-RUN-XXX-RESULTS.md`. Must satisfy INIT-43 required outputs (per-layer report, confidence trace, correlation rule evaluation, residual ambiguity).

Protocols reference their results (e.g. "Full results: LAB-RUN-014-RESULTS.md"). Results reference evidence files under `$LAB_DIR` (e.g. `~/cowork-lab/LAB-RUN-014/`).

---

## 3. Lab run and results index

### Completed runs (protocol + results)

| Run ID | Tool | Calibration Fixture | Scenario |
|--------|------|---------------------|----------|
| LAB-RUN-001 | Claude Code | `collector/tests/fixtures/lab_runs/LAB-RUN-001.json` | CC-POS-01 |
| LAB-RUN-001-root | Claude Code (root rerun) | `collector/tests/fixtures/lab_runs/LAB-RUN-001-root.json` | CC-POS-01 with full visibility. 2026-03-16: Pass, 0.825 (High); protocol-expected (Path B). |
| LAB-RUN-002 | Claude Code | (extends 001) | CC-POS-02 |
| LAB-RUN-EVASION-001 | Claude Code | `collector/tests/fixtures/lab_runs/LAB-RUN-EVASION-001.json` | CC-EVA-01 |
| LAB-RUN-003 | Ollama | `collector/tests/fixtures/lab_runs/LAB-RUN-003.json` | OL-POS-01 |
| LAB-RUN-004 | Cursor | `collector/tests/fixtures/lab_runs/LAB-RUN-004.json` | CUR-POS-01 |
| LAB-RUN-005 | GitHub Copilot | `collector/tests/fixtures/lab_runs/LAB-RUN-005.json` | CP-POS-01 |
| LAB-RUN-006 | Open Interpreter | `collector/tests/fixtures/lab_runs/LAB-RUN-006.json` | OI-POS-01 |
| LAB-RUN-007 | OpenClaw | `collector/tests/fixtures/lab_runs/LAB-RUN-007.json` | OC-POS-01 |
| LAB-RUN-013 | OpenClaw (local LLM) | `collector/tests/fixtures/lab_runs/LAB-RUN-013.json` | OC-POS-05 |
| LAB-RUN-014 | Claude Cowork | `collector/tests/fixtures/lab_runs/LAB-RUN-014.json` | CW-POS-01 |
| LAB-RUN-008 | Aider | `collector/tests/fixtures/lab_runs/LAB-RUN-008.json` | AI-POS-01 |
| LAB-RUN-012 | Cline | `collector/tests/fixtures/lab_runs/LAB-RUN-012.json` | CLINE-POS-01 |
| LAB-RUN-010 | Continue | `collector/tests/fixtures/lab_runs/LAB-RUN-010.json` | CONT-POS-01 |
| LAB-RUN-009 | LM Studio | `collector/tests/fixtures/lab_runs/LAB-RUN-009.json` | LMS-POS-01 |
| LAB-RUN-011 | GPT-Pilot | `collector/tests/fixtures/lab_runs/LAB-RUN-011.json` | GPT-POS-01 |
| LAB-RUN-015 | Claude Cowork (gap) | `collector/tests/fixtures/lab_runs/LAB-RUN-015.json` | CW-POS-02, CW-POS-03, skill-creator |

> **Note:** Lab run protocol and results files were previously stored in `lab-runs/`. That directory has been removed. Calibration fixtures in `collector/tests/fixtures/lab_runs/` are the remaining machine-readable evidence for each run.

### Protocol only (pending or gap scenarios)

**Calibrated vs synthetic:** Tools with a calibration fixture in `collector/tests/fixtures/lab_runs/*.json` and (optionally) a completed RESULTS file are considered **calibrated**; confidence scores are empirically validated. LAB-RUN-008 (Aider) has a live run (2026-03-16; repo in ~/Documents/aider-lab; evidence in that repo's LAB-RUN-008/ subdir, do not commit). LAB-RUN-012 (Cline) has RESULTS and fixture from protocol-expected scenario (collector run had Cline not installed). LAB-RUN-010 (Continue) has RESULTS and fixture from protocol-expected scenario (no live run). LAB-RUN-009 (LM Studio) has RESULTS and fixture from protocol-expected scenario (no live run). LAB-RUN-011 (GPT-Pilot) has RESULTS and fixture from protocol-expected scenario (no live run). LAB-RUN-015 (Cowork gap) has RESULTS and fixture from protocol-expected scenario (evidence supplied; CW-POS-02/03, skill-creator). LAB-RUN-001-root (Claude Code root rerun) has RESULTS and fixture from protocol-expected scenario (Path B; full visibility baseline). Tools with only synthetic scanner tests and no fixture are **synthetic only**; PM and sales should phrase confidence accordingly until live lab runs are completed.

**Next runs (20-30 tool goal):** The prioritised order (template tools first, then gap scenarios, then net-new tools) and the executable task breakdown (WP1-WP7) were previously tracked in `project-tasks/` (removed). When new runs are completed, add them to the tables above and to playbook Section 12.5.

---

## 4. Capture scripts

| Script | Purpose | Doc |
|--------|---------|-----|
| **lab-runs/scripts/cowork-capture.sh** (removed) | Was automated capture for Claude Cowork (LAB-RUN-014): baseline, phase1, phase2, phase4. Phase 3 is manual. Optional `--with-monitors` for phase2 (connection/pstree streams). | Removed with `lab-runs/` |
| **lab-runs/scripts/claude-code-capture.sh** (removed) | Was automated capture for Claude Code (LAB-RUN-001/002): baseline, phase1 post-install, phase2 post-launch, phase4. Phase 3 (agentic session) is manual. Optional `--with-monitors` for phase2. | Removed with `lab-runs/` |

Usage: Set `LAB_DIR` to override default (Cowork: `~/cowork-lab/LAB-RUN-014`; Claude Code: `~/claude-lab/LAB-RUN-001`). Capture scripts were previously in `lab-runs/scripts/` (removed).

---

## 5. Links to other documentation

### Playbook

- **Location:** [playbook/PLAYBOOK-v0.4.1-agentic-ai-endpoint-detection-governance.md](../playbook/PLAYBOOK-v0.4.1-agentic-ai-endpoint-detection-governance.md)
- **Relevant sections:** Section 4 (tool detection profiles and IOCs), Section 12 (Lab Validation Runs), Section 12.5 (Lab Run Log), Appendix A (cross-layer correlation rules), Appendix B (confidence scoring).
- Lab run log (12.5) lists every run with date, tool, scenario, result, and notes. Methodology (12.4) records lessons from each run.

### INIT-43 (process/file/network signal map)

- **Location:** [init-issues/INIT-43-claude-process-file-network-signal-map.md](../init-issues/INIT-43-claude-process-file-network-signal-map.md)
- **Role:** Defines process, file, and network normalization fields, failure modes, correlation rules C1–C4, and validation plan. Lab outputs must produce: per-layer signal report, confidence trace, correlation rule evaluation, residual ambiguity.
- **Link from INIT-43:** Section 8 links to LAB-RUN-014 protocol, LAB-RUN-014-RESULTS, LAB-RUN-015 protocol, and cowork-capture.sh as empirical run artifacts.

### Calibration (confidence engine)

- **Fixtures:** [collector/tests/fixtures/lab_runs/](../collector/tests/fixtures/lab_runs/) — one JSON per lab run (e.g. `LAB-RUN-014.json`) with signals, penalties, expected band.
- **Test:** `pytest collector/tests/test_calibration.py -v` replays fixtures through the confidence engine; run before changing weights (see [architecture-calibration-pipeline.md](architecture-calibration-pipeline.md)).
- **Doc:** [architecture-calibration-pipeline.md](architecture-calibration-pipeline.md) describes lab replay harness, fixture format, and calibration discipline.

### Behavioral core detections (DETEC-BEH-CORE-01/02/03)

- **Event-level fixtures:** [collector/tests/fixtures/behavioral_core_fixtures.py](../collector/tests/fixtures/behavioral_core_fixtures.py) — seed functions for shell fan-out, read-modify-write loop, and sensitive access + outbound (positive, false-positive, ambiguous, renamed).
- **Test:** `pytest collector/tests/test_behavioral_core_detections.py -v` replays event stores through BehavioralScanner and asserts pattern presence and evidence. Uses a lowered detection threshold (0.28) so fixtures that trigger the core patterns pass aggregate.
- **Specs:** The DETEC-BEH-CORE-01/02/03 specification documents were previously in `project-specs/` (removed). Detection logic is implemented in `collector/scanner/behavioral_patterns.py`.

### Init issues (backlog)

- **Location:** [init-issues/](../init-issues/)
- Lab-related: INIT-43 (signal map); INIT-13–22 (detection profiles). Other init issues drive playbook structure and shelved work (Playbook Section 13).

### Progress and conventions

- **Progress:** [PROGRESS.md](../PROGRESS.md) — milestone checklist, including lab runs (e.g. LAB-RUN-014 Claude Cowork).
- **Agent brief:** [AGENTS.md](../AGENTS.md) — key paths (playbook, lab-runs, init-issues), calibration note, docs conventions.

---

## 6. Running a lab (high level)

1. **Pick protocol** from `lab-runs/` (e.g. LAB-RUN-014 for Claude Cowork).
2. **Set up evidence dir** (e.g. `export LAB_DIR=~/cowork-lab/LAB-RUN-014`; create phase dirs per protocol).
3. **Run capture** — by hand (copy-paste protocol bash blocks) or via script if available (e.g. `cowork-capture.sh baseline`, then `phase1`, then launch tool and `phase2`, then `phase4`).
4. **Complete Phase 3** manually if the protocol requires it (e.g. session analysis with session-specific paths).
5. **Fill Phase 5 / RESULTS** — Signal Observation Matrix, confidence trace, C1–C4 evaluation, residual ambiguity, playbook feedback.
6. **Update playbook** — Section 12.5 Lab Run Log, Section 12.4 Methodology if new findings; add or update calibration fixture in `collector/tests/fixtures/lab_runs/` and run `test_calibration.py`.

Evidence dirs contain sensitive snapshots (config, process list, env); do not commit them. Archive per playbook Section 9.4 retention if applicable.

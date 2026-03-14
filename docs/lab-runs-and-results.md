# Lab Runs, Results, and Related Documentation

**Purpose:** Index of lab validation runs, results, capture scripts, and how they link to the playbook, INIT-43, and calibration. Use this when running or extending lab validation, adding new tool profiles, or tracing evidence back to playbook sections.

---

## 1. Lab run layout

| Path | Contents |
|------|----------|
| **lab-runs/** | All lab run protocols (procedures) and results. |
| **lab-runs/*.md** | Protocol docs (e.g. `LAB-RUN-014-claude-cowork-install-and-runtime.md`) and matching `*-RESULTS.md` (e.g. `LAB-RUN-014-RESULTS.md`). Templates (e.g. `LAB-RUN-012-TEMPLATE-cline.md`) are protocols for tools not yet lab-run. |
| **lab-runs/scripts/** | Executable capture scripts. [lab-runs/scripts/README.md](../lab-runs/scripts/README.md) describes usage. |
| **lab-runs/lab-cleanup.sh** | Utility for cleaning lab evidence directories (if present). |

---

## 2. Protocol vs results

- **Protocol** = step-by-step procedure: prerequisites, baseline capture, phases (install, launch, behavior, teardown), Phase 5 analysis template, evidence inventory, INIT-43 validation mapping. Stored as `LAB-RUN-XXX-<tool-or-scenario>.md`.
- **Results** = filled-in analysis for a completed run: Signal Observation Matrix, confidence score, policy decision, findings, playbook feedback. Stored as `LAB-RUN-XXX-RESULTS.md`. Must satisfy INIT-43 required outputs (per-layer report, confidence trace, correlation rule evaluation, residual ambiguity).

Protocols reference their results (e.g. "Full results: LAB-RUN-014-RESULTS.md"). Results reference evidence files under `$LAB_DIR` (e.g. `~/cowork-lab/LAB-RUN-014/`).

---

## 3. Lab run and results index

### Completed runs (protocol + results)

| Run ID | Tool | Protocol | Results | Scenario |
|--------|------|----------|---------|----------|
| LAB-RUN-001 | Claude Code | [LAB-RUN-001-claude-code-install-and-runtime.md](../lab-runs/LAB-RUN-001-claude-code-install-and-runtime.md) | [LAB-RUN-001-RESULTS.md](../lab-runs/LAB-RUN-001-RESULTS.md) | CC-POS-01 |
| LAB-RUN-001-root | Claude Code (root rerun) | [LAB-RUN-001-ROOT-RERUN.md](../lab-runs/LAB-RUN-001-ROOT-RERUN.md) | [LAB-RUN-001-root-RESULTS.md](../lab-runs/LAB-RUN-001-root-RESULTS.md) | CC-POS-01 with full visibility (template; fill after run) |
| LAB-RUN-002 | Claude Code | (extends 001) | [LAB-RUN-002-RESULTS.md](../lab-runs/LAB-RUN-002-RESULTS.md) | CC-POS-02 |
| LAB-RUN-EVASION-001 | Claude Code | (evasion) | [LAB-RUN-EVASION-001-RESULTS.md](../lab-runs/LAB-RUN-EVASION-001-RESULTS.md) | CC-EVA-01 |
| LAB-RUN-003 | Ollama | [LAB-RUN-003-ollama-install-and-runtime.md](../lab-runs/LAB-RUN-003-ollama-install-and-runtime.md) | [LAB-RUN-003-RESULTS.md](../lab-runs/LAB-RUN-003-RESULTS.md) | OL-POS-01 |
| LAB-RUN-004 | Cursor | [LAB-RUN-004-cursor-install-and-runtime.md](../lab-runs/LAB-RUN-004-cursor-install-and-runtime.md) | [LAB-RUN-004-RESULTS.md](../lab-runs/LAB-RUN-004-RESULTS.md) | CUR-POS-01 |
| LAB-RUN-005 | GitHub Copilot | [LAB-RUN-005-copilot-install-and-runtime.md](../lab-runs/LAB-RUN-005-copilot-install-and-runtime.md) | [LAB-RUN-005-RESULTS.md](../lab-runs/LAB-RUN-005-RESULTS.md) | CP-POS-01 |
| LAB-RUN-006 | Open Interpreter | [LAB-RUN-006-open-interpreter-install-and-runtime.md](../lab-runs/LAB-RUN-006-open-interpreter-install-and-runtime.md) | [LAB-RUN-006-RESULTS.md](../lab-runs/LAB-RUN-006-RESULTS.md) | OI-POS-01 |
| LAB-RUN-007 | OpenClaw | [LAB-RUN-007-openclaw-install-and-runtime.md](../lab-runs/LAB-RUN-007-openclaw-install-and-runtime.md) | [LAB-RUN-007-RESULTS.md](../lab-runs/LAB-RUN-007-RESULTS.md) | OC-POS-01 |
| LAB-RUN-013 | OpenClaw (local LLM) | [LAB-RUN-013-openclaw-local-llm.md](../lab-runs/LAB-RUN-013-openclaw-local-llm.md) | [LAB-RUN-013-RESULTS.md](../lab-runs/LAB-RUN-013-RESULTS.md) | OC-POS-05 |
| LAB-RUN-014 | Claude Cowork | [LAB-RUN-014-claude-cowork-install-and-runtime.md](../lab-runs/LAB-RUN-014-claude-cowork-install-and-runtime.md) | [LAB-RUN-014-RESULTS.md](../lab-runs/LAB-RUN-014-RESULTS.md) | CW-POS-01 |

### Protocol only (pending or gap scenarios)

| Run ID | Tool / scenario | Protocol | Notes |
|--------|-----------------|----------|--------|
| LAB-RUN-008 | Aider | [LAB-RUN-008-TEMPLATE-aider.md](../lab-runs/LAB-RUN-008-TEMPLATE-aider.md) | Template; synthetic validation only. |
| LAB-RUN-009 | LM Studio | [LAB-RUN-009-TEMPLATE-lm-studio.md](../lab-runs/LAB-RUN-009-TEMPLATE-lm-studio.md) | Template; synthetic validation only. |
| LAB-RUN-010 | Continue | [LAB-RUN-010-TEMPLATE-continue.md](../lab-runs/LAB-RUN-010-TEMPLATE-continue.md) | Template; synthetic validation only. |
| LAB-RUN-011 | GPT-Pilot | [LAB-RUN-011-TEMPLATE-gpt-pilot.md](../lab-runs/LAB-RUN-011-TEMPLATE-gpt-pilot.md) | Template; synthetic validation only. |
| LAB-RUN-012 | Cline | [LAB-RUN-012-TEMPLATE-cline.md](../lab-runs/LAB-RUN-012-TEMPLATE-cline.md) | Template; synthetic validation only. |
| LAB-RUN-015 | Claude Cowork (gap) | [LAB-RUN-015-claude-cowork-scheduled-dxt-skill.md](../lab-runs/LAB-RUN-015-claude-cowork-scheduled-dxt-skill.md) | CW-POS-02 (scheduled task), CW-POS-03 (DXT), skill-creator. Protocol ready; run pending. Cowork scanner includes schedule-skill artifact detection (file layer). |

**Calibrated vs synthetic:** Tools with a calibration fixture in `collector/tests/fixtures/lab_runs/*.json` and (optionally) a completed RESULTS file are considered **calibrated**; confidence scores are empirically validated. Tools with only synthetic scanner tests and no fixture (LAB-RUN-008 through 012) are **synthetic only**; PM and sales should phrase confidence accordingly until live lab runs are completed.

**Next runs (20–30 tool goal):** See [project-tasks/detec-validation-expansion-lab-priority.md](../project-tasks/detec-validation-expansion-lab-priority.md) for prioritised order (template tools first, then gap scenarios, then net-new tools). When new runs are completed, add them to the tables above and to playbook Section 12.5.

---

## 4. Capture scripts

| Script | Purpose | Doc |
|--------|---------|-----|
| **lab-runs/scripts/cowork-capture.sh** | Automated capture for Claude Cowork (LAB-RUN-014): baseline, phase1, phase2, phase4. Phase 3 is manual. Optional `--with-monitors` for phase2 (connection/pstree streams). | [lab-runs/scripts/README.md](lab-runs/scripts/README.md) |
| **lab-runs/scripts/claude-code-capture.sh** | Automated capture for Claude Code (LAB-RUN-001/002): baseline, phase1 post-install, phase2 post-launch, phase4. Phase 3 (agentic session) is manual. Optional `--with-monitors` for phase2. | [lab-runs/scripts/README.md](lab-runs/scripts/README.md) |

Usage: Set `LAB_DIR` to override default (Cowork: `~/cowork-lab/LAB-RUN-014`; Claude Code: `~/claude-lab/LAB-RUN-001`). See [scripts/README.md](../lab-runs/scripts/README.md).

---

## 5. Links to other documentation

### Playbook

- **Location:** [playbook/PLAYBOOK-v0.4-agentic-ai-endpoint-detection-governance.md](../playbook/PLAYBOOK-v0.4-agentic-ai-endpoint-detection-governance.md)
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

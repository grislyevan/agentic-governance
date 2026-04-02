# Progress

This file tracks lab run validation progress and test coverage milestones. For evidence policy, per-run protocol links, and results file references, see [docs/lab-runs-and-results.md](docs/lab-runs-and-results.md).

---

## Lab Run Validation

| Run ID | Tool | Type | Status | Date |
|--------|------|------|--------|------|
| LAB-RUN-001 | Claude Code | Live | Complete | 2026-03-10 |
| LAB-RUN-001-root | Claude Code (root rerun) | Live | Complete | 2026-03-16 |
| LAB-RUN-002 | Claude Code | Live | Complete | 2026-03-12 |
| LAB-RUN-003 | Ollama | Live | Complete | 2026-03-12 |
| LAB-RUN-004 | Cursor | Live | Complete | 2026-03-13 |
| LAB-RUN-005 | GitHub Copilot | Live | Complete | 2026-03-13 |
| LAB-RUN-006 | Open Interpreter | Live | Complete | 2026-03-14 |
| LAB-RUN-007 | OpenClaw | Live | Complete | 2026-03-14 |
| LAB-RUN-008 | Aider | Live | Complete | 2026-03-16 |
| LAB-RUN-009 | LM Studio | Protocol-expected | Complete | 2026-03-17 |
| LAB-RUN-010 | Continue | Protocol-expected | Complete | 2026-03-17 |
| LAB-RUN-011 | GPT-Pilot | Protocol-expected | Complete | 2026-03-17 |
| LAB-RUN-012 | Cline | Protocol-expected | Complete | 2026-03-18 |
| LAB-RUN-013 | OpenClaw (local LLM) | Live | Complete | 2026-03-19 |
| LAB-RUN-014 | Claude Cowork | Live | Complete | 2026-03-20 |
| LAB-RUN-015 | Claude Cowork (gap) | Live | Complete | 2026-03-21 |
| LAB-RUN-EVASION-001 | Claude Code | Live/Evasion | Complete | 2026-03-21 |

**Validation type notes:**
- **Live** — agent was installed and executed in a real lab environment; evidence files captured from actual process/network activity.
- **Protocol-expected** — fixture-backed scenario; collector run with tool not installed or protocol-expected path. Results and confidence scores are empirically calibrated but not from a live install. Refer to per-run RESULTS files for specifics.
- **Live/Evasion** — live run targeting evasion vectors (trailer/attribution suppression family).

---

## Test Coverage Snapshot

As of 2026-04-01:

| Suite | Tests |
|-------|-------|
| Collector | 1,026 |
| API | 498 |
| Protocol | 59 |
| **Total** | **1,583** |

Test count is a rolling point-in-time metric. When referencing this figure in external docs, include the date.

---

## Calibration Status

The calibration regression gate is active in CI. Any change to confidence scoring logic or policy rule thresholds requires updated fixture evidence before merging. Fixtures are stored under `collector/tests/fixtures/lab_runs/`. A CI run that changes confidence outputs without a corresponding fixture update will fail the calibration gate.

See [docs/calibration-metrics.md](docs/calibration-metrics.md) for calibration methodology and per-layer weight definitions.

---

_For evidence policy and per-run protocol/results links, see [docs/lab-runs-and-results.md](docs/lab-runs-and-results.md)._

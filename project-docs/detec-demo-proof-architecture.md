# Detec Demo Proof — Architecture and Artifact Layout

For implementers and QA. Source: [project-specs/detec-demo-proof-setup.md](../project-specs/detec-demo-proof-setup.md) and [task list](../project-tasks/detec-demo-proof-tasklist.md).

---

## 1. Purpose and scope

- **Goal:** A stable, presentation-ready demo artifact set for the **one-minute** demo (install, run scan, see output). Distinct from the existing **five-minute** demo (full stack, dashboard, sample events) in [docs/demo/](../docs/demo.md).
- **In scope:** Artifacts that back the README one-minute demo: terminal transcript, optional screenshot, short demo evidence doc, README pointer, and completion report. No changes to collector, API, dashboard, or policy engine.

---

## 2. Artifact locations and naming

### 2.1 One-minute demo evidence directory: `docs/demo-proof/`

All one-minute demo proof artifacts live under **`docs/demo-proof/`** so reviewers find them in one place and they are clearly separate from the five-minute demo (`docs/demo/`).

| Artifact | Path | Purpose |
|----------|------|--------|
| Terminal transcript | `docs/demo-proof/terminal-transcript.txt` or `terminal-transcript.md` | Checked-in sample output from a validated run of `pip install -e .` then `detec scan --verbose` (or `detec-agent scan --verbose`). Must be clearly labeled as demo/sample evidence at top of file. |
| Screenshot (optional) | `docs/demo-proof/scan-success.png` | Image of terminal showing successful one-minute flow. Optional if in-repo capture is not feasible; document why in demo evidence doc. |
| Demo evidence doc | `docs/demo-proof/README.md` or `docs/demo-proof/demo-evidence.md` | Short description: what was run, what the viewer should notice, how it aligns with README, and that transcript/screenshot are sample or from a specific run. Truthful; no fake capabilities. |

### 2.2 Optional capture script

If a minimal script is added to run the flow and capture output:

- **Path:** `scripts/demo-one-min-capture.sh` (or similar).
- **Behavior:** Run install (if needed) and `detec scan --verbose`, redirecting stdout to a file. Minimal and documented in the demo evidence doc as for demo capture only.

### 2.3 Project docs (existing pattern)

| Doc | Path | Purpose |
|-----|------|--------|
| Architecture | `project-docs/detec-demo-proof-architecture.md` | This file: artifact layout, naming, README alignment. |
| Completion report | `project-docs/detec-demo-proof-completion-report.md` | Final status, changed files, integration result, known limitations. |

---

## 3. Alignment with README one-minute demo

The root [README.md](../README.md) (lines 5–42) defines the one-minute demo:

1. **Install:** `pip install -e .`
2. **Scan:** `detec-agent scan --verbose` or `detec scan --verbose`
3. **Example output:** Detected tools (e.g. Cursor, Ollama), confidence scores, signals, and the line: `Scan complete. Events emitted: N, validation failures: 0`

Demo proof artifacts must **match** this story:

- The terminal transcript must show the same **shape** of output (scanner blocks, confidence, "Scan complete" summary). Tool names and counts may vary by environment; the transcript should be from a real or validated run and labeled as such.
- The demo evidence doc must state what was run, what to notice, and how it aligns with the README. If the transcript is from a specific environment or date, say so (truthful, no fake capabilities).

---

## 4. Sample vs live evidence

- **Sample/demo evidence:** Any checked-in transcript or screenshot that is not necessarily from the viewer's machine. It must be **clearly labeled** (e.g. "Demo/sample evidence from a validated run on [date/env]. Your run may show different tools or counts.").
- **Live evidence:** A reviewer can always run `pip install -e .` and `detec scan --verbose` themselves; the demo proof set backs the README story with stable artifacts while remaining truthful that live output may vary.

---

## 5. Validation (for EvidenceQA and integration)

- **Per task:** Artifacts exist at the paths above; naming matches this doc; any script is documented; sample/demo labeling is present and clear; no misleading claims.
- **Final:** Reviewer can find the demo proof set from the README; completion report lists changed files, status, and known limitations.

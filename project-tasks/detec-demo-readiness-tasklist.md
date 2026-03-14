# Detec Demo Readiness — Task List

Source: [project-specs/detec-demo-readiness-setup.md](../project-specs/detec-demo-readiness-setup.md)

## Quoted requirements from spec

- **Goal:** "Improve first-impression clarity and signal for security investors and evaluators: lead with a one-minute demo (install, run scan, see output) and optional short CLI name, without changing product behavior."
- **Required (one-minute demo):** "Add a section at the top of the root README (after the main title and tagline) that: (1) States in 2–3 lines what Detec does (discover AI tools on developer machines). (2) Shows the install command (e.g. `pip install -e .` from repo, or `pip install detec` when published). (3) Shows the one-shot scan command: `detec-agent scan --verbose` (or `detec scan` if the short CLI is implemented). (4) Includes a screenshot or pasted terminal output that shows: detected tools (e.g. Cursor, Claude Code, Ollama), capabilities or confidence, and the 'Scan complete' line. This section must appear before 'Repo layout' or other structural sections so a reader sees the demo first."
- **Optional (short CLI):** "If implemented: add a console script or entry point so that `detec scan` (and optionally `detec run`, `detec status`) invokes the same behavior as `detec-agent scan`, `detec-agent run`, `detec-agent status`. Implementation may be a thin wrapper or alias that delegates to the existing `detec-agent` CLI. No change to collector behavior."
- **Optional (discovery-first narrative):** "If implemented: adjust the opening sentence or paragraph of the README so the primary message is 'discover what AI tools run on developer machines' with governance/control presented as the next step, not the first phrase."
- **Out of scope:** "Changing scanner or confidence logic; adding new tools or detection profiles; modifying API, dashboard, or deployment beyond documentation/CLI surface; moving or deleting existing folders."

---

## Tasks

### Task 1: Add one-minute demo section to root README (required)

- **What:** Insert a new section after the main title and tagline, before "Repo layout" (and any other structural sections). The section must:
  - State in 2–3 lines what Detec does (discover AI tools on developer machines).
  - Show the install command (e.g. `pip install -e .` from repo, or `pip install detec` when published).
  - Show the one-shot scan command: `detec-agent scan --verbose` (or `detec scan` if Task 2 is done).
  - Include a screenshot or pasted terminal output showing: detected tools (e.g. Cursor, Claude Code, Ollama), capabilities or confidence, and the "Scan complete" line.
- **Acceptance criteria:**
  - [ ] Section exists and is the first substantive section after title/tagline.
  - [ ] It appears before "Repo layout" in the README.
  - [ ] All four elements above are present (what Detec does, install command, scan command, example output).
  - [x] A new visitor can run two commands and see concrete scan output within one minute.
- **Status:** [x]

---

### Task 2: Optional — Add short `detec` CLI (console script)

- **What:** Add a console script so that `detec scan` (and optionally `detec run`, `detec status`) invokes the same behavior as `detec-agent scan`, `detec-agent run`, `detec-agent status`. Thin wrapper that delegates to `detec-agent`; no change to collector behavior.
- **Acceptance criteria:**
  - [ ] After `pip install -e .`, `detec scan` runs and produces the same one-shot scan as `detec-agent scan`.
  - [ ] If implemented: `detec run` and `detec status` behave like `detec-agent run` and `detec-agent status`.
  - [x] No new logic in collector; delegation only.
- **Status:** [x]

---

### Task 3: Optional — Discovery-first narrative in README opening

- **What:** Adjust the opening sentence or paragraph of the README so the primary message is "discover what AI tools run on developer machines," with governance/control as the next step.
- **Acceptance criteria:**
  - [ ] First sentence or short paragraph leads with discovery (what AI tools run on developer machines).
  - [x] Governance/control is presented as the next step, not the first phrase.
- **Status:** [x]

---

## Completion

- All required tasks (Task 1) must pass QA before Phase 4.
- Optional tasks (Task 2, Task 3) may be skipped or implemented; if implemented, they must pass QA.

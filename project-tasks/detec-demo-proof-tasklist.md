# Detec Demo Proof — Task List

Source: [project-specs/detec-demo-proof-setup.md](../project-specs/detec-demo-proof-setup.md)

## Quoted requirements from spec

- **Goal:** "Create a polished, repeatable demo artifact set for Detec so investors, design partners, and first-time technical reviewers can see a clean product story with concrete evidence."
- **Requirements (excerpt):** "Produce a stable demo artifact set for the recommended Detec scan flow. The demo artifact set must include at least: one clean terminal transcript or terminal-style output artifact; one screenshot or image of the successful demo flow, if feasible in-repo; one short demo evidence document describing what was run and what the viewer should notice. Align the artifact set with the README one-minute demo section. If fixtures, sample outputs, or canned evidence are introduced, they must be clearly labeled as demo/sample evidence. Preserve the truthful product story."
- **Success criteria:** "A reviewer can open the repo and find a concrete demo evidence set quickly. README demo claims are backed by visible artifacts in the repo. The demo artifacts are clean enough to use in investor/design-partner conversations. The artifacts are truthful and clearly labeled where they are sample-based. The work remains minimal and scoped."
- **Suggested deliverables:** "Updated task list at project-tasks/detec-demo-proof-tasklist.md; Foundation/architecture guidance for demo artifacts; Demo evidence artifacts (transcript, screenshot, and/or sample output); Short documentation describing the demo proof set; Completion report with final status and known limitations."
- **Out of scope:** "New dashboard features; policy engine changes; broad collector refactors; packaging/release work; branding overhaul; website/landing-page work."

---

## Tasks

### Task 1: Create spec and task list (pre-step)

- **What:** Ensure the project spec exists at `project-specs/detec-demo-proof-setup.md` and this task list at `project-tasks/detec-demo-proof-tasklist.md` with quoted requirements and acceptance criteria.
- **Acceptance criteria:**
  - [x] `project-specs/detec-demo-proof-setup.md` exists and contains goal, requirements, success criteria, and out of scope.
  - [x] `project-tasks/detec-demo-proof-tasklist.md` exists with quoted spec requirements and tasks below.
- **Status:** [x]

---

### Task 2: Add foundation/architecture doc for demo artifacts

- **What:** Add a project-docs document that defines where demo proof artifacts live, naming conventions, how they align with the README one-minute demo, and what is sample vs live evidence.
- **Acceptance criteria:**
  - [x] `project-docs/detec-demo-proof-architecture.md` exists.
  - [x] Doc specifies artifact locations (e.g. `docs/demo-proof/`), file names, and README alignment.
  - [x] Doc clarifies labeling of sample/demo evidence.
- **Status:** [x]

---

### Task 3: Add checked-in terminal transcript (one-minute flow)

- **What:** Add a terminal transcript or terminal-style output artifact from the one-minute demo flow (`pip install -e .` then `detec scan --verbose` or `detec-agent scan --verbose`). Place in `docs/demo-proof/`. Clearly label as demo/sample evidence in the file (e.g. header comment or first line).
- **Acceptance criteria:**
  - [x] Transcript file exists under `docs/demo-proof/` (e.g. `terminal-transcript.txt` or `terminal-transcript.md`).
  - [x] Content shows the same shape as README example: detected tools, confidence, "Scan complete. Events emitted: N, validation failures: 0".
  - [x] File contains a clear label that it is demo/sample evidence (and optionally from which environment/run).
- **Status:** [x]

---

### Task 4: Screenshot or document why optional

- **What:** Add one screenshot of the successful one-minute demo flow in `docs/demo-proof/` if feasible (e.g. terminal showing scan output). If in-repo screenshot capture is not feasible, add a short note in the demo evidence doc explaining why and that the transcript serves as the primary evidence.
- **Acceptance criteria:**
  - [x] Either a screenshot file exists in `docs/demo-proof/` (e.g. `scan-success.png`) or the demo evidence doc states that screenshot is optional and why (e.g. no automated capture in pipeline).
  - [x] No misleading claims; if no screenshot, say so clearly.
- **Status:** [x]

---

### Task 5: Add short demo evidence document

- **What:** Add a short document in `docs/demo-proof/` (e.g. `README.md` or `demo-evidence.md`) that describes: what was run (install + scan commands), what the viewer should notice (detected tools, confidence, scan complete line), how the artifacts align with the README one-minute demo, and that transcript/screenshot are sample or from a specific run. Truthful; no fake capabilities.
- **Acceptance criteria:**
  - [x] Doc exists in `docs/demo-proof/` and is linked or easy to find.
  - [x] Doc describes what was run, what to notice, README alignment, and labeling of sample/live evidence.
  - [x] Doc is concise and credible; no misleading claims.
- **Status:** [x]

---

### Task 6: Add README pointer to demo proof set

- **What:** Add one sentence or link in the root README (e.g. in the One-minute demo section or immediately after it) so a reviewer can find the demo proof set quickly (e.g. "Demo evidence: see [docs/demo-proof/](docs/demo-proof/).").
- **Acceptance criteria:**
  - [x] README contains a pointer to the demo proof set (sentence or link).
  - [x] Pointer is discoverable without scrolling past long sections (e.g. in or right after One-minute demo).
- **Status:** [x]

---

### Task 7: Write completion report

- **What:** After all artifact and doc tasks are done, write a completion report at `project-docs/detec-demo-proof-completion-report.md` with: final status, list of changed/added files, integration result (e.g. reviewer can find artifacts, README aligned), and known limitations.
- **Acceptance criteria:**
  - [x] `project-docs/detec-demo-proof-completion-report.md` exists.
  - [x] Report includes completed task list summary, changed files, and known limitations.
- **Status:** [x]

---

## Completion

- Tasks 2–6 must pass QA before Task 7. Task 7 (completion report) is written after integration.
- Maximum 3 retries per task before marking blocked. EvidenceQA validates: artifacts exist, align with README, are labeled where sample-based, and are readable/credible.

# Claude Code Lab Plan: Process Alignment and Execution

**Purpose:** Plan and execute a Claude Code lab run at the same level of detail as LAB-RUN-014 (Claude Cowork), with full INIT-43 alignment, correlation rules, required outputs, and optional capture automation. This document is the orchestrator plan for running or re-running Claude Code validation.

**References:**
- Protocol: [LAB-RUN-001-claude-code-install-and-runtime.md](LAB-RUN-001-claude-code-install-and-runtime.md)
- Results: [LAB-RUN-001-RESULTS.md](LAB-RUN-001-RESULTS.md), [LAB-RUN-002-RESULTS.md](LAB-RUN-002-RESULTS.md)
- Process template: [LAB-RUN-014-claude-cowork-install-and-runtime.md](LAB-RUN-014-claude-cowork-install-and-runtime.md), [LAB-RUN-014-RESULTS.md](LAB-RUN-014-RESULTS.md)
- Signal map: [init-issues/INIT-43-claude-process-file-network-signal-map.md](../init-issues/INIT-43-claude-process-file-network-signal-map.md)
- Index: [docs/lab-runs-and-results.md](../docs/lab-runs-and-results.md)

---

## 1. Lab run process (target level of detail)

Match the following structure so the Claude Code lab satisfies INIT-43 and playbook Section 12.

### 1.1 Protocol document must include

| Element | LAB-RUN-001 current | LAB-RUN-014 reference | Action |
|--------|----------------------|------------------------|--------|
| **INIT-43 reference** | Missing | Section "INIT-43 Reference" + link to INIT-43 | Add explicit INIT-43 ref and required-outputs list |
| **INIT-43 signal map alignment table** | Missing | Table mapping INIT-43 layers (Process/File/Network) to protocol captures | Add table mapping proc.path, parent_chain, child_chain; artifact.path/type/last_modified; net.dest_*, net.proc_link_confidence to phase captures |
| **Correlation rules C1–C4** | Not in protocol | Phase 5.2 "Correlation Rule Evaluation" with C1–C4 checkboxes | Add Phase 5.2 C1–C4 evaluation block; ensure RESULTS fill it |
| **Required outputs (INIT-43)** | Implicit in Phase 5 | Explicit list: per-layer report, confidence trace, correlation rule evaluation, residual ambiguity | Add "INIT-43 Validation Plan Coverage" subsection with the four required outputs |
| **Evidence inventory** | Present | Present with phase-by-phase checklist | Keep; ensure any new capture script matches it |
| **Phases** | Baseline, 1–4, Phase 5 analysis | Baseline, 1–4 + Phase 3 split (3A/3B/3C), Phase 5 | Keep 001 phases; Phase 3 is single "agentic" phase (no 3A/3B/3C split unless we add scenarios) |

### 1.2 Results document must include

| Output | LAB-RUN-001-RESULTS | Required |
|--------|---------------------|----------|
| Per-layer signal capture report | Section 1 Signal Observation Matrix | Yes |
| Confidence calculation trace | Section 2 with weights, penalties, final score | Yes |
| Correlation rule evaluation (C1–C4) | Missing | Add; can be short table in RESULTS |
| Residual ambiguity notes | In "Residual Risk" and "Pass/Fail" | Yes |
| Evidence template (Run ID, Date, Tool, Scenario, Observations, Confidence, Policy, Evidence Links, Pass/Fail, Residual Risk) | Section 4 | Yes |
| Findings and playbook feedback | Section 5 (001), Section 5.5 (014) | Yes |

### 1.3 Execution phases (unchanged from LAB-RUN-001)

| Phase | Purpose | Automated? |
|-------|---------|------------|
| **Pre-install: Baseline** | File, process, network, env, persistence baseline; TIMESTAMP_MARKER; EVIDENCE-HASHES | Yes (script) |
| **Phase 1: Installation** | npm install, background monitors (tcpdump, DNS, ps stream), post-install capture, binary metadata, new files, shell profile diff | Partially (install + post-install script; monitors manual or script) |
| **Phase 2: First launch** | Monitors (tcpdump, connections, pstree), `script` session recorder, launch `claude`, auth/idle captures, permission model, strace (Linux) | Partially (post-launch capture script; launch + script session manual) |
| **Phase 3: Agentic session** | Monitors (tcpdump, pstree 1s, inotify/fswatch, connections, strace), task: "Create a simple Python hello world project with a README and a test file, then run the test" (CC-POS-01) or git-heavy task (CC-POS-02), post-task capture | Manual (task and timing operator-driven) |
| **Phase 4: Teardown** | Exit claude, wait, remaining processes, connections diff, home-tree diff, persistence check, MASTER-HASHES | Yes (script) |
| **Phase 5: Analysis** | Signal Observation Matrix, C1–C4, confidence score, evidence template, playbook feedback | Manual (fill RESULTS) |

---

## 2. Scenario options

| Scenario | Protocol | Description | When to use |
|----------|----------|-------------|-------------|
| **CC-POS-01** | LAB-RUN-001 | Standard install, first launch, simple agentic task (hello world + test). | Re-run for new version or INIT-43 alignment; first-time run. |
| **CC-POS-02** | LAB-RUN-001 + task variant | Multi-module project + git (init/add/commit) + tests. Uses same phase structure; task prompt differs. | Validate git IOCs and Co-Authored-By; already done in LAB-RUN-002. |
| **CC-POS-03** | Extension of 001 | Shell tool usage in a sensitive repo context (playbook Section 13 backlog). | Future; not yet protocol-ready. |
| **CC-EVA-01** | Evasion | Renamed binary / wrapper (LAB-RUN-EVASION-001 already has results). | Evasion validation. |

Recommended for "plan a claude code lab" at highest detail:
- **Option A (re-run CC-POS-01):** Execute LAB-RUN-001 as-is on a clean environment; use capture script for baseline/phase1/phase2/phase4; complete Phase 5 with INIT-43 C1–C4 and residual ambiguity; update playbook 12.4/12.5 and calibration fixture if needed.
- **Option B (align then run):** First update LAB-RUN-001 protocol with INIT-43 alignment and Phase 5.2 C1–C4; add capture script; then run as in Option A.

---

## 3. INIT-43 alignment (to add to LAB-RUN-001)

### 3.1 Signal map alignment table (insert after Prerequisites)

| INIT-43 layer | Normalization fields (INIT-43) | Protocol capture |
|---------------|--------------------------------|------------------|
| **Process** | proc.path, parent_chain, child_chain, proc.signer | Phase 1: binary path, npm list, which claude, binary-metadata (hash). Phase 2: claude-process-tree, pstree-stream, claude-tree-idle, auth-processes. Phase 3: pstree-stream (1s), strace-agentic (clone/execve/openat/connect). |
| **File** | artifact.path, artifact.type, artifact.last_modified, artifact.repo_scope | Baseline: home-tree, claude-dir-check, claude-artifact-scan. Phase 1: new-files, claude-dir-post. Phase 2: new-files-at-launch, claude-dir-at-launch, claude-config-contents. Phase 3: workspace-files, workspace-contents, new-files-during-agentic, claude-dir-post-agentic. Phase 4: home-tree-diff, claude-dir-final, claude-artifacts-detail. |
| **Network** | net.dest_ip, net.conn_*, net.proc_link_confidence | Phase 1: install-traffic.pcap, dns-queries. Phase 2: launch-traffic.pcap, connections-stream, outbound-at-launch. Phase 3: agentic-traffic.pcap, connections-stream. (Process-to-socket linkage requires lsof -i per PID or EDR; 2s polling limits attribution.) |

### 3.2 Required outputs (INIT-43 Section 7)

- **Per-layer signal capture report** → LAB-RUN-001-RESULTS Section 1 (Signal Observation Matrix).
- **Confidence calculation trace** → LAB-RUN-001-RESULTS Section 2 (weights, penalties, final_confidence).
- **Correlation rule evaluation** → Add to RESULTS: C1 (high-confidence), C2 (medium), C3 (low), C4 (ambiguity override) with Met / Not met.
- **Residual ambiguity notes** → "Residual Risk" in completed evidence template and in RESULTS summary.

---

## 4. Capture script plan (claude-code-capture.sh)

**Goal:** Automate baseline, phase1 (post-install only; install and monitors remain manual), phase2 (post-launch only; launch and `script` manual), and phase4 so the operator runs fewer copy-paste blocks and can focus on Phase 3 and Phase 5.

**Location:** `lab-runs/scripts/claude-code-capture.sh`

**Usage (target):**

```bash
export LAB_DIR=~/claude-lab/LAB-RUN-001   # or LAB-RUN-002
./lab-runs/scripts/claude-code-capture.sh baseline
# Operator: run npm install -g @anthropic-ai/claude-code (and optionally monitors per protocol)
./lab-runs/scripts/claude-code-capture.sh phase1
# Operator: start script, launch claude, complete auth; then run phase2 capture
./lab-runs/scripts/claude-code-capture.sh phase2
# Optional: phase2 --with-monitors (connection + pstree stream in background; stop in phase4)
# Operator: Phase 3 manual (task, monitors, post-task capture)
# Operator: exit claude, exit script
./lab-runs/scripts/claude-code-capture.sh phase4
```

**Script responsibilities:**

- **baseline:** Create `$LAB_DIR/{baseline,phase1-install,phase2-launch,phase3-agentic,phase4-teardown}`; run all baseline commands from LAB-RUN-001 (file, process, network, env, persistence); TIMESTAMP_MARKER; EVIDENCE-HASHES.
- **phase1:** Post-install capture only (npm list -g, which claude, binary metadata, new-files since baseline, claude-dir-post, shellprofile diffs, crontab diff); TIMESTAMP_MARKER; EVIDENCE-HASHES. Do not run `npm install` or tcpdump/ps stream (operator does that).
- **phase2:** Post-launch capture only (claude-process-tree, claude-tree-idle, new-files-at-launch, claude-dir-at-launch, claude-config-contents, listening-ports-during-auth, outbound-at-launch). Optional `--with-monitors`: start connections-stream and pstree-stream in background; write PIDs to phase2-launch/monitor-pids.txt.
- **phase4:** If monitor-pids.txt exists, kill monitors; then run all phase4 teardown commands (remaining-processes, pstree-post-exit, connections-post-exit, connections-diff, listening-ports-post, claude-dir-final, home-tree-final, home-tree-diff, claude-artifacts-detail, shellprofile diffs, crontab/service/LaunchAgent diffs); phase4-end-time; EVIDENCE-HASHES; MASTER-HASHES.

**Platform:** Support macOS (lsof, pstree if available) and Linux (ss/tcpdump/strace where noted). Skip tcpdump/strace in script if no sudo; document in script header.

---

## 5. Task breakdown (dev-eng / subagents)

| # | Task | Owner | Deliverable |
|---|------|-------|-------------|
| 1 | Add INIT-43 section to LAB-RUN-001 protocol | Dev-eng / doc | LAB-RUN-001: INIT-43 reference, signal map alignment table, Phase 5.2 C1–C4, "INIT-43 Validation Plan Coverage" with four required outputs. |
| 2 | Add C1–C4 correlation evaluation to LAB-RUN-001-RESULTS template (Section 5) | Dev-eng / doc | Protocol Phase 5.2 and RESULTS template include C1–C4 table; existing RESULTS can be backfilled with one line. |
| 3 | Implement claude-code-capture.sh | Dev-eng / DevOps | Script: baseline, phase1, phase2, phase4; optional --with-monitors for phase2; LAB_DIR env; macOS + Linux friendly. |
| 4 | Document claude-code-capture.sh in lab-runs/scripts/README.md | Dev-eng | README: usage, LAB_DIR, phase3 manual, link to LAB-RUN-001. |
| 5 | Update docs/lab-runs-and-results.md | Dev-eng | Add row for claude-code-capture.sh in Capture scripts section when script exists. |
| 6 | (Optional) Backfill LAB-RUN-001-RESULTS with C1–C4 evaluation | Dev-eng | One-time edit: add "## 2.5 Correlation Rule Evaluation (INIT-43)" with C1–C4 Met/Not met from existing narrative. |
| 7 | (Optional) Add calibration fixture LAB-RUN-002.json if missing | Dev-eng | Fixture for CC-POS-02 for calibration regression. |

---

## 6. Execution checklist (single run)

- [ ] Environment: Node v18+, npm, tcpdump (sudo), script, pstree; LAB_DIR set; phase dirs created.
- [ ] Baseline: Run baseline capture (script or manual).
- [ ] Phase 1: Start monitors (tcpdump, DNS, ps stream); run `npm install -g @anthropic-ai/claude-code`; stop monitors; run post-install capture (script or manual).
- [ ] Phase 2: Start monitors (tcpdump, connections, pstree); start `script`; launch `claude`; complete auth; capture auth/idle state; stop monitors; timestamp and hashes.
- [ ] Phase 3: Start monitors (tcpdump, pstree 1s, file watcher, connections, strace if Linux); run agentic task (CC-POS-01 or CC-POS-02); post-task capture; stop monitors; timestamp and hashes.
- [ ] Phase 4: Exit claude and script; wait; run teardown capture; MASTER-HASHES.
- [ ] Phase 5: Fill Signal Observation Matrix, C1–C4, confidence trace, evidence template, playbook feedback in RESULTS.
- [ ] Post-run: Update playbook Section 12.5 Lab Run Log and 12.4 Methodology if needed; add/update calibration fixture; run `pytest collector/tests/test_calibration.py -v`; archive evidence per 9.4.

---

## 7. Success criteria

- Protocol has explicit INIT-43 alignment and required-outputs list.
- RESULTS contain all four INIT-43 outputs: per-layer report, confidence trace, correlation rule evaluation, residual ambiguity.
- If capture script is implemented: baseline, phase1, phase2, phase4 runnable via script; Phase 3 and Phase 5 remain manual.
- One logical run (CC-POS-01 or CC-POS-02) completed with evidence hashes and RESULTS filled; playbook and calibration updated as appropriate.

---

**Plan version:** 1.0  
**Last updated:** 2026-03-12

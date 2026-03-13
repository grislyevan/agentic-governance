# Agent prompt: Run Claude Code root-access lab (LAB-RUN-001-root)

Use this prompt to have another agent (or yourself in a fresh session) execute the Claude Code root-access rerun. The lab requires a machine where you can run `sudo tcpdump` and have Node/npm and the `claude` CLI installed (or install it during the run). Several steps are interactive (browser auth, typing the agentic task in the Claude Code prompt).

---

## Prompt (copy below)

**Task:** Run the Claude Code root-access lab rerun for the Detec project (LAB-RUN-001-root). Follow the runbook exactly so we get full process-to-network linkage and can update calibration.

**Repo:** This workspace is the agentic-governance (Detec) repo. All paths are relative to the repo root.

**Runbook:** Read and follow [lab-runs/LAB-RUN-001-ROOT-RERUN.md](lab-runs/LAB-RUN-001-ROOT-RERUN.md). Use evidence directory `~/claude-lab/LAB-RUN-001-root/`.

**Steps to execute:**

1. **Set up and baseline**  
   Set `export LAB_DIR=~/claude-lab/LAB-RUN-001-root`. From repo root, run:  
   `./lab-runs/scripts/claude-code-capture.sh baseline`  
   Ensure the baseline phase completes (check for `$LAB_DIR/baseline/TIMESTAMP_MARKER` and EVIDENCE-HASHES.txt).

2. **Phase 1 (install with tcpdump)**  
   Start `sudo tcpdump -i any -w "$LAB_DIR/phase1-install/install-traffic.pcap" &` and note the PID.  
   Run `npm install -g @anthropic-ai/claude-code`.  
   Stop tcpdump: `sudo kill $TCPDUMP_PID`.  
   Run `./lab-runs/scripts/claude-code-capture.sh phase1`.  
   Ensure phase1 evidence exists under `$LAB_DIR/phase1-install/`.

3. **Phase 2 (first launch)**  
   Start tcpdump: `sudo tcpdump -i any -w "$LAB_DIR/phase2-launch/launch-traffic.pcap" &`.  
   Start terminal recorder: `script -q "$LAB_DIR/phase2-launch/terminal-session.log"`.  
   Run `claude` and complete browser authentication.  
   When Claude Code is idle at the prompt, in a **second terminal** (with `LAB_DIR` set): run  
   `./lab-runs/scripts/claude-code-capture.sh phase2`.  
   Stop tcpdump and any connection-stream loop, then type `exit` to leave the script session.

4. **Phase 3 (agentic task)**  
   Start tcpdump: `sudo tcpdump -i any -w "$LAB_DIR/phase3-agentic/agentic-traffic.pcap" &`.  
   In the terminal where Claude Code is running, run the agentic task: paste or type exactly:  
   `Create a simple Python hello world project with a README and a test file, then run the test.`  
   Wait for the task to complete. Capture workspace and `~/.claude` state per the runbook (or run the protocol’s Phase 3 post-task captures). Stop tcpdump: `sudo kill $TCPDUMP_PID`.

5. **Phase 4 (teardown)**  
   Exit Claude Code (`/exit` or Ctrl+C). After a short wait, run:  
   `./lab-runs/scripts/claude-code-capture.sh phase4`.

6. **Phase 5 (analysis)**  
   Open [lab-runs/LAB-RUN-001-root-RESULTS.md](lab-runs/LAB-RUN-001-root-RESULTS.md). Fill in:  
   - Section 1: Signal Observation Matrix (per-layer strengths; note network improvement from pcap).  
   - Section 2: Correlation rules C1–C4 (met/not met).  
   - Section 3: Confidence score and band; state whether `unresolved_proc_net_linkage` penalty is 0 or 0.05.  
   - Section 4: Completed lab run evidence template (same format as LAB-RUN-001-RESULTS Section 4).  
   - Section 5: Calibration notes (fixture path and whether to run `pytest collector/tests/test_calibration.py` after adding a fixture).

**Constraints:**

- You need **sudo** for tcpdump. If the environment cannot run sudo or tcpdump, report that and complete as much as possible without it (network layer will remain weak).
- Phase 2 and Phase 3 require **interactive** steps: browser auth for Claude Code, and typing the agentic task. Do not fabricate evidence; if a step cannot be done (e.g. no browser), record what was skipped.
- Do not overwrite the original LAB-RUN-001 evidence; use only `~/claude-lab/LAB-RUN-001-root/`.

**Success criteria:**

- Evidence directories `baseline`, `phase1-install`, `phase2-launch`, `phase3-agentic`, `phase4-teardown` exist under `$LAB_DIR` with expected capture files (including pcaps for phase1, phase2, phase3 when sudo was used).
- LAB-RUN-001-root-RESULTS.md is filled with the run date, signal matrix, C1–C4, confidence score/band, and completed evidence template.
- If you added or updated a calibration fixture, run `pytest collector/tests/test_calibration.py -v` and report pass/fail.

**Reference:** Full protocol detail (optional monitors, strace, etc.) is in [lab-runs/LAB-RUN-001-claude-code-install-and-runtime.md](lab-runs/LAB-RUN-001-claude-code-install-and-runtime.md). The runbook [LAB-RUN-001-ROOT-RERUN.md](lab-runs/LAB-RUN-001-ROOT-RERUN.md) is the source of truth for this root rerun.

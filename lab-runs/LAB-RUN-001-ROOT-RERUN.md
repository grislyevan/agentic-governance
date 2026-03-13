# Claude Code Lab: Root-Access Rerun (CC-POS-01 with full visibility)

**Purpose:** Rerun LAB-RUN-001 with root/sudo so that tcpdump and process-to-network linkage can be captured. Use results to update calibration (fixture and optionally `CLAUDE_CODE_WEIGHTS`) and document confidence with full visibility.

**Base protocol:** [LAB-RUN-001-claude-code-install-and-runtime.md](LAB-RUN-001-claude-code-install-and-runtime.md)  
**Evidence directory:** `~/claude-lab/LAB-RUN-001-root/` (separate from original run so existing evidence is preserved)

---

## Prerequisites

- Same as LAB-RUN-001: Node 18+, bash/zsh, `script`, `pstree`, **and** `tcpdump` (requires sudo).
- **Root/sudo** available for: `sudo tcpdump`, and on Linux `sudo strace` if desired.
- Optional: `fswatch` (macOS) or `inotifywait` (Linux) for Phase 3 file watcher.

---

## Checklist

### 0. Evidence directory and env

```bash
export LAB_DIR=~/claude-lab/LAB-RUN-001-root
mkdir -p "$LAB_DIR"/{baseline,phase1-install,phase2-launch,phase3-agentic,phase4-teardown}
```

From repo root, capture script (use same script; it reads `LAB_DIR`):

```bash
export LAB_DIR=~/claude-lab/LAB-RUN-001-root
./lab-runs/scripts/claude-code-capture.sh baseline
```

---

### 1. Phase 1: Install with network capture (root)

Start **tcpdump** before install so npm/registry traffic is captured and attributable:

```bash
# Terminal A (with sudo)
sudo tcpdump -i any -w "$LAB_DIR/phase1-install/install-traffic.pcap" &
TCPDUMP_PID=$!
```

Then run install (no sudo):

```bash
npm install -g @anthropic-ai/claude-code
```

Stop tcpdump, then run script phase1:

```bash
sudo kill $TCPDUMP_PID 2>/dev/null
./lab-runs/scripts/claude-code-capture.sh phase1
```

---

### 2. Phase 2: First launch with tcpdump and script

Start **tcpdump** and optional connection/pstree streams (see LAB-RUN-001 Phase 2 "Start Background Monitors"):

```bash
# Terminal A
sudo tcpdump -i any -w "$LAB_DIR/phase2-launch/launch-traffic.pcap" &
TCPDUMP_PID=$!
```

Start **script** so the full terminal session is recorded:

```bash
script -q "$LAB_DIR/phase2-launch/terminal-session.log"
claude
```

Complete auth in the browser. When Claude Code is idle at the prompt, in **another terminal** (with `LAB_DIR` set):

```bash
# Optional: connection stream every 2s
while true; do
  echo "=== $(date -u +%H:%M:%S) ===" >> "$LAB_DIR/phase2-launch/connections-stream.txt"
  lsof -i -nP >> "$LAB_DIR/phase2-launch/connections-stream.txt" 2>/dev/null
  sleep 2
done &
CONN_PID=$!
```

Run phase2 capture (stops any monitors started by the script if you used `--with-monitors`):

```bash
./lab-runs/scripts/claude-code-capture.sh phase2
# or: phase2 --with-monitors if you want the script to start connection/pstree streams
```

Stop tcpdump and connection loop:

```bash
sudo kill $TCPDUMP_PID 2>/dev/null
kill $CONN_PID 2>/dev/null
```

Then exit the `script` session (type `exit`).

---

### 3. Phase 3: Agentic task with tcpdump

Start **tcpdump** for the agentic window:

```bash
sudo tcpdump -i any -w "$LAB_DIR/phase3-agentic/agentic-traffic.pcap" &
TCPDUMP_PID=$!
```

(Optional: 1s pstree and connection streams per LAB-RUN-001 Phase 3.)

In the same terminal where `claude` is running (or start `script` in phase3 dir and then `claude`), run the agentic task:

```
Create a simple Python hello world project with a README and a test file, then run the test.
```

After the task completes, capture workspace and state per protocol (workspace files, `~/.claude` diff, etc.), then stop tcpdump:

```bash
sudo kill $TCPDUMP_PID 2>/dev/null
```

---

### 4. Phase 4: Teardown

Exit Claude Code (`/exit` or Ctrl+C), wait a few seconds, then:

```bash
export LAB_DIR=~/claude-lab/LAB-RUN-001-root
./lab-runs/scripts/claude-code-capture.sh phase4
```

---

### 5. Phase 5: Analysis and RESULTS

1. **Signal Observation Matrix**  
   Fill Section 5.1 in [LAB-RUN-001-root-RESULTS.md](LAB-RUN-001-root-RESULTS.md) from your evidence. With pcap you can attribute TLS/SNI to the claude process; note whether **unresolved_proc_net_linkage** still applies or can be removed.

2. **Correlation rules C1–C4**  
   Fill Section 5.2 (C1–C4 met/not met) per INIT-43.

3. **Confidence score**  
   Compute five-layer weighted score and penalties. If network is now attributable, penalty may be 0; document final score and band (Medium vs High).

4. **Evidence template**  
   Fill the completed lab run template (Section 4 style in LAB-RUN-001-RESULTS).

5. **Playbook feedback**  
   Note any differences from LAB-RUN-001 (e.g. "With root, network layer 0.65; no unresolved_proc_net_linkage penalty").

---

## After the run

- **Fixture:** Add or update a calibration fixture. Options: (a) add `LAB-RUN-001-root.json` with the new signals/penalties and expected band, or (b) update `LAB-RUN-001.json` if this run replaces the non-root run as the canonical CC-POS-01.
- **Weights:** If the root run consistently scores in a different band, consider tuning `CLAUDE_CODE_WEIGHTS` in `collector/engine/confidence.py` and re-running `pytest collector/tests/test_calibration.py`.
- **Docs:** Update [docs/lab-runs-and-results.md](docs/lab-runs-and-results.md) and playbook Section 12.5 with the root run date and result (e.g. "LAB-RUN-001 root rerun: High with full visibility").

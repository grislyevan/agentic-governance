# Lab run capture scripts

## cowork-capture.sh

Executable capture script for Claude Cowork (LAB-RUN-014). Implements baseline, phase1, phase2, and phase4 from [LAB-RUN-014-claude-cowork-install-and-runtime.md](../LAB-RUN-014-claude-cowork-install-and-runtime.md). Phase 3 (session analysis) is manual (session UUIDs and paths vary).

**Usage:**

```bash
export LAB_DIR=~/cowork-lab/LAB-RUN-014   # optional; default is ~/cowork-lab/LAB-RUN-014
./cowork-capture.sh baseline
./cowork-capture.sh phase1
# Launch Claude Desktop, then:
./cowork-capture.sh phase2
# Optional: run with connection and process stream monitors (INIT-43 linkage)
./cowork-capture.sh phase2 --with-monitors
# ... later, after quitting Claude:
./cowork-capture.sh phase4
```

Phase 4 stops any monitors started with `phase2 --with-monitors` and refreshes phase2 EVIDENCE-HASHES. Complete Phase 3 (3A/3B/3C) manually per protocol; then run Phase 5 analysis in LAB-RUN-014-RESULTS.md.

---

## claude-code-capture.sh

Executable capture script for Claude Code (LAB-RUN-001 / LAB-RUN-002). Implements baseline, phase1 (post-install only), phase2 (post-launch only), and phase4 from [LAB-RUN-001-claude-code-install-and-runtime.md](../LAB-RUN-001-claude-code-install-and-runtime.md). Phase 3 (agentic session) is manual: operator runs monitors, `script`, and the agentic task per protocol.

**Usage:**

```bash
export LAB_DIR=~/claude-lab/LAB-RUN-001   # optional; default is ~/claude-lab/LAB-RUN-001
./claude-code-capture.sh baseline
# Operator: run "npm install -g @anthropic-ai/claude-code" (and optionally tcpdump/ps monitors per protocol)
./claude-code-capture.sh phase1
# Operator: start script, launch claude, complete auth; then run phase2 capture
./claude-code-capture.sh phase2
# Optional: run with connection and pstree stream monitors (INIT-43 linkage)
./claude-code-capture.sh phase2 --with-monitors
# ... complete Phase 3 (agentic task) manually, then exit claude and script ...
./claude-code-capture.sh phase4
```

Phase 4 stops any monitors started with `phase2 --with-monitors` and refreshes phase2 EVIDENCE-HASHES. Complete Phase 3 and Phase 5 analysis per LAB-RUN-001 protocol and LAB-RUN-001-RESULTS.md.

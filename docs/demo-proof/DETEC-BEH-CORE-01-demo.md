# DETEC-BEH-CORE-01 — Autonomous Shell Fan-Out

**Status:** Available
**Generated:** 2026-03-24 (representative output from test harness)

---

## Detection Output

```text
[DETEC-BEH-CORE-01] Autonomous Shell Fan-Out

Detected process: claude (pid=48291)
Parent: claude (pid=48291)

Shell fan-out events (last 60s):
- bash -c "git status" (pid=48301, t=+0.0s)
- bash -c "npm run build" (pid=48302, t=+2.1s)
- bash -c "python tests/run_all.py" (pid=48303, t=+4.3s)
- bash -c "git diff HEAD~1" (pid=48304, t=+6.7s)

Spawn rate: 0.67 shells/sec (threshold: 0.20)

Policy:
detect

Confidence: 0.71 (Medium-High)
Evidence layers: process_tree[0.82], behavioral[0.74], scanner[0.68]

Summary:
Autonomous shell fan-out pattern detected. Spawn rate and command diversity are
inconsistent with interactive developer shell usage.
```

---

## Event Trace

Events that triggered this detection, in order:

| # | Event Type | Detail | Timestamp |
|---|-----------|--------|-----------|
| 1 | `ProcessExecEvent` | `claude` (pid=48291) launched; process tree established | +0.0s |
| 2 | `ProcessExecEvent` | `bash -c "git status"` spawned by pid=48291 (pid=48301) | +0.0s |
| 3 | `ProcessExecEvent` | `bash -c "npm run build"` spawned by pid=48291 (pid=48302) | +2.1s |
| 4 | `ProcessExecEvent` | `bash -c "python tests/run_all.py"` spawned by pid=48291 (pid=48303) | +4.3s |
| 5 | `ProcessExecEvent` | `bash -c "git diff HEAD~1"` spawned by pid=48291 (pid=48304) | +6.7s |

---

## Evidence Summary

| Confidence Layer | Signal | Weight |
|-----------------|--------|--------|
| Process tree (L1) | 4 shell children of single parent within 60s window; parent is tracked AI tool process | 0.82 |
| Behavioral (L2) | Spawn rate 0.67 shells/sec exceeds interactive-developer threshold (0.20); command diversity (git, npm, python) | 0.74 |
| Scanner (L3) | Process name `claude` matched Claude Code scanner profile | 0.68 |

Combined confidence: **0.71 (Medium-High)**

---

## Policy Outcome

`detect` — visibility outcome. Session recorded. No enforcement action taken.

---

## Test Command

```bash
python -m pytest collector/tests/test_behavioral_core_detections.py -k "DETEC_BEH_CORE_01" -v
```

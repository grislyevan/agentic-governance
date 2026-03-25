# DETEC-BEH-CORE-02 — Agentic Read-Modify-Write Loop

**Status:** Available
**Generated:** 2026-03-24 (representative output from test harness)

---

## Detection Output

```text
[DETEC-BEH-CORE-02] Agentic Read-Modify-Write Loop

Detected process: cursor (pid=61022)

Read-modify-write cycles detected (last 120s):
- READ  src/engine/policy.py        (t=+0.0s)
- WRITE src/engine/policy.py        (t=+1.3s, delta=+247 bytes)
- READ  src/engine/policy.py        (t=+2.8s)
- WRITE src/engine/policy.py        (t=+4.1s, delta=+89 bytes)
- READ  src/engine/policy.py        (t=+5.6s)
- WRITE src/engine/policy.py        (t=+6.9s, delta=-34 bytes)

Cycle count: 3 (threshold: 3)
Files involved: src/engine/policy.py

Policy:
warn

Confidence: 0.78 (High)
Evidence layers: file_activity[0.85], behavioral[0.79], scanner[0.72]

Summary:
Read-modify-write loop detected on source file. Cycle count, timing, and pattern
are consistent with model-driven code iteration rather than manual editing.
```

---

## Event Trace

Events that triggered this detection, in order:

| # | Event Type | Detail | Timestamp |
|---|-----------|--------|-----------|
| 1 | `ProcessExecEvent` | `cursor` (pid=61022) active; scanner match confirmed | +0.0s |
| 2 | `FileReadEvent` | `src/engine/policy.py` read by pid=61022 | +0.0s |
| 3 | `FileChangeEvent` | `src/engine/policy.py` written by pid=61022 (+247 bytes) | +1.3s |
| 4 | `FileReadEvent` | `src/engine/policy.py` read by pid=61022 (second cycle) | +2.8s |
| 5 | `FileChangeEvent` | `src/engine/policy.py` written by pid=61022 (+89 bytes) | +4.1s |

---

## Evidence Summary

| Confidence Layer | Signal | Weight |
|-----------------|--------|--------|
| File activity (L1) | 3 complete read→write cycles on same file within 120s; alternating pattern confirmed (not bulk-copy) | 0.85 |
| Behavioral (L2) | Cycle cadence (avg 2.3s read-to-write latency) consistent with model inference time; delta sizes vary (model editing, not templating) | 0.79 |
| Scanner (L3) | Process name `cursor` matched Cursor scanner profile | 0.72 |

Combined confidence: **0.78 (High)**

---

## Policy Outcome

`warn` — user receives a warning notification. Session recorded. No blocking action taken.

---

## Test Command

```bash
python -m pytest collector/tests/test_behavioral_core_detections.py -k "DETEC_BEH_CORE_02" -v
```

# DETEC-BEH-CORE-04 — Agent Execution Chain

**Status:** Available
**Generated:** 2026-03-24 (representative output from test harness)

---

## Detection Output

```text
[DETEC-BEH-CORE-04] Agent Execution Chain

Detected process: claude (pid=48291)

Chain events:
- NETWORK api.anthropic.com:443 (t=+0.0s) [LLM API call]
- EXEC    bash -c "python src/main.py --patch" (pid=48305, t=+3.2s) [shell execution]
- WRITE   src/main.py (t=+4.8s, delta=+512 bytes) [file write]
- EXEC    git commit -am "fix: update error handler" (pid=48306, t=+6.1s) [git activity]

Chain complete: network → shell → file/git (within 180s window)
Chain duration: 6.1s

Policy:
detect

Confidence: 0.76 (Medium-High)
Evidence layers: network[0.88], process_tree[0.79], file_activity[0.74], behavioral[0.71]

Summary:
Agent execution chain detected. LLM API call followed by shell execution and
file/git activity within the configured window matches the canonical agentic
loop pattern.
```

---

## Event Trace

Events that triggered this detection, in order:

| # | Event Type | Detail | Timestamp |
|---|-----------|--------|-----------|
| 1 | `NetworkConnectEvent` | Outbound TCP to `api.anthropic.com:443` by pid=48291 | +0.0s |
| 2 | `ProcessExecEvent` | `bash -c "python src/main.py --patch"` spawned by pid=48291 (pid=48305) | +3.2s |
| 3 | `FileChangeEvent` | `src/main.py` written by pid=48305 (+512 bytes) | +4.8s |
| 4 | `ProcessExecEvent` | `git commit -am "fix: update error handler"` spawned by pid=48291 (pid=48306) | +6.1s |

---

## Evidence Summary

| Confidence Layer | Signal | Weight |
|-----------------|--------|--------|
| Network (L1) | Outbound to `api.anthropic.com` — classified as known LLM API endpoint; initiates chain window | 0.88 |
| Process tree (L2) | Shell child (bash) and git child spawned from same parent (pid=48291) within chain window | 0.79 |
| File activity (L3) | Source file write from shell child within window; followed by git commit — persistence confirmed | 0.74 |
| Behavioral (L4) | All three phases present (network → shell → file/git) in correct order; total chain duration 6.1s | 0.71 |

Combined confidence: **0.76 (Medium-High)**

---

## Policy Outcome

`detect` — visibility outcome. Session recorded. No enforcement action taken.

**Session report:** Session reports aggregate the full execution chain into structured output. Available via:

```bash
detec scan --verbose
curl -H "Authorization: Bearer <api-key>" https://<server>/api/sessions/<session-id>/report
```

See [session-report-demo.md](session-report-demo.md) for example session report output.

---

## Test Command

```bash
python -m pytest collector/tests/test_behavioral_core_detections.py -k "DETEC_BEH_CORE_04" -v
```

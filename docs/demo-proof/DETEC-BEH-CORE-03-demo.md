# DETEC-BEH-CORE-03 — Sensitive Access Followed by Outbound Activity

**Status:** Available
**Generated:** 2026-03-24 (representative output from test harness)

---

## Detection Output

```text
[DETEC-BEH-CORE-03] Sensitive Access Followed by Outbound Activity

Detected process: claude (pid=48291)

Sensitive path access detected:
- ~/.aws/credentials
- .env

Related outbound activity:
- api.anthropic.com
- unknown external destination

Correlation window: 300s
Time from sensitive access to outbound: 14.2s

Policy:
approval_required

Confidence: 0.84 (High)
Evidence layers: file_activity[0.91], network[0.86], behavioral[0.78], scanner[0.71]

Summary:
Sensitive configuration access was followed by outbound model/network activity
within the configured correlation window. Analyst review required before
proceeding.
```

---

## Event Trace

Events that triggered this detection, in order:

| # | Event Type | Detail | Timestamp |
|---|-----------|--------|-----------|
| 1 | `ProcessExecEvent` | `claude` (pid=48291) active; scanner match confirmed | +0.0s |
| 2 | `FileReadEvent` | `~/.aws/credentials` read by pid=48291 | +0.0s |
| 3 | `FileReadEvent` | `.env` read by pid=48291 | +1.4s |
| 4 | `NetworkConnectEvent` | Outbound TCP connection to `api.anthropic.com:443` by pid=48291 | +14.2s |
| 5 | `NetworkConnectEvent` | Outbound TCP connection to uncategorized external host (185.x.x.x:443) by pid=48291 | +14.9s |

---

## Evidence Summary

| Confidence Layer | Signal | Weight |
|-----------------|--------|--------|
| File activity (L1) | Access to `~/.aws/credentials` and `.env` — both classified as sensitive credential/config paths | 0.91 |
| Network (L2) | Outbound to `api.anthropic.com` (known model API) and uncategorized external host within correlation window | 0.86 |
| Behavioral (L3) | Temporal correlation: 14.2s from sensitive file access to first outbound connection; within 300s window | 0.78 |
| Scanner (L4) | Process name `claude` matched Claude Code scanner profile | 0.71 |

Combined confidence: **0.84 (High)**

---

## Policy Outcome

`approval_required` — session held pending analyst approval. Analyst must review and approve or deny before execution continues.

---

## Test Command

```bash
python -m pytest collector/tests/test_behavioral_core_detections.py -k "DETEC_BEH_CORE_03" -v
```

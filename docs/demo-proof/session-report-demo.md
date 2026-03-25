# Session Report Demo

**Status:** Available
**Generated:** 2026-03-24 (representative output from test harness)

Detec aggregates detection events into session reports that summarize tool activity, action counts, risk signals, and the final policy decision for a session. Session reports are available via `detec scan --verbose` and the API.

---

## Example Session Report Output

```text
=== Detec Session Report ===

session_id:     sess_a3f8c2d1e94b
tool:           claude-code
endpoint_id:    endpoint_macbook-dev-01
start_time:     2026-03-24T09:14:03Z
end_time:       2026-03-24T09:21:47Z
duration:       7m 44s

--- Action Counts ---

Action                          Count
------------------------------  -----
LLM API calls                      14
Shell executions                   31
File reads                         58
File writes                        27
Git commits                         4
Network connections                16
Sensitive path accesses             2

--- Risk Signals ---

Signal                                              Severity    Rule
--------------------------------------------------  ----------  -------------------------
Autonomous Shell Fan-Out                            Medium      DETEC-BEH-CORE-01
Agent Execution Chain                               Medium      DETEC-BEH-CORE-04
Sensitive Access Followed by Outbound Activity      High        DETEC-BEH-CORE-03

--- Confidence Score ---

Layer                       Score
--------------------------  ------
Process tree (L1)           0.82
File activity (L2)          0.88
Network (L3)                0.86
Behavioral (L4)             0.79
Scanner (L5)                0.74

Aggregate confidence:       0.82 (High)

--- Policy Decision ---

policy_decision:    approval_required
enforcement_taken:  none (enforcement_enabled: false — pilot visibility mode)
audit_trail_id:     audit_9c4d1a7f

--- Summary ---

Session recorded 14 LLM API calls, 31 shell executions, and 2 sensitive path
accesses followed by outbound activity. Three behavioral detections fired:
DETEC-BEH-CORE-01, DETEC-BEH-CORE-03, DETEC-BEH-CORE-04. Highest-severity
outcome (approval_required) applied per policy ladder.

Analyst action required: review session detail in dashboard and approve or deny.
```

---

## API Request

```bash
curl -H "Authorization: Bearer <api-key>" \
  https://<server>/api/sessions/sess_a3f8c2d1e94b/report
```

## CLI

```bash
detec scan --verbose
```

The `--verbose` flag includes session report output in the scan result printed to stdout.

---

## Related

- [DETEC-BEH-CORE-04 demo](DETEC-BEH-CORE-04-demo.md) — Agent Execution Chain (the detection most associated with full session aggregation)
- [docs/behavioral-core-demo-pack.md](../behavioral-core-demo-pack.md) — full demo pack for all four core detections

# Session report demo

**What it is:** A concise summary of agent activity for the current (or recent) window: tool name, duration, action counts (file reads/writes, shell commands, model calls), and risk signals. Detec can produce session reports from the **collector** (telemetry on the endpoint) and from the **API** (aggregated detection events).

---

## Command

From repo root, after install:

```bash
pip install -e .
detec-agent session-report
```

Or run a normal scan and append the session report:

```bash
detec-agent scan --session-report
```

No API is required for the CLI; the agent uses local telemetry and scan results.

---

## Example output

```text
Agent Session Detected

tool: Claude Cowork
duration: 4m18s

actions:
- 53 file reads
- 8 file writes
- 3 shell commands
- 2 model calls

risk signals:
- credential access
- repo modification
```

When telemetry is limited (e.g. polling-only or no events in the window), counts may show `N/A` or `0` with a short note. Risk signals are derived from detection evidence (action type, behavioral patterns, MITRE tactics).

---

## Why it matters

Session reports make Detec feel **intelligent** instead of just "tool on/off." They answer:

- **What did this agent do?** Action counts and duration.
- **What should we care about?** Risk signals (credential access, repo modification, etc.) in plain language.

That sits on top of Detec’s existing **multi-layer behavioral correlation** (process tree, telemetry, confidence, policy). Pushing toward **agent session understanding** puts Detec in a category most security tools do not yet address.

---

## API sessions vs collector sessions

| | **API-aggregated sessions** | **Collector telemetry sessions** |
|--|-----------------------------|-----------------------------------|
| **Source** | Stored `detection.observed` events in the central API. | Event store on the endpoint (process, file, network events) plus scan results. |
| **Session boundary** | Consecutive events for the same endpoint + tool within a configurable window (e.g. 15 minutes). One session = one time span per (endpoint, tool). | Current retention window (e.g. last 2 minutes) of telemetry; one report per detected tool for that window. |
| **Action counts** | Not available from event payloads today; API reports N/A with a note. | Filled from telemetry when available: file writes (created/modified), shell execs, model calls (LLM endpoints). File reads = N/A until telemetry supports them. |
| **Risk signals** | Derived from each event’s `action.type`, `action.risk_class`, and `mitre_attack.techniques`. | Derived from scan result: `action_type`, `action_risk`, behavioral pattern IDs (e.g. BEH-006, BEH-007). |
| **Use case** | SOC view over time: "What sessions did we see for this endpoint?" | Live or recent view on the machine: "What did this agent just do?" |

Both use the same **risk label set** (credential access, repo modification, etc.); no separate taxonomy. The API is for historical/aggregate analysis; the collector is for real-time or recent session summaries on the endpoint.

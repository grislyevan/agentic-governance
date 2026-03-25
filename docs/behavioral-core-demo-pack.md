# Behavioral Core Demo Pack

This document shows what each of the four core behavioral detections triggers on, what evidence it produces, and how to run it locally. Each detection is backed by a test fixture in `collector/tests/test_behavioral_core_detections.py` and produces representative output in `docs/demo-proof/`.

---

## DETEC-BEH-CORE-01 — Autonomous Shell Fan-Out

### What it detects

Detects autonomous command execution patterns consistent with AI agents rather than normal interactive developer shell usage. Specifically: a single parent process spawning multiple shell child processes in rapid succession, at a rate and volume inconsistent with human typing.

### Trigger Conditions

- A tracked process spawns ≥3 distinct shell child processes (e.g., `bash`, `sh`, `zsh`) within a configurable window (default: 60 seconds).
- The spawning rate exceeds the interactive-developer threshold (configurable; default: >1 shell spawn per 5 seconds sustained).
- At least one spawned command includes non-trivial arguments (not just `bash -i` or bare shell invocations).

### Expected Output

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

### Policy Default

`detect` — visibility outcome; no enforcement action.

### Evidence Layers That Contribute

| Layer | Signal |
|-------|--------|
| Process tree (L1) | Parent–child spawn relationships and timing |
| Behavioral (L2) | Spawn rate vs interactive-developer threshold |
| Scanner (L3) | Process name matched against known AI tool scanner |

### How to Run

```bash
python -m pytest collector/tests/test_behavioral_core_detections.py -k "DETEC_BEH_CORE_01" -v
```

Demo artifact: [docs/demo-proof/DETEC-BEH-CORE-01-demo.md](demo-proof/DETEC-BEH-CORE-01-demo.md)

---

## DETEC-BEH-CORE-02 — Agentic Read-Modify-Write Loop

### What it detects

Detects AI-assisted code modification loops, not just the presence of AI coding tools. The pattern is: repeated cycles of file read, followed by file modification, in a tight loop — consistent with a model iterating on code rather than a developer making manual edits.

### Trigger Conditions

- The same file (or files in the same directory) is read and then written ≥3 times within a configurable window (default: 120 seconds).
- Reads and writes alternate in a read → write → read → write pattern (not bulk-copy behavior).
- The process responsible is a known AI coding tool or exhibits other AI-agent indicators.

### Expected Output

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

### Policy Default

`warn` — user receives a warning notification; no blocking.

### Evidence Layers That Contribute

| Layer | Signal |
|-------|--------|
| File activity (L1) | Read/write event sequence and timing on the same file |
| Behavioral (L2) | Cycle count and alternating read/write pattern |
| Scanner (L3) | Process matched against known AI coding tool scanner |

### How to Run

```bash
python -m pytest collector/tests/test_behavioral_core_detections.py -k "DETEC_BEH_CORE_02" -v
```

Demo artifact: [docs/demo-proof/DETEC-BEH-CORE-02-demo.md](demo-proof/DETEC-BEH-CORE-02-demo.md)

---

## DETEC-BEH-CORE-03 — Sensitive Access Followed by Outbound Activity

### What it detects

Detects sequences where sensitive configuration or credential files are accessed and then followed by outbound model or network activity within a correlation window. This pattern indicates potential credential exfiltration risk or unauthorized use of secrets by an AI agent.

### Trigger Conditions

- A tracked process reads a sensitive path (e.g., `~/.aws/credentials`, `.env`, `~/.ssh/id_rsa`, `*.pem`, keychain-adjacent files).
- Within the correlation window (default: 300 seconds), the same process or a child process initiates an outbound network connection.
- The outbound destination matches a known model API endpoint or an uncategorized external host.

### Expected Output

```text
[DETEC-BEH-CORE-03] Sensitive Access Followed by Outbound Activity

Sensitive path access detected:
- ~/.aws/credentials
- .env

Related outbound activity:
- api.anthropic.com
- unknown external destination

Policy:
approval_required

Confidence: 0.84 (High)
Evidence layers: file_activity[0.91], network[0.86], behavioral[0.78], scanner[0.71]

Summary:
Sensitive configuration access was followed by outbound model/network activity
within the configured correlation window. Analyst review required before
proceeding.
```

### Policy Default

`approval_required` — session is held pending analyst approval before execution continues.

### Evidence Layers That Contribute

| Layer | Signal |
|-------|--------|
| File activity (L1) | Access to sensitive credential/config paths |
| Network (L2) | Outbound connection to model API or uncategorized external host |
| Behavioral (L3) | Temporal correlation between file access and outbound activity |
| Scanner (L4) | Process matched against known AI tool scanner |

### How to Run

```bash
python -m pytest collector/tests/test_behavioral_core_detections.py -k "DETEC_BEH_CORE_03" -v
```

Demo artifact: [docs/demo-proof/DETEC-BEH-CORE-03-demo.md](demo-proof/DETEC-BEH-CORE-03-demo.md)

---

## DETEC-BEH-CORE-04 — Agent Execution Chain

### What it detects

Detects the canonical agent loop: an LLM API call, followed by shell or interpreter execution, followed by a file write or git activity, all within a time window. This is the foundational agentic pattern — a model receiving context, executing code, and persisting output.

### Trigger Conditions

- An outbound connection to a known LLM API endpoint (e.g., `api.anthropic.com`, `api.openai.com`) is observed.
- Within the chain window (default: 180 seconds), a shell execution event occurs (child process matching shell or interpreter patterns).
- Within the same window, a file write or `git` command is observed from the same process tree.
- All three phases must occur in order: network → shell → file/git.

### Expected Output

```text
[DETEC-BEH-CORE-04] Agent Execution Chain

Detected process: claude (pid=48291)

Chain events:
- NETWORK api.anthropic.com:443 (t=+0.0s) [LLM API call]
- EXEC    bash -c "python src/main.py --patch" (pid=48305, t=+3.2s) [shell execution]
- WRITE   src/main.py (t=+4.8s, delta=+512 bytes) [file write]
- EXEC    git commit -am "fix: update error handler" (pid=48306, t=+6.1s) [git activity]

Chain complete: network → shell → file/git (within 180s window)

Policy:
detect

Confidence: 0.76 (Medium-High)
Evidence layers: network[0.88], process_tree[0.79], file_activity[0.74], behavioral[0.71]

Summary:
Agent execution chain detected. LLM API call followed by shell execution and
file/git activity within the configured window matches the canonical agentic
loop pattern.
```

### Policy Default

`detect` — visibility outcome; no enforcement action.

### Evidence Layers That Contribute

| Layer | Signal |
|-------|--------|
| Network (L1) | Outbound connection to known LLM API endpoint |
| Process tree (L2) | Shell or interpreter child process spawned in window |
| File activity (L3) | File write or git command in same process tree and window |
| Behavioral (L4) | Temporal ordering and chain completion (all three phases present) |

### How to Run

```bash
python -m pytest collector/tests/test_behavioral_core_detections.py -k "DETEC_BEH_CORE_04" -v
```

Demo artifact: [docs/demo-proof/DETEC-BEH-CORE-04-demo.md](demo-proof/DETEC-BEH-CORE-04-demo.md)

**Session reports:** For DETEC-BEH-CORE-04, session reports aggregate the full chain into a structured output (tool, duration, action counts, risk signals). Session reports are available via `detec scan --verbose` and the API (`GET /api/sessions/<session-id>/report`). See [docs/demo-proof/session-report-demo.md](demo-proof/session-report-demo.md) for example output.

---

## Demo Proof Index

All demo artifacts and representative output are in:

→ [docs/demo-proof/README.md](demo-proof/README.md)

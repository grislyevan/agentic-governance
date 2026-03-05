# Detec

**See what AI agents do. Govern what they're allowed to.**

Endpoint governance for agentic AI tools

---

## The Problem

AI coding tools run code, access networks, and modify files on developer endpoints. Claude Code executes shell commands autonomously. Cursor spawns agent processes that write to the filesystem. Ollama runs large language models locally with no cloud visibility.

Security teams have no consistent way to detect which agentic tools are active, what they're doing, or whether they comply with policy. App-name blocklists don't work when tools rename, wrap, or run locally.

---

## What Detec Finds

Detec scans endpoints for agentic AI tools using a class-based detection model. Detection targets capability and risk, not product names — so new tools map to existing policy automatically.

| Class | Category | Examples |
|---|---|---|
| **A** | SaaS Copilots | Cursor, GitHub Copilot, Continue |
| **B** | Local Runtimes | Ollama, LM Studio |
| **C** | Autonomous Executors | Claude Code, Open Interpreter, Aider, GPT-Pilot, Cline |
| **D** | Open Source / Reference | OpenClaw |

**11 tools today. Class-based detection means new tools map to existing policy.**

---

## How Detec Decides

Every detection is built from five signal layers — no single signal drives enforcement alone.

```
Process   File   Network   Identity   Behavior
   \       |       |          |       /
    ╲      |       |          |      ╱
     ╲     |       |          |     ╱
      ╲    |       |          |    ╱
       ╲   |       |          |   ╱
        ▼  ▼       ▼          ▼  ▼
     ┌─────────────────────────────┐
     │    Attribution Engine       │
     │    Multi-signal correlation │
     │    Confidence scoring       │
     └─────────────┬───────────────┘
                   │
                   ▼
            Confidence Score
          (0.00 → 1.00, explainable)
                   │
                   ▼
           Policy Decision
       (Detect / Warn / Approve / Block)
```

Confidence is scored, explainable, and auditable. Every decision traces back to the signals that produced it.

---

## What You Control

Detec's enforcement ladder lets your policy define the friction level.

```
  ┌──────────┐    ┌──────────┐    ┌──────────────────┐    ┌──────────┐
  │  Detect  │ →  │   Warn   │ →  │ Approval Required│ →  │  Block   │
  │          │    │          │    │                  │    │          │
  │ Visibility    │ Operator │    │ Someone must     │    │ Hard stop│
  │ only     │    │ notified │    │ approve          │    │          │
  └──────────┘    └──────────┘    └──────────────────┘    └──────────┘
```

- **Low-risk tools** get visibility. Your team knows what's running.
- **Medium-risk tools** trigger warnings. Operators stay informed.
- **High-risk tools** require approval. Governance without guesswork.
- **Policy violations** are blocked. Enforcement with evidence.

Your policy defines which tools land where. Detec enforces it.

---

## Audit and Evidence

Every detection event is a structured, auditable record:

- **What** was detected (tool, class, version)
- **How** it was detected (which signal layers matched)
- **How confident** the detection is (0.00–1.00 score with contributing weights)
- **What policy** was applied (enforcement state + rule ID)
- **What action** was taken (detect / warn / approval required / block)

Events follow a canonical JSON schema designed for SIEM integration, compliance reporting, and forensic review.

---

## Known Limits

We publish our limits because trust is earned, not assumed.

- **Containerized/remote dev environments** reduce host-level telemetry. Process and file signals may be partial.
- **Custom forks and renamed binaries** require behavior-layer correlation. Single-layer process detection alone won't catch them.
- **Short-lived network connections** (sub-second HTTPS bursts) need EDR or endpoint security framework integration for reliable process-to-socket attribution. Polling-based capture has blind spots.
- **Evasion is possible.** We test for it (lab-validated evasion runs), document the vectors, and design multi-signal correlation to raise the cost of evasion.

---

## Start a Pilot

Deploy the Detec collector on a small endpoint group. Review detections against your tool inventory. Validate confidence scores and policy decisions against your expectations.

No agents to install permanently. No network reconfiguration. Results in minutes.

**Contact:** [your-email@domain.com]

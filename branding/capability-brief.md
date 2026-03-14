---
title: "Detec: Discover and Control Autonomous AI Tools on Developer Endpoints"
subtitle: Capability Brief
version: "1.0"
date: 2026-03-12
---

# See what AI agents do. Govern what they're allowed to.

Detec discovers and controls autonomous AI tools on developer endpoints. These tools run code, access networks, and modify files with minimal visibility. Claude Code executes shell commands autonomously. Cursor spawns agent processes. Ollama runs large language models locally with no cloud telemetry. Application blocklists fail when tools rename, wrap, or run as local processes.

**Detec** is an endpoint agent that detects autonomous AI tools by capability class, scores attribution confidence across five evidence layers, and enforces graduated policy with auditable decisions.

**Primary use case:** Repo-destructive coding agents. Class C tools (Claude Code, Aider, Open Interpreter, Cursor agent mode) execute shell, write files, and mutate repos. Detec detects them, scores confidence, and enforces policy so high-risk actions on sensitive assets can be blocked while lower-risk use stays visible.

## What We Detect

Detec ships 12 named scanners covering four capability classes:

| Class | Category | Tools | Risk Profile |
|-------|----------|-------|-------------|
| **A** | SaaS Copilots | Cursor, GitHub Copilot, Continue | Assistive, cloud-mediated |
| **B** | Local Runtimes | Ollama, LM Studio | Local inference, no code execution |
| **C** | Autonomous Executors | Claude Code, Aider, Open Interpreter, GPT-Pilot, Cline | Shell access, file writes, network calls |
| **D** | Persistent Agents | OpenClaw | Long-running, self-restarting, multi-step |

A behavioral scanner detects 8 agentic patterns (shell fan-out, LLM API cadence, multi-file burst writes, read-modify-write loops, autonomous session duration, credential access, git automation, process resurrection) that catch renamed or unknown tools through behavior rather than signatures.

## How We Decide

Every detection is scored across five signal layers. No single signal drives enforcement.

| Layer | What It Captures |
|-------|-----------------|
| Process | Binary identity, parent-child lineage, command chains |
| File | Config files, session caches, model storage |
| Network | API destinations, burst cadence, process-connection linkage |
| Identity | User/account mapping, credential context |
| Behavior | Temporal action sequences, prompt-edit-commit loops |

Confidence is scored 0.00 to 1.00 and classified into bands: **Low** (<0.45), **Medium** (0.45-0.74), **High** (>=0.75). Hard enforcement requires at least two aligned layers, one of which must be Process or Behavior.

**Lab-validated scores** (10 completed lab runs):

- Claude Code: 0.71-0.77 (Medium), projected 0.82 with EDR enrichment
- Cursor: 0.79 (High, first High without EDR)
- Claude Cowork: 0.905 (highest of any profiled tool)
- OpenClaw: 0.725-0.80 (Medium to High)
- Ollama: 0.69 (Medium)
- Open Interpreter: 0.525 (Medium)

## What We Enforce

Four-state enforcement ladder, mapped to tool class and confidence band:

1. **Detect**: Log and monitor. No user disruption.
2. **Warn**: Alert operator. Create policy awareness.
3. **Approval Required**: Hold pending human decision.
4. **Block**: Terminate process, null-route network, or delegate to EDR.

15 baseline policy rules (from Playbook v0.4.0 Section 6.3) ship with every tenant. Policies are deterministic: given the same signals, the same decision is produced every time. Enforcement posture is per-endpoint (passive, audit, active) and centrally managed.

## Proof and Validation

| Metric | Value |
|--------|-------|
| Lab runs completed | 10 (across 7 tools, 2 platforms) |
| Calibration fixtures | 8 replay harnesses run on every CI push |
| Evasion testing | LAB-RUN-EVASION-001: 6 vectors tested against identity signals |
| Automated tests | 400+ (233 collector, 122 API, 45 protocol) |
| Behavioral patterns | 8 (BEH-001 through BEH-008) |
| Baseline policies | 15 rules seeded per tenant |

Every detection produces a canonical JSON event with: tool attribution, confidence score, signal sources, policy rule applied, decision rationale, and enforcement outcome. Events are SIEM-ready (webhook delivery with HMAC signing, Splunk HEC recipe included).

## Known Limits

We publish these so buyers can assess fit honestly:

- **Containerized/remote dev** reduces host-level telemetry. Detection relies on the endpoint where the tool runs.
- **Custom forks** of known tools require behavioral correlation; named-process matching alone is insufficient.
- **Short-lived network connections** need EDR enrichment for reliable attribution (Detec integrates with CrowdStrike Falcon for server-side enrichment).
- **Identity signal evasion** is possible: LAB-RUN-EVASION-001 proved git trailer suppression succeeds 6/6 vectors. Identity is treated as a one-way signal (high confidence when present, zero when absent).
- **5 scanners** (Aider, GPT-Pilot, Cline, LM Studio, Continue) have synthetic test coverage but await live lab validation.

## Next Step

We scope pilots at 5-25 endpoints over 2-4 weeks. Success criteria are defined before deployment: detection coverage for your tool inventory, false positive rate below your threshold, and enforcement decisions your SOC team agrees with.

**Contact**: hello@detec.io

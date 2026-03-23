---
title: "Detec: Discover and Control Autonomous AI Tools on Developer Endpoints"
subtitle: Capability Brief
version: "1.1"
date: 2026-03-21
---

# See what AI agents do. Govern what they're allowed to.

Detec discovers and controls autonomous AI tools on developer endpoints. It detects tools by capability class, scores attribution confidence across five evidence layers, and applies deterministic policy decisions with auditable rule IDs. It also reconstructs agent sessions — the ordered sequence of actions an agent took (LLM request → shell exec → file write → git commit) — giving analysts behavioral context alongside the enforcement decision.

**Primary use case:** Repo-destructive coding agents (Class C).

## Validation scope labels used in this brief

- **Live-validated:** confirmed with completed lab run evidence and/or runtime tests.
- **Protocol-expected:** fixture/protocol-backed expectation; not equivalent to a full live run.
- **Experimental:** partially implemented or provider-limited.

## What We Detect

Detec ships named scanners across four capability classes:

| Class | Category | Tools | Validation scope |
|-------|----------|-------|------------------|
| **A** | SaaS Copilots | Cursor, GitHub Copilot, Continue | Mixed (Cursor/Copilot live; Continue protocol-expected) |
| **B** | Local Runtimes | Ollama, LM Studio | Mixed (Ollama live; LM Studio protocol-expected) |
| **C** | Autonomous Executors | Claude Code, Aider, Open Interpreter, GPT-Pilot, Cline, Cursor agent mode, Claude Cowork | Mixed (Claude Code, Open Interpreter, Cursor, Cowork, Aider live; GPT-Pilot/Cline protocol-expected) |
| **D** | Persistent Agents | OpenClaw | Live-validated only for OpenClaw reference implementation |

A behavioral scanner family tracks 9 agentic patterns (shell fan-out, API cadence, burst writes, read-modify-write loops, session duration, credential access, git automation, process resurrection, LLM→shell→file/git chains).

## How We Decide

Confidence score: 0.00–1.00

- **Low:** <0.45
- **Medium:** 0.45–0.74
- **High:** >=0.75

Hard enforcement requires at least two aligned layers, with one from Process or Behavior.

## Evidence snapshot (as documented now)

**Lab runs listed in the run index:** 16 completed entries with protocol + RESULTS in [docs/lab-runs-and-results.md](../docs/lab-runs-and-results.md).

**Live vs protocol-expected qualifiers:**

- **Live-validated examples:** Claude Code, Cursor, OpenClaw, Claude Cowork (primary run), Open Interpreter, Ollama, Aider.
- **Protocol-expected examples:** Claude Code root rerun (Path B), Cowork gap run (CW-POS-02/03), Cline, Continue, LM Studio, GPT-Pilot.

**Class D scope statement (evidence-aligned):**

- Class D policy logic is implemented in runtime and baseline policy.
- Empirical Class D tool coverage is currently validated against OpenClaw as the reference implementation.
- Language about Class D generalization should be treated as design intent until additional persistent-agent tools are live-validated.

## What We Enforce

Four-state ladder: **Detect → Warn → Approval Required → Block**.

Baseline policy set: 15 rules (6 enforcement, 3 Class D, 3 overlay, 3 fallback).

### Enforcement availability by tactic / OS / caveat

| Tactic | Linux | macOS | Windows | Status | Caveat |
|--------|-------|-------|---------|--------|--------|
| Process kill | Available | Available | Available | Live-validated | Process-tree kill + command-line guard |
| Network null-route | Available (cgroup v2 preferred; UID fallback optional) | Available (`pf`) | Available (`netsh`) | Live-validated | Linux UID fallback may have collateral impact |
| Proxy injection | Available | Available | Available | Live-validated when configured | Env-based and process-model dependent |
| EDR delegate enforcement | Experimental | Experimental | Experimental | Protocol-expected / partial | CrowdStrike path is partial maturity |
| ISO-001 container isolation overlay | Advisory only | Advisory only | Advisory only | Inactive in baseline | Rule exists but `is_active: false` |

## Proof and Validation

| Metric | Value |
|--------|-------|
| Lab run entries with protocol + RESULTS | 16 ([docs/lab-runs-and-results.md](../docs/lab-runs-and-results.md)) |
| Calibration fixtures | Lab-run fixtures in [collector/tests/fixtures/lab_runs/](../collector/tests/fixtures/lab_runs/) |
| Evasion testing | LAB-RUN-EVASION-001 (6 vectors) |
| Behavioral patterns | 9 |
| Baseline policies | 15 |
| Automated tests (rolling snapshot) | 1,318 collected on 2026-03-21 via `.venv/bin/pytest ... --collect-only -q` (849 collector + 421 API + 48 protocol) |

**Test-count methodology:** use rolling collected counts (`--collect-only`) as point-in-time evidence; do not treat any single number as fixed marketing baseline.

## Known Limits (explicit)

- Containerized/remote dev can reduce host-level telemetry.
- Renamed/custom forks require behavior-layer correlation.
- Short-lived network bursts need EDR/kernel enrichment for reliable process attribution.
- Identity-trailer evasion exists and is documented (LAB-RUN-EVASION-001).
- Class D empirical coverage is currently limited to one reference implementation.

## Next Step

Pilot scope: 5–25 endpoints over 2–4 weeks with explicit success criteria (coverage, false positives, and SOC acceptance of enforcement decisions).

**Contact:** Hello@detecadg.com

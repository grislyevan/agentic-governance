# Pilot Intake Brief

**Date:** 2026-03-24 | **Version:** 0.4.0

This document is a one-page intake summary for security teams evaluating Detec. It covers what the product does, what it does not do, what you need to deploy it, and what to expect from output quality during a pilot.

---

## What Detec Does

- **Behavioral detection of AI tools and autonomous agents** on developer endpoints. Detection is based on behavioral pattern (not tool name), using five evidence layers: process signals, file signals, network signals, behavioral patterns, and optional EDR enrichment.
- **Explainable confidence scoring.** Each detection produces a confidence score with per-layer contribution visible to analysts. Scores are classified as High, Medium, or Low.
- **Deterministic policy ladder.** Each detection outcome maps to one of four policy decisions — Detect, Warn, Approval Required, or Block — based on configured rules. Policy logic is auditable and not black-box.
- **Session reconstruction.** The dashboard provides a timeline, risk summary, behavior chains, evidence drill-down, and export (Markdown/JSON) per endpoint session.

---

## What Detec Is Not

- **Not a general-purpose EDR.** Detec is scoped to AI coding tools and autonomous agents. It does not replace endpoint detection for malware, ransomware, or general threat categories.
- **Not a browser filter.** Detec does not monitor browser activity, web traffic, or URL access.
- **Not a prompt logging system.** Detec does not capture or log LLM prompts, completions, or conversation content.

---

## Deployment Prerequisites

| Requirement | Notes |
|-------------|-------|
| Python 3.11+ | Required on each monitored endpoint |
| API server | Must be reachable from endpoints via HTTPS or TCP port 8001 |
| Agent config file | Must include: API URL, API key, endpoint registration |
| Database | PostgreSQL recommended for production; SQLite supported for evaluation and small pilots |
| macOS | Standard user permissions; full disk access recommended for file telemetry; ESF entitlement optional (not required for baseline) |
| Windows | Admin rights for install; agent runs as scheduled task under a user account |
| Linux | User-level process access sufficient for detection; root required for iptables-based network enforcement |

---

## Telemetry Realities

- **Detection is psutil-based polling.** The agent polls process, file, and network state on a configurable interval (default: 60 seconds). Events are batched and sent to the API server.
- **Native telemetry (ESF, ETW, eBPF) is not yet in production.** Do not expect syscall-level precision in this release. Polling telemetry is the baseline for all platforms.
- **High-risk tools commonly report Medium confidence without EDR enrichment.** This is expected, disclosed, and does not indicate a detection failure. Enrichment via CrowdStrike is optional and not a pilot dependency.
- **Short-lived processes between polling cycles may not be captured.** This is a known constraint of interval-based telemetry.

---

## Expected Output Quality Bands

| Confidence Level | Score Range | Typical Cause | Suggested Action |
|------------------|-------------|---------------|-----------------|
| High | ≥ 0.75 | Strong multi-layer corroboration: process + network + file + behavioral signals aligned | Policy enforcement appropriate |
| Medium | 0.45 – 0.74 | Partial corroboration; common when process signals are present but kernel or file evidence is absent | Warn or manual review |
| Low | < 0.45 | Weak signal; may reflect a partial install or inactive agent | Visibility and logging only |

---

## Policy Ladder

| Decision | Behavior | Current Implementation Status |
|----------|----------|-------------------------------|
| Detect | Logged; visibility only | Available |
| Warn | Logged + analyst notification | Available |
| Approval Required | Hold label logged and surfaced in dashboard | Available — execution is not currently blocked pending approval; that is a Roadmap capability |
| Block | Process kill + network null-route (platform constraints apply) | Available — see known constraints below |

---

## Known Constraints for Pilot Teams

- **Confidence at Medium is normal for high-risk tools.** Claude Code and similar tools typically score Medium without EDR or kernel telemetry. This is by design; do not treat Medium as a calibration failure.
- **Linux network block affects all processes under the UID, not just the target.** If enforcement is enabled on Linux, a block decision will null-route outbound traffic for the entire user account. Plan user account isolation accordingly.
- **Approval Required does not currently suspend execution.** The hold label is recorded but the process continues running. If your pilot scenario requires execution suspension pending human approval, this capability is not available in 0.4.0.
- **Windows enforcement posture is limited.** The agent runs as a scheduled task under a user account. System-level enforcement actions are not available on Windows in this release.
- **ISO-001 container isolation is advisory only.** It is defined in policy logic but ships inactive. Do not include it in enforcement scenarios for this pilot.

---

## Questions for Your Security Team

Before expanding a pilot or moving toward production, your security team should be able to answer:

1. **What is the scope of endpoints in scope?** Developer workstations only, or also CI runners, build servers, and shared infrastructure? Detection posture differs by environment type.
2. **What is your acceptable false-positive rate?** Medium-confidence detections require analyst triage. Understand your team's bandwidth for triage before setting policy to Warn or above at that confidence band.
3. **What enforcement posture do you want?** Passive (Detect/Warn only) or active (Block)? Active enforcement has platform-specific side effects — confirm your Linux and Windows posture before enabling Block decisions.
4. **What is your escalation path for Approval Required decisions?** Currently, the hold label is logged but execution is not suspended. Who owns triage of hold-labeled events, and what is the response SLA?
5. **Do you have CrowdStrike deployed?** If yes, CrowdStrike enrichment (Experimental) can improve confidence scoring for covered endpoints. If no, baseline operation is unaffected.

---

Full limitations: [docs/known-limitations.md](known-limitations.md) | Product status: [docs/product-status.md](product-status.md) | Pilot runbook: [docs/pilot-runbook.md](pilot-runbook.md)

# Known Limitations

Detec publishes known limitations openly so teams can govern with accurate information. This page is the authoritative reference for what Detec does not do, where detection coverage is partial, and where policy outcomes differ from their stated intent. Last updated: 2026-03-24.

---

## Telemetry Constraints

- **Psutil-based polling is the production telemetry path.** It captures process, file, and network signals but operates at poll intervals, not in real time. Events between polling cycles are not captured. This is the baseline for all platforms in this release.
- **Detection latency is polling-bounded.** Default scan interval is 60 seconds. Short-lived processes or network connections that complete between cycles may not be captured.
- **Telemetry is process-level, not syscall-level.** Psutil does not provide syscall visibility. Fine-grained file access patterns (e.g., individual reads within a process) are not available.
- **Native telemetry (macOS ESF, Windows ETW, Linux eBPF) is Roadmap.** Scaffolding exists for ESF and ETW but neither is baseline-active. eBPF support is Roadmap. Without native telemetry, detection latency is higher and some low-dwell behaviors may not be captured.
- **High-risk tools commonly report Medium confidence, not High, without EDR enrichment or kernel telemetry.** Claude Code is the documented example. Multi-layer corroboration is incomplete at polling level; this is expected and disclosed.

---

## Confidence Caveats

- **Confidence scores are calibrated against 16+ lab runs.** Scores vary by tool, platform, and environment. Calibration baselines reflect controlled conditions; production environments may produce different distributions.
- **Scores are point-in-time.** A tool that evasion-modifies its behavior signature after calibration may not match baselines. Detec does not continuously recalibrate against live behavior drift.
- **Evasion testing covers 6 validated Claude Code trailer/attribution suppression vectors.** Other evasion vectors — including novel or tool-specific techniques — may not be covered.
- **Class D (persistent agent) coverage is anchored to the OpenClaw reference implementation.** Other persistent-agent tools may behave differently and may not match Class D detection signatures.

---

## Policy and Enforcement Constraints

- **ISO-001 (container isolation) ships inactive and advisory.** Runtime containerization of already-running processes is not implemented. The rule is defined in policy logic and can be referenced in playbooks, but it does not produce enforcement outcomes.
- **Linux network null-route blocks all outbound traffic for the UID, not just the target process.** This is a constraint of iptables UID-owner matching. Other processes running under the same user account are also affected.
- **Proxy injection enforcement requires that the target process honor HTTP_PROXY / HTTPS_PROXY environment variables.** Processes that hardcode their HTTP client configuration are not affected by proxy injection.
- **Approval Required enforcement behavior depends on posture.** In **active** posture, the collector suspends detected processes (SIGSTOP on macOS/Linux) while polling for an approval decision — execution is genuinely blocked pending human review. In **passive** or **audit** posture, the hold label is logged and surfaced in the dashboard, but execution continues (advisory only). Windows does not support SIGSTOP; enforcement on Windows uses network null-route and process termination instead of suspension.
- **Windows agent runs as a scheduled task under a user account, not a system service.** This limits enforcement posture on Windows — enforcement actions available to a user account are a subset of what a system service can perform.

---

## Deployment Constraints

- **CrowdStrike enrichment is Experimental and optional.** It is not a dependency for pilot deployments. Confidence layer 5 (EDR enrichment) falls back gracefully when no CrowdStrike integration is configured.
- **Multi-tenant isolation is enforced at the API and database layer.** Physical data separation (separate databases or storage per tenant) is not available in this release.
- **High-volume deployments (>500 endpoints) have not been formally load-tested in the current release.** See [docs/large-fleet-scenario.md](large-fleet-scenario.md) and [docs/soak-test-runbook.md](soak-test-runbook.md) for documented test scope and known performance envelopes.

---

## Detection Scope

- **Detec detects AI coding tools and autonomous agents on developer endpoints.** It is not a general-purpose EDR, browser filter, or prompt logging system. It does not monitor browser activity, inspect LLM prompts, or detect non-AI software categories.
- **Detection accuracy depends on tool behavior visible at scan time.** Tools that are installed but not actively running, or that have been significantly modified from their standard behavior profile, may not match scanner signatures.
- **Stealthy or evasion-modified tools may not be detected.** Detec's evasion coverage is defined and bounded; it is not a guarantee of detection against adversarially modified tools.

---

For capability status and roadmap, see [docs/product-status.md](product-status.md).

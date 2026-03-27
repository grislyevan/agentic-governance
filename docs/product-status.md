# Product Status

This page tracks capability maturity across Detec's core components. Use it to understand what is shipping in production, what is partial or provider-limited, and what is planned but not yet implemented. Status labels: **Available** — shipped, production-quality; **Experimental** — partial or provider-limited, not baseline-active; **Roadmap** — planned, not yet implemented.

---

## Detection Capabilities

| Capability | Status | Notes |
|------------|--------|-------|
| DETEC-BEH-CORE-01 — Autonomous Shell Fan-Out | Available | |
| DETEC-BEH-CORE-02 — Agentic Read-Modify-Write Loop | Available | |
| DETEC-BEH-CORE-03 — Sensitive Access Followed by Outbound Activity | Available | |
| DETEC-BEH-CORE-04 — Agent Execution Chain | Available | |
| 5-dimension confidence scoring with calibration regression gate | Available | ECE 0.11 (improved from 0.31); 8 new labeled fixtures |
| Behavioral evasion detection | Available | Validated via EVASION-001 lab run |
| MCP scanner | Available | |
| CrowdStrike enrichment (confidence layer 5) | Experimental | Partial; not required for baseline operation |
| Native macOS ESF telemetry | Experimental | Scaffolding exists; polling-based psutil is the production path |
| Native Windows ETW telemetry | Experimental | Scaffolding exists; polling-based is the production path |
| Native Linux eBPF telemetry | Roadmap | Scaffolding exists; lower fidelity than kernel provider |

---

## Tool Scanners

| Scanner | Status | Validation Type |
|---------|--------|----------------|
| Claude Code | Available | Live |
| Claude Cowork | Available | Live |
| Cursor | Available | Live |
| Ollama | Available | Live |
| GitHub Copilot | Available | Live |
| Open Interpreter | Available | Live |
| OpenClaw | Available | Live |
| Aider | Available | Live |
| Cline | Available | Protocol-expected |
| GPT-Pilot | Available | Protocol-expected |
| LM Studio | Available | Protocol-expected |
| Continue | Available | Protocol-expected |
| Behavioral scanner | Available | |
| Evasion scanner | Available | |
| MCP scanner | Available | |

---

## Enforcement Capabilities

| Capability | Status | Notes |
|------------|--------|-------|
| Process kill (macOS / Linux / Windows) | Available | |
| Network null-route — pfctl (macOS) | Available | |
| Network null-route — iptables (Linux) | Available | Blocks by UID owner; affects all processes for that UID |
| Network null-route — netsh (Windows) | Available | |
| Proxy injection | Available | Requires process model support for env-proxy control |
| ISO-001 container isolation | Available (advisory) | Defined in policy; ships inactive by default — advisory recommendation only |
| EDR delegate enforcement via CrowdStrike RTR | Experimental | Partial; provider-limited |
| Tamper controls (uninstall tokens, decommission, tamper_suspected) | Available | SHA-256 hashed tokens; see [docs/tamper-controls.md](tamper-controls.md) |

---

## Telemetry Providers

| Provider | Status | Notes |
|----------|--------|-------|
| psutil polling (process / file / network) | Available | Production path for all platforms |
| macOS ESF (Endpoint Security Framework) | Experimental | Requires entitlement; not baseline-active |
| Windows ETW (Event Tracing for Windows) | Experimental | Scaffolding; not baseline-active |
| Linux eBPF | Roadmap | Scaffolding; lower signal fidelity without kernel provider |

---

## API + Platform Features

| Feature | Status | Notes |
|---------|--------|-------|
| FastAPI backend — SQLite (default) | Available | |
| FastAPI backend — PostgreSQL | Available | |
| JWT authentication, invite, reset flows | Available | |
| API key support | Available | |
| Multi-tenant isolation | Available | |
| SSO — OIDC / Okta | Available | |
| SIEM integration (JSON export) | Available | Field mapping may require per-org configuration |
| ATT&CK mapping | Available | |
| Stripe billing | Available | |
| HTTP event emitter | Available | |
| TCP binary protocol emitter | Available | |
| Binary protocol gateway (port 8001) | Available | Low-latency agent connections |
| Daemon mode with heartbeat | Available | |
| Session reports via API + CLI | Available | |
| Webhooks | Available | |
| Agent key rotation | Roadmap | Deferred; tracked post-sprint/remediation-1 |

---

## Dashboard + Workflow Features

| Feature | Status | Notes |
|---------|--------|-------|
| React/Vite SOC console | Available | |
| Authentication flows | Available | |
| Endpoints view | Available | |
| Sessions view + session detail | Available | |
| Policies CRUD | Available | |
| Audit log | Available | |
| User management (owner / admin / analyst / viewer) | Available | |
| Webhooks configuration | Available | |
| macOS menu bar GUI + .app/.pkg packaging | Available | MDM deployment supported |
| Windows scheduled task support | Available | Runs under user account, not system service |
| Linux systemd support | Available | |
| Approval flows UI | Roadmap | |
| Exceptions / allow-list UI | Roadmap | |
| Tenant / org switcher | Roadmap | |
| Richer policy editing UI | Roadmap | |

---

## Known Limitations

- High-risk tools such as Claude Code often report Medium confidence without EDR or kernel telemetry. Confidence varies by tool and environment; this is published openly.
- Native telemetry (ESF / ETW / eBPF) is not yet production-ready. The polling-based psutil path is the baseline; it has lower signal fidelity than kernel or EDR providers.
- Linux network block uses UID-owner match via iptables, which blocks all processes running under that UID — not only the target process.
- Proxy injection requires that the target process model supports environment-variable proxy control.
- ISO-001 container isolation is defined in policy logic but ships as an inactive advisory recommendation by default.

For the full list of known limitations, see [docs/known-limitations.md](known-limitations.md) (forthcoming).

---

_Last updated: 2026-03-26_

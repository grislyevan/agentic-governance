# Changelog

All notable changes to the Detec (agentic-governance) project are documented here. The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

## [Unreleased]

(Next release will appear here.)

## [0.2.0-detection-core] — 2026-03-14

Sprint 01: Trust and repo clarity. Introduces canonical behavioral detections and makes the repo credible to security engineers and design partners.

### Canonical behavioral detections

- **DETEC-BEH-CORE-01** — Autonomous shell fan-out from AI agents.
- **DETEC-BEH-CORE-02** — Agentic read-modify-write coding loops.
- **DETEC-BEH-CORE-03** — Sensitive credential/config access followed by outbound activity.
- **DETEC-BEH-CORE-04** — Agent execution chain (LLM then shell then file/git within a window).

Demo artifacts: [Behavioral demo pack](docs/behavioral-core-demo-pack.md), [Demo proof index](docs/demo-proof/README.md) (DETEC-BEH-CORE-01/02/03/04 demos).

### Sprint 01 deliverables

- README reordered around product wedge (hero, core detections, verify in 5 minutes, example output, product status).
- Explicit maturity labels (AVAILABLE / EXPERIMENTAL / ROADMAP) for CrowdStrike and native telemetry.
- Security: seed credentials printed once to stdout only; no plaintext file on disk.
- API bootstrap refactor: `api/startup/` (app_factory, bootstrap, background_tasks); `main.py` under 200 lines; gateway health via `gateway.is_running()`.
- [Architecture overview](docs/architecture-overview.md) and [product status](docs/product-status.md) docs.

## [0.4.0] — 2026-03-14

First tagged release. Aligns with Playbook v0.4 and canonical event schema v0.4.0.

### Shipped in this release

**Endpoint agent (collector)**

- 12 scanners: Claude Code, Claude Cowork, Cursor, Ollama, Copilot, Open Interpreter, Aider, Cline, GPT-Pilot, LM Studio, Continue, OpenClaw; plus behavioral, evasion, and MCP scanners.
- 5-dimension confidence model with playbook-aligned weights; policy engine (visibility / warning / approval / block).
- HTTP and TCP (binary protocol) emitters; daemon mode with configurable interval and heartbeat.
- Telemetry: psutil-based polling (process, file, network). Native providers (ESF, ETW, eBPF) on the roadmap.
- Cross-platform: macOS, Windows, Linux. macOS menu bar GUI and .app/.pkg packaging for MDM.

**API**

- FastAPI backend with SQLite (default) and PostgreSQL; JWT auth, invite and password reset flows.
- Multi-tenant isolation; API key support for headless agents.
- Events, endpoints, policies, users, audit log, webhooks; Stripe billing and tier limits.
- Binary protocol gateway (port 8001) for low-latency agent connections.
- Enterprise-oriented features: SSO, SIEM integration, ATT&CK mapping, compliance baseline policies.

**Dashboard**

- React/Vite SOC console: auth (JWT + API key fallback), endpoints view (filterable, searchable), policies (create, edit, toggle), audit log, user management (owner, admin, analyst, viewer).
- Served by FastAPI at root when built; dev server with hot reload.

**Methodology and schema**

- Playbook v0.4: detection profiles, Rule ID Catalog, enforcement pipeline, weight alignment.
- Canonical event schema v0.4.0; lab runs and calibration fixtures for regression.

### How to run

- Agent: `pip install -e .` then `detec-agent --dry-run --verbose` (see [README](README.md) and [DEPLOY.md](DEPLOY.md)).
- Full stack: build dashboard, start API, open http://localhost:8000 (see [README quick start](README.md#quick-start-full-stack)).

[Unreleased]: https://github.com/your-org/agentic-governance/compare/v0.2.0-detection-core...HEAD
[0.2.0-detection-core]: https://github.com/your-org/agentic-governance/releases/tag/v0.2.0-detection-core
[0.4.0]: https://github.com/your-org/agentic-governance/releases/tag/v0.4.0

# Changelog

All notable changes to the Detec (agentic-governance) project are documented here. The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

## [Unreleased]

### Added

- **Tamper controls:** Uninstall tokens (SHA-256 hashed, shown once at generation), `POST /api/endpoints/{id}/decommission` endpoint, and `tamper_suspected` endpoint status. See [docs/tamper-controls.md](docs/tamper-controls.md).
- **Approval backoff:** Approval poll uses exponential backoff with jitter to prevent thundering-herd on the API during high-concurrency approval windows.
- **Dashboard interactivity:** Summary cards and badges are now clickable; sidebar navigation added for faster operator workflows.
- **Calibration fixtures:** 8 new labeled fixtures added to the calibration regression suite.

### Changed

- **Enforcement module split:** `collector/engine/enforcement.py` (1004 lines) replaced by the `collector/enforcement/` package: `enforcer.py`, `posture.py`, `approval_hold.py`, `network_block.py`, `process_kill.py`, `proxy_inject.py`, `cleanup.py`, `rate_limiter.py`, `service_restore.py`. Public API unchanged.
- **Orchestrator module split:** `collector/orchestrator.py` (1190 lines) split into `collector/orchestrator.py` (975), `collector/event_builder.py` (223), and `collector/decision_engine.py` (77). Public API unchanged.
- **Exception handling:** 16 broad `except Exception:` blocks tightened to specific exception types with structured logging.
- **ECE calibration:** Expected Calibration Error improved from 0.31 to 0.11.
- **CI health check:** Lighthouse health-check loop replaces `sleep` in both the CI workflow and the local dev script for more reliable startup detection.

### Fixed

- **`generate_agent_key()` tuple unpacking:** Fixed a bug that broke tenant creation via the API when generating agent keys.
- **Case-insensitive email lookups:** Auth email matching is now case-insensitive across all paths (register, login, forgot-password, SSO, user creation).
- **Bootstrap seed:** Seed now correctly stores the plaintext agent key for MSI download stamping.

### Security

- **MSI stamper hardened:** Parameterized queries replace f-string SQL interpolation in the MSI stamper; allowlist input validation added.
- **LoginRequest.email:** `max_length=320` added to prevent oversized email payloads.

## [0.4.0] — 2026-03-14

First public release. Aligns with Playbook v0.4 and canonical event schema v0.4.0.

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

[Unreleased]: https://github.com/grislyevan/agentic-governance/compare/v0.4.0...HEAD
[0.4.0]: https://github.com/grislyevan/agentic-governance/releases/tag/v0.4.0

# Agentic Governance — Progress Tracker

**Last updated:** 2026-03-14  
**Current phase:** M5 — enterprise feature set complete; live validation and native telemetry (ESF/ETW/eBPF) in progress.  
**Ultimate goal:** Production SaaS for agentic AI endpoint governance

**What's production-ready:** The stack is feature-complete for pilot and production use: endpoint agent, multi-tenant API, SOC dashboard, billing, SSO, SIEM templates, ATT&CK mapping, and baseline policies. Remaining work is live lab validation for some scanners, native OS telemetry providers (roadmap), and optional multi-region/SLA docs. Limitations and roadmap details are in the Pre-v1.0 table and [docs](docs/) (e.g. [esf-entitlement](docs/esf-entitlement.md), [lab-runs-and-results](docs/lab-runs-and-results.md)).

---

## Current State

| Item | Status |
|---|---|
| Python collector (12 scanners) | Done |
| Cross-platform abstraction layer (`collector/compat/`) | Done |
| Confidence + policy engine | Done |
| NDJSON event output | Done |
| Canonical event schema v0.4.0 | Done |
| Playbook v0.4 (Rule ID Catalog, enforcement pipeline, weight alignment) | Done |
| Synthetic scanner fixture tests (22 tests, 5 scanners) | Done |
| Scan pipeline integration tests (20 tests) | Done |
| Alembic auto-migration on API startup | Done |
| Lab runs (10 completed, 5 pending live validation) | In progress |
| React/Vite dashboard (auth, live data, controls) | Done |
| FastAPI backend (PostgreSQL, JWT, multi-tenancy) | Done |
| User management API (CRUD, roles, auth_provider) | Done |
| Invite + password reset flows (backend + dashboard) | Done |
| Webhook alerts (CRUD, HMAC delivery, dispatcher) | Done |
| macOS agent GUI (menu bar + status window) | Done |
| macOS .app/.pkg packaging for MDM distribution | Done |
| MDM deployment docs (Jamf, Endpoint Central) | Done |
| BSL 1.1 license + ToS + License Agreement | Done |
| SaaS frontend (auth, org management, responsive) | Done |
| Cloud deployment + CI/CD | Done |
| Billing (Stripe, tier limits, dashboard) | Done |
| Enterprise features (SSO, SIEM, ATT&CK, compliance) | Done |

**Completed init issues:** INIT-43 (process/file/network signal map) — complete; LAB-RUN-014/015 and capture script aligned.

---

## Pre-v1.0 / PM Brief (2026-03-12)

Items from the internal technical assessment. Track here until done or explicitly deferred.

| # | Item | Owner | Status |
|---|------|--------|--------|
| 1 | ESF entitlement application (macOS; unlocks full behavioral layer) | Eng | Not started; 3–6 month Apple timeline |
| 2 | Cron/LaunchAgent artifact scanning (user crontab, LaunchAgents for AI binaries) | Eng | Planned |
| 3 | LAB-RUN-015 (Cowork scheduled task, DXT, skill-creator) | Research | Protocol ready; run pending |
| 4 | Aider calibration (LAB-RUN-008 or equivalent; add fixture) | Research | Pending |
| 5 | ISO-001 advisory wording (container isolation = recommendation until implementation) | PM + Eng | Done |
| 6 | Messaging alignment: Claude Code at Medium confidence; API/confidence limitations in docs | PM + Marketing | Pending |

See [docs/esf-entitlement.md](docs/esf-entitlement.md) for ESF status. Claude Cowork scanner added to production scan list (main.py).

---

## Architecture Target (SaaS)

```
Endpoint Agent                  Backend API                  Frontend SaaS
──────────────                  ───────────                  ─────────────
Scanner Modules                 FastAPI App                  React Dashboard
      ↓                         ┌──────────┐                 Policy Config UI
Collector Engine  ──events──▶  │ REST API  │  ◀──────────── Alerts / Notifs
      ↓                         │ Auth/JWT  │
API Client ────────────────────▶│ Multi-ten │
                                │ Event Q   │
                                └────┬─────┘
                                     │
                               PostgreSQL DB
                               ┌─────┴──────┐
                               Stripe  SIEM
                               Billing Integ
```

---

## Milestone M1 — Prototype Complete (Local Tool)

**Goal:** Everything works end-to-end on a single machine with no rough edges.

- [x] Claude Code scanner (LAB-RUN-001, LAB-RUN-002)
- [x] Ollama scanner (LAB-RUN-003)
- [x] Cursor scanner (LAB-RUN-004)
- [x] GitHub Copilot scanner (LAB-RUN-005)
- [x] Open Interpreter scanner (LAB-RUN-006)
- [x] OpenClaw scanner — Class D reference implementation (LAB-RUN-007, LAB-RUN-013 local LLM)
- [x] Confidence scoring engine (Appendix B formula)
- [x] Policy engine (ENFORCE-001 through ENFORCE-D03)
- [x] NDJSON emitter + schema validator
- [x] Canonical event schema v0.2.0
- [x] Evasion detection: Co-Authored-By suppression (LAB-RUN-EVASION-001)
- [x] Playbook v0.3 with Class D taxonomy
- [x] React/Vite dashboard (WIP → fixed)
- [x] 5 new scanner modules: Aider, GPT-Pilot, Cline, LM Studio, Continue
- [x] Claude Cowork scanner module (LAB-RUN-014 — VM-based execution, 0.905 confidence)
- [x] Synthetic fixture tests for 5 new scanners (22 tests: Aider, LM Studio, Continue, GPT-Pilot, Cline)
- [ ] Live lab-validate all 5 new scanners (lab run per tool — synthetic validation complete, live runs pending hardware)
- [x] Schema v0.4.0: `enforcement.applied` example added, enum audit complete (8 live, 10 forward-declared)
- [x] Integration tests for `main.py` end-to-end + scanner stubs
- [ ] Playbook v0.4: integrate findings from new lab runs

**Files:** `collector/scanner/`, `collector/tests/`, `dashboard/src/`, `schemas/`, `playbook/`

---

## Milestone M2 — Backend API (Production-Ready Core)

**Goal:** Replace file-based NDJSON pipeline with a real API and database.

- [x] FastAPI backend scaffolded (`api/`)
- [x] SQLite default database (zero-config, platform-aware path); PostgreSQL supported via `DATABASE_URL`
- [x] Database schema: `events`, `endpoints`, `tenants`, `users`, `policies`, `audit_log`
- [x] JWT authentication: register, login, token refresh
- [x] Per-tenant data isolation (row-level filter on `tenant_id`; owner/admin get cross-tenant read visibility)
- [x] API key support for headless collector agents
- [x] Docker Compose for local dev (API + DB)
- [x] OpenAPI spec auto-generated from FastAPI routes
- [x] Collector HTTP emitter (`collector/output/http_emitter.py`) — POST /events with retry + local buffer fallback
- [x] Persistent endpoint agent daemon (`--interval`, `--api-url`, `--api-key`, `--report-all` flags)
- [x] StateDiffer — change-only reporting with JSON persistence (`collector/agent/state.py`)
- [x] LocalBuffer — offline NDJSON queue flushed on reconnect (`collector/agent/buffer.py`)
- [x] `POST /endpoints/heartbeat` — auto-registers endpoints, updates `last_seen_at`
- [x] OS-level install scripts: macOS LaunchAgent, Linux systemd, Windows Task (`deploy/`); installer builds in `packaging/`
- [x] Cross-platform abstraction layer (`collector/compat/`) — psutil-backed process, network, service, identity, and path abstraction; macOS/Linux/Windows dispatch; Cursor, Ollama, and Copilot scanners migrated
- [x] User management API — CRUD endpoints for tenant users (first_name, last_name, email, role), owner/admin/analyst/viewer roles, auth_provider placeholder for future SSO/SAML, password_reset_required for email provisioning (`api/routers/users.py`, `api/schemas/users.py`)
- [x] macOS agent GUI — rumps-based menu bar app with status window matching Detec branding, PyObjC NSWindow, Icon.icns from app bundle with programmatic fallback (`collector/gui/`)
- [x] Windows agent GUI — pystray tray icon with tkinter status window, matching macOS design. Separate PyInstaller spec (`packaging/windows/detec-agent-gui.spec`)
- [x] Branding icon assets — `branding/Icon.icns` (macOS), `branding/Icon.ico` (Windows, 7 sizes), `branding/Icon.png` (source)
- [x] macOS .app bundle — PyInstaller spec, build script, icon from `branding/Icon.icns`, entitlements plist (`packaging/macos/`)
- [x] macOS .pkg installer — pkgbuild/productbuild, pre/postinstall scripts, distribution XML, LaunchAgent configuration (`packaging/macos/`)
- [x] MDM deployment documentation — Jamf Pro, Endpoint Central, generic MDM; PPPC profile template for Full Disk Access (`docs/mdm-deployment.md`, `docs/macos-permissions.md`)
- [x] Dashboard served from FastAPI — API routes under `/api/`, React SPA served at root, no separate Node process needed
- [x] All 12 scanners migrated to compat layer (cross-platform via psutil)
- [x] Events page — full SOC event browser with filters, pagination, detail panel
- [x] M-28 fix: `approval_required` no longer triggers enforcement
- [x] Integration tests for API endpoints (3 multi-step flows: auth lifecycle, policy lifecycle, event ingestion-to-query)
- [x] Alembic migrations wired up
- [x] Windows Service packaging — `detec-server` CLI with setup/run/install/start/stop/remove commands, pywin32 service wrapper, PyInstaller spec
- [x] Windows collector agent packaging — `detec-agent` CLI with setup/scan/run/install/start/stop/remove commands, pywin32 service wrapper, PyInstaller spec
- [x] Windows lab validation on Windows Server VM (deployed, service running, health OK)
- [x] Cross-platform validation: macOS agent reporting to Windows Server (18 events ingested, endpoint registered)
- [x] Binary wire protocol (`protocol/`): msgpack framing, 13 message types, length-prefixed TCP transport with TLS support
- [x] Gateway server (`api/gateway.py`): asyncio TCP listener, API key auth, event ingestion via shared models, session registry, push support
- [x] TCP emitter (`collector/output/tcp_emitter.py`): persistent connection, auto-reconnect with backoff, batching (50 events/1s), ack tracking, local buffer fallback
- [x] Protocol integration: `--protocol tcp` flag, gateway auto-starts in API lifespan, config loader + CLI support, PyInstaller specs updated
- [x] Protocol test suite: 67 unit tests (wire, messages, connection, gateway, emitter) + end-to-end integration test
- [x] BSL 1.1 license, Terms of Service, Software License Agreement (`LICENSE`, `legal/`)
- [x] Installer EULAs aligned: Windows server (`packaging/windows/installer/license.txt`), macOS agent license screen (`packaging/macos/`)
- [x] Zero-touch agent deployment: server generates pre-configured agent packages via dashboard/API (`GET /api/agent/download`), config loader auto-discovers platform-specific paths, build scripts accept optional baked-in config
- [x] Tenant agent key: server-managed shared key for agent auth, lazy generation on first download, key rotation via `POST /api/agent/key/rotate`, agents authenticate with tenant key (no user API key in packages)
- [x] Email enrollment: admins send download links via `POST /api/agent/enroll-email`, time-limited single-use tokens, SMTP configuration, unauthenticated token-based download at `GET /api/agent/download/{token}`
- [x] Windows agent service startup fixes: SCM dispatch for frozen exe, `signal.signal()` guard for non-main thread, 120s START_PENDING wait hint for slow module loading
- [x] Schema validator uses `sys._MEIPASS` for PyInstaller bundles
- [x] End-to-end deployment validated: macOS agent (18 events) + Windows agent service (6 events) both reporting to Windows Server VM
- [x] Windows GUI installer (`DetecServerSetup.exe`): dark-themed (Slate 900) Inno Setup wizard with indigo accent bar, pre-flight checks, admin account creation, service install, firewall rules, desktop shortcut, uninstaller
- [x] Installer security: admin password passed via env var (not CLI), error tracking with early exit on setup failure, upgrade path stops service before file extraction
- [x] `[dev]` optional-dependencies added to `pyproject.toml` for CI test runner
- [x] Agent download packages bundled into installer: build pipeline builds agent exe, creates zip, places in `dist/packages/` so dashboard downloads work out of the box
- [x] Installer UX polish: brand-voice copy on wizard subtitles and validation messages, post-install health check (polls dashboard for 15s), install log persisted to `C:\ProgramData\Detec\install.log`, finish page guidance text with duplicate-button fix, Shift-click easter egg to open server log
- [x] Asset generator hardened: `_load_font()` fallback chain (bundled/system/Pillow), tagline text on sidebar image, graceful handling of headless Server Core
- [x] Event-driven telemetry foundation (agent-side): `EventStore` ring buffer, `TelemetryProvider` interface, `PollingProvider` (psutil-based fallback), provider registry with `--telemetry-provider auto|native|polling` CLI flag, `BaseScanner` event store injection, all 11 scanners wired
- [x] Server-side EDR enrichment: `EDRProvider` interface, CrowdStrike Falcon stub (OAuth2, token caching), enrichment pipeline (penalty removal, confidence rescoring, band change detection), `telemetry_providers` schema extension, `BackgroundTasks` hook on event ingestion, EDR config in `api/core/config.py`
- [x] 43 new tests: EventStore (14), PollingProvider/registry (12), enrichment pipeline (7), CrowdStrike provider (5), schema validation (5)

**Files:** `api/`, `api/integrations/`, `collector/output/`, `collector/agent/`, `collector/gui/`, `collector/compat/`, `collector/telemetry/`, `collector/providers/`, `packaging/macos/`, `packaging/windows/`, `docs/`, `docker-compose.yml`, `protocol/`, `legal/`, `schemas/`

---

## Milestone M3 — Frontend SaaS UI

**Goal:** Replace the prototype React app with a production-quality multi-tenant dashboard.

- [x] Auth flows: login, register (JWT with auto-refresh, API key fallback)
- [x] Auth flows: invite tokens, password reset (forgot/reset/accept-invite endpoints, SetPasswordPage, ResetPasswordPage)
- [x] User management: CRUD for tenant users, four-role model (owner/admin/analyst/viewer), Admin page UI
- [x] Invite members UI: email/role form on AdminPage, accept-invite route, RBAC enforcement
- [x] Create org flow: multi-org creation and switching (tenants router, memberships model, dashboard org page + switcher)
- [x] Endpoint management: multi-endpoint view with filter, status, signal bars
- [x] Events dashboard: filterable table, confidence bands, enforcement state, time range
- [x] Policy list (read-only, from API)
- [x] Policy configuration UI: create/edit/toggle policies from dashboard (owner/admin)
- [x] Baseline policies: 15 rules from Playbook v0.4.0 seeded per tenant (6 enforcement, 3 Class D, 3 overlay, 3 fallback), restore-defaults endpoint, dashboard category grouping with baseline badges
- [x] Audit log page (read-only, paginated, from API)
- [x] Webhook alerts: CRUD, HMAC-signed delivery, event type filtering, test endpoint, Settings UI
- [x] Real-time updates via 30s polling with pause/resume and "Updated Xs ago" indicator
- [x] Accessible design (ARIA labels, keyboard nav, screen reader support)
- [x] Responsive design (mobile breakpoints across all 9 pages, sidebar hamburger, table overflow, Tailwind)

---

## Milestone M4 — SaaS Infrastructure

**Goal:** Deploy to cloud with billing, observability, and security hardening.

- [x] Cloud deployment: Docker Compose + Caddy TLS, Kubernetes manifests (7 files), Fly.io config
- [x] CI/CD pipeline: release workflow (5 jobs on v* tags), dashboard build in CI, dep scanning
- [x] Stripe integration: subscription tiers (free/pro/enterprise), tier limits, billing dashboard, 23 tests
- [x] Secrets management: decision doc (`docs/secrets-management.md`), platform-native env vars, migration path to Doppler
- [x] Structured logging (JSON in production) + Prometheus metrics (5 counters/histograms/gauges at `/metrics`)
- [x] Uptime monitoring: documented in `SERVER.md` (UptimeRobot, Grafana Cloud, alert escalation)
- [x] Privacy review and data retention: per-tenant `retention_days` (default 90), background purge, admin purge endpoint, `docs/data-privacy.md`
- [x] Security hardening: rate limiting (slowapi on auth endpoints), CORS production mode, input validation audit, dependency scanning CI

---

## Milestone M5 — Enterprise Features

**Goal:** Features needed for SOC/enterprise procurement.

- [x] SSO / OIDC support: authlib integration, login redirect, callback, user auto-provisioning, dashboard SSO button, 9 tests
- [x] SIEM integrations: 5 templates (Splunk HEC, Elastic, Sentinel, PagerDuty, Slack), template API, dashboard selector, `docs/siem-integration.md`
- [x] Compliance reporting: JSON/CSV/PDF export via reportlab, compliance summary endpoint, dashboard export modal, 12 tests
- [x] Evasion detection suite: E1-E5 vectors (git hooks, template hooks, force-push, renamed binaries, Cursor settings), 30 tests
- [x] MITRE ATT&CK tactics mapping: BEH-001..008 and tool classes A-D mapped, schema extension, event enrichment, dashboard column, 21 tests
- [ ] Multi-region deployment option
- [ ] SLA and support tier documentation

---

## Housekeeping

- [x] `scan-results.ndjson` excluded via `.gitignore` (`*.ndjson`)
- [x] `dashboard/dist/` removed from git tracking
- [x] `.env.example` added to `collector/` and `api/`
- [x] `CONTRIBUTING.md` added
- [x] `docker-compose.yml` added at repo root
- [x] Push unpushed commits to `origin/main`
- [ ] Triage INIT-28 through INIT-42 shelved issues
- [x] Add integration tests before M2 merge (3 multi-step flows in `api/tests/test_integration_flows.py`)

---

## Parking Lot

Items that are valuable but not yet scheduled:

| Item | Ref | Notes |
|---|---|---|
| ~~Evasion test suite~~ | ~~INIT-29~~ | Done: `collector/scanner/evasion.py`, 30 tests |
| Replay / simulation mode | INIT-28 | Replay canned events against policy engine |
| Benchmark suite | INIT-31 | Scanner performance, confidence accuracy, FP rate |
| ~~Capability brief~~ | ~~INIT-32~~ | Done (A2, `branding/capability-brief.md`) |
| ~~Demo mode~~ | ~~INIT-37~~ | Done (A1, `api/core/demo_seed.py`, 10 tests) |
| Deep-dive / positioning | INIT-36 | Market positioning document |
| Metrics pipeline | INIT-30 | Detection rate, FP%, policy coverage KPIs |
| ~~MITRE tactics mapping~~ | ~~INIT-40~~ | Done (C3, `collector/engine/attack_mapping.py`, 21 tests) |
| Lab runs 008–012 (live) | — | Aider, GPT-Pilot, Cline, LM Studio, Continue — synthetic validation complete, live runs pending hardware |
| LAB-RUN-013 findings | — | Local LLM variant: confidence floor for infrastructure-class tools, co-residency detection, model-dependent behavioral weights |
| LAB-RUN-014 findings | — | Claude Cowork: VM-based execution model, 10 GB footprint, cleartext identity, "soft proactive" scheduled tasks, DXT cross-app automation, 0.905 confidence (new highest) |
| ~~Active defense roadmap~~ | ~~—~~ | ~~All 6 phases complete (2026-03-12). See `docs/enforcement-remaining-work.md` for final status.~~ |

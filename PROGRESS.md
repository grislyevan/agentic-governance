# Agentic Governance — Progress Tracker

**Last updated:** 2026-03-10  
**Current phase:** M2 — Backend API + Dashboard + Agent Packaging  
**Ultimate goal:** Production SaaS for agentic AI endpoint governance

---

## Current State

| Item | Status |
|---|---|
| Python collector (12 scanners) | Done |
| Cross-platform abstraction layer (`collector/compat/`) | Done |
| Confidence + policy engine | Done |
| NDJSON event output | Done |
| Canonical event schema v0.3.0 | Done |
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
| SaaS frontend (auth, org management) | In progress |
| Cloud deployment + CI/CD | Not started |
| Billing + enterprise features | Not started |

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
- [ ] Schema v0.3.0: add `enforcement.applied` example, finalize enum values
- [ ] Integration tests for `main.py` end-to-end + scanner stubs
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
- [ ] Integration tests for API endpoints
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
- [x] Windows GUI installer (`DetecServerSetup.exe`): branded Inno Setup wizard, pre-flight checks, admin account creation, service install, firewall rules, desktop shortcut, uninstaller
- [x] Installer security: admin password passed via env var (not CLI), error tracking with early exit on setup failure, upgrade path stops service before file extraction
- [x] `[dev]` optional-dependencies added to `pyproject.toml` for CI test runner
- [x] Agent download packages bundled into installer: build pipeline builds agent exe, creates zip, places in `dist/packages/` so dashboard downloads work out of the box
- [x] Installer UX polish: brand-voice copy on wizard subtitles and validation messages, post-install health check (polls dashboard for 15s), install log persisted to `C:\ProgramData\Detec\install.log`, finish page guidance text with duplicate-button fix, Shift-click easter egg to open server log
- [x] Asset generator hardened: `_load_font()` fallback chain (bundled/system/Pillow), tagline text on sidebar image, graceful handling of headless Server Core

**Files:** `api/`, `collector/output/`, `collector/agent/`, `collector/gui/`, `collector/compat/`, `packaging/macos/`, `packaging/windows/`, `docs/`, `docker-compose.yml`, `protocol/`, `legal/`

---

## Milestone M3 — Frontend SaaS UI

**Goal:** Replace the prototype React app with a production-quality multi-tenant dashboard.

- [x] Auth flows: login, register (JWT with auto-refresh, API key fallback)
- [x] Auth flows: invite tokens, password reset (forgot/reset/accept-invite endpoints, SetPasswordPage, ResetPasswordPage)
- [x] User management: CRUD for tenant users, four-role model (owner/admin/analyst/viewer), Admin page UI
- [ ] Org/tenant management: create org, invite members
- [x] Endpoint management: multi-endpoint view with filter, status, signal bars
- [x] Events dashboard: filterable table, confidence bands, enforcement state, time range
- [x] Policy list (read-only, from API)
- [x] Policy configuration UI: create/edit/toggle policies from dashboard (owner/admin)
- [x] Audit log page (read-only, paginated, from API)
- [x] Webhook alerts: CRUD, HMAC-signed delivery, event type filtering, test endpoint, Settings UI
- [x] Real-time updates via 30s polling with pause/resume and "Updated Xs ago" indicator
- [x] Accessible design (ARIA labels, keyboard nav, screen reader support)
- [ ] Responsive design (mobile breakpoints)

---

## Milestone M4 — SaaS Infrastructure

**Goal:** Deploy to cloud with billing, observability, and security hardening.

- [ ] Cloud deployment: containerized API + frontend (fly.io, Render, or AWS ECS)
- [ ] CI/CD pipeline: lint, test, build, deploy on merge to `main`
- [ ] Stripe integration: subscription tiers (free/pro/enterprise), usage metering
- [ ] Secrets management (Doppler or AWS Secrets Manager)
- [ ] Structured logging + distributed tracing (OpenTelemetry)
- [ ] Uptime monitoring and alerting
- [ ] Privacy review and data retention policy (aligns with INIT-41)
- [ ] Security hardening: rate limiting, input validation, dependency scanning

---

## Milestone M5 — Enterprise Features

**Goal:** Features needed for SOC/enterprise procurement.

- [ ] SSO / SAML 2.0 / OIDC support (auth_provider column and password_reset_required flag in place)
- [ ] SIEM integrations: Splunk HEC, Elastic Beats, Microsoft Sentinel (aligns with INIT-28)
- [ ] Compliance reporting: downloadable audit reports (PDF/CSV)
- [ ] Evasion detection suite (aligns with INIT-29, builds on LAB-RUN-EVASION-001)
- [ ] MITRE ATT&CK tactics mapping (aligns with INIT-40)
- [ ] Multi-region deployment option
- [ ] SLA and support tier documentation

---

## Housekeeping

- [x] `scan-results.ndjson` excluded via `.gitignore` (`*.ndjson`)
- [x] `dashboard/dist/` removed from git tracking
- [x] `.env.example` added to `collector/` and `api/`
- [x] `CONTRIBUTING.md` added
- [x] `docker-compose.yml` added at repo root
- [ ] Push unpushed commits to `origin/main` when ready
- [ ] Triage INIT-28 through INIT-42 shelved issues
- [ ] Add integration tests before M2 merge

---

## Parking Lot

Items that are valuable but not yet scheduled:

| Item | Ref | Notes |
|---|---|---|
| Evasion test suite | INIT-29 | Systematic coverage beyond LAB-RUN-EVASION-001 |
| Replay / simulation mode | INIT-28 | Replay canned events against policy engine |
| Benchmark suite | INIT-31 | Scanner performance, confidence accuracy, FP rate |
| Capability brief | INIT-32 | Customer-facing one-pager; needed before M4 |
| Demo mode | INIT-37 | Canned data for live demos; needed before M4 |
| Deep-dive / positioning | INIT-36 | Market positioning document |
| Metrics pipeline | INIT-30 | Detection rate, FP%, policy coverage KPIs |
| Privacy review | INIT-41 | Data minimization + retention; required before M4 |
| MITRE tactics mapping | INIT-40 | Map signals to ATT&CK for enterprise buyers |
| Lab runs 008–012 (live) | — | Aider, GPT-Pilot, Cline, LM Studio, Continue — synthetic validation complete, live runs pending hardware |
| LAB-RUN-013 findings | — | Local LLM variant: confidence floor for infrastructure-class tools, co-residency detection, model-dependent behavioral weights |
| LAB-RUN-014 findings | — | Claude Cowork: VM-based execution model, 10 GB footprint, cleartext identity, "soft proactive" scheduled tasks, DXT cross-app automation, 0.905 confidence (new highest) |

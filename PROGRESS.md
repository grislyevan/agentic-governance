# Agentic Governance — Progress Tracker

**Last updated:** 2026-03-04  
**Current phase:** M1 — Prototype Complete  
**Ultimate goal:** Production SaaS for agentic AI endpoint governance

---

## Current State

| Item | Status |
|---|---|
| Python collector (6 scanners) | Done |
| Confidence + policy engine | Done |
| NDJSON event output | Done |
| Canonical event schema v0.2.0 | Done |
| Playbook v0.3 (Class D taxonomy) | Done |
| Lab runs (8 completed, 5 pending) | In progress |
| React/Vite dashboard | In progress |
| FastAPI backend (PostgreSQL, JWT, multi-tenancy) | Not started |
| SaaS frontend (auth, org management) | Not started |
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
- [x] OpenClaw scanner — Class D reference implementation (LAB-RUN-007)
- [x] Confidence scoring engine (Appendix B formula)
- [x] Policy engine (ENFORCE-001 through ENFORCE-D03)
- [x] NDJSON emitter + schema validator
- [x] Canonical event schema v0.2.0
- [x] Evasion detection: Co-Authored-By suppression (LAB-RUN-EVASION-001)
- [x] Playbook v0.3 with Class D taxonomy
- [x] React/Vite dashboard (WIP → fixed)
- [x] 5 new scanner modules: Aider, GPT-Pilot, Cline, LM Studio, Continue
- [ ] Lab-validate all 5 new scanners (lab run per tool)
- [ ] Schema v0.3.0: add `enforcement.applied` example, finalize enum values
- [ ] Integration tests for `main.py` end-to-end + scanner stubs
- [ ] Playbook v0.4: integrate findings from new lab runs

**Files:** `collector/scanner/`, `dashboard/src/`, `schemas/`, `playbook/`

---

## Milestone M2 — Backend API (Production-Ready Core)

**Goal:** Replace file-based NDJSON pipeline with a real API and database.

- [x] FastAPI backend scaffolded (`api/`)
- [x] PostgreSQL schema: `events`, `endpoints`, `tenants`, `users`, `policies`, `audit_log`
- [x] JWT authentication: register, login, token refresh
- [x] Per-tenant data isolation (row-level filter on `tenant_id`)
- [x] API key support for headless collector agents
- [x] Docker Compose for local dev (API + DB)
- [x] OpenAPI spec auto-generated from FastAPI routes
- [ ] Collector emits to API endpoint instead of local NDJSON file
- [ ] Integration tests for API endpoints
- [ ] Alembic migrations wired up

**Files:** `api/`, `docker-compose.yml`

---

## Milestone M3 — Frontend SaaS UI

**Goal:** Replace the prototype React app with a production-quality multi-tenant dashboard.

- [ ] Auth flows: login, register, invite, password reset
- [ ] Org/tenant management: create org, invite members, roles (admin, analyst, viewer)
- [ ] Endpoint management: register endpoints, assign groups, view status
- [ ] Events dashboard: filterable table, confidence bands, enforcement state, time range
- [ ] Policy configuration UI: edit enforcement ladder rules, risky action controls
- [ ] Alerts and notifications: email or webhook on enforcement state change
- [ ] Real-time updates via WebSocket or polling
- [ ] Responsive, accessible design

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

- [ ] SSO / SAML 2.0 / OIDC support
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
- [ ] Push 5 unpushed commits to `origin/main`
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
| Lab runs 008–012 | — | Aider, GPT-Pilot, Cline, LM Studio, Continue |

# Security Evidence Pack

**Date:** 2026-03-24 | **Version:** 0.4.0 | **Prepared for:** Enterprise security review

---

## What This Pack Contains

This pack bundles the key security artifacts for Detec v0.4.0. It references canonical source files; reviewers can verify all claims against the live repo.

---

## 1. Threat Model Summary

**Reference:** docs/threat-model.md (full STRIDE analysis)

Detec covers four components: API (FastAPI), Gateway (TCP/TLS binary protocol, port 8001), Collector (endpoint Python agent), and Dashboard (React/Vite SOC UI). The system was analyzed using STRIDE across all four components plus the Playbook/Orchestrator subsystem. Key mitigations in force are: JWT and API key authentication with algorithm pinning, tenant isolation enforced at the database query layer on all resource paths, per-route rate limiting, secrets redaction in logs and responses, and an immutable audit trail scoped to tenant and actor.

### Key trust boundaries

| Boundary | Description | Reference |
|----------|-------------|-----------|
| Unauthenticated / authenticated | Public routes (login, register, health) vs. routes requiring JWT or API key; enforced via `resolve_auth()` / `get_tenant_id()` and `require_role()` | api/core/tenant.py, api/routers/auth.py |
| Tenant / tenant | All resource access scoped by `tenant_id` from auth context; BOLA-style tests assert tenant A cannot access tenant B resources | api/core/tenant.py, api/tests/test_security_pentest.py |
| Agent / user | Gateway accepts only tenant agent keys (exact match); user roles (owner, admin, analyst, viewer) apply to HTTP API; agent role has no user_id | api/core/tenant.py AGENT_ROLE, api/gateway.py |

### Data classification

| Data | Classification | Notes |
|------|----------------|-------|
| Tenant/endpoint/event data | Tenant-sensitive | Scoped by `tenant_id`; list/get/update/delete enforce tenant and role |
| API keys | Secret | User API key (prefix + hash in DB); tenant agent key (exact match). Used for HTTP and TCP auth |
| JWT (access/refresh) | Secret | Signed with `JWT_SECRET`; short-lived access, refresh with optional revocation |
| Webhook URLs and secrets | Secret | Stored per tenant; used for outbound HTTP callbacks |
| Billing (Stripe) | Secret/sensitive | Customer IDs, subscription state; Stripe webhooks verified by signature |
| Audit log | Tamper-evident | Immutable entries; actor, action, resource, tenant, IP |
| Playbook definitions | Tenant-sensitive | Response playbooks and restore-defaults scoped by tenant |

---

## 2. Hardening Controls in Force

**Reference:** docs/hardening-checklist.md (living control map)

| Control Area | Status | Verification Method |
|--------------|--------|---------------------|
| Security headers (X-Content-Type-Options, X-Frame-Options, HSTS, CSP, etc.) | Applied to all responses including error paths | Manual + unit tests |
| Error handling (no stack trace or internal detail) | Production sanitized | Unit tests (test_security_pentest.py) |
| Secrets (never in logs or responses) | Applied | Code review + Gitleaks CI |
| Auth (JWT alg pinning, API key hash, refresh reuse rejected) | Applied | Unit tests (TestAPI2BrokenAuth) |
| Rate limiting (per-route, per-IP) | Applied | Unit tests (test_rate_limits.py) |
| Tenant isolation (BOLA controls) | Applied | Pentest tests (TestAPI1) |
| Audit logging (immutable, fail-open with metric) | Applied | Unit tests + code review |

---

## 3. CI Security Gate Inventory

**Source:** .github/workflows/security.yml

| Gate | Tool | Severity threshold | Runs on | Blocks merge? |
|------|------|--------------------|---------|---------------|
| SAST | Semgrep (OWASP Top 10, CWE Top 25, Python, JS) | Any finding | Every PR to main | Yes |
| Dependency scan | Trivy | CRITICAL or HIGH | Every PR to main | Yes |
| Dependency audit | pip-audit + npm audit | Moderate+ | Every PR to main | Yes |
| Secrets detection | Gitleaks | Any secret detected | Every PR to main | Yes |
| API security tests | pytest (pentest, gateway, rate limits) | Test failure | Every PR to main | Yes |

Note: Codacy static analysis runs on push/PR but is non-blocking (see .github/workflows/codacy.yml).

---

## 4. Known Limitations and Mitigations

**Reference:** docs/known-limitations.md (full list)

| Limitation | Mitigation | Severity |
|------------|------------|----------|
| High-risk tools (e.g. Claude Code) commonly report Medium confidence without EDR enrichment | Expected behavior; documented; use High confidence threshold or EDR enrichment for enforcement | Medium |
| Linux network null-route blocks all UID traffic (not just target process) | Document and warn; do not use network block in production Linux without UID-level review | Medium |
| Approval Required decisions emit a hold label but do not yet block execution | Roadmap; operators must review and act manually | High (roadmap item) |
| Windows agent runs as scheduled task under user account | Not a system service; lower enforcement posture on Windows | Medium |
| ISO-001 container isolation ships inactive (advisory only) | Advisory; no runtime enforcement; documented in product-status.md | Low |

---

## 5. Test Coverage Snapshot

As of 2026-03-21: **1,318 automated tests** (849 collector, 421 API, 48 protocol).

Security-specific test suites:
- API pentest suite (TestAPI1–TestAPI10)
- Gateway security suite
- Rate limit suite
- Evasion regression suite

**Reference:** docs/SECURITY-TECHNICAL-REPORT.md for full methodology.

---

## How to Verify

- Clone the repo and run `make bootstrap` to set up the environment.
- Run the full security test suite with `make test-api` (requires Postgres) to execute pentest, gateway, and rate-limit tests.
- Run CI security gates locally via `act` (GitHub Actions local runner) or review CI output on GitHub for the most recent run of `.github/workflows/security.yml`.
- For header and error-body verification, run `curl -I` against any route (including a 404 and a rate-limited path) in a production/staging environment and confirm all expected headers are present with sanitized error bodies.

---

*For full detail on any section, see the referenced canonical docs. Last updated: 2026-03-24.*

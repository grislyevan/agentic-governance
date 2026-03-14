# Secure Code Review: Detec API and Collector

**Scope:** Authentication and authorization, tenant isolation, input validation at trust boundaries, and secrets handling.  
**Methodology:** Manual review of code paths plus alignment with existing tests (`test_security_pentest.py`, `test_gateway_security.py`, `test_tenant_isolation.py`, `test_auth.py`, `test_agent_security.py`).  
**Date:** 2025-03-13.

---

## 1. Summary

| Area | Risk summary | Critical | High | Medium | Low | Info |
|------|--------------|----------|------|--------|-----|------|
| Auth and authorization | No missing auth on protected routes; JWT/API key handling and role checks consistent | 0 | 0 | 0 | 1 | 0 |
| Tenant isolation | Tenant ID from auth only; list/get/update/delete correctly scoped; BOLA covered by tests | 0 | 0 | 0 | 0 | 0 |
| Input validation | Event and gateway payloads validated; webhook URL has SSRF gap for hostnames; playbook test payload unbounded | 0 | 0 | 2 | 0 | 0 |
| Secrets | No API key or JWT in logs; webhook secret in API/UI by design; collector API key in env/config only | 0 | 0 | 0 | 0 | 1 |

**Overall:** No critical or high findings. A few medium and low items have concrete remediations below.

---

## 2. Auth and Authorization

### 2.1 Findings

| ID | Finding | Severity | Reference | Remediation |
|----|---------|----------|-----------|-------------|
| A1 | **No finding:** All mutation and data routes use `resolve_auth()` (JWT or API key). Role-restricted routes use `require_role()` after `resolve_auth`. | N/A | All routers under `api/routers/` | None. |
| A2 | **No finding:** JWT uses `jwt_secret` and fixed algorithm; `is_valid_token()` checks `type`; refresh reuse is rejected (auth flow). | N/A | `api/core/auth.py`, `api/core/tenant.py`, `api/tests/test_security_pentest.py` (TestAPI2BrokenAuth) | None. |
| A3 | **No finding:** API key resolution: user key (prefix + hash) then tenant agent key (exact). Gateway mirrors this in `_verify_api_key()`. | N/A | `api/core/tenant.py`, `api/gateway.py` | None. |
| A4 | **Routes with auth but no role check:** Several read-only routes intentionally allow any authenticated user: `GET /webhooks/templates`, `GET /reports/compliance/summary`, `GET /data-flow/summary`, `GET /policies/presets`. Data is still scoped by `auth.tenant_id` (or presets are code-defined). | Low | `api/routers/webhooks.py`, `api/routers/reports.py`, `api/routers/data_flow.py`, `api/routers/policies.py` | Optional: add `require_role(auth, "owner", "admin", "analyst", "viewer")` for consistency if you want to enforce role on every endpoint; current behavior is documented and safe. |

### 2.2 References

- **Auth:** `api/core/auth.py` (create/decode JWT, password hashing), `api/core/tenant.py` (`resolve_auth`, `get_tenant_id`, `require_role`, `get_tenant_filter`).
- **Usage:** Every router except `auth` uses `resolve_auth(authorization, x_api_key, db)` and, where needed, `require_role(auth, ...)`. Event ingest uses `get_tenant_id()` only (no user role; agent key is sufficient).
- **Tests:** `api/tests/test_security_pentest.py` (expired token, refresh reuse, alg=none, wrong secret, role checks), `api/tests/test_auth.py`.

---

## 3. Tenant Isolation

### 3.1 Findings

| ID | Finding | Severity | Reference | Remediation |
|----|---------|----------|-----------|-------------|
| T1 | **No finding:** Tenant ID is never taken from request body or path. It is always derived from `resolve_auth()` / `get_tenant_id()`. | N/A | Grep: no `tenant_id = body.*` or path param for tenant | None. |
| T2 | **No finding:** Tenant-scoped list/get/update/delete use either `auth.tenant_id` directly or `get_tenant_filter(auth, Model)`. Owner/admin get cross-tenant read via `get_tenant_filter` (intended). | N/A | `api/routers/events.py`, `policies.py`, `endpoints.py`, `users.py`, `enforcement.py`, `audit.py`, `response_playbooks.py` | None. |
| T3 | **No finding:** BOLA is explicitly tested: analyst in tenant A cannot modify/delete tenant B resources (webhooks, policies). | N/A | `api/tests/test_tenant_isolation.py`, `api/tests/test_security_pentest.py` (TestAPI1BrokenObjectLevelAuth) | None. |

### 3.2 References

- **Filter helper:** `api/core/tenant.py` `get_tenant_filter(auth, model)` (owner/admin: non-null tenant_id; others: `model.tenant_id == auth.tenant_id`).
- **Usage:** Events, policies, endpoints, users, enforcement, audit, response playbooks all use `get_tenant_filter` or explicit `Model.tenant_id == auth.tenant_id` for queries and existence checks.

---

## 4. Input Validation

### 4.1 Findings

| ID | Finding | Severity | Reference | Remediation |
|----|---------|----------|-----------|-------------|
| I1 | **No finding:** Event ingest (HTTP and gateway) uses `validate_event_payload()`: depth, key count, top-level keys, types, string length, payload size. | N/A | `api/core/event_validator.py`, `api/routers/events.py`, `api/gateway.py` `_ingest_event()` | None. |
| I2 | **Webhook URL SSRF (hostname):** `_validate_webhook_url()` blocks private/link-local **IP literals** only. Hostnames that resolve to private IPs (e.g. internal DNS) are not blocked and could be used for SSRF. | Medium | `api/schemas/webhooks.py` (urlparse hostname, `ipaddress.ip_address(hostname)` only when hostname is an IP string) | Consider resolving hostname and checking the resolved address against `_BLOCKED_NETWORKS`; handle resolution failures and timeouts safely. |
| I3 | **Playbook test payload unbounded:** `PlaybookTestRequest.event_payload` is an arbitrary dict with no max size or depth. A very large payload could stress the server. | Medium | `api/schemas/response_playbooks.py`, `api/routers/response_playbooks.py` (`POST /{playbook_id}/test`) | Add validation (e.g. max keys, max depth, max JSON size) to `PlaybookTestRequest` or in the route, aligned with `event_validator` limits where appropriate. |
| I4 | **No finding:** Gateway auth payload is a dict with `api_key`, `hostname`, `agent_version`; type checked; no raw key logged. Event/batch payloads go through `validate_event_payload()`. | N/A | `api/gateway.py` `_handle_auth`, `_handle_event`, `_handle_event_batch` | None. |
| I5 | **No finding:** Protocol frame size is capped (`MAX_FRAME_SIZE` 16 MiB); oversized frames rejected. | N/A | `protocol/wire.py`, `protocol/connection.py` | None. |

### 4.2 References

- **Event validator:** `api/core/event_validator.py` (depth, keys, allowed keys, types, string length, total size).
- **Webhooks:** `api/schemas/webhooks.py` (`WebhookCreate`, `WebhookUpdate` url validator).
- **Playbooks:** `api/schemas/response_playbooks.py`, `api/core/response_playbooks.py` (`match_trigger`), `api/routers/response_playbooks.py`.
- **Gateway:** `api/gateway.py`, `protocol/wire.py`.

---

## 5. Secrets

### 5.1 Findings

| ID | Finding | Severity | Reference | Remediation |
|----|---------|----------|-----------|-------------|
| S1 | **No finding:** No logging of raw API key, JWT, or password in API or gateway. Auth failure logs mention "no valid JWT or API key" and role denial logs user_id/role only. | N/A | `api/core/auth.py` (no logger), `api/core/tenant.py`, `api/gateway.py` (`_handle_auth` logs hostname only) | None. |
| S2 | **No finding:** Webhook secret is used only for HMAC in delivery; not logged in sender or dispatcher. | N/A | `api/webhooks/sender.py`, `api/webhooks/dispatcher.py` | None. |
| S3 | **By design:** Webhook secret is returned in API responses and shown in dashboard (Signing secret) for SIEM configuration. Ensure response bodies are not logged in production. | Informational | `api/schemas/webhooks.py` `WebhookOut`, `dashboard/src/pages/SettingsPage.jsx` | Confirm no middleware or logging records response bodies for webhook list/get. |
| S4 | **No finding:** Collector API key is read from env (`AGENTIC_GOV_API_KEY`) or config file; config load logs path only, not config contents. | N/A | `collector/config_loader.py`, `collector/agent/credentials.py` | None. |
| S5 | **No finding:** Dashboard stores access/refresh tokens and optional API key in localStorage; documented in threat model. Short-lived access tokens and refresh flow limit exposure. | N/A | `dashboard/src/lib/auth.js`, `docs/threat-model.md` | None. |

### 5.2 References

- **Logging:** Grep for `logger.*(api_key|secret|password|token|jwt)` in `api/` and `collector/`: no sensitive values logged.
- **Config:** `collector/config_loader.py` (env and file; no dump of merged config with api_key).
- **Frontend:** `dashboard/src/lib/auth.js` (storage keys and token handling).

---

## 6. Checklist

Use this for quick pass/fail against the codebase (and after changes).

| # | Item | Pass | Reference |
|---|------|------|-----------|
| 1 | All mutation routes use `resolve_auth` + `require_role` (or equivalent) | Yes | All routers |
| 2 | All tenant-scoped reads use `get_tenant_filter(auth, Model)` or `Model.tenant_id == auth.tenant_id` | Yes | events, policies, endpoints, users, enforcement, audit, response_playbooks |
| 3 | Tenant ID is never taken from client (body/path); always from auth context | Yes | Grep + review |
| 4 | Event ingest (HTTP and TCP) uses `validate_event_payload()` | Yes | `api/routers/events.py`, `api/gateway.py` |
| 5 | Webhook URL validated (scheme, length); private IP literals blocked | Yes | `api/schemas/webhooks.py`; hostname→IP resolution not done (see I2) |
| 6 | Gateway auth validates payload type and does not log API key | Yes | `api/gateway.py` |
| 7 | Protocol frame size limited (MAX_FRAME_SIZE) | Yes | `protocol/wire.py`, `protocol/connection.py` |
| 8 | No API key, JWT, or password in log messages | Yes | auth, tenant, gateway, config_loader |
| 9 | Webhook secret not logged in delivery path | Yes | `api/webhooks/sender.py`, dispatcher |
| 10 | BOLA and auth tests present | Yes | `test_tenant_isolation.py`, `test_security_pentest.py`, `test_gateway_security.py` |

---

## 7. Role Map and Orchestrator Use

| Review area | Primary role | Supporting roles | Notes |
|-------------|--------------|------------------|--------|
| Auth and authorization | Security Engineer | Backend Architect | JWT, API keys, RBAC, gateway auth |
| Tenant isolation | Security Engineer | Backend Architect, Code Reviewer | All routers, get_tenant_filter, BOLA |
| Input validation | Security Engineer | Backend Architect | Event validator, webhooks, playbooks, gateway |
| Secrets | Security Engineer | DevOps Automator, Frontend Developer | Logs, config, dashboard storage |
| Document and checklist | Security Engineer | Code Reviewer | Consistency, actionable remediation |
| Validation (tests align) | API Tester | Security Engineer | Confirm findings map to tests; suggest new tests |

**Orchestrator:** Use this document as the spec for re-running the review (e.g. post-release). Tasks: (1) Auth review, (2) Tenant isolation review, (3) Input validation review, (4) Secrets review, (5) Checklist and doc update, (6) Code Reviewer validation and optional API Tester confirmation that critical assertions are covered by tests.

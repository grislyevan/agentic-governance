# Security Findings and Remediation

**Document version:** 1.0  
**Last updated:** 2025-03-13  
**Scope:** Mini security assessment of Auth, Playbooks API/orchestrator, Gateway, tenant isolation, and input validation.

---

## Summary

| Item | Detail |
|------|--------|
| **Scope** | Auth (JWT, API key, refresh, invite/reset); Playbooks API and response orchestrator; Gateway (agent auth, message validation, limits); Tenant isolation (BOLA/IDOR); Input validation (events, webhooks, playbooks). |
| **Methodology** | Manual code review of listed components, alignment with existing tests (`api/tests/`, `collector/tests/`), and reference to [docs/hardening-checklist.md](hardening-checklist.md) and [docs/ci-security.md](ci-security.md). |
| **Overall risk** | **Low to medium.** No critical issues identified. Strong tenant scoping, refresh reuse detection, and production config checks. Findings are mostly hardening and edge-case improvements. |

---

## Findings Table

| ID | Title | Severity | Component | Location | Description | Remediation | Status / Ref |
|----|--------|----------|-----------|----------|-------------|-------------|----------------|
| F-001 | Default JWT secret in non-production | Low | Auth | `api/core/config.py` | Default `jwt_secret` is a known value when `ENV` is not production/staging. | Already mitigated: `_reject_unsafe_defaults_in_production` raises in production; dev logs a warning. Ensure `ENV=production` (or `staging`) and strong `JWT_SECRET` in deployment. | Open / Config |
| F-002 | Refresh token reuse detection clears all refresh validity | Informational | Auth | `api/routers/auth.py` (refresh endpoint) | On reuse, `user.refresh_jti = None` invalidates the current refresh token but does not revoke all sessions. | By design: one-time use per refresh; reuse indicates possible theft. Consider optional full session revocation (e.g. clear all refresh JTIs for user) as a configurable policy. | Open |
| F-003 | Invite and reset tokens stored by hash only | Informational | Auth | `api/models/auth_token.py` | Invite/reset tokens are stored as SHA-256 hash; raw token shown once. No keyed HMAC. | Acceptable for short-lived, single-use tokens. For higher assurance, consider HMAC with server secret. | Accepted risk |
| F-004 | Playbooks API rejects agent role | Informational | Playbooks | `api/routers/response_playbooks.py` | List/get require `owner`, `admin`, `analyst`, or `viewer`. Create/update/delete require `owner` or `admin`. Tenant agent key yields role `agent`, so 403. | By design: agents cannot manage playbooks via API. Document in API or playbook docs. | Open |
| F-005 | Orchestrator runs only default playbooks | Medium | Playbooks | `api/core/response_orchestrator.py` | `run_playbooks()` uses only `get_default_playbooks()`. Tenant-created custom playbooks in DB are not executed on event ingest. | If product intent is to run custom playbooks on ingest, add loading of tenant custom playbooks (with same trigger/action contract) and merge with defaults in `run_playbooks`. If intent is default-only, document clearly. | Open |
| F-006 | Playbook test payload unbounded | Low | Playbooks | `api/schemas/response_playbooks.py` (`PlaybookTestRequest`) | `event_payload` is `dict[str, Any]` with no size or depth limit. | Add optional max size/depth in schema or in endpoint (e.g. reject payloads > 64KB or depth > 4). Rate limiting already applies. | Open |
| F-007 | Gateway auth hostname length not validated | Low | Gateway | `api/gateway.py` (`_handle_auth`, `_get_or_create_endpoint`) | Auth payload `hostname` is required but not length-limited before DB. `Endpoint.hostname` is `String(255)`. | Truncate or reject hostname > 255 chars before `_get_or_create_endpoint` to avoid DB error or truncation inconsistency. | Open |
| F-008 | Gateway API key in auth payload unchecked length | Informational | Gateway | `api/gateway.py` (`_handle_auth`) | `api_key` from auth payload is passed to `_verify_api_key` without max length. User keys are 64 hex; agent keys from `generate_agent_key`. | Optional: enforce max length (e.g. 256) to avoid unnecessary DB lookups or log noise. | Open |
| F-009 | Connection limits and frame size enforced | Positive | Gateway | `api/gateway.py`, `protocol/connection.py`, `protocol/wire.py` | Global 500 connections, 20 per IP; 16 MiB max frame; 120s idle timeout. | No change. Document in SERVER.md or hardening doc. | N/A |
| F-010 | Tenant isolation in routers | Positive | Tenant isolation | `api/routers/*.py`, `api/core/tenant.py` | All tenant-scoped resources use `resolve_auth` and filter by `tenant_id` (or path ID + tenant_id). Tenants router validates membership for PATCH `/{tenant_id}` and POST `/switch`. | No change. | N/A |
| F-011 | Owner/admin cross-tenant read scope | Informational | Tenant isolation | `api/core/tenant.py` (`get_tenant_filter`) | Owner and admin get `model.tenant_id.isnot(None)` for list/count queries (read-only cross-tenant). Mutations and get-by-id still require resource belonging to tenant or membership. | By design for admin visibility. Ensure no mutation uses this filter without explicit tenant check. | Open |
| F-012 | Event payload validation | Positive | Input validation | `api/core/event_validator.py` | Depth, key allowlist, payload size, and type checks. Used by HTTP ingest and gateway. | No change. | N/A |
| F-013 | Webhook URL validation | Positive | Input validation | `api/schemas/webhooks.py` | Private/link-local blocked; HTTPS required in production; max length 2048. | No change. | N/A |
| F-014 | Playbook trigger/actions schema depth | Low | Input validation | `api/schemas/response_playbooks.py` | `trigger`, `actions`, `escalation` are dict/list with no depth limit. | Add Pydantic validators or recursive depth cap (e.g. 4) to avoid deeply nested payloads. | Open |

---

## Remediation Tracking

| ID | Status | Notes |
|----|--------|--------|
| F-001 | Open | Config / ops |
| F-002 | Open | Design decision |
| F-003 | Accepted risk | |
| F-004 | Open | Documentation |
| F-005 | Open | Product decision + possible code change |
| F-006 | Open | Schema/endpoint |
| F-007 | Open | Gateway validation |
| F-008 | Open | Optional hardening |
| F-009 | N/A | Positive |
| F-010 | N/A | Positive |
| F-011 | Open | Review mutations |
| F-012 | N/A | Positive |
| F-013 | N/A | Positive |
| F-014 | Open | Schema validation |

---

## Roles and Orchestrator Flow

| Task | Primary | Supporting | Notes |
|------|---------|------------|--------|
| Scope and template | Security Engineer | Backend Architect | Which areas, doc structure |
| Auth assessment | Security Engineer | Backend Architect | JWT, keys, flows |
| Playbooks assessment | Security Engineer | Backend Architect | API, orchestrator, audit |
| Gateway assessment | Security Engineer | Backend Architect | Auth, validation, limits |
| Tenant isolation and input validation | Security Engineer | Backend Architect | BOLA, validators |
| Summary and doc finalization | Security Engineer | Code Reviewer | Consistency, actionable remediation |
| Implement fixes (optional) | Backend Architect, Security Engineer | Code Reviewer | Code changes and tests |

**Orchestrator use:** project-manager-senior turns this plan into a task list; Security Engineer performs assessments and writes findings; Backend Architect supports with code references and remediation; Code Reviewer validates references and severity; API Tester adds/runs tests for Critical/High fixes.

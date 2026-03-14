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
| F-006 | Playbook test payload unbounded | Low | Playbooks | `api/schemas/response_playbooks.py` (`PlaybookTestRequest`) | `event_payload` is `dict[str, Any]` with no size or depth limit. | Add optional max size/depth in schema or in endpoint (e.g. reject payloads > 64KB or depth > 4). Rate limiting already applies. | Fixed |
| F-007 | Gateway auth hostname length not validated | Low | Gateway | `api/gateway.py` (`_handle_auth`, `_get_or_create_endpoint`) | Auth payload `hostname` is required but not length-limited before DB. `Endpoint.hostname` is `String(255)`. | Truncate or reject hostname > 255 chars before `_get_or_create_endpoint` to avoid DB error or truncation inconsistency. | Fixed |
| F-008 | Gateway API key in auth payload unchecked length | Informational | Gateway | `api/gateway.py` (`_handle_auth`) | `api_key` from auth payload is passed to `_verify_api_key` without max length. User keys are 64 hex; agent keys from `generate_agent_key`. | Optional: enforce max length (e.g. 256) to avoid unnecessary DB lookups or log noise. | Open |
| F-009 | Connection limits and frame size enforced | Positive | Gateway | `api/gateway.py`, `protocol/connection.py`, `protocol/wire.py` | Global 500 connections, 20 per IP; 16 MiB max frame; 120s idle timeout. | No change. Document in SERVER.md or hardening doc. | N/A |
| F-010 | Tenant isolation in routers | Positive | Tenant isolation | `api/routers/*.py`, `api/core/tenant.py` | All tenant-scoped resources use `resolve_auth` and filter by `tenant_id` (or path ID + tenant_id). Tenants router validates membership for PATCH `/{tenant_id}` and POST `/switch`. | No change. | N/A |
| F-011 | Owner/admin cross-tenant read scope | Informational | Tenant isolation | `api/core/tenant.py` (`get_tenant_filter`) | Owner and admin get `model.tenant_id.isnot(None)` for list/count queries (read-only cross-tenant). Mutations and get-by-id still require resource belonging to tenant or membership. | By design for admin visibility. Ensure no mutation uses this filter without explicit tenant check. | Open |
| F-012 | Event payload validation | Positive | Input validation | `api/core/event_validator.py` | Depth, key allowlist, payload size, and type checks. Used by HTTP ingest and gateway. | No change. | N/A |
| F-013 | Webhook URL validation | Positive | Input validation | `api/schemas/webhooks.py` | Private/link-local blocked; HTTPS required in production; max length 2048. | No change. | N/A |
| F-014 | Playbook trigger/actions schema depth | Low | Input validation | `api/schemas/response_playbooks.py` | `trigger`, `actions`, `escalation` are dict/list with no depth limit. | Add Pydantic validators or recursive depth cap (e.g. 4) to avoid deeply nested payloads. | Fixed |

---

## Remediation Tracking

| ID | Status | Notes |
|----|--------|--------|
| F-001 | Open | Config / ops |
| F-002 | Open | Design decision |
| F-003 | Accepted risk | |
| F-004 | Open | Documentation |
| F-005 | Open | Product decision + possible code change |
| F-006 | Fixed | Schema: max depth 4, max size 64KB for PlaybookTestRequest.event_payload |
| F-007 | Fixed | Gateway: reject hostname > 255 chars; test in test_gateway_security.py |
| F-008 | Open | Optional hardening |
| F-009 | N/A | Positive |
| F-010 | N/A | Positive |
| F-011 | Open | Review mutations |
| F-012 | N/A | Positive |
| F-013 | N/A | Positive |
| F-014 | Fixed | Schema: max depth 4 for trigger/actions/escalation in Create/Update |

---

## Risk and prioritization (CISO)

Findings are mapped to governance layers and ordered by severity and impact. References: [docs/threat-model.md](threat-model.md), [api/core/config.py](../api/core/config.py), [api/gateway.py](../api/gateway.py), [api/core/response_orchestrator.py](../api/core/response_orchestrator.py), [api/schemas/response_playbooks.py](../api/schemas/response_playbooks.py).

**Mapping to layers:**

- **API/Gateway (trust boundary):** F-001 (JWT secret), F-002 (refresh reuse), F-007 (hostname length), F-008 (API key length). These protect the Identity/tenant boundary; they do not change endpoint detection layers.
- **Playbook/orchestrator (response automation):** F-004 (agent role doc), F-005 (only default playbooks run), F-006 (test payload unbounded), F-014 (trigger/actions depth). F-005 is the only Medium finding; it requires a product decision (document default-only vs. implement custom playbook execution on ingest).
- **Input validation (tampering/DoS):** F-012 and F-013 are positive controls; F-006 and F-014 are defense-in-depth improvements.

**Prioritized remediation order:**

1. **F-005 (Medium):** Resolve product intent; then either document in threat model and playbook docs or implement tenant custom playbook execution in `api/core/response_orchestrator.py` (merge with `get_default_playbooks()`).
2. **F-007 (Low):** Gateway hostname length. Truncate or reject hostname > 255 in `api/gateway.py` before `_get_or_create_endpoint`; add test in gateway security suite.
3. **F-006, F-014 (Low):** Playbook payload and schema limits. Add max size/depth to `api/schemas/response_playbooks.py` (`PlaybookTestRequest.event_payload`, and recursive depth cap for trigger/actions/escalation).
4. **F-001 (Low):** Config/ops; ensure deployment uses `ENV=production` and strong `JWT_SECRET`; already guarded by `_reject_unsafe_defaults_in_production` in `api/core/config.py`.
5. **F-002, F-004, F-008, F-011:** Informational or optional; document (F-004, F-011) or backlog (F-002, F-008).

---

## Assessment scope and handoff to /security-engineer

Scope for the security assessment aligned with the threat model and findings:

**In scope:** Auth (JWT, API key, refresh, invite/reset); Gateway (agent auth, msgpack validation, connection limits, hostname/key length); Playbooks API and response orchestrator; tenant isolation (BOLA); input validation (events, webhooks, playbook payloads/schemas); collector config and TLS emitter.

**Out of scope for this round:** EDR integration, Stripe billing internals, dashboard-only UX; new feature development.

**Success criteria:**

- All findings F-001 through F-014 have a documented status (Open, Accepted risk, Fixed, N/A) and remediation or rationale.
- Security test suites pass: [api/tests/test_security_pentest.py](../api/tests/test_security_pentest.py), [api/tests/test_gateway_security.py](../api/tests/test_gateway_security.py), [api/tests/test_rate_limits.py](../api/tests/test_rate_limits.py), [collector/tests/test_agent_security.py](../collector/tests/test_agent_security.py).
- No new Critical/High findings from Semgrep, Trivy, or Gitleaks (per [docs/ci-security.md](ci-security.md)).
- Threat model and this document remain accurate after any code changes.

**Handoff to /security-engineer (explicit tasks):**

1. Implement F-007 (gateway hostname length validation) in [api/gateway.py](../api/gateway.py) and add a test in the gateway security suite.
2. Implement F-006 and F-014 (playbook payload and schema depth limits) in [api/schemas/response_playbooks.py](../api/schemas/response_playbooks.py) and any endpoint that accepts these payloads.
3. After product decision on F-005: either update docs only or implement tenant custom playbook loading in [api/core/response_orchestrator.py](../api/core/response_orchestrator.py).
4. Run full security suite and CI security job; fix any regressions.
5. Update this document and [docs/hardening-checklist.md](hardening-checklist.md) if new controls are added.

When assigning work, say: "This needs /security-engineer to [specific task]."

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

---

## Post–Agent Reliability Review (2025-03-13)

A combined Dev-Eng / Security Engineer / CISO review of the Agent Reliability and Admin Control implementation (endpoint profiles, tamper controls, packaging) is in [docs/security-review-agent-reliability.md](security-review-agent-reliability.md). Three items were identified and remediated:

| ID | Title | Severity | Remediation | Status |
|----|--------|----------|-------------|--------|
| R-001 | TCP gateway did not return profile-derived interval_seconds | Medium | Gateway loads endpoint with profile, returns interval_seconds in HEARTBEAT_ACK and uses it for next_expected_in. | Fixed |
| R-002 | Endpoint profile enforcement_posture not validated | Low | Pydantic pattern `^(passive\|audit\|active)$` on Create/Update/Config schemas. | Fixed |
| R-003 | macOS uninstall without root check when LaunchDaemon present | Low | uninstall.sh exits with clear message if LaunchDaemon plist exists and effective uid != 0. | Fixed |

# Detec Threat Model

This document describes the threat model for Detec (agentic-governance): endpoint security for agentic AI tools. It covers system overview, STRIDE analysis per component, attack surface, key compromise scenarios, and a mitigation table. The document is intended to align with existing security tests and code; it does not introduce new controls.

---

## 1. System Overview

### 1.1 Architecture

- **Collector (endpoint agent):** Python agent that scans the machine for AI tools (Claude Code, Cursor, Ollama, Copilot, etc.), scores confidence, evaluates policy, and sends events to the central API. It can use HTTP (`POST /api/events`, `POST /api/endpoints/heartbeat`) or a persistent binary/msgpack connection on port 8001 (TCP) via DetecGateway.
- **API:** FastAPI backend providing auth (JWT + API key, invite tokens, password reset), events, endpoints, policies, users, webhooks, billing, and EDR enrichment. Serves the built dashboard at root.
- **DetecGateway:** Binary protocol TCP/TLS server (port 8001) in the same process as FastAPI. Agents authenticate with API key, then send events and heartbeats; the server can push policy and posture updates to connected agents.
- **Dashboard:** React/Vite SOC UI; built assets served by FastAPI. Dev mode proxies API.
- **Integrations:** Webhook outbound calls (per-tenant), Stripe billing (webhooks + API), EDR provider (e.g. CrowdStrike Falcon stub) for enrichment.
- **Data store:** SQLite or PostgreSQL; tenant-scoped data with RBAC.

References: [AGENTS.md](../AGENTS.md), [api/main.py](../api/main.py), [api/gateway.py](../api/gateway.py).

### 1.2 Data Classification

| Data | Classification | Notes |
|------|----------------|-------|
| Tenant/endpoint/event data | Tenant-sensitive | Scoped by `tenant_id`; list/get/update/delete enforce tenant and role |
| API keys | Secret | User API key (prefix + hash in DB); tenant agent key (exact match). Used for HTTP and TCP auth |
| JWT (access/refresh) | Secret | Signed with `JWT_SECRET`; short-lived access, refresh with optional revocation |
| Webhook URLs and secrets | Secret | Stored per tenant; used for outbound HTTP callbacks |
| Billing (Stripe) | Secret/sensitive | Customer IDs, subscription state; Stripe webhooks verified by signature |
| Audit log | Tamper-evident | Immutable entries; actor, action, resource, tenant, IP |
| Playbook definitions | Tenant-sensitive | Response playbooks and restore-defaults scoped by tenant |

References: [api/core/auth.py](../api/core/auth.py), [api/core/tenant.py](../api/core/tenant.py), [api/models/user.py](../api/models/user.py), [api/models/tenant.py](../api/models/tenant.py).

### 1.3 Trust Boundaries

- **Unauthenticated vs authenticated:** Public routes (e.g. login, register, health) vs routes requiring JWT or API key. Auth enforced via `resolve_auth()` / `get_tenant_id()` and role checks (`require_role()`). References: [api/core/tenant.py](../api/core/tenant.py), [api/routers/auth.py](../api/routers/auth.py).
- **Tenant vs tenant:** All resource access is scoped by `tenant_id` derived from the auth context. BOLA-style tests assert that an analyst in tenant A cannot access tenant B resources by ID. References: [api/tests/test_security_pentest.py](../api/tests/test_security_pentest.py) (e.g. `TestAPI1BrokenObjectLevelAuth`).
- **Agent (API key) vs user (JWT/user API key):** Same API key resolution supports both user API key (prefix + hash) and tenant agent key (exact). Agent role (`AGENT_ROLE`) has no user_id; user roles (owner, admin, analyst, viewer) carry user_id. References: [api/core/tenant.py](../api/core/tenant.py), [api/gateway.py](../api/gateway.py) `_verify_api_key`.
- **Server vs third party:** Outbound calls to webhooks, EDR providers, and Stripe. Trust boundary at TLS and (where applicable) signature verification (e.g. Stripe webhooks).

---

## 2. STRIDE by Component

### 2.1 API (FastAPI)

| Threat | Mitigation | Reference |
|--------|------------|-----------|
| **Spoofing** | JWT validation (exp, alg, secret); API key lookup (user prefix+hash, tenant agent key). Reused refresh token rejected; alg=none and wrong secret rejected in tests | [api/core/auth.py](../api/core/auth.py), [api/core/tenant.py](../api/core/tenant.py), [api/tests/test_security_pentest.py](../api/tests/test_security_pentest.py) `TestAPI2BrokenAuth` |
| **Tampering** | Input validation (Pydantic), event payload validation (depth, keys, size) before persistence | [api/core/event_validator.py](../api/core/event_validator.py), [api/routers/events.py](../api/routers/events.py) |
| **Repudiation** | Audit log for sensitive actions (user create/update/delete, policy, playbooks, enforcement, restore-defaults) | [api/core/audit_logger.py](../api/core/audit_logger.py), [api/routers/users.py](../api/routers/users.py), [api/routers/response_playbooks.py](../api/routers/response_playbooks.py) |
| **Information disclosure** | Errors sanitized; tenant/user IDs not leaked across tenants. User create ignores client-supplied `tenant_id` | [api/tests/test_security_pentest.py](../api/tests/test_security_pentest.py) (e.g. `test_user_create_ignores_tenant_id`) |
| **Denial of service** | Rate limits: login 5/min, register 3/min, event ingest 120/min, per-route limits on policies, endpoints, enforcement, auth, agent download. Default 300/min. SlowAPI by IP | [api/core/rate_limit.py](../api/core/rate_limit.py), [api/routers/auth.py](../api/routers/auth.py), [api/routers/events.py](../api/routers/events.py), [api/tests/test_rate_limits.py](../api/tests/test_rate_limits.py) |
| **Elevation of privilege** | RBAC via `require_role()`; tenant isolation on all list/get/update/delete. Owner/admin can cross-tenant read; write remains tenant-scoped | [api/core/tenant.py](../api/core/tenant.py) `get_tenant_filter`, [api/routers/policies.py](../api/routers/policies.py), [api/routers/webhooks.py](../api/routers/webhooks.py), etc. |

### 2.2 Gateway (TCP, port 8001)

| Threat | Mitigation | Reference |
|--------|------------|-----------|
| **Spoofing** | Auth required before any non-AUTH message; API key verified (user key or tenant agent key) same as HTTP | [api/gateway.py](../api/gateway.py) `_handle_auth`, `_verify_api_key` |
| **Tampering** | Msgpack frames parsed; event payload passed through same `validate_event_payload()` as HTTP ingest. Invalid payloads rejected (ingestion returns false, NACK sent) | [api/gateway.py](../api/gateway.py) `_ingest_event`, [api/core/event_validator.py](../api/core/event_validator.py) |
| **Repudiation** | Audit entries for enforcement/posture events; playbook execution and webhook dispatch logged in orchestrator/audit context | [api/gateway.py](../api/gateway.py) (audit for enforcement/posture), [api/core/response_orchestrator.py](../api/core/response_orchestrator.py) |
| **Information disclosure** | Tenant and endpoint derived from authenticated session only; no cross-tenant data on connection | [api/gateway.py](../api/gateway.py) `_tenant_id`, `_endpoint_id` |
| **Denial of service** | Connection limits: 500 global, 20 per IP; idle read timeout (120s) to evict stale connections | [api/gateway.py](../api/gateway.py) `_MAX_GLOBAL_CONNECTIONS`, `_MAX_CONNECTIONS_PER_IP`, `_READ_TIMEOUT`, `_track_connect` |
| **Elevation of privilege** | All ingested events and heartbeats scoped to session `_tenant_id` and `_endpoint_id`; no ability to act for another tenant | [api/gateway.py](../api/gateway.py) `_ingest_event`, `_get_or_create_endpoint` |

### 2.3 Collector

| Threat | Mitigation | Reference |
|--------|------------|-----------|
| **Spoofing** | Config/credentials (API URL, API key) from trusted config file and env; no interactive login on endpoint | [collector/config_loader.py](../collector/config_loader.py), [collector/tests/test_agent_security.py](../collector/tests/test_agent_security.py) |
| **Tampering** | Invalid or non-dict JSON config returns empty; private keys stripped from loaded config. HTTPS emitter uses SSL context | [collector/tests/test_agent_security.py](../collector/tests/test_agent_security.py) `TestConfigTampering`, `TestHttpEmitterTLS` |
| **Information disclosure** | Logs may contain hostnames/tool names; config loader does not log raw API key | [collector/config_loader.py](../collector/config_loader.py) |
| **Elevation of privilege** | Local enforcement (posture) is best-effort on endpoint; no server-side privilege change from collector alone | [collector/](../collector/) |

### 2.4 Dashboard

| Threat | Mitigation | Reference |
|--------|------------|-----------|
| **Spoofing** | Session via JWT in memory or storage; refresh flow; logout invalidates client-side token | Dashboard uses API auth; no server-side session store beyond JWT |
| **Tampering** | Client-side state is not trusted for authorization; all mutations go through API with JWT/API key | [dashboard/src/](../dashboard/src/) |
| **Information disclosure** | Tokens in storage (e.g. localStorage) are a known risk; reduce exposure by short-lived access tokens and secure refresh | [api/core/auth.py](../api/core/auth.py) (token expiry) |
| **Elevation of privilege** | Role-based UI and API: owner/admin/analyst/viewer; API enforces `require_role()` so downgrading UI alone does not grant access | [api/core/tenant.py](../api/core/tenant.py) `require_role` |

### 2.5 Playbook / Orchestrator

| Threat | Mitigation | Reference |
|--------|------------|-----------|
| **Tampering** | Event payload drives trigger matching and actions; payload validated and size/depth limited before orchestration | [api/core/response_orchestrator.py](../api/core/response_orchestrator.py), [api/core/event_validator.py](../api/core/event_validator.py) |
| **Repudiation** | Audit log for playbook actions and restore-defaults | [api/core/response_orchestrator.py](../api/core/response_orchestrator.py), [api/core/audit_logger.py](../api/core/audit_logger.py), [docs/rollback.md](../docs/rollback.md) |
| **Elevation of privilege** | Playbooks run in tenant context (tenant_id from ingest path); only owner/admin can create/customize/restore playbooks via API | [api/routers/response_playbooks.py](../api/routers/response_playbooks.py) `require_role(auth, "owner", "admin")` |

---

## 3. Attack Surface

### 3.1 External

- **Public API routes:** Login, register, password reset, forgot password, health. Rate limited. No tenant data without auth.
- **Authenticated API routes:** Events, endpoints, policies, users, webhooks, enforcement, audit, billing, response playbooks, retention. All require JWT or API key and enforce tenant + role.
- **Gateway port (8001):** TCP/TLS; auth via first message (API key + hostname). Connection and per-IP limits.
- **Dashboard:** Served by FastAPI; all data fetched via API with user auth.
- **Webhook outbound:** Server calls tenant-configured URLs with event payloads; no auth from third party to Detec (outbound only).
- **Stripe:** Webhook ingress (signature verification); API calls to Stripe with secret key.

### 3.2 Internal

- **Service-to-DB:** API and gateway use same DB session factory; tenant_id and endpoint_id always from auth/session.
- **Gateway-to-API:** Shared process; event ingest and playbook run use same DB and audit; no separate network boundary.
- **Collector-to-API/gateway:** HTTPS or TCP with API key; no mutual TLS or client certs in current design.
- **EDR provider:** Server-side calls to EDR (e.g. CrowdStrike); interface in [api/integrations/](../api/integrations/).

### 3.3 Data Flows

- **Event ingest:** Collector → HTTP `POST /api/events` or gateway TCP → validate → persist → webhooks + playbooks. Event payload constrained by [api/core/event_validator.py](../api/core/event_validator.py) (depth, keys, size).
- **Policy/posture:** Dashboard/API → enforcement API → gateway `push_posture` to connected agent. Scoped by tenant and endpoint.
- **Audit:** All sensitive actions → `audit_logger.record()` → `audit_log` table.

---

## 4. Key Scenarios

### 4.1 Agent Compromised

- **Scenario:** Attacker obtains a tenant agent key or a user API key (e.g. from a stolen config or endpoint).
- **Capabilities:** Ingest events (including malicious or misleading payloads within validation limits), receive posture updates, trigger playbook actions (webhook, audit, enforcement) in that tenant.
- **Existing mitigations:** Tenant isolation (attacker cannot read or write other tenants’ data); rate limits on event ingest (120/min HTTP; gateway has connection and idle limits); audit log for actions; event payload validation limits impact of malicious payloads.
- **Gaps to consider:** No automatic key rotation or revocation for agent key (tenant-level); user API key revocation requires user deactivation or key rotation. Documented in mitigation table below.

### 4.2 API Key Compromised

- **Scenario:** Same as above; distinction between user API key (tied to a user and role) and tenant agent key (no user, used for ingest/heartbeat).
- **Mitigations:** User key can be rotated or user deactivated; tenant agent key is a single shared secret per tenant (rotation is manual). JWT expiry limits exposure of stolen access tokens; refresh token reuse is rejected.

### 4.3 Tenant Isolation

- **Scenario:** User or agent in tenant A attempts to access or modify tenant B’s resources by ID.
- **Mitigations:** All list/get/update/delete paths resolve tenant from auth and filter by `tenant_id` (or `get_tenant_filter` for read). BOLA-style tests in [api/tests/test_security_pentest.py](../api/tests/test_security_pentest.py) (e.g. analyst cannot PATCH tenant B webhook, cannot DELETE tenant B policy). User creation ignores client-supplied `tenant_id`. Gateway events and endpoints are bound to session tenant/endpoint only.

---

## 5. Mitigation Table

| # | Component | Threat | Severity | Existing control | Gap / note | Owner / reference |
|---|-----------|--------|----------|-------------------|------------|-------------------|
| 1 | API | Spoofing (auth bypass) | High | JWT + API key; alg validation; refresh reuse rejected | None | [api/core/auth.py](../api/core/auth.py), [api/tests/test_security_pentest.py](../api/tests/test_security_pentest.py) |
| 2 | API | BOLA (cross-tenant access) | High | Tenant scoping on all resources; require_role | None | [api/core/tenant.py](../api/core/tenant.py), [api/tests/test_security_pentest.py](../api/tests/test_security_pentest.py) |
| 3 | API | Tampering (input/body) | Medium | Pydantic + event_validator (depth, keys, size) | None | [api/core/event_validator.py](../api/core/event_validator.py) |
| 4 | API | DoS (brute force / abuse) | Medium | Rate limits (login 5/min, register 3/min, events 120/min, per-route) | Optional: consider keyed limits per tenant/user | [api/core/rate_limit.py](../api/core/rate_limit.py), [api/tests/test_rate_limits.py](../api/tests/test_rate_limits.py) |
| 5 | API | Repudiation | Medium | Audit log for sensitive actions | None | [api/core/audit_logger.py](../api/core/audit_logger.py) |
| 6 | Gateway | Spoofing (agent auth) | High | API key required; same verify as HTTP | None | [api/gateway.py](../api/gateway.py), [api/tests/test_gateway_security.py](../api/tests/test_gateway_security.py) |
| 7 | Gateway | Tampering (msgpack/event) | Medium | validate_event_payload; NACK on failure | None | [api/gateway.py](../api/gateway.py), [api/core/event_validator.py](../api/core/event_validator.py) |
| 8 | Gateway | DoS (connection exhaustion) | Medium | 500 global, 20 per IP, 120s idle timeout | None | [api/gateway.py](../api/gateway.py) |
| 9 | Gateway | Tenant elevation | High | All operations use session tenant_id/endpoint_id | None | [api/gateway.py](../api/gateway.py) |
| 10 | Collector | Config tampering | Medium | Invalid/non-dict JSON → empty; private keys stripped | None | [collector/tests/test_agent_security.py](../collector/tests/test_agent_security.py) |
| 11 | Collector | Credential disclosure (TLS) | High | HTTPS emitter uses SSL context | Plaintext TCP gateway optional (deployer choice) | [collector/tests/test_agent_security.py](../collector/tests/test_agent_security.py) |
| 12 | Playbook/orchestrator | Malicious event driving actions | Medium | Event validation; tenant-scoped execution | Playbook definitions are tenant-scoped; only default playbooks run in code today | [api/core/response_orchestrator.py](../api/core/response_orchestrator.py) |
| 13 | All | Agent/key compromise | High | Tenant isolation; rate limits; audit | Agent key rotation and revocation process is manual | [docs/rollback.md](../docs/rollback.md), operations |

---

## 6. References

- **Security tests:** [api/tests/test_security_pentest.py](../api/tests/test_security_pentest.py), [api/tests/test_gateway_security.py](../api/tests/test_gateway_security.py), [api/tests/test_rate_limits.py](../api/tests/test_rate_limits.py), [collector/tests/test_agent_security.py](../collector/tests/test_agent_security.py).
- **Auth and tenant:** [api/core/auth.py](../api/core/auth.py), [api/core/tenant.py](../api/core/tenant.py).
- **Gateway:** [api/gateway.py](../api/gateway.py).
- **Response automation:** [api/core/response_orchestrator.py](../api/core/response_orchestrator.py), [api/core/response_playbooks.py](../api/core/response_playbooks.py).
- **Rollback and operations:** [docs/rollback.md](../docs/rollback.md).

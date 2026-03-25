# Security Hardening Checklist

Use this checklist to verify and maintain security hardening of the Detec API and collector. Each item references the code or config that implements it.

## Security headers and CSP

| Item | Status | Reference | Owner | Verification | Cadence |
|------|--------|-----------|-------|--------------|---------|
| X-Content-Type-Options: nosniff | Applied to all responses | `api/main.py`: `_apply_security_headers()`, `security_headers` middleware | Backend | Unit Test (CI) | On every PR |
| X-Frame-Options: DENY | Applied to all responses | Same | Backend | Unit Test (CI) | On every PR |
| Referrer-Policy: strict-origin-when-cross-origin | Applied to all responses | Same | Backend | Unit Test (CI) | On every PR |
| Permissions-Policy (camera, microphone, geolocation disabled) | Applied to all responses | Same | Backend | Unit Test (CI) | On every PR |
| X-XSS-Protection: 1; mode=block | Applied to all responses (legacy browsers) | Same | Backend | Unit Test (CI) | On every PR |
| HSTS | Production/staging only | Same; env in (`production`, `staging`) | DevOps | Manual-curl on deploy | On deploy |
| Content-Security-Policy | Production/staging only | Same | DevOps | Manual-curl on deploy | On deploy |
| Headers on error responses | Exception and rate-limit handlers call `_apply_security_headers()` so 4xx/5xx get same headers | `api/main.py`: `_rate_limit_handler`, `_unhandled_exception_handler` | Backend | Unit Test (CI) | On every PR |

## Error and exception handling

| Item | Status | Reference | Owner | Verification | Cadence |
|------|--------|-----------|-------|--------------|---------|
| Global exception handler returns generic message only | Yes; never stack trace or internal detail | `api/main.py`: `_unhandled_exception_handler` returns `"Internal server error"` | Backend | Unit Test — test_security_pentest.py | On every PR |
| Production route-level errors avoid leaking internals | Policy preset and billing webhook use generic detail when `settings.debug` is False | `api/routers/policies.py`: preset ValueError; `api/routers/billing.py`: Stripe webhook exception | Backend | Unit Test (CI) | On every PR |
| Playbook action failures not exposed to clients | Orchestrator returns `"action failed"` instead of `str(e)` in `actions_run` | `api/core/response_orchestrator.py`: exception branch in `run_playbooks()` | Backend | Unit Test (CI) | On every PR |

## Playbook and audit paths

| Item | Status | Reference | Owner | Verification | Cadence |
|------|--------|-----------|-------|--------------|---------|
| Playbook execution error text not exposed | Sanitized in orchestrator | `api/core/response_orchestrator.py` | Backend | Unit Test (CI) | On every PR |
| Audit log and playbook API scoped to tenant | Enforced by auth and tenant_id in queries | `api/routers/response_playbooks.py`, `api/routers/audit.py` (tenant from auth) | Security Engineer | Unit Test (CI) | On every PR |
| Webhook secret masking in audit detail | Optional; document or implement as needed | Future: audit detail could mask `secret` field in webhook-related entries | Backend | Code review | On every PR touching audit |

## Secrets

| Item | Status | Reference | Owner | Verification | Cadence |
|------|--------|-----------|-------|--------------|---------|
| No API key, JWT, or webhook secret in API response bodies | Auth returns tokens only on login/register; keys not echoed | `api/routers/auth.py`, `api/schemas/auth.py` | Backend | Code review + Gitleaks CI | On every PR |
| No secrets in application logs | Collector redacts `api_key` in config warnings; auth does not log raw reset token | `collector/config_loader.py`: `_SENSITIVE_KEYS`, redaction in `load_env_overrides()`; `api/routers/auth.py`: password reset log | Backend | Code review + Gitleaks CI | On every PR |
| No plaintext seed credentials on disk | Seed credentials are printed once to stdout on first startup; never written to cwd or a file | `api/main.py`: `_seed()` | Backend | Code review | On every PR touching auth |
| Dashboard token storage | Tokens in memory or secure storage; not in URLs or logs | Dashboard auth flow (no server-side session storage of full token in logs) | Any Reviewer | Code review | On every PR touching auth |

## Auth and access controls

| Item | Status | Reference | Owner | Verification | Cadence |
|------|--------|-----------|-------|--------------|---------|
| JWT algorithm pinned to HS256; alg=none rejected | Yes | api/tests/test_security_pentest.py TestAPI2BrokenAuth | Security Engineer | Unit Test (CI) | On every PR |
| Refresh token reuse rejected | Yes | api/core/auth.py | Security Engineer | Unit Test (CI) | On every PR |
| API key prefix+hash; full key never stored | Yes | api/core/auth.py, api/routers/auth.py | Backend | Code review | On every PR touching auth |
| Tenant isolation on all mutations | Yes | api/core/tenant.py strict_tenant_filter | Security Engineer | Unit Test (CI) — test_security_pentest.py | On every PR |
| Agent key separate from user key | Yes | api/core/tenant.py AGENT_ROLE | Backend | Code review | On every PR touching auth |

## Rate limiting controls

| Item | Status | Reference | Owner | Verification | Cadence |
|------|--------|-----------|-------|--------------|---------|
| Login: 5/min | Yes | api/routers/auth.py | Backend | Unit Test — test_rate_limits.py | On every PR |
| Register: 3/min | Yes | api/routers/auth.py | Backend | Unit Test | On every PR |
| Event ingest: 120/min | Yes | api/routers/events.py | Backend | Unit Test | On every PR |
| Enforcement endpoints: 30/min | Yes | api/routers/enforcement.py | Backend | Unit Test | On every PR |

## CI security gates

| Gate | Status | Workflow | Owner | Verification | Cadence |
|------|--------|----------|-------|--------------|---------|
| Semgrep SAST (OWASP Top 10, CWE Top 25) | Active | .github/workflows/security.yml | DevOps | CI pass | On every PR to main |
| Trivy dependency scan (CRITICAL/HIGH fail) | Active | security.yml | DevOps | CI pass | On every PR to main |
| pip-audit + npm audit | Active | security.yml | DevOps | CI pass | On every PR to main |
| Gitleaks secrets scan | Active | security.yml | DevOps | CI pass | On every PR to main |
| API security tests (pentest, gateway, rate limits) | Active | security.yml | Security Engineer | CI pass | On every PR to main |

## Audit logging controls

| Item | Status | Reference | Owner | Verification | Cadence |
|------|--------|-----------|-------|--------------|---------|
| Audit entries for: user CRUD, policy, playbooks, enforcement posture, restore-defaults, approve/deny | Yes | api/core/audit_logger.py | Backend | Code review on each new sensitive endpoint | On every PR |
| Audit write fail-open with metric increment | Yes | api/core/audit_logger.py, api/core/metrics.py detec_audit_write_failures_total | Backend | Unit Test | On every PR |
| Audit records are tenant-scoped and immutable (no delete endpoint) | Yes | api/routers/audit.py | Security Engineer | Code review + pentest tests | On every PR touching audit |

## Validation

- **Headers:** Use browser devtools or `curl -I` on any route (including `/api/nonexistent` and a 500 path); confirm all headers above are present.
- **Error bodies:** With `DEBUG=false` and `ENV=production`, trigger 500 and rate limit; response body must contain only generic messages.
- **Secrets:** Grep logs and API responses for `api_key`, `secret`, `password`, `token` (context-dependent); confirm no plain values.

## Re-validation cadence

- **On every PR to main:** All CI security gates run automatically. Auth/rate-limit tests must pass.
- **Monthly:** Security Engineer manually re-runs validation commands (see §Validation above) against staging.
- **On release:** Full checklist reviewed; any "Manual" items re-verified; cadence updated.
- **On deploy:** DevOps verifies HSTS, CSP, and TLS headers against the live server.

## Ownership

| Role | Owns |
|------|------|
| Security Engineer | Auth controls, tenant isolation, rate limits, this checklist |
| Backend | API implementation of controls |
| DevOps | CI security gates, deployment hardening |
| Any Reviewer | Code review verification on PRs touching security-sensitive code |

# Security Hardening Checklist

Use this checklist to verify and maintain security hardening of the Detec API and collector. Each item references the code or config that implements it.

## Security headers and CSP

| Item | Status | Reference |
|------|--------|-----------|
| X-Content-Type-Options: nosniff | Applied to all responses | `api/main.py`: `_apply_security_headers()`, `security_headers` middleware |
| X-Frame-Options: DENY | Applied to all responses | Same |
| Referrer-Policy: strict-origin-when-cross-origin | Applied to all responses | Same |
| Permissions-Policy (camera, microphone, geolocation disabled) | Applied to all responses | Same |
| X-XSS-Protection: 1; mode=block | Applied to all responses (legacy browsers) | Same |
| HSTS | Production/staging only | Same; env in (`production`, `staging`) |
| Content-Security-Policy | Production/staging only | Same |
| Headers on error responses | Exception and rate-limit handlers call `_apply_security_headers()` so 4xx/5xx get same headers | `api/main.py`: `_rate_limit_handler`, `_unhandled_exception_handler` |

## Error and exception handling

| Item | Status | Reference |
|------|--------|-----------|
| Global exception handler returns generic message only | Yes; never stack trace or internal detail | `api/main.py`: `_unhandled_exception_handler` returns `"Internal server error"` |
| Production route-level errors avoid leaking internals | Policy preset and billing webhook use generic detail when `settings.debug` is False | `api/routers/policies.py`: preset ValueError; `api/routers/billing.py`: Stripe webhook exception |
| Playbook action failures not exposed to clients | Orchestrator returns `"action failed"` instead of `str(e)` in `actions_run` | `api/core/response_orchestrator.py`: exception branch in `run_playbooks()` |

## Playbook and audit paths

| Item | Status | Reference |
|------|--------|-----------|
| Playbook execution error text not exposed | Sanitized in orchestrator | `api/core/response_orchestrator.py` |
| Audit log and playbook API scoped to tenant | Enforced by auth and tenant_id in queries | `api/routers/response_playbooks.py`, `api/routers/audit.py` (tenant from auth) |
| Webhook secret masking in audit detail | Optional; document or implement as needed | Future: audit detail could mask `secret` field in webhook-related entries |

## Secrets

| Item | Status | Reference |
|------|--------|-----------|
| No API key, JWT, or webhook secret in API response bodies | Auth returns tokens only on login/register; keys not echoed | `api/routers/auth.py`, `api/schemas/auth.py` |
| No secrets in application logs | Collector redacts `api_key` in config warnings; auth does not log raw reset token | `collector/config_loader.py`: `_SENSITIVE_KEYS`, redaction in `load_env_overrides()`; `api/routers/auth.py`: password reset log |
| Seed credentials only in seed-credentials.txt or (dev) logs with prefix only | Production/staging write file and log prefix only; dev may log full key once | `api/main.py`: `_seed()` |
| Dashboard token storage | Tokens in memory or secure storage; not in URLs or logs | Dashboard auth flow (no server-side session storage of full token in logs) |

## Validation

- **Headers:** Use browser devtools or `curl -I` on any route (including `/api/nonexistent` and a 500 path); confirm all headers above are present.
- **Error bodies:** With `DEBUG=false` and `ENV=production`, trigger 500 and rate limit; response body must contain only generic messages.
- **Secrets:** Grep logs and API responses for `api_key`, `secret`, `password`, `token` (context-dependent); confirm no plain values.

## Re-runs and ownership

- **Security Engineer:** Owns this checklist and tasks 1–5 in the hardening plan.
- **Backend Architect:** Implements header/error/orchestrator changes in API.
- **Code Reviewer:** Verifies changes match checklist and do not introduce disclosure.
- **Orchestrator:** `project-manager-senior` turns the plan into task list; Security Engineer leads implementation.

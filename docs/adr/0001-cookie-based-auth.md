# ADR 0001: Cookie-based auth for browser session

**Status:** Accepted  
**Date:** 2026-03  
**Context:** Big-Ole Remediation Program, Sprint 2

## Context

Access and refresh tokens (and optionally API key for dashboard) were stored in `localStorage`. Any XSS vulnerability gives an attacker full access to these credentials. Moving tokens to secure, httpOnly, sameSite cookies reduces the blast radius: JavaScript cannot read the tokens.

## Decision

- **Access and refresh tokens:** Stored in httpOnly, secure (when HTTPS), sameSite (Lax or Strict) cookies. The API sets them on login, register, refresh, and SSO callback; clears them on logout.
- **API key:** Remains in localStorage for "API key" mode (e.g. settings, non-browser use). Only session tokens move to cookies.
- **Backend:** Login, register, refresh, and SSO callback responses set `Set-Cookie` for access and refresh. New `POST /auth/logout` clears those cookies. Auth resolution accepts the access token from the `Cookie` header when `Authorization: Bearer` is missing (browser requests send cookies automatically with `credentials: 'include'`).
- **Frontend:** All fetch calls that require session auth use `credentials: 'include'`. No access or refresh token is read from or written to localStorage/sessionStorage. Logout calls `POST /auth/logout` and then clears local state.

## Migration strategy

- **Phased:** Backend sets cookies in addition to returning JSON body (so existing clients that rely on body still work). Frontend is updated to stop storing tokens and to use credentials and logout.
- **Backward compatibility:** Clients that send `Authorization: Bearer` (e.g. API key or token from body) continue to work; cookie is only used when Authorization is absent.

## Consequences

- Same-origin or correctly configured CORS origins required; `allow_credentials=True` is already set.
- Cookie domain/path must match the dashboard origin (same site or configured domain).
- Security test or manual checklist validates cookie flags: HttpOnly, Secure, SameSite.

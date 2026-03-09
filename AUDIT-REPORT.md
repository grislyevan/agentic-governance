# Comprehensive Security and Code Quality Audit Report

**Project:** Agentic Governance Platform  
**Date:** March 8, 2026  
**Scope:** Full stack (API, Collector, Dashboard, Infrastructure)

---

## Executive Summary

This audit examined the entire agentic-governance codebase across four domains: backend API, frontend dashboard, collector agent, and infrastructure/CI. The audit identified **5 Critical**, **19 High**, **41 Medium**, and **53 Low** findings across security, code quality, accessibility, and operational concerns.

The most urgent issues are: hardcoded secrets in version-controlled Docker Compose files, an unenforced role-based access control system, an empty audit log (compliance gap), localStorage token storage vulnerable to XSS, race conditions in the collector's buffer that can lose events, and enforcement PIDs that silently fail for most scanners.

---

## Findings by Severity

### CRITICAL (5 findings)

#### C-1: Hardcoded Secrets in Docker Compose (Infrastructure)

- **Files:** `docker-compose.yml` lines 5-8, 26-28
- **Description:** `POSTGRES_PASSWORD: postgres`, `JWT_SECRET: dev-secret-change-in-production`, and full `DATABASE_URL` with credentials are committed to version control.
- **Risk:** Anyone with repo access has production-viable credentials. If `ENV` is not set to `production`, these defaults are used in deployment.
- **Recommendation:** Replace with `${VARIABLE}` substitution sourced from `env_file: .env`. Never commit credential values.
- **Effort:** Small (1-2 hours)

#### C-2: Collector Buffer Drain Race Condition Loses Events (Collector)

- **Files:** `collector/agent/buffer.py` lines 50-68
- **Description:** `drain()` reads the buffer file, parses it, then unlinks. Between read and unlink, another process or thread can append events. No file locking or atomic read-and-truncate.
- **Risk:** Concurrent daemon instances or heartbeat + flush can lose events or produce duplicates. Data integrity is not guaranteed.
- **Recommendation:** Use `fcntl.flock` file locking or atomic rename (write to temp, rename to replace). Document single-instance requirement.
- **Effort:** Medium (3-4 hours)

#### C-3: Enforcement PIDs Never Extracted for Most Scanners (Collector)

- **Files:** `collector/main.py` lines 66-77; multiple scanners
- **Description:** `_extract_pids()` only accepts `int` PIDs, but most scanners (Aider, Claude Code, GPT-Pilot, LM Studio, Open Interpreter, OpenClaw, Claude Cowork, Cline, Continue) store PIDs as strings from `pgrep`. These PIDs are silently ignored.
- **Risk:** Process kill and network block enforcement only work for Cursor, Copilot, and Ollama. All other tools bypass enforcement even when policy says "block."
- **Recommendation:** Normalize PIDs with `int()` coercion before type checking. Standardize scanners to store `int` PIDs.
- **Effort:** Small (1-2 hours)

#### C-4: Audit Log Never Written (Backend)

- **Files:** Entire `api/` codebase; `api/models/audit.py`, `api/routers/audit.py`
- **Description:** The `audit_log` table, model, and read endpoint exist, but no code anywhere writes audit entries. The table will always be empty.
- **Risk:** Complete compliance gap. No record of logins, policy changes, endpoint enrollments, or any administrative action. Forensic investigation is impossible.
- **Recommendation:** Create an audit logging helper and instrument: login/logout, policy create/update, endpoint create/enroll, user creation. Log actor, action, resource, tenant, IP, and timestamp.
- **Effort:** Medium (4-6 hours)

#### C-5: Role-Based Access Control Defined but Never Enforced (Backend)

- **Files:** `api/models/user.py` line 43; all routers
- **Description:** `User.role` supports `admin` and `analyst` values but is never checked in any router. All authenticated users can perform all actions including policy management, endpoint enrollment, and audit log access.
- **Risk:** Any authenticated user (including analyst-level accounts) can modify policies, enroll endpoints, and perform admin operations.
- **Recommendation:** Add a `require_role()` dependency and apply it to sensitive endpoints: `POST/PATCH /policies` (admin), `POST /endpoints/enroll` (admin), `GET /audit-log` (admin or analyst read-only).
- **Effort:** Medium (3-4 hours)

---

### HIGH (19 findings)

#### H-1: localStorage Token Storage Vulnerable to XSS (Frontend)

- **Files:** `dashboard/src/lib/auth.js`, `dashboard/src/lib/api.js`
- **Description:** Access tokens, refresh tokens, and API keys stored in `localStorage`. Any XSS vulnerability gives an attacker full access to these credentials.
- **Recommendation:** Prefer httpOnly cookies for tokens. If localStorage is required, enforce strict Content Security Policy and sanitize all inputs.
- **Effort:** Large (6-8 hours for cookie-based auth refactor)

#### H-2: python-jose Vulnerable to CVE-2024-33663 / CVE-2024-33664 (Backend)

- **Files:** `api/requirements.txt` line 8
- **Description:** `python-jose[cryptography]>=3.3.0` allows versions with known algorithm confusion (auth bypass) and JWT bomb (DoS) vulnerabilities.
- **Recommendation:** Pin to `>=3.4.0`.
- **Effort:** Minimal (5 minutes)

#### H-3: Refresh Token Not Rotated on Use (Backend)

- **Files:** `api/routers/auth.py` lines 113-128
- **Description:** Refresh tokens can be reused indefinitely for 30 days. A stolen refresh token stays valid with no revocation mechanism.
- **Recommendation:** Rotate refresh tokens on each use (issue new, invalidate old). Optionally store JTI for server-side revocation.
- **Effort:** Medium (3-4 hours)

#### H-4: Seed API Key Written to /tmp (Backend)

- **Files:** `api/main.py` lines 141-147
- **Description:** Seed admin API key written to `/tmp/detec-seed-key.txt`. On shared systems or containers with shared `/tmp`, other users can read this file.
- **Recommendation:** Write to `$HOME/.config/detec/` or print to stdout only. Delete after first use.
- **Effort:** Small (1 hour)

#### H-5: No React Error Boundaries (Frontend)

- **Files:** `dashboard/src/main.jsx`, `dashboard/src/App.jsx`
- **Description:** No error boundaries anywhere in the React tree. An uncaught error in any component blanks the entire app.
- **Recommendation:** Add an ErrorBoundary component wrapping the app and major page sections.
- **Effort:** Small (1-2 hours)

#### H-6: No URL-Based Routing (Frontend)

- **Files:** `dashboard/src/App.jsx` lines 24-25
- **Description:** Routing is via `useState('endpoints')`. Refreshing the page resets to the default view. Browser back/forward buttons do nothing. URLs are not shareable.
- **Recommendation:** Add React Router with URL-based routes.
- **Effort:** Medium (3-4 hours)

#### H-7: Process Kill Without Identity Verification (Collector)

- **Files:** `collector/enforcement/process_kill.py` lines 20-61
- **Description:** PIDs are killed without re-checking that they still belong to the target tool. PID reuse can cause the collector to kill the wrong process.
- **Recommendation:** Before killing, verify the process command line matches the expected tool via `psutil` or `/proc`.
- **Effort:** Small (1-2 hours)

#### H-8: Linux Network Block Affects Entire UID (Collector)

- **Files:** `collector/enforcement/network_block.py` lines 49-85
- **Description:** `iptables` blocks by UID because `--pid-owner` is unavailable. All processes for that user are blocked, not just the target tool.
- **Recommendation:** Document prominently. Consider cgroups or network namespaces as alternatives.
- **Effort:** Large (documentation: 1 hour; alternative implementation: 8+ hours)

#### H-9: Credential Store Errors Silently Swallowed (Collector)

- **Files:** `collector/config_loader.py` lines 127-134
- **Description:** Credential store failures (locked keychain, missing backend, permission denied) logged at DEBUG. Callers cannot distinguish "no key" from "lookup failed."
- **Recommendation:** Log at WARNING. Surface a specific error type for credential store failures.
- **Effort:** Small (1 hour)

#### H-10: No Key Rotation for Ed25519 Signing Keys (Collector)

- **Files:** `collector/crypto/signer.py`
- **Description:** Keys are generated once and reused forever. No rotation, expiry, or versioning.
- **Recommendation:** Add key versioning and rotation support. Document rotation procedure.
- **Effort:** Medium (4-6 hours)

#### H-11: HTTP Emitter No Explicit TLS Verification (Collector)

- **Files:** `collector/output/http_emitter.py` lines 96-106
- **Description:** `urllib.request.urlopen()` uses Python's default SSL context (which verifies by default) but does not explicitly create or pass an SSL context. Future changes or environment configuration could disable verification.
- **Recommendation:** Create an explicit `ssl.create_default_context()` and pass it to `urlopen`.
- **Effort:** Minimal (15 minutes)

#### H-12: docker-compose.override.yml Auto-Loads in Production (Infrastructure)

- **Files:** `docker-compose.override.yml`
- **Description:** Docker Compose automatically loads `override.yml`. This enables `DEBUG=true`, `--reload`, volume mount `./api:/app`, and exposes PostgreSQL on port 5432.
- **Recommendation:** Rename to `docker-compose.dev.yml` and use `-f` flag explicitly. Document in SERVER.md.
- **Effort:** Small (30 minutes)

#### H-13: No Build or Test Jobs in CI (Infrastructure)

- **Files:** `.github/workflows/`
- **Description:** CI only runs security scans (Semgrep, Trivy, Gitleaks). No Docker build verification, no pytest execution, no npm test.
- **Recommendation:** Add CI jobs for: `docker build` (API + dashboard), `pytest collector/tests/`, `pytest api/tests/` (run separately due to package name collision).
- **Effort:** Medium (2-3 hours)

#### H-14: Two Conflicting .env.example Files (Infrastructure)

- **Files:** `.env.example` (root), `api/.env.example`
- **Description:** Root file has 45 lines with `DATABASE_URL`, `JWT_SECRET`, etc. API file is shorter with different defaults including `DEBUG=true`. No canonical source of truth.
- **Recommendation:** Consolidate into one root `.env.example`. Add comments explaining Docker vs local usage.
- **Effort:** Small (1 hour)

#### H-15: Token Refresh Race Condition (Frontend)

- **Files:** `dashboard/src/hooks/useAuth.jsx` lines 19-28
- **Description:** 4-minute `setInterval` can trigger concurrent refresh calls if the previous one hasn't completed.
- **Recommendation:** Add a mutex/lock (e.g., a `refreshing` ref) to ensure only one refresh runs at a time.
- **Effort:** Small (30 minutes)

#### H-16: Unsigned Events Accepted by API (Backend)

- **Files:** `api/routers/events.py` lines 67-99, 126-133
- **Description:** Signature verification returns `None` for unsigned events and only rejects when it returns `False`. Unsigned events are accepted even from enrolled endpoints.
- **Recommendation:** Add a configuration flag to require signatures. At minimum, require signatures from enrolled endpoints.
- **Effort:** Small (1-2 hours)

#### H-17: DB Port Exposed in Override (Infrastructure)

- **Files:** `docker-compose.override.yml` lines 5-7
- **Description:** PostgreSQL port 5432 mapped to host, exposing the database directly.
- **Recommendation:** Remove from override or restrict to `127.0.0.1:5432:5432`. Same as H-12: rename override file.
- **Effort:** Minimal (included in H-12)

#### H-18: No Deployment Pipeline (Infrastructure)

- **Files:** `.github/workflows/`
- **Description:** No automated deployment workflow. All deploys are manual.
- **Recommendation:** Add staging/production deploy workflow with proper secrets management.
- **Effort:** Large (4-8 hours)

#### H-19: Test Package Name Collision (Infrastructure)

- **Files:** `collector/tests/`, `api/tests/`
- **Description:** Both use `tests` as the package name. Running `pytest` from root causes `ModuleNotFoundError` for collector tests.
- **Recommendation:** Add `pytest.ini` or `pyproject.toml` `[tool.pytest.ini_options]` with separate paths. Run in CI as separate jobs.
- **Effort:** Small (1 hour)

---

### MEDIUM (41 findings)

| # | Domain | Finding | Files |
|---|--------|---------|-------|
| M-1 | Backend | EventIngest schema lacks length limits on strings | `api/schemas/events.py` |
| M-2 | Backend | PolicyCreate.parameters dict is unbounded | `api/routers/policies.py` |
| M-3 | Backend | Rate limits are per-IP only, no per-user/tenant | `api/main.py` |
| M-4 | Backend | No global exception handler (debug stack traces) | `api/main.py` |
| M-5 | Backend | EnrollRequest.public_key_pem unbounded | `api/routers/endpoints.py` |
| M-6 | Backend | CORS allows all methods and headers with credentials | `api/main.py` |
| M-7 | Frontend | No CSRF protection on POST requests | `dashboard/src/lib/auth.js` |
| M-8 | Frontend | Duplicate storage key definitions in auth.js and api.js | `dashboard/src/lib/auth.js`, `dashboard/src/lib/api.js` |
| M-9 | Frontend | API errors displayed directly to users (info leakage) | `LoginPage.jsx`, `DashboardPage.jsx`, `PoliciesPage.jsx` |
| M-10 | Frontend | Search input missing aria-label | `dashboard/src/components/layout/TopBar.jsx` |
| M-11 | Frontend | Filter dropdowns missing aria-expanded/aria-haspopup | `dashboard/src/components/dashboard/FilterBar.jsx` |
| M-12 | Frontend | User menu missing aria-expanded/aria-haspopup | `dashboard/src/components/layout/TopBar.jsx` |
| M-13 | Frontend | useEndpoints useEffect deps suppressed with eslint-disable | `dashboard/src/hooks/useEndpoints.js` |
| M-14 | Frontend | SettingsPage setTimeout not cleared on unmount | `dashboard/src/pages/SettingsPage.jsx` |
| M-15 | Frontend | searchQuery lost on page refresh | `dashboard/src/App.jsx` |
| M-16 | Frontend | Unused CopyToast import in ToolRow | `dashboard/src/components/dashboard/ToolRow.jsx` |
| M-17 | Frontend | Em dashes used throughout (violates workspace rule) | `parseNdjson.js`, `EndpointContextBar.jsx`, `ToolRow.jsx`, `index.html`, `index.css`, `DetecLogo.jsx`, `CopyToast.jsx` |
| M-18 | Frontend | Pagination pluralization bug ("5 totals") | `dashboard/src/components/dashboard/Pagination.jsx` |
| M-19 | Frontend | npm audit: esbuild vulnerability (GHSA-67mh-4wv8-2f99) | `dashboard/package.json` |
| M-20 | Collector | Env vars can override security-critical config (api_key) | `collector/config_loader.py` |
| M-21 | Collector | Config file not validated against schema | `collector/config_loader.py` |
| M-22 | Collector | No PID file for daemon mode (multiple instances) | `collector/main.py` |
| M-23 | Collector | Scanner exceptions swallowed, treated as inconclusive | `collector/main.py` |
| M-24 | Collector | Process name/cmdline can be spoofed | All pgrep-based scanners |
| M-25 | Collector | State file has no file locking | `collector/agent/state.py` |
| M-26 | Collector | Buffer trim not atomic (race with append) | `collector/agent/buffer.py` |
| M-27 | Collector | Policy network_elevated heuristic tied to rule ID naming | `collector/main.py` |
| M-28 | Collector | approval_required triggers same enforcement path as block | `collector/main.py` |
| M-29 | Collector | flush_buffer requeue list unused (dead code) | `collector/output/http_emitter.py` |
| M-30 | Collector | HttpEmitter import paths assume package layout | `collector/output/http_emitter.py` |
| M-31 | Collector | LM Studio scanner queries localhost HTTP without doc | `collector/scanner/lm_studio.py` |
| M-32 | Infra | docker-compose override volume mount overwrites container | `docker-compose.override.yml` |
| M-33 | Infra | Dashboard depends_on without health condition | `docker-compose.yml` |
| M-34 | Infra | Trivy action pinned to @master (unstable) | `.github/workflows/security.yml` |
| M-35 | Infra | Alembic 0002 downgrade loses API key data | `api/alembic/versions/0002_hash_api_keys.py` |
| M-36 | Infra | No pytest config in pyproject.toml | Root |
| M-37 | Infra | README quick start omits dashboard from compose | `README.md` |
| M-38 | Infra | SERVER.md .env instructions don't match compose config | `SERVER.md` |
| M-39 | Infra | Playbook version mismatch in cursor rules | `.cursor/rules/git-and-versioning.mdc` |
| M-40 | Infra | No dashboard health check in compose | `docker-compose.yml` |
| M-41 | Infra | Transitive Python deps not fully pinned | `api/requirements.lock` |

---

### LOW (53 findings)

| # | Domain | Finding |
|---|--------|---------|
| L-1 | Backend | Staleness monitor queries all endpoints without tenant scope |
| L-2 | Backend | HeartbeatRequest.hostname no max_length |
| L-3 | Backend | HeartbeatRequest.interval_seconds no min/max bounds |
| L-4 | Backend | Audit log filter parameters unvalidated lengths |
| L-5 | Backend | event_id unique globally, not per-tenant |
| L-6 | Backend | API key prefix collision possible (8 chars) |
| L-7 | Backend | No password complexity rules beyond length |
| L-8 | Backend | psycopg2-binary used (prefer source build for production) |
| L-9 | Backend | Staleness monitor swallows exceptions in loop |
| L-10 | Backend | ilike search does not escape % and _ wildcards |
| L-11 | Frontend | No dangerouslySetInnerHTML (good, informational) |
| L-12 | Frontend | CSRF risk reduced by Bearer token auth (not cookie-based) |
| L-13 | Frontend | Refresh failure clears tokens with no retry |
| L-14 | Frontend | Pagination page-size select missing aria-label |
| L-15 | Frontend | Sidebar nav buttons missing aria-current |
| L-16 | Frontend | TopBar debounce timeout not cleared on unmount |
| L-17 | Frontend | EventsPage is placeholder |
| L-18 | Frontend | AdminPage is placeholder |
| L-19 | Frontend | FilterBar "ACKNOWLEDGE ALL" button disabled (incomplete) |
| L-20 | Frontend | Hardcoded localhost API URL default |
| L-21 | Frontend | Vite proxy target hardcoded |
| L-22 | Frontend | ToolsTable key uses name+index (prefer stable IDs) |
| L-23 | Frontend | ToolRow not wrapped in React.memo |
| L-24 | Frontend | parseNdjson silently skips invalid lines |
| L-25 | Frontend | EndpointContextBar assumes API key length >= 8 |
| L-26 | Frontend | AuditLogPage crashes if actor_id is null |
| L-27 | Frontend | AuditLogPage crashes if resource_id is null |
| L-28 | Collector | Signing key generation not atomic (crash between writes) |
| L-29 | Collector | Linux key file mode check is unusual |
| L-30 | Collector | macOS Keychain locked/timeout not distinguished |
| L-31 | Collector | Windows PowerShell path injection possible |
| L-32 | Collector | Buffer directory created without explicit permissions |
| L-33 | Collector | EventEmitter output file no explicit permissions |
| L-34 | Collector | Daemon shutdown event not sent on SIGKILL |
| L-35 | Collector | Heartbeat thread is daemon (killed abruptly on exit) |
| L-36 | Collector | find_processes regex not documented |
| L-37 | Collector | State file malformed entries silently skipped |
| L-38 | Collector | ConfigWatcher extra_paths not validated |
| L-39 | Collector | verify_event_signature swallows all exceptions |
| L-40 | Collector | No rate limiting on HTTP retries |
| L-41 | Collector | Claude Cowork uses non-canonical action_type values |
| L-42 | Collector | Public key file has no explicit permissions set |
| L-43 | Infra | Docker base images not pinned to digest |
| L-44 | Infra | api/Dockerfile chmod runs as root |
| L-45 | Infra | api/.env.example has DEBUG=true |
| L-46 | Infra | Test conftest uses sys.path manipulation |
| L-47 | Infra | Alembic 0001 downgrade drops all tables |
| L-48 | Infra | dashboard/README.md scripts table outdated |
| L-49 | Infra | Deploy plist has placeholder API URL |
| L-50 | Infra | install/ vs deploy/ directories (two deploy paths) |
| L-51 | Infra | pyproject.toml only includes collector package |
| L-52 | Infra | requirements.lock may be stale |
| L-53 | Infra | dashboard/server.js NDJSON path may not exist in Docker |

---

## Remediation Plan

### Priority 1: Critical Security (Week 1)

| # | Fix | Files | Effort | Commit Message |
|---|-----|-------|--------|----------------|
| 1 | Remove hardcoded secrets from docker-compose.yml; use env_file + variable substitution | `docker-compose.yml`, `.env.example` | 1-2h | "Use env_file for Docker secrets to avoid committed credentials" |
| 2 | Fix PID extraction to handle string PIDs from scanners | `collector/main.py` | 1-2h | "Fix enforcement PID extraction to coerce string PIDs from pgrep" |
| 3 | Add file locking to buffer drain/append/trim | `collector/agent/buffer.py` | 3-4h | "Add file locking to LocalBuffer to prevent race conditions" |
| 4 | Implement audit log writes for sensitive actions | `api/routers/*.py`, new helper | 4-6h | "Populate audit_log for login, policy, and enrollment actions" |
| 5 | Enforce role-based access control in routers | `api/core/auth.py`, `api/routers/*.py` | 3-4h | "Enforce User.role checks on admin-only endpoints" |

### Priority 2: High Security (Week 2)

| # | Fix | Files | Effort |
|---|-----|-------|--------|
| 6 | Upgrade python-jose to >= 3.4.0 | `api/requirements.txt`, `api/requirements.lock` | 5 min |
| 7 | Rotate refresh tokens on use | `api/routers/auth.py` | 3-4h |
| 8 | Move seed key from /tmp to secure location | `api/main.py` | 1h |
| 9 | Add React error boundaries | `dashboard/src/` | 1-2h |
| 10 | Add React Router for URL-based navigation | `dashboard/src/` | 3-4h |
| 11 | Add explicit TLS context to HTTP emitter | `collector/output/http_emitter.py` | 15 min |
| 12 | Add process identity verification before kill | `collector/enforcement/process_kill.py` | 1-2h |
| 13 | Rename docker-compose.override.yml | `docker-compose.override.yml` | 30 min |
| 14 | Add CI jobs for build + tests | `.github/workflows/` | 2-3h |
| 15 | Consolidate .env.example files | `.env.example`, `api/.env.example` | 1h |
| 16 | Add refresh token mutex | `dashboard/src/hooks/useAuth.jsx` | 30 min |

### Priority 3: Medium Improvements (Week 3-4)

| # | Fix | Effort |
|---|-----|--------|
| 17 | Add Field(max_length) to all Pydantic schemas | 2h |
| 18 | Add per-user/tenant rate limiting | 2-3h |
| 19 | Add global exception handler to API | 1h |
| 20 | Fix all em dash violations | 1h |
| 21 | Centralize localStorage key definitions | 30 min |
| 22 | Fix Pagination pluralization bug | 5 min |
| 23 | Add aria-label/aria-expanded to UI elements | 2h |
| 24 | Add PID file for daemon mode | 1-2h |
| 25 | Add state file locking | 1-2h |
| 26 | Add config file schema validation | 2h |
| 27 | Fix flush_buffer dead code (requeue) | 30 min |
| 28 | Add dashboard health check to compose | 15 min |
| 29 | Pin Trivy action version | 5 min |
| 30 | Update cursor rules playbook version reference | 5 min |

### Priority 4: Low Polish (Ongoing)

Address remaining Low findings as part of regular development. Key items:
- Fix null crashes in AuditLogPage (`actor_id`, `resource_id`)
- Clear timeouts on component unmount
- Add aria-current to sidebar navigation
- Document regex patterns in process scanning
- Pin Docker base images to digest
- Add pytest configuration to pyproject.toml

---

## Suggested Commit Groupings

Following the workspace rule of one logical change per commit:

1. **Security: Docker secrets** (C-1, H-12, H-17)
2. **Security: Collector enforcement fixes** (C-3, H-7)
3. **Security: Buffer file locking** (C-2, M-26)
4. **Security: Audit log implementation** (C-4)
5. **Security: RBAC enforcement** (C-5)
6. **Security: Dependency upgrade** (H-2)
7. **Security: Auth hardening** (H-3, H-4, H-16)
8. **Frontend: Error boundaries + routing** (H-5, H-6)
9. **Frontend: Auth race condition** (H-15)
10. **Frontend: Accessibility improvements** (M-10, M-11, M-12, L-14, L-15)
11. **Frontend: Code quality fixes** (M-8, M-16, M-17, M-18, L-26, L-27)
12. **Backend: Input validation** (M-1, M-2, M-5, L-2, L-3)
13. **Collector: Daemon hardening** (M-22, M-25, H-9)
14. **Collector: Config validation** (M-21, M-20)
15. **Infra: CI pipeline** (H-13, M-34)
16. **Infra: Env + docs cleanup** (H-14, M-37, M-38, M-39)

---

## Methodology

Four parallel audit workstreams analyzed every file in the codebase:

1. **Backend Security**: All `api/` Python files (routers, models, schemas, core, migrations)
2. **Frontend Audit**: All `dashboard/src/` JS/JSX files (components, hooks, libs, pages)
3. **Collector Audit**: All `collector/` Python files (scanners, crypto, enforcement, output, agent)
4. **Infrastructure Audit**: Docker, CI/CD, env configs, deploy templates, documentation

Each finding was verified by reading source code and graded by exploitability, impact, and likelihood.

---

## Remediation Status

| ID | Severity | Status | Description |
|----|----------|--------|-------------|
| C-1 | Critical | Fixed | docker-compose env_file, .env.example |
| C-2 | Critical | Fixed | fcntl.flock advisory locking, atomic trim |
| C-3 | Critical | Fixed | _normalize_pid for string PIDs |
| C-4 | Critical | Fixed | audit_logger.record, auth/policy/endpoint logging |
| C-5 | Critical | Fixed | require_role in policies, endpoints, audit |
| H-2 | High | Fixed | python-jose >= 3.4.0 |
| H-4 | High | Fixed | seed key logged to stdout only |
| H-5 | High | Fixed | React ErrorBoundary |
| H-7 | High | Fixed | Process identity verification before kill |
| H-9 | High | Fixed | Credential store errors at WARNING level |
| H-11 | High | Fixed | ssl.create_default_context in HttpEmitter |
| H-12 | High | Fixed | docker-compose.override.yml renamed to .dev.yml |
| H-14 | High | Fixed | Consolidated two .env.example files |
| H-15 | High | Fixed | refresh mutex in useAuth |
| H-16 | High | Fixed | unsigned event rejection for enrolled endpoints |
| H-17 | High | Fixed | DB port no longer auto-exposed (via H-12) |
| H-19 | High | Fixed | pytest config in pyproject.toml |
| M-1/M-2/M-5 | Medium | Fixed | Field(max_length) on schemas |
| M-4 | Medium | Fixed | Global exception handler |
| M-8 | Medium | Fixed | STORAGE_KEYS centralized in auth.js |
| M-10 | Medium | Fixed | Search input aria-label |
| M-11 | Medium | Fixed | FilterBar dropdown aria-expanded/aria-haspopup |
| M-12 | Medium | Fixed | User menu aria-expanded/aria-haspopup |
| M-17 | Medium | Fixed | em dashes replaced in all dashboard files |
| M-18 | Medium | Fixed | Pagination "totals" pluralization |
| M-25 | Medium | Fixed | State file advisory locking |
| M-29 | Medium | Fixed | flush_buffer dead code removed |
| M-33 | Medium | Fixed | Dashboard depends_on health condition |
| M-34 | Medium | Fixed | Trivy action pinned to v0.28.0 |
| M-40 | Medium | Fixed | Dashboard health check in compose |
| L-10 | Low | Fixed | ilike wildcard escaping |
| L-14 | Low | Fixed | Pagination page-size aria-label |
| L-15 | Low | Fixed | Nav buttons aria-current |
| L-16 | Low | Fixed | TopBar debounce timeout cleanup |
| L-26/L-27 | Low | Fixed | AuditLogPage null guards |
| M-14 | Medium | Fixed | SettingsPage timeout cleanup |
| H-3 | High | Fixed | Refresh token rotation with JTI tracking |
| H-8 | High | Fixed | Documented UID-scoped network block limitation in DEPLOY.md |
| H-13 | High | Fixed | Added CI workflow for tests and Docker builds |
| M-6 | Medium | Fixed | CORS restricted to specific methods and headers |
| M-22 | Medium | Fixed | PID file for daemon mode (prevents duplicate instances) |
| L-25 | Low | Fixed | EndpointContextBar API key length guard |
| L-33 | Low | Fixed | EventEmitter output file explicit 0o600 permissions |
| L-42 | Low | Fixed | Public key file explicit 0o644 permissions |
| H-6 | High | Fixed | React Router for URL-based navigation |
| L-9 | Low | Fixed | Staleness monitor exception logging at WARNING |

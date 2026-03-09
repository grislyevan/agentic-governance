# Changelog

All notable changes to this project are documented here.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [Unreleased]

### Added

- **All 12 scanners cross-platform**: Migrated the remaining 9 scanners (aider,
  claude_code, claude_cowork, cline, continue_ext, gpt_pilot, lm_studio,
  open_interpreter, openclaw) from Unix-specific `pgrep`/`ps`/`lsof` commands
  to the compat abstraction layer (`find_processes`, `get_child_pids`,
  `get_process_info`, `get_connections`). All scanners now work on Windows,
  macOS, and Linux via psutil. Added lm_studio and openclaw path entries to
  the compat path registry.
- **Events page**: Built a full SOC event browser at `/events` with filterable
  table (decision state, tool name), pagination, and a slide-out detail panel
  showing the complete event payload. Replaces the previous placeholder.
- **Windows Service packaging**: Added `detec-server` CLI with `setup`, `run`,
  `install`, `start`, `stop`, `remove`, and `status` subcommands. On Windows,
  the server registers as a Windows Service ("Detec Server") via pywin32.
  Includes a PyInstaller spec (`packaging/windows/detec-server.spec`) that
  bundles the API, dashboard, and all dependencies into a single distributable
  directory. First-run `setup` command auto-generates JWT secret and seed admin
  password, writing config to `C:\ProgramData\Detec\server.env`.
- **Dashboard served from FastAPI**: The React dashboard is now served as static
  files directly from FastAPI (`dashboard/dist/`). Build with
  `cd dashboard && npm run build`, then start the API. No separate Node.js
  process or Docker container needed. API routes moved under the `/api/` prefix;
  the dashboard UI is served at the root URL. SPA routing is handled via a
  catch-all that returns `index.html` for non-file paths.
- **SQLite as default database**: The API now defaults to a local SQLite database
  with zero configuration. The database file is created automatically at a
  platform-appropriate path (Windows: `C:\ProgramData\Detec\detec.db`, macOS:
  `~/Library/Application Support/Detec/detec.db`, Linux:
  `~/.local/share/detec/detec.db`). SQLite uses WAL journal mode for concurrent
  read support and busy timeout for resilience. PostgreSQL remains fully
  supported by setting `DATABASE_URL`.

### Changed

- **JSONB replaced with JSON**: All three models that used PostgreSQL-specific
  `JSONB` columns (`Event.payload`, `AuditLog.detail`, `Policy.parameters`) now
  use SQLAlchemy's dialect-agnostic `JSON` type. This makes the API compatible
  with SQLite, PostgreSQL, and other SQL backends without code changes.
- **Alembic migrations**: Initial migration (0001) updated from `postgresql.JSONB`
  to `sa.JSON()`. Alembic `env.py` now enables `render_as_batch` mode when
  running against SQLite (required for `ALTER TABLE` operations).
- **RBAC**: `require_role` guards on policy, enrollment, and audit endpoints now
  include `owner` alongside `admin`. Previously, tenant owners (the first user
  who registers) were locked out of policy management and endpoint enrollment.
- **Rate limiting in tests**: Test environment sets `RATELIMIT_ENABLED=false` via
  slowapi's config key, preventing rate limit interference in the test suite.
  Production rate limiting is unaffected.

### Fixed

- **M-28: approval_required enforcement**: `approval_required` policy decisions
  no longer trigger the enforcer (process kill / network block). Only `block`
  decisions invoke enforcement. Previously both states were treated identically,
  contradicting the playbook semantics where `approval_required` means "flag for
  human review," not "block."
- Test `test_me_returns_user_info` expected `role == "admin"` but registration
  returns `"owner"` (changed in a prior release). Updated assertion.
- Policy list tests iterated over `resp.json()` directly instead of
  `resp.json()["items"]` (the endpoint was updated to paginated responses but
  the tests were not).

---

- **User management system**: backend CRUD for tenant users at `/users` (list,
  create, get, update, deactivate). Enforces a four-role model: owner, admin,
  analyst, viewer. Owner cannot be modified or deactivated. Soft-delete via
  `is_active=false`. All actions write to the audit log (`user.created`,
  `user.updated`, `user.deactivated`).
- **Admin page (dashboard)**: replaces the placeholder with a full users table,
  search, pagination, "Add user" modal, inline edit, deactivate/reactivate
  toggle, and color-coded role badges (gold/blue/teal/slate). Page is gated to
  owner and admin roles.
- **Split name fields**: `full_name` column replaced by `first_name` and
  `last_name` (migration 0005). TopBar, LoginPage registration form, and
  `/auth/me` response all use the new fields.
- **SSO/SAML groundwork**: `auth_provider` column (`local`, `saml`, `oidc`) and
  `password_reset_required` flag added to the users table. Only `local` users
  can be created today; the columns prepare for future SSO integration.
- **User schemas** (`api/schemas/users.py`): `UserCreate`, `UserUpdate`,
  `UserOut`, `UserListResponse` with field validation.
- **Frontend API client**: `fetchUsers`, `createUser`, `updateUser`,
  `deleteUser` functions and shared `apiMutate` helper.

### Changed

- Seed user and self-registered users now get role `owner` instead of `admin`
  (they are tenant creators).
- `VALID_ROLES` constant defined in `api/models/user.py` and imported by
  `api/core/tenant.py` for RBAC checks.
- Registration form uses separate first name / last name fields instead of a
  single full name input.
- TopBar displays `first_name last_name` and derives initials from split fields.
- `UserResponse` schema includes `first_name`, `last_name`, and `auth_provider`.

- **Dashboard UI redesign**: full SOC operator console with sidebar navigation,
  top bar, multi-endpoint dashboard, tabbed tool filtering, and dark theme
  matching the Detec design tokens.
- **Dashboard authentication**: login/register pages, JWT token management with
  auto-refresh, user profile display (name, role, initials) in TopBar, logout.
  `AuthProvider` context wraps the app and gates access.
- **Functional dashboard controls**: search (client-side with debounce), refresh,
  notification bell (block + approval count), endpoint filter dropdown, time
  range picker (1h/6h/24h/7d/30d/All), tool tab navigation links (Collector
  logs, View policies), overflow menu on tool rows (View details, Copy tool
  name, Copy full details).
- **Live data pages**: Policies page fetches from `GET /policies`, Audit Log
  page fetches from `GET /audit-log`.
- **Backend: `GET /audit-log` route** (`api/routers/audit.py`): read-only,
  paginated, tenant-scoped endpoint for the `AuditLog` model. Mounted in main
  app.
- **Backend: `GET /auth/me` now accepts `X-Api-Key`** in addition to Bearer
  JWT, resolving the user via API key prefix lookup.
- **Backend: event filters**: `GET /events` gained `observed_after`,
  `observed_before` (datetime range), and `search` (ILIKE on tool_name) query
  params.
- **API client extensions**: `fetchAuditLog()` and `fetchPolicies()` functions;
  `fetchEvents` and `fetchAllEvents` support new filter params.
- **Accessibility**: `aria-label` on both nav elements, tools table, bell
  button, and row actions; `aria-hidden="true"` on all decorative SVG icons;
  keyboard support (tabIndex, role, onKeyDown, aria-expanded) on expandable
  table rows; `role="tablist"` and `aria-selected` on tool filter tabs.

### Fixed

- Pagination "first page" button jumped to `page - 1` instead of page 1.
- Confidence dot color used fragile CSS class-name string comparison; replaced
  with a direct color map keyed by confidence band.
- "Detected" summary card used `detec-teal-500` (teal) instead of
  `detec-enforce-detect` (indigo), inconsistent with other enforcement colors.
- "DETECTED" badge in ToolRow also updated to use `detec-enforce-detect` tokens.
- Sidebar icons used hardcoded hex stroke colors; switched to `currentColor`
  with Tailwind text classes for consistency with TopBar icons.

### Removed

- Dead code: `fetchAllApiEvents` and `transformApiEvents` from `parseNdjson.js`
  (unused after API client refactor).
- Duplicate `severityLabel` function from `ToolRow.jsx` (now imported from
  `parseNdjson.js`).
- Hardcoded "Alex Smith / DevOps Engineer" user profile (replaced with real
  auth context).
- Non-functional edit icon on Dashboard page title.
- Fake dropdown chevrons on TopBar nav items (Endpoints, Admin).
- Non-functional "Filter" button in TopBar (refresh button retained).

### Changed

- `api.js` uses Bearer JWT token when available, falling back to X-Api-Key.
- `useEndpoints` hook accepts filter params (observedAfter, endpointId) and
  passes them through to the API.
- `EndpointContextBar` shows real API key prefix from config, derives signal
  bars from endpoint status ratios, and displays "Multiple" / "Various" for
  multi-endpoint scenarios.
- Sidebar Events badge is data-driven (shows dot only when block + approval
  count > 0).
- FilterBar "ACKNOWLEDGE ALL" button is honestly disabled with a tooltip
  indicating the feature is coming.
- `severityLabel` in `parseNdjson.js` now returns human-readable names (Info,
  Low, Medium, High, Critical) instead of echoing the S0-S4 codes.

---

- Centralized collector configuration: JSON config file
  (`collector/config/collector.json`), environment variable overrides
  (`AGENTIC_GOV_*` prefix), and documented precedence
  (CLI > env > config file > code defaults).
- `collector/config_loader.py` — single module for loading and merging config
  from all sources.
- `collector/config/collector.example.json` — annotated example config with
  `config_version: 1`.
- Configuration section in `collector/README.md` covering config file location,
  env var table, and precedence rules.
- This `CHANGELOG.md` for tracking versioned, user-facing changes (complements
  `PROGRESS.md` which tracks ongoing development work).

### Changed

- `collector/main.py` now loads defaults from the config file and environment
  variables before applying CLI flags, rather than relying solely on hardcoded
  argparse defaults.

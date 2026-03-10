# Changelog

All notable changes to this project are documented here.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [Unreleased]

### Fixed

- **Windows agent service startup (3 fixes)**:
  - **SCM dispatch**: When the SCM started `detec-agent.exe` with no arguments,
    the process printed argparse help and exited instead of calling
    `StartServiceCtrlDispatcher`. Now detects frozen + no-args + Windows and
    delegates to the service framework.
  - **Signal registration crash**: `_run_daemon` called `signal.signal()` from a
    background thread (the service wrapper runs the daemon in a thread), which
    raises `ValueError`. Now caught so the daemon loop proceeds; the SCM handles
    stop via the service stop event.
  - **SCM timeout**: The frozen PyInstaller bundle takes >30s to import all
    scanner modules, exceeding the SCM's default startup timeout. The service now
    reports `SERVICE_START_PENDING` with a 120-second wait hint before the slow
    import.
- **Schema validator in PyInstaller bundles**: The event validator resolved the
  schema path relative to `__file__`, which points inside `_internal/` in frozen
  bundles. Now uses `sys._MEIPASS` when available, so the bundled `schemas/`
  directory is found correctly.
- **Inno Setup preprocessor error**: Lines starting with `#13` (Pascal character
  constants) inside `[Code]` sections were interpreted as preprocessor directives.
  Moved `#13#10` onto previous lines so no line begins with `#`.

- **API test suite (35 of 53 failures)**: `test_gateway.py` created its own
  `StaticPool` in-memory SQLite engine and patched `core.database`, overwriting
  the conftest's shared engine. This caused test-to-test contamination where
  `drop_all`/`create_all` cleaned one database while the app used another.
  Additionally, the gateway (`GATEWAY_ENABLED` defaulting to `true`) started a
  TCP listener during every `TestClient` lifespan, causing import failures or
  port conflicts. Fixed by sharing the conftest engine and setting
  `GATEWAY_ENABLED=false` in the test environment. Suite now passes 54/54.

- **Status window icon**: The status window now loads `Icon.icns` from the app
  bundle resources instead of the programmatic aperture renderer, so the window
  displays the actual app icon. Falls back to the programmatic renderer when
  running outside the bundled `.app`.
- **Status window footer**: Version string updated to
  `Version 0.3 - Build no. 0.3.0` (added dash separator, corrected build number
  to match `CFBundleVersion`).
- **Status text ellipsis**: "Agent Status:" changed to "Agent Status..." across
  all status states and the dynamic fallback.

- **macOS .pkg installer ownership**: The postinstall script runs as root,
  so the LaunchAgent plist, log directory, state directory, and Application
  Support directory were all created with root ownership. `launchctl`
  silently refuses to load user-domain plists owned by root, preventing the
  agent from starting. The script now resolves the real user via
  `stat -f '%Su' "$HOME"` and `chown`s all created files back to them.
- **GUI crash on unwritable log directory**: If `~/Library/Logs/DetecAgent/`
  is not writable (e.g., from the ownership bug above), the menu bar app
  now falls back to stderr-only logging instead of crashing on startup.

### Added

- **Windows system tray agent**: New `detec-agent-gui.exe` for Windows provides a
  notification-area icon (using pystray) and a tkinter status window matching the
  macOS reference design. Shows connection status, logo, version, and year. Context
  menu with status, scan-now, and quit. Separate PyInstaller spec
  (`packaging/windows/detec-agent-gui.spec`) produces a windowed (non-console) build.
- **Icon assets**: Generated `branding/Icon.ico` (7 sizes, 16-256px) from the macOS
  iconset PNGs. Copied `branding/Icon.icns` to canonical location. Both are bundled
  into their respective platform builds.
- **Dashboard auto-refresh polling**: All data pages (Dashboard, Events, Policies,
  Audit Log) now auto-refresh every 30 seconds. A `usePolling` hook manages the
  interval with an in-flight guard to prevent overlapping fetches. Each page shows
  a live "Updated Xs ago" indicator with an animated pulse dot and a pause/play
  toggle. Pausing stops the interval; resuming restarts it.
- **Policy configuration UI**: The Policies page is now fully interactive for
  owner and admin roles. Create policies with rule ID, version, description,
  active toggle, and a JSON parameters editor. Edit existing policies inline.
  Enable/disable policies with a single click. Policy cards show decision state
  badges and a readable parameter grid. Empty state prompts the user to create
  their first policy.
- **Policy partial updates (backend)**: `PATCH /policies/{id}` now accepts a
  `PolicyUpdate` schema with all-optional fields. Only provided fields are
  updated (true PATCH semantics). `is_active` can be toggled independently
  without resending the full policy.
- **API client functions**: `createPolicy()` and `updatePolicy()` added to the
  dashboard's API client (`dashboard/src/lib/api.js`).

- **Binary wire protocol (Detec Wire Protocol)**: New `protocol/` package providing
  a msgpack-based, length-prefixed binary framing layer for agent-server
  communication over persistent TCP connections (port 8001). Includes message
  type enum, encode/decode functions, incremental `FrameReader`, and an asyncio
  `BaseConnection` class with keepalive and graceful shutdown.
- **DetecGateway (server-side TCP gateway)**: `api/gateway.py` implements an
  asyncio TCP/TLS server that accepts persistent agent connections, authenticates
  via API key, ingests events and heartbeats using existing SQLAlchemy models,
  and supports server-push (policy updates, remote commands). Integrated into the
  FastAPI lifespan so it starts/stops with the API process.
- **TcpEmitter (agent-side TCP transport)**: `collector/output/tcp_emitter.py`
  provides a synchronous interface over a background asyncio thread for persistent
  TCP connections, event batching, acknowledgement tracking, automatic reconnection
  with exponential backoff, and fallback to `LocalBuffer` when disconnected.
- **Protocol selection CLI**: `--protocol tcp|http`, `--gateway-host`, and
  `--gateway-port` flags on both `detec-agent` and `detec-agent setup`. Config
  keys `protocol`, `gateway_host`, `gateway_port` supported in collector.json
  and `AGENTIC_GOV_*` environment variables.
- **Gateway server config**: `GATEWAY_ENABLED`, `GATEWAY_HOST`, `GATEWAY_PORT`,
  `GATEWAY_TLS_CERT`, `GATEWAY_TLS_KEY` settings in `api/core/config.py` and
  `.env.example`.
- **Protocol test suite**: 45 unit tests for wire format, messages, and connection,
  plus an end-to-end integration test that verifies the full agent-gateway-database
  path.
- **Packaging updates**: PyInstaller specs (macOS, Windows agent, Windows server)
  updated with `protocol` and `msgpack` hidden imports. Windows deploy script
  adds firewall rule for TCP 8001 alongside HTTP 8000.

- **macOS uninstaller**: `packaging/macos/uninstall.sh` cleanly removes the
  Detec Agent: stops the LaunchAgent, deletes the app from `/Applications`,
  removes config (`~/Library/Application Support/Detec/`), logs
  (`~/Library/Logs/DetecAgent/`), state (`~/.agentic-gov/`), the Keychain
  entry, and the installer receipt. Run with `sudo`.

- **GUI agent loads agent.env**: The macOS menu bar app (`DaemonBridge`) now
  loads `~/Library/Application Support/Detec/agent.env` on startup so config
  written by `detec-agent setup` is picked up by the GUI app without manual
  environment variable setup. Cross-platform: also loads from
  `C:\ProgramData\Detec\Agent\agent.env` (Windows) and
  `~/.local/share/detec/agent.env` (Linux).

- **Scan pipeline integration tests**: 20 new tests covering `build_event`
  schema conformance for all event types, `_process_detection` event chains,
  parent_event_id linking, enforcement gating (M-28 regression guard),
  StateDiffer suppression, cleared events, scanner failure isolation,
  run_scan end-to-end (dry-run and NDJSON), and HttpEmitter stats
  compatibility. Total collector tests: 186.
- **Auto-migration on API startup**: The server now runs
  `alembic upgrade head` automatically during startup, falling back to
  `create_all` if Alembic is unavailable. Operators no longer need a
  separate migration step for on-prem deployments.
- **Windows collector agent packaging**: Added `detec-agent` CLI
  (`collector/agent_cli.py`) with `setup`, `scan`, `run`, `install`, `start`,
  `stop`, `remove`, and `status` subcommands. Includes a pywin32 Windows
  Service wrapper (`collector/win_agent_service.py`) registered as "Detec
  Agent". PyInstaller spec (`packaging/windows/detec-agent.spec`) bundles
  the collector, all scanners, and compat layer into a distributable
  directory. Build script (`build-agent.ps1`) automates the pipeline.
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
- **Inno Setup GUI installer for Windows Server**: Single `DetecServerSetup.exe`
  for zero-PowerShell client deployment. Branded wizard; build via
  `packaging/windows/build-installer.ps1` (requires Inno Setup 6).
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

- **Cross-tenant read visibility for owner/admin roles**: Read-only query
  endpoints (events, endpoints, endpoint status, audit log, policies, users)
  now return data across all tenants when the authenticated user has the
  `owner` or `admin` role. Analyst and viewer roles remain scoped to their
  own tenant. Write and ingest endpoints are unchanged and still enforce
  strict per-tenant isolation. Centralized via `get_tenant_filter()` helper
  in `api/core/tenant.py`.
- **Event schema v0.3.0**: Added `enforcement` object definition (tactic,
  success, detail) to the canonical schema alongside `outcome`. The
  `enforcement.applied` conditional now requires both `enforcement` and
  `outcome`. Added `removal` to the `action.type` enum for
  `detection.cleared` events. Schema `$id` bumped to v0.3.0.
- **build_event populates outcome**: `enforcement.applied` events now include
  both the `enforcement` detail block and the `outcome` block
  (`enforcement_result`, `incident_flag`, `incident_id`), making them
  schema-compliant. Previously only `enforcement` was written, which the
  schema didn't recognize.
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

- **Windows Service auto-start**: Both `DetecServer` and `DetecAgent` services
  now register with `SERVICE_AUTO_START`, so they start automatically on boot
  without manual intervention.
- **Desktop shortcut**: The deploy script (`deploy.ps1`) creates a "Detec
  Dashboard" shortcut on the Public Desktop that opens the dashboard URL in the
  default browser. Deployment now runs 9 steps (was 8).
- **One-command VM deploy**: `bootstrap.ps1` installs Python 3.11, Node.js
  22.14 LTS, and Git, then runs the full deployment. Updated to use Node 22 to
  meet Vite's minimum version requirements.

### Fixed

- **Windows Service Error 1053**: When the SCM started `detec-server.exe` with
  no arguments, it fell through to argparse help and exited instead of
  registering with the service dispatcher. Now detects the no-argument case and
  enters service mode immediately.
- **Windows Service crash (stderr is None)**: Uvicorn's `DefaultFormatter`
  calls `sys.stderr.isatty()` during logging setup, but Windows Services have
  no console so `sys.stderr` is `None`. Both streams are now redirected to
  `C:\ProgramData\Detec\server.log` when absent.
- **Service crash diagnostics**: The `SvcDoRun` exception handler now writes
  the full Python traceback to the Windows Event Log (Application, source
  "DetecServer") instead of a generic "crashed unexpectedly" message.
- **Frozen bundle path resolution**: `win_service.py` now uses `sys._MEIPASS`
  (PyInstaller's bundle directory) for `_api_dir` instead of
  `Path(__file__).parent`, ensuring modules and data files are found regardless
  of the working directory the SCM launches from.
- **Deploy script --port bug**: Removed the invalid `--port` argument from the
  `setup` call in `deploy.ps1` (the `setup` subcommand only accepts
  `--admin-email` and `--force`).
- **HttpEmitter stats interface**: `HttpEmitter.stats` now includes `emitted`
  and `failed` keys (aliasing `sent` and `buffered`), matching the interface
  `run_scan` expects. Previously, daemon mode would crash with a `KeyError`
  when accessing stats after a scan cycle.
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

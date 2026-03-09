# Changelog

All notable changes to this project are documented here.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [Unreleased]

### Added

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

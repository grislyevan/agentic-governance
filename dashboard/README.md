# Agentic Governance Dashboard

SOC operator console for the Detec platform. Multi-endpoint view of detected AI tools, confidence scoring, policy decisions, and enforcement state. For a short product roadmap (evidence drill-down, approval flows, alerts, etc.), see [docs/dashboard-roadmap.md](../docs/dashboard-roadmap.md).

## Prerequisites

- Node.js 20+
- A running Detec API (see [SERVER.md](../SERVER.md)) or the local NDJSON server for demo mode

## Quick start

```bash
cd dashboard
npm install
npm run dev
```

Open [http://localhost:5173](http://localhost:5173).

The dashboard requires authentication. Log in with your email and password (created via `POST /auth/register` or the seed admin from the API). Alternatively, configure an API key in Settings.

## Architecture

```
dashboard/src/
  main.jsx                  Entry point, wraps app in AuthProvider
  App.jsx                   Auth gate + shell (sidebar, topbar, page router)
  index.css                 Tailwind directives + base overrides
  parseNdjson.js            NDJSON parsing and event helpers
  lib/
    api.js                  API client (endpoints, events, policies, audit log, users, webhooks, auth flows)
    auth.js                 Token management (login, register, refresh, logout)
  hooks/
    useAuth.jsx             React auth context (user, login, logout, auto-refresh)
    useEndpoints.js         Fetch + aggregate multi-endpoint data with filters
  components/
    branding/DetecLogo.jsx  SVG aperture mark + wordmark
    layout/Sidebar.jsx      Left nav with data-driven event badge
    layout/TopBar.jsx       Search, refresh, notifications, user profile + logout
    dashboard/
      SummaryCards.jsx      Blocked/Approval/Warned/Detected counts
      FilterBar.jsx         Endpoint selector, time range picker
      EndpointContextBar.jsx  Endpoint count, status, API key, signal bars
      ToolTabs.jsx          Tab filter + navigation links
      ToolsTable.jsx        Main data table
      ToolRow.jsx           Expandable row with overflow menu
      Pagination.jsx        Page navigation + rows-per-page
  pages/
    LoginPage.jsx           Email/password login with registration toggle, forgot password
    ResetPasswordPage.jsx   Forgot-password email form with copyable reset link
    SetPasswordPage.jsx     Token-based password set (invite accept + password reset)
    DashboardPage.jsx       Full implementation with search, filters, refresh
    EventsPage.jsx          Full SOC event browser (filters, pagination, detail panel)
    PoliciesPage.jsx        Live policy list from API
    AuditLogPage.jsx        Live audit log table from API
    AdminPage.jsx           User management (table, search, invite/edit/deactivate)
    SettingsPage.jsx        API connection config + webhook management
```

## Authentication

The dashboard supports two auth methods:

1. **JWT login** (primary): email + password via `POST /auth/login`. Tokens are stored in localStorage and auto-refreshed.
2. **API key** (fallback): configured in Settings. Used when no JWT is available.

User profile (first name, last name, role) is pulled from `GET /auth/me` and displayed in the top bar. The Admin page (visible to owner and admin roles) provides user management: listing, inviting, editing, and deactivating users. Owner and admin roles see data across all tenants on read endpoints; analyst and viewer roles see only their own tenant's data. Logout clears tokens and returns to the login page.

### Invite and password reset flows

- **Invite**: Admins create users via the "Invite user" button (no temporary password). The API returns a one-time invite token. The admin copies the invite link and shares it. The new user visits `/set-password?token=...&purpose=invite` to set their password.
- **Password reset**: The login page has a "Forgot password?" link. The user enters their email, receives a reset link (displayed in the UI until email is configured), and visits `/set-password?token=...&purpose=reset` to choose a new password.
- **Login enforcement**: When a user with `password_reset_required=true` logs in, the dashboard redirects them to the set-password page.

## Data flow

The `useEndpoints` hook fetches events from the API with optional filters (time range, endpoint ID), aggregates them client-side into per-tool rows with decision counts, and provides the data to all dashboard components. The TopBar search filters tools client-side with debounce.

## Scripts

| Command | Description |
|---------|-------------|
| `npm run dev` | Start Vite + NDJSON server (for demo without the API) |
| `npm run dev:vite` | Vite only |
| `npm run build` | Build static assets to `dist/` |
| `npm run server` | Run only the NDJSON server (port 3001) |
| `npm start` | Build and serve app + NDJSON server (port 3001) |

## Design tokens

Colors are defined in `branding/tailwind-colors.js` and imported into `tailwind.config.cjs`. The dashboard uses IBM Plex Sans (body) and IBM Plex Mono (code/data). Dark theme throughout, with enforcement colors mapped to `detec-enforce-*` tokens.

# Dashboard roadmap

Short product/UX roadmap for the Detec SOC dashboard. The stack is React/Vite with a minimal dependency set today; this doc marks what exists vs planned so the UI direction is explicit without overexposing complexity on the front page.

## Today (shipped)

- **Auth:** JWT login, register, invite and password reset flows, API key fallback in Settings
- **Endpoints:** Multi-endpoint view with filter, status, signal bars; search and time range
- **Policies:** List from API; create, edit, toggle active from the dashboard (owner/admin)
- **Audit log:** Paginated read-only table from API
- **User management:** Admin page for users (invite, edit, deactivate); roles: owner, admin, analyst, viewer
- **Webhooks:** CRUD and test in Settings
- **Layout:** Sidebar, top bar, responsive; dark theme and Detec branding

## Planned (roadmap)

- **Policy editing UX:** Richer rule configuration (conditions, thresholds, exceptions) and bulk edit
- **Evidence drill-down:** Per-event and per-detection evidence (signals, layers, raw refs) in the UI
- **Tenant/admin views:** Org switcher and tenant-scoped views; admin-only dashboards
- **Exceptions and allow lists:** UI to manage per-endpoint or per-tool exceptions and allow-list entries
- **Alerts and notifications:** In-app and external (e.g. webhook-triggered) alert configuration and history
- **Approval flows:** Workflow for “approval required” decisions (request, approve/deny, audit trail)

Dependencies (e.g. data grid, form library) will be added as we implement these; the current `package.json` is intentionally minimal.

## Links

- [Dashboard README](../dashboard/README.md) for architecture and dev setup
- [Root README](../README.md#dashboard) for quick start and serving

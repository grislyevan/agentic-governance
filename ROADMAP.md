# Detec Roadmap

## Shipped (this sprint — 2026-04)

### Telemetry
- macOS ESF native telemetry: code complete, entitlement + MDM deployment guide (`docs/mdm-deployment.md`)
- Windows ETW native telemetry: code complete, ctypes backend (no pywintrace dependency)
- Telemetry provider badge per endpoint in dashboard (Native ESF/ETW/eBPF vs Polling)

### Dashboard & Workflow
- Approval flows UI: full request / approve / deny workflow
- Exceptions / allow-list UI: CRUD with expiry, scope, reason codes, bulk extend
- Policy change history: per-policy audit timeline with before/after field diff
- Exception change history: per-exception audit timeline with diff view
- docker-compose demo: single `docker compose -f docker-compose.demo.yml up` evaluator stack

### Agent & Collector
- ETW ctypes backend bundled in Windows installer (no pip install required)
- Cross-platform scanner fixes: pgrep/lsof replaced with psutil compat layer on Windows
- PowerShell version query caching + timeout reduction

## In Progress (active development — 2026-04)

- Real-time approval queue: Server-Sent Events replacing 30s polling on ApprovalsPage
- Agent key rotation: `POST /api/agent/key/rotate` + dashboard UI
- Universal ESF helper binary: arm64 + x86_64 fat binary via CI matrix build
- Policy Studio edit mode: routing existing-policy edits through the guided wizard

## Planned (next)

- Policy editing UX: richer rule configuration (conditions, thresholds) + bulk edit
- Tenant / org switcher: multi-org support in dashboard
- Alerts and notifications: in-app + webhook-triggered alert config
- Agent key rotation: automatic re-auth on key rotation without agent restart
- Linux eBPF telemetry: CO-RE eBPF backend (requires BCC or libbpf)
- ETW UserData struct validation: manifest-driven field extraction (requires Windows test environment)

## Explicitly Deferred

- General-purpose EDR capabilities (Detec is scoped to AI tools and agents)
- Browser activity monitoring / prompt logging
- Tenant isolation at the infrastructure level (current: logical DB isolation)

---

*Last updated: 2026-04-01. For capability maturity details see [docs/product-status.md](docs/product-status.md).*

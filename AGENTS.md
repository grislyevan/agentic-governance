# Agent brief — read this first

**What this repo is:** Detec (agentic-governance) — endpoint security for agentic AI tools. An endpoint agent (collector) scans machines for tools (Claude Code, Cursor, Ollama, Copilot, etc.), scores confidence, evaluates policy, and sends events to a central API. A React dashboard and FastAPI backend complete the stack.

**Architecture:** Endpoint agent → `POST /api/events`, `POST /api/endpoints/heartbeat` (HTTP) or persistent binary/msgpack connection on port 8001 (TCP) → FastAPI (API + serves dashboard) + DetecGateway → SQLite or PostgreSQL.

---

## Key paths (open only when the task needs them)

| Path | Purpose |
|------|--------|
| `collector/` | Python agent: scanners, confidence engine, policy, HTTP + TCP emitters, telemetry providers. Entry: `main.py`; daemon: `--interval` + `--api-url` + `--api-key` + `--protocol tcp\|http` + `--telemetry-provider auto\|native\|polling`. Config: `config_loader.py` + `config/collector.json` + `AGENTIC_GOV_*` env. |
| `collector/telemetry/` | Event store (thread-safe ring buffer) and typed event classes (`ProcessExecEvent`, `NetworkConnectEvent`, `FileChangeEvent`). Decouples telemetry collection from scanner consumption. |
| `collector/providers/` | Telemetry provider interface and implementations. `PollingProvider` (psutil-based, always available), provider registry (`get_best_provider()`). Native OS providers (ESF, ETW, eBPF) will be added here. |
| `api/` | FastAPI backend: auth (JWT + API key, invite tokens, password reset), events, endpoints, policies, users, webhooks, billing, EDR enrichment. Binary protocol gateway (`gateway.py`, port 8001). Stripe billing (`core/billing.py`, `core/tier_limits.py`, `routers/billing.py`). Baseline policies seeded per tenant (`core/baseline_policies.py`). Config: `core/config.py` + `.env` (see root `.env.example`). |
| `api/integrations/` | Server-side EDR enrichment: `EDRProvider` interface, CrowdStrike Falcon stub, enrichment pipeline for rescoring confidence with EDR telemetry. |
| `protocol/` | Shared binary wire protocol package (msgpack framing, message types, connection base class). Imported by both `api/` and `collector/`. |
| `dashboard/` | React/Vite SOC UI. Build: `npm run build`; dev: `npm run dev` (proxies API). Served by FastAPI at root when built. |
| `playbook/` | Governance playbook (versioned Markdown). Detection profiles, policy rules, lab methodology. |
| `schemas/` | Canonical event JSON Schema. |
| `deploy/` | Agent auto-start templates: macOS LaunchAgent, Linux systemd, Windows Task. |
| `packaging/` | Installer builds: macOS .app/.pkg, Windows agent + server (PyInstaller, Inno Setup). |
| `docs/` | MDM deployment, macOS permissions. |
| `branding/` | Logos, guidelines, agent-v1 UI reference. |
| `legal/` | Terms of Service, Software License Agreement. Root `LICENSE` has BSL 1.1. |
| `lab-runs/`, `init-issues/` | Lab results and backlog. |

---

## Quick start (for “does it run?” checks)

```bash
# Agent one-shot (no API)
pip install -e . && detec-agent --dry-run --verbose

# Full stack (API + dashboard at http://localhost:8000)
cd dashboard && npm run build && cd ../api && pip install -r requirements.txt
export JWT_SECRET="$(openssl rand -hex 32)" SEED_ADMIN_PASSWORD="pick-a-strong-password"
uvicorn main:app --reload
```

Default dashboard login: `admin@example.com` / `change-me` (unless overridden by `SEED_ADMIN_EMAIL` / `SEED_ADMIN_PASSWORD`).

---

## Conventions

- **Config:** Collector: `collector/config_loader.py` + `collector/config/collector.json` + env. API: `api/core/config.py` + root or `api/.env`. Production: set `ENV=production` and strong `JWT_SECRET` / `SEED_ADMIN_PASSWORD`.
- **Docs:** Agent deployment → [DEPLOY.md](DEPLOY.md). Central server → [SERVER.md](SERVER.md). Playbook → `playbook/PLAYBOOK-v0.4-*.md`. Progress → [PROGRESS.md](PROGRESS.md).
- **Versioning:** Playbook uses semantic version in filename and `Version:` header; see `.cursor/rules/git-and-versioning.mdc` for commit/version discipline.
- **Tests:** `pytest collector/tests/` (233 tests), `pytest api/tests/` (244), `pytest protocol/tests/` (48). Run separately to avoid package conflicts.
- **Calibration:** `pytest collector/tests/test_calibration.py -v` runs the replay harness against 8 lab-run fixtures. Runs automatically in CI as a dedicated "Calibration Regression" job on every push/PR to main. Run it locally before changing weights or penalties in `engine/confidence.py`. Add new fixtures to `collector/tests/fixtures/lab_runs/` after each lab run.
- **Baseline policies:** 15 rules from Playbook v0.4.0 Section 6.3 are seeded per tenant on creation (`api/core/baseline_policies.py`). Baseline rules are `is_baseline=True`, cannot be deleted, and can be reset via `POST /api/policies/restore-defaults`. ISO-001 (container isolation) ships inactive; all others active.

---

## How to use this file

1. Read this file first. Do not re-scan the whole repo unless the task requires it.
2. Do the user’s task. Open other files only when needed (e.g. “add a scanner” → `collector/scanner/`, `main.py`, `engine/confidence.py`).
3. When the task touches deploy/packaging, check DEPLOY.md or SERVER.md for the canonical steps.
4. One logical change per commit; message should explain *why* (see git-and-versioning rule).

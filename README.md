# Agentic-governance

Endpoint telemetry and policy for agentic AI tool detection. This repo defines detection profiles, schemas, and a collector that scans endpoints for tools (Claude Code, Ollama, Cursor, Copilot, Open Interpreter), computes confidence, evaluates policy, and emits NDJSON events.

**Main reference:** the [playbook](playbook/PLAYBOOK-v0.4-agentic-ai-endpoint-detection-governance.md) (detection profiles, policy, and lab methodology).

## Repo layout

- **playbook/** — Governance playbook and detection profiles
- **collector/** — Endpoint telemetry collector (5-dimension confidence model, 12 scanners)
- **api/** — Multi-tenant FastAPI backend (auth, endpoints, events, policies)
- **dashboard/** — Web UI for viewing detection results
- **schemas/** — Event and config schemas
- **lab-runs/** — Lab run outputs and findings
- **init-issues/** — Initial issue write-ups and references

## Install (Detec Agent)

From the repo root, install the package so the agent is available as a single command:

```bash
pip install -e .
```

This installs the **detec-agent** console script (Detec endpoint agent). Use it for daemon mode or one-shot scans; see [DEPLOY.md](DEPLOY.md) for auto-start and deployment.

## Running the collector

```bash
detec-agent --dry-run --verbose
```

Or without installing (from repo root):

```bash
cd collector && python main.py --dry-run --verbose
```

Or:

```bash
python -m collector.main --dry-run --verbose
```

Without `--dry-run`, the collector writes NDJSON to `collector/scan-results.ndjson`. For running tests, see [collector/README.md](collector/README.md).

## Quick start (full stack)

```bash
cp .env.example .env          # edit secrets for production
docker compose up -d           # starts db + api
cd dashboard && npm install && npm run dev
```

Open http://localhost:5173. Log in with the seed admin credentials (see [SERVER.md](SERVER.md#first-api-key)) or register a new account. The dashboard connects to the API at `http://localhost:8000` by default; configure this in Settings if needed.

## Running the API

```bash
cd api && pip install -r requirements.txt && uvicorn main:app --reload
```

The API requires a PostgreSQL database. Set `DATABASE_URL`, `JWT_SECRET`, and `SEED_ADMIN_PASSWORD` via environment variables or `.env` file. Auth endpoints are rate-limited (5 req/min). `GET /health` verifies DB connectivity (returns 503 when degraded). For production deployment, security hardening, and environment variable reference, see [SERVER.md](SERVER.md).

## Running tests

```bash
python -m pytest collector/tests/ -v                           # 58 collector unit tests
python -m pytest collector/tests/test_scanner_consistency.py -v # 108 scanner consistency tests
python -m pytest api/tests/ -v                                 # 42 API tests
```

The scanner consistency tests verify that all 12 scanners populate `action_type`, `action_risk`, `action_summary`, `tool_class`, and `tool_name` correctly. They run actual scans so take ~2 minutes.

Note: Run collector and API tests separately (not in a single pytest invocation) to avoid `tests` package name conflicts.

## Dashboard

SOC operator console for monitoring detected AI tools, confidence scoring, and policy enforcement. The dashboard requires authentication (JWT login or API key).

- **Login/Register**: email + password, JWT with auto-refresh. User profile (name, role) shown in the top bar.
- **API key fallback**: configure in Settings when JWT is unavailable (headless access).
- **Live pages**: Endpoints dashboard (filterable by endpoint, time range, searchable), Policies list, Audit log (paginated).

Dev mode: `cd dashboard && npm install && npm run dev` (opens http://localhost:5173). See [dashboard/README.md](dashboard/README.md).

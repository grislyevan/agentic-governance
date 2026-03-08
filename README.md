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
docker compose up -d           # starts db + api + dashboard
```

Open http://localhost:3001 (dashboard). Click **API config**, enter `http://localhost:8000` and the seeded admin API key (see [SERVER.md](SERVER.md#first-api-key)), then click **Load from API**.

## Running the API

```bash
cd api && pip install -r requirements.txt && uvicorn main:app --reload
```

The API requires a PostgreSQL database. Set `DATABASE_URL`, `JWT_SECRET`, and `SEED_ADMIN_PASSWORD` via environment variables or `.env` file. For production deployment, environment variable reference, and schema migrations, see [SERVER.md](SERVER.md).

## Running tests

```bash
python -m pytest collector/tests/ -v                           # 58 collector unit tests
python -m pytest collector/tests/test_scanner_consistency.py -v # 108 scanner consistency tests
python -m pytest api/tests/ -v                                 # 42 API tests
```

The scanner consistency tests verify that all 12 scanners populate `action_type`, `action_risk`, `action_summary`, `tool_class`, and `tool_name` correctly. They run actual scans so take ~2 minutes.

Note: Run collector and API tests separately (not in a single pytest invocation) to avoid `tests` package name conflicts.

## Dashboard

A web UI showing detected tools, confidence, and policy decisions. Two data modes:

- **Load from API** (recommended): connects to the FastAPI backend with your API key. Shows live events ingested by agents.
- **Load NDJSON / Load file**: reads raw NDJSON from the collector server or a local file (for offline inspection).

Dev mode: `cd dashboard && npm install && npm run dev` (opens http://localhost:5173). Docker: included in `docker compose up` on http://localhost:3001. See [dashboard/README.md](dashboard/README.md).

# Contributing

## Development Setup

### Prerequisites
- Python 3.11+
- Node.js 20+
- Docker + Docker Compose (for the API + database)

### Collector (Python)

```bash
cd collector
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python main.py --dry-run --verbose
```

Run tests:
```bash
python -m pytest tests/ -v
```

### Dashboard (React/Vite)

```bash
cd dashboard
npm install
npm run dev          # starts Vite (port 5173)
```

The dashboard requires a running backend API for authentication and data. Log in with the seed admin credentials or register a new account. See [dashboard/README.md](dashboard/README.md) for architecture and auth details.

### Backend API (FastAPI)

```bash
cd api
cp .env.example .env    # edit as needed
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
uvicorn main:app --reload
```

Or with Docker Compose (API + PostgreSQL):
```bash
docker compose up db api
```

OpenAPI docs: http://localhost:8000/docs (available when `DEBUG=true`)

---

## Project Structure

```
agentic-governance/
├── collector/          Python endpoint collector (scanners, engine, schema)
├── dashboard/          React/Vite SOC dashboard (auth, live data, Tailwind)
├── api/                FastAPI backend (SQLite/PostgreSQL, JWT, multi-tenancy)
├── playbook/           Governance playbook (Markdown, versioned)
├── schemas/            Canonical event JSON Schema
├── lab-runs/           Lab run evidence and results
├── init-issues/        Backlog issue tracking docs
├── diagrams/           Architecture diagrams
├── deploy/             Agent auto-start templates (LaunchAgent, systemd, Windows Task)
├── packaging/          Installer builds (macOS .app/.pkg, Windows agent/server)
├── docs/               Deployment guides (MDM, macOS permissions)
├── branding/           Brand assets and guidelines
├── install/            Legacy; prefer deploy/ and packaging/
└── docker-compose.yml  Dev environment (API + DB)
```

---

## Git Discipline

- One logical change per commit
- Commit message: explain *why*, not *what*
- Run the collector test suite before committing collector changes
- See `.cursor/rules/git-and-versioning.mdc` for playbook versioning rules

---

## Adding a New Scanner

1. Create `collector/scanner/<tool_name>.py` following the `BaseScanner` interface
2. Add per-tool confidence weights in `collector/engine/confidence.py`
3. Register in `collector/scanner/__init__.py` and `collector/main.py`
4. Write a lab run template in `lab-runs/LAB-RUN-XXX-TEMPLATE-<tool>.md`
5. Add a unit test stub in `collector/tests/`
6. Update the playbook detection profile section if findings differ from IOCs
7. After lab validation, mark the lab run template as completed and update `PROGRESS.md`

---

## Schema Changes

When changing `schemas/canonical-event-schema.json`:
- Bump the `version` field (semver)
- Update `schemas/example-events.json` with at least one example per new event type
- Verify the collector's `output/emitter.py` validator still passes

---

## Playbook Versioning

See `.cursor/rules/git-and-versioning.mdc` for the bump policy:
- **Patch** (0.3 → 0.3.1): typos, clarifications
- **Minor** (0.3 → 0.4): new sections, lab findings, detection profile changes
- **Major** (0.4 → 1.0): structural overhaul, production-ready milestone

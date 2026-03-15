# Detec (agentic-governance)

**Discover what AI tools run on developer machines; then control and govern them with evidence-based policy.**

## One-minute demo

Detec discovers which AI tools run on developer machines (Cursor, Claude Code, Ollama, Copilot, and more), scores each with explainable confidence, and can enforce policy. Install and run a one-shot scan to see detections in under a minute.

**Install** (from repo):

```bash
pip install -e .
```

**Run a one-shot scan:**

```bash
detec-agent scan --verbose
```

Or use the short CLI: `detec scan --verbose`.

Example output (detected tools, confidence, and scan summary):

```text
=== Scanning for Cursor ===
  Cursor: change detected (initial)
  Confidence: 0.7234 (High)
  Signals - P:0.85 F:0.90 N:0.70 I:0.65 B:0.00
  Emitting detection.observed event...

=== Scanning for Ollama ===
  Ollama: change detected (initial)
  Confidence: 0.8100 (High)
  Signals - P:0.95 F:0.80 N:0.90 I:0.00 B:0.00
  Emitting detection.observed event...

============================================================
Scan complete. Events emitted: 2, validation failures: 0
```

Stable demo evidence (transcript and description) is in [docs/demo-proof/](docs/demo-proof/).

---

Detec gives security teams evidence-based visibility and control: discover what runs, how confident each detection is, and whether it fits your policy. See what AI agents do; govern what they're allowed to.

- **Discover:** We detect agentic AI tools (Claude Code, Cursor, Ollama, Copilot, Open Interpreter, Aider, Cline, and more) by what they do, not what they're called. Twelve scanners feed a single evidence pipeline; the [playbook](playbook/PLAYBOOK-v0.4-agentic-ai-endpoint-detection-governance.md) documents our methodology.
- **Core behavioral detections:** We name and ship three security-relevant behaviors that EDR and signature-based tools miss: **DETEC-BEH-CORE-01** (autonomous shell fan-out), **DETEC-BEH-CORE-02** (agentic read-modify-write loop), **DETEC-BEH-CORE-03** (sensitive access followed by outbound activity). See [docs/behavioral-core-demo-pack.md](docs/behavioral-core-demo-pack.md) for demo flow and event examples.
- **Score:** Every detection gets an explainable confidence score (five dimensions, playbook-aligned weights). You see why we said "high" or "medium" and can tune sensitivity.
- **Enforce:** Policy runs on a ladder you control: visibility only, warning, approval required, or block. Rules are configurable per tenant; the API and dashboard apply them consistently.
- **For whom:** Security teams, SOC operators, and compliance leads who need to govern agentic tools without blocking blindly. The dashboard is the operator console; the agent and API are built for deployment at scale.

Detec is a production-ready stack: endpoint agent, multi-tenant API, and SOC dashboard. The playbook and lab runs document our methodology and evidence. **For AI agents and new contributors:** read [AGENTS.md](AGENTS.md) first for a short project brief and where to look.

---

## Repo layout

**Core:** collector, api, dashboard, protocol, schemas  
**Reference and ops:** playbook, lab-runs, deploy, packaging, docs

- **collector/** — Endpoint agent (12 scanners, 5-dimension confidence, HTTP + TCP emitters)
- **api/** — Multi-tenant FastAPI backend (auth, invite/reset, endpoints, events, policies, webhooks) + binary protocol gateway
- **dashboard/** — Web UI for viewing detection results and managing policy
- **protocol/** — Shared binary wire protocol (msgpack framing, message types)
- **schemas/** — Event and config JSON Schema
- **playbook/** — Governance playbook and detection profiles
- **lab-runs/** — Lab run outputs and findings
- **deploy/** — Agent auto-start templates (LaunchAgent, systemd, Windows Task)
- **packaging/** — Installer builds (macOS .app/.pkg, Windows agent/server)
- **docs/** — Deployment guides (MDM, macOS permissions), [current status and roadmap](PROGRESS.md)
- **init-issues/** — Backlog and issue references
- **diagrams/** — Architecture diagrams
- **branding/** — Brand assets and guidelines
- **install/** — Legacy; prefer deploy/ and packaging/ for new use

---

## Get started

### Install (Detec Agent)

From the repo root, install the package so the agent is available as a single command:

```bash
pip install -e .
```

This installs the **detec-agent** console script. Use it for daemon mode or one-shot scans; see [DEPLOY.md](DEPLOY.md) for auto-start and deployment.

### Run the collector (one-shot)

```bash
detec-agent --dry-run --verbose
```

Or from repo root without installing: `python -m collector.main --dry-run --verbose`. Without `--dry-run`, the collector writes NDJSON to `collector/scan-results.ndjson`. Prefer `python -m collector.main` from repo root or `detec-agent` after install; see [collector/README.md](collector/README.md).

### Quick start (full stack)

```bash
cd dashboard && npm install && npm run build   # build the dashboard
cd ../api && pip install -r requirements.txt
export JWT_SECRET="$(openssl rand -hex 32)"
export SEED_ADMIN_PASSWORD="pick-a-strong-password"
uvicorn main:app --reload
```

Open http://localhost:8000. The FastAPI server serves both the API (under `/api/`) and the dashboard at the root. Log in with the seed admin credentials (see [SERVER.md](SERVER.md#first-api-key)) or register a new account.

For dashboard development with hot reload: `cd dashboard && npm run dev` (Vite proxies `/api` to FastAPI on port 8000).

### Five-minute demo

Discover and control autonomous AI tools on developer endpoints: run the stack with demo data in about five minutes.

```bash
./scripts/demo-five-min.sh
```

Then open http://localhost:8000 and log in (e.g. `admin@example.com` / `change-me`). See [docs/demo.md](docs/demo.md) for full instructions, what you see, and how to reset demo data. The demo includes:

- **Sample event set:** [docs/demo/sample-events.json](docs/demo/sample-events.json) — a minimal detection → policy (block) → enforcement chain in canonical form.
- **Screenshots:** [docs/demo/screenshots/](docs/demo/screenshots/) — required shots and how to capture them (dashboard, events, policies).
- **One block decision and why:** [docs/demo/block-decision-example.md](docs/demo/block-decision-example.md) — one concrete block (ENFORCE-005, Claude Code, crown-jewel) with rule, rationale, and evidence chain.

---

## Telemetry and detection

**Today:** Psutil-based polling (process, file, and network signals) powers detection. The collector runs on macOS, Windows, and Linux with a single code path.  
**Roadmap:** Native telemetry (macOS ESF, Windows ETW, Linux eBPF) for lower latency and stronger guarantees. See [docs/esf-entitlement.md](docs/esf-entitlement.md) for ESF status.

---

## Running the API

```bash
cd api && pip install -r requirements.txt && uvicorn main:app --reload
```

The API defaults to a local **SQLite** database (zero setup). For production, set `DATABASE_URL` to a PostgreSQL connection string and set `JWT_SECRET` and `SEED_ADMIN_PASSWORD` via environment or `.env`. Auth endpoints are rate-limited (5 req/min). `GET /health` verifies DB connectivity. See [SERVER.md](SERVER.md) for production deployment and security hardening.

---

## Running tests

```bash
python -m pytest collector/tests/ -v                           # collector tests (includes scanner consistency)
python -m pytest collector/tests/test_scanner_consistency.py -v # 108 scanner consistency tests
python -m pytest api/tests/ -v                                 # API tests
python -m pytest protocol/tests/ -v                            # protocol tests
```

Run collector and API tests separately to avoid package name conflicts. Scanner consistency tests run actual scans and take about two minutes.

---

## Dashboard

SOC operator console for monitoring detected AI tools, confidence scoring, and policy enforcement. Requires authentication (JWT or API key).

- **Login/Register:** email + password, JWT with auto-refresh. User profile in the top bar.
- **API key fallback:** configure in Settings for headless access.
- **Live pages:** Endpoints (filterable, searchable), Policies (create, edit, toggle active), Audit log (paginated).
- **User management:** Admin page for users; roles: owner, admin, analyst, viewer. Gated to owner/admin.

Served by FastAPI from `dashboard/dist/`. Build: `cd dashboard && npm run build`. See [dashboard/README.md](dashboard/README.md) for architecture and [docs/dashboard-roadmap.md](docs/dashboard-roadmap.md) for roadmap.

---

## License

This project is licensed under the [Business Source License 1.1](LICENSE). You may copy, modify, create derivative works, and use the software in production, provided you do not offer it as a competing hosted or managed service. On the Change Date (March 9, 2030), the software becomes available under the [Apache License 2.0](https://www.apache.org/licenses/LICENSE-2.0).

See [LICENSE](LICENSE), [legal/LICENSE-AGREEMENT.md](legal/LICENSE-AGREEMENT.md), and [legal/TERMS-OF-SERVICE.md](legal/TERMS-OF-SERVICE.md).

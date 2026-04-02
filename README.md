# Detec

Detec **discovers and controls** autonomous AI tools on developer endpoints. It detects tools by what they do (not what they're called), scores detections with explainable confidence across five evidence layers, and applies deterministic policy outcomes (Detect / Warn / Approval Required / Block).

Detec also reconstructs agent sessions to show concrete action sequences (e.g., LLM request → shell exec → file write → git commit) for analyst review. It identifies behavioral patterns that traditional EDR and inventory tools often miss without cross-signal correlation, including:

- autonomous shell execution
- AI-assisted read-modify-write coding loops
- sensitive credential/config access followed by outbound activity
- agent execution chain (LLM then shell then file/git within a window)

See the behavioral demo pack:

→ [docs/behavioral-core-demo-pack.md](docs/behavioral-core-demo-pack.md)

---

## Try Detec in 90 Seconds

The fastest way to evaluate the full stack (API + dashboard + pre-seeded sample data):

```bash
git clone https://github.com/anomalyco/agentic-governance
cd agentic-governance
docker compose -f docker-compose.demo.yml up
```

Then open **http://localhost:8000** — log in with `admin@example.com` / `detec-demo-2026`.

The demo stack boots Postgres, the API, and the dashboard. On first start it seeds:
- 3 demo endpoints (macOS/ESF, Windows/ETW, Linux/polling)
- ~50 realistic events across detection, policy, enforcement, and approval scenarios
- 15 baseline policy rules

No `.env` file or manual configuration needed. All credentials are pre-filled and clearly marked as demo-only. See comments in [`docker-compose.demo.yml`](docker-compose.demo.yml).

**Requirements:** Docker Desktop ≥ 4.x (or Docker Engine + Compose v2). ~2 GB disk for images.

---

## Why Detec Exists

Security teams increasingly face AI coding tools, local LLM runtimes, and autonomous agents running on developer machines.

Traditional endpoint tools can see processes, files, and network connections, but they cannot explain:

- when an AI agent is acting autonomously
- when an agent is modifying code in a model-driven loop
- when sensitive material is accessed before outbound model or network activity

Detec detects these behaviors and maps them to **deterministic policy outcomes**.

We publish known limits, evasion findings, and telemetry blind spots alongside capabilities so teams can govern with evidence, not marketing claims. Detection confidence varies by tool and environment; high-risk tools such as Claude Code are often reported at Medium confidence without EDR or kernel telemetry.

---

## Core Behavioral Detections

### DETEC-BEH-CORE-01 — Autonomous Shell Fan-Out
Detects autonomous command execution patterns consistent with AI agents rather than normal interactive developer shell usage.

### DETEC-BEH-CORE-02 — Agentic Read-Modify-Write Loop
Detects AI-assisted code modification loops, not just the presence of AI coding tools.

### DETEC-BEH-CORE-03 — Sensitive Access Followed by Outbound Activity
Detects sequences where sensitive configuration or credential files are accessed and followed by outbound model or network activity.

### DETEC-BEH-CORE-04 — Agent Execution Chain
Detects the canonical agent loop: LLM API call, then shell/interpreter execution, then file write or git activity, within a time window.

Demo artifacts:

- [DETEC-BEH-CORE-01 demo](docs/demo-proof/DETEC-BEH-CORE-01-demo.md)
- [DETEC-BEH-CORE-02 demo](docs/demo-proof/DETEC-BEH-CORE-02-demo.md)
- [DETEC-BEH-CORE-03 demo](docs/demo-proof/DETEC-BEH-CORE-03-demo.md)
- [DETEC-BEH-CORE-04 demo](docs/demo-proof/DETEC-BEH-CORE-04-demo.md)

---

## Verify Detec in 5 Minutes

Bootstrap once (installs the project with dev extras so pytest and plugins are available), then run the core behavioral detection tests:

```bash
make bootstrap-dev
detec scan --verbose
python -m pytest collector/tests/test_behavioral_core_detections.py -q
```

Review the behavioral demo pack and demo proof index:

- [Behavioral demo pack](docs/behavioral-core-demo-pack.md)
- [Demo proof index](docs/demo-proof/README.md)

These demos show the canonical detections, event output, evidence summaries, and policy outcomes. Detec can also summarize detections into **agent session reports** (tool, duration, action counts, risk signals) via API and CLI; see [Session report demo](docs/demo-proof/session-report-demo.md).

---

## Example Detection Output

```text
[DETEC-BEH-CORE-03] Sensitive Access Followed by Outbound Activity

Sensitive path access detected:
- ~/.aws/credentials
- .env

Related outbound activity:
- api.anthropic.com
- unknown external destination

Policy:
approval_required

Summary:
Sensitive configuration access was followed by outbound model/network activity within the configured correlation window.
```

---

## How It Works

Detec combines endpoint telemetry, behavioral detection, confidence scoring, deterministic policy evaluation, and enforcement.

High-level flow:

```
endpoint telemetry → detection engine → policy engine → enforcement → API / dashboard
```

Policy decisions follow a four-state ladder: Detect / Warn / Approval Required / Block.

Architecture overview:

- [Architecture overview](docs/architecture-overview.md)
- [Behavioral core demo pack](docs/behavioral-core-demo-pack.md)

---

## Product Status

| Capability | Status |
|------------|--------|
| Core behavioral detections | Available |
| Confidence scoring and calibration | Available (ECE 0.11) |
| Deterministic policy engine | Available |
| Endpoint enforcement | Available |
| Tamper controls (uninstall tokens, decommission) | Available |
| Behavioral demo artifacts | Available |
| CrowdStrike enrichment | Experimental |
| Native ESF / ETW telemetry | Experimental (code complete; MDM deployment docs available) |
| Native eBPF telemetry (Linux) | Roadmap |
| Dashboard and management workflows | Available |

See [docs/product-status.md](docs/product-status.md) for details.

---

## Repository Layout

→ [docs/START-HERE.md](docs/START-HERE.md) — navigation index for contributors, operators, and deployers

- **collector/** — Endpoint agent, telemetry, scanners, confidence, policy, enforcement (`collector/enforcement/` package), orchestrator, event builder, decision engine
- **api/** — Backend API, ingest, policy/config management
- **protocol/** — Wire protocol and gateway support
- **dashboard/** — Management UI
- **docs/** — Architecture, demo pack, policy mapping, deployment docs
- **lab-runs/** — Validation protocols and results
- **playbook/** — Governance playbook and detection profiles
- **deploy/** — Agent auto-start templates (LaunchAgent, systemd, Windows Task)
- **installers/** — Installer builds (macOS .app/.pkg, Windows agent/server)
- **schemas/** — Event and config JSON Schema

---

## Quickstart (contributor / bare-metal)

Bootstrap the repo (single command for contributors; installs project with dev extras including pytest), then run a local scan:

```bash
make bootstrap-dev
detec scan --verbose
```

Run the core behavioral detection tests:

```bash
python -m pytest collector/tests/test_behavioral_core_detections.py -q
```

For full setup and deployment guidance, see:

- [SERVER.md](SERVER.md)
- [docs/ci-security.md](docs/ci-security.md)

### Running tests

From repo root, run **`make bootstrap-dev`** once so pytest and dev dependencies are installed (avoids missing pytest plugin surprises). Then:

- **All suites:** `make test-all-safe` (collector, api, protocol). API tests require Postgres and env vars; see [docs/ci-security.md](docs/ci-security.md#test-split-and-how-to-run-tests-contributors).
- **Per suite:** `make test-collector`, `make test-api`, `make test-protocol`.
- **Dashboard build:** `make build-dashboard`.

See [docs/ci-security.md](docs/ci-security.md) for CI gates and merge protection.

### Full stack (API + dashboard)

```bash
make bootstrap-dev
cd dashboard && npm install && npm run build
cd ../api && pip install -r requirements.txt
export JWT_SECRET="$(openssl rand -hex 32)" SEED_ADMIN_PASSWORD="pick-a-strong-password"
uvicorn main:app --reload
```

Open http://localhost:8000. Log in with the seed admin credentials (printed once at first startup; see [SERVER.md](SERVER.md#first-api-key)) or register a new account.

---

## Technical Validation

Detec includes:

- Behavioral detection replay tests
- Confidence calibration regression
- Enforcement end-to-end tests
- Security workflow checks (Semgrep, Trivy, dependency audit, secrets scanning)

See:

- [Behavioral demo pack](docs/behavioral-core-demo-pack.md)
- [CI and security docs](docs/ci-security.md)
- [Demo proof](docs/demo-proof/README.md)

---

## What Detec Is Not

Detec is not just AI tool inventory, browser filtering, or prompt logging.

Its primary focus is behavioral detection and governance for AI agents and AI coding workflows on endpoints.

---

## Telemetry and Detection

**Today:** Psutil-based polling (process, file, and network signals) is the default path. The dashboard shows a **Telemetry** badge per endpoint — `Native (ESF)`, `Native (ETW)`, or `Polling` — so operators can see which endpoints have elevated signal fidelity.

**macOS ESF / Windows ETW:** Native telemetry providers are code-complete and available as Experimental. ESF requires an Apple Developer ID with the `com.apple.developer.endpoint-security.client` entitlement; see [`docs/mdm-deployment.md`](docs/mdm-deployment.md) for the MDM deployment guide (Jamf + Intune). ETW works with or without pywintrace via a ctypes fallback path.

**Linux eBPF:** On the roadmap. Requires BCC or eBPF CO-RE, which introduces a heavyweight runtime dependency not yet suitable for developer endpoints.

---

## Running the API

```bash
make bootstrap-dev
cd api && pip install -r requirements.txt && uvicorn main:app --reload
```

The API defaults to a local **SQLite** database (zero setup). For production, set `DATABASE_URL` to a PostgreSQL connection string and set `JWT_SECRET` and `SEED_ADMIN_PASSWORD` via environment or `.env`. Auth endpoints are rate-limited (5 req/min). `GET /health` verifies DB connectivity. See [SERVER.md](SERVER.md) for production deployment and security hardening.

---

## Running Tests

After `make bootstrap-dev`, run:

```bash
python -m pytest collector/tests/ -m 'not benchmark and not slow' -x -q   # collector (default CI subset)
python -m pytest collector/tests/test_scanner_consistency.py -v           # scanner consistency
python -m pytest protocol/tests/ -q                                       # protocol
cd api && python -m pytest tests/ -m 'not benchmark and not slow' -x -q   # API (requires DATABASE_URL, JWT_SECRET, SEED_ADMIN_PASSWORD)
```

Or use the Makefile: `make test-collector`, `make test-protocol`, `make test-api`. Run collector and API tests in separate invocations to avoid package name conflicts.

---

## Dashboard

SOC operator console for monitoring detected AI tools, confidence scoring, and policy enforcement. Requires authentication (JWT or API key). Served by FastAPI from `dashboard/dist/`. Build: `cd dashboard && npm run build`. See [dashboard/README.md](dashboard/README.md) and [docs/dashboard-roadmap.md](docs/dashboard-roadmap.md).

---

## For Contributors

**For AI agents and new contributors:** read [AGENTS.md](AGENTS.md) first for a short project brief and where to look.

---

## License

This project is licensed under the [Business Source License 1.1](LICENSE). You may copy, modify, create derivative works, and use the software in production, provided you do not offer it as a competing hosted or managed service. On the Change Date (March 9, 2030), the software becomes available under the [Apache License 2.0](https://www.apache.org/licenses/LICENSE-2.0).

See [LICENSE](LICENSE), [legal/LICENSE-AGREEMENT.md](legal/LICENSE-AGREEMENT.md), and [legal/TERMS-OF-SERVICE.md](legal/TERMS-OF-SERVICE.md).

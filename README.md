# Detec

Detec (formerly Agentic Governance) detects and governs **AI-agent behavior on developer endpoints**.

It identifies behavioral patterns that traditional EDR and simple AI-tool inventory miss, including:

- autonomous shell execution
- AI-assisted read-modify-write coding loops
- sensitive credential/config access followed by outbound activity

See the behavioral demo pack:

→ [docs/behavioral-core-demo-pack.md](docs/behavioral-core-demo-pack.md)

---

## Core Behavioral Detections

### DETEC-BEH-CORE-01 — Autonomous Shell Fan-Out
Detects autonomous command execution patterns consistent with AI agents rather than normal interactive developer shell usage.

### DETEC-BEH-CORE-02 — Agentic Read-Modify-Write Loop
Detects AI-assisted code modification loops, not just the presence of AI coding tools.

### DETEC-BEH-CORE-03 — Sensitive Access Followed by Outbound Activity
Detects sequences where sensitive configuration or credential files are accessed and followed by outbound model or network activity.

Demo artifacts:

- [DETEC-BEH-CORE-01 demo](docs/demo-proof/DETEC-BEH-CORE-01-demo.md)
- [DETEC-BEH-CORE-02 demo](docs/demo-proof/DETEC-BEH-CORE-02-demo.md)
- [DETEC-BEH-CORE-03 demo](docs/demo-proof/DETEC-BEH-CORE-03-demo.md)

---

## Why Detec Exists

Security teams increasingly face AI coding tools, local LLM runtimes, and autonomous agents running on developer machines.

Traditional endpoint tools can see processes, files, and network connections, but they cannot explain:

- when an AI agent is acting autonomously
- when an agent is modifying code in a model-driven loop
- when sensitive material is accessed before outbound model or network activity

Detec detects these behaviors and maps them to **deterministic policy outcomes**.

---

## Verify Detec in 5 Minutes

Run the core behavioral detection tests:

```bash
pip install -e .
detec scan --verbose
python -m pytest collector/tests/test_behavioral_core_detections.py -q
```

Review the behavioral demo pack and demo proof index:

- [Behavioral demo pack](docs/behavioral-core-demo-pack.md)
- [Demo proof index](docs/demo-proof/README.md)

These demos show the canonical detections, event output, evidence summaries, and policy outcomes.

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

Architecture overview:

- [Architecture overview](docs/architecture-overview.md)
- [Behavioral core demo pack](docs/behavioral-core-demo-pack.md)

---

## Product Status

| Capability | Status |
|------------|--------|
| Core behavioral detections | Available |
| Confidence scoring and calibration | Available |
| Deterministic policy engine | Available |
| Endpoint enforcement | Available |
| Behavioral demo artifacts | Available |
| CrowdStrike enrichment | Experimental |
| Native ESF / ETW / eBPF telemetry | Experimental / roadmap |
| Dashboard and management workflows | In progress |

See [docs/product-status.md](docs/product-status.md) for details.

---

## Repository Layout

- **collector/** — Endpoint agent, telemetry, scanners, confidence, policy, enforcement
- **api/** — Backend API, ingest, policy/config management
- **protocol/** — Wire protocol and gateway support
- **dashboard/** — Management UI
- **docs/** — Architecture, demo pack, policy mapping, deployment docs
- **lab-runs/** — Validation protocols and results
- **playbook/** — Governance playbook and detection profiles
- **deploy/** — Agent auto-start templates (LaunchAgent, systemd, Windows Task)
- **packaging/** — Installer builds (macOS .app/.pkg, Windows agent/server)
- **schemas/** — Event and config JSON Schema

---

## Quickstart

Install dependencies and run a local scan:

```bash
pip install -e .
detec scan --verbose
```

Run the core behavioral detection tests:

```bash
python -m pytest collector/tests/test_behavioral_core_detections.py -q
```

For full setup and deployment guidance, see:

- [SERVER.md](SERVER.md)
- [docs/ci-security.md](docs/ci-security.md)

### Full stack (API + dashboard)

```bash
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

**Today:** Psutil-based polling (process, file, and network signals) powers detection. The collector runs on macOS, Windows, and Linux with a single code path.

**Roadmap:** Native telemetry (macOS ESF, Windows ETW, Linux eBPF) is on the roadmap for lower latency and stronger guarantees (status: ROADMAP). See [docs/esf-entitlement.md](docs/esf-entitlement.md) for ESF status.

---

## Running the API

```bash
cd api && pip install -r requirements.txt && uvicorn main:app --reload
```

The API defaults to a local **SQLite** database (zero setup). For production, set `DATABASE_URL` to a PostgreSQL connection string and set `JWT_SECRET` and `SEED_ADMIN_PASSWORD` via environment or `.env`. Auth endpoints are rate-limited (5 req/min). `GET /health` verifies DB connectivity. See [SERVER.md](SERVER.md) for production deployment and security hardening.

---

## Running Tests

```bash
python -m pytest collector/tests/ -v                           # collector tests (includes scanner consistency)
python -m pytest collector/tests/test_scanner_consistency.py -v # scanner consistency tests
python -m pytest api/tests/ -v                                 # API tests
python -m pytest protocol/tests/ -v                            # protocol tests
```

Run collector and API tests separately to avoid package name conflicts.

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

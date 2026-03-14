# Five-minute demo

Detec discovers and controls autonomous AI tools on developer endpoints. This page is the single entry point for the five-minute proof: run the stack with demo data, see sample events, see screenshots, and read one block decision and why.

## Run the demo

From the repo root:

```bash
./scripts/demo-five-min.sh
```

The script:

1. Checks for Python 3 and Node, and optionally installs the Detec package and dashboard dependencies if missing.
2. Builds the dashboard (`dashboard/dist/`).
3. Starts the API with `DEMO_MODE=true` so that demo data is seeded when the default tenant is created (first run).
4. Waits for the API to be ready and prints the dashboard URL and login.

**URL:** http://localhost:8000  
**Login:** `admin@example.com` / `change-me` (unless you set `SEED_ADMIN_EMAIL` and `SEED_ADMIN_PASSWORD`).

On first run, the seed creates a default tenant and, when `DEMO_MODE=true`, populates it with demo endpoints, events, and enforcement records (see [api/core/demo_seed.py](api/core/demo_seed.py)). If the database already had a tenant created without demo mode, log in as owner and call `POST /api/demo/reset` (with your auth) to wipe and re-seed demo data.

Press Ctrl+C to stop the API.

## What you see

- **Dashboard:** Summary cards (Endpoints, Detect, Warn, Approval required, Blocked) and endpoint list. Demo data includes blocked and approval-required events so you can see the full ladder.
- **Events:** Filter by decision (e.g. Block) and open an event to see tool name, rule ID, confidence, and enforcement detail.
- **Policies:** Baseline rules (ENFORCE-001 through ENFORCE-D03, NET-001, NET-002, etc.). The block you see in Events comes from one of these (e.g. ENFORCE-005 for crown-jewel explicit deny).

## Sample event set

A minimal event chain (detection → policy block → enforcement) is in **[docs/demo/sample-events.json](demo/sample-events.json)**. It uses the same scenario as the block-decision example: Claude Code, Tier3, ENFORCE-005, process kill. Use it to see the canonical event shape without running the stack or to test SIEM/playbook integrations.

## Screenshots

Screenshots that tell the five-minute story live in **[docs/demo/screenshots/](demo/screenshots/)**. The [screenshots README](demo/screenshots/README.md) lists the required shots (dashboard summary, one block event, policies, optional login and audit log) and how to capture them after running the demo script.

## One block decision and why

**[docs/demo/block-decision-example.md](demo/block-decision-example.md)** walks through a single block: scenario, event snippet, rule (ENFORCE-005), decision, plain-language rationale, and evidence chain. It references the same event chain as [sample-events.json](demo/sample-events.json).

## Optional: run the agent once

To see the endpoint agent output (no API required):

```bash
pip install -e .
detec-agent --dry-run --verbose
```

This runs a one-shot scan and prints detections to the console. It does not send events to the API; the five-minute demo uses pre-seeded data so you can focus on the dashboard and policy story.

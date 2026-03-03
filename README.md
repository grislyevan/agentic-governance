# Agentic-governance

Endpoint telemetry and policy for agentic AI tool detection. This repo defines detection profiles, schemas, and a collector that scans endpoints for tools (Claude Code, Ollama, Cursor, Copilot, Open Interpreter), computes confidence, evaluates policy, and emits NDJSON events.

**Main reference:** the [playbook](playbook/PLAYBOOK-v0.2-agentic-ai-endpoint-detection-governance.md) (detection profiles, policy, and lab methodology).

## Repo layout

- **playbook/** — Governance playbook and detection profiles
- **collector/** — Endpoint telemetry collector
- **schemas/** — Event and config schemas
- **lab-runs/** — Lab run outputs and findings
- **init-issues/** — Initial issue write-ups and references

## Running the collector

```bash
cd collector && python main.py --dry-run --verbose
```

Without `--dry-run`, the collector writes NDJSON to `collector/scan-results.ndjson`. For running tests, see [collector/README.md](collector/README.md).

## Dashboard

A minimal web UI shows detected tools, confidence, and policy decisions for a single endpoint. Run the collector (to produce `scan-results.ndjson`), then from the repo root: `cd dashboard && npm install && npm run dev` and open http://localhost:5173. Use **Load from server** to view results. See [dashboard/README.md](dashboard/README.md).

# Detec collector

Endpoint telemetry collector for Detec (agentic-governance). Detec Agent scans for AI tools on developer endpoints. Scans for tools (Claude Code, Ollama, Cursor, Copilot, Open Interpreter, and others), computes confidence, evaluates policy, and emits NDJSON events.

## Telemetry and detection

**Current:** Only the **polling provider** (psutil-based process, file, and network signals) is implemented. It works on macOS, Windows, and Linux.  
**Roadmap:** Native telemetry (macOS ESF, Windows ETW, Linux eBPF) is on the roadmap for lower latency and stronger guarantees (status: ROADMAP). See [docs/esf-entitlement.md](../docs/esf-entitlement.md) for ESF status.

## Install

From the **repository root**: `pip install -e .` installs the **detec-agent** console script. Use `detec-agent` for one-shot or daemon mode. See the root [README](../README.md) and [DEPLOY.md](../DEPLOY.md) for deployment and auto-start.

## Configuration

The collector supports three layers of configuration, applied in order of
increasing priority:

1. **Config file** — `collector/config/collector.json` or platform-specific path (optional)
2. **Environment variables** — prefixed with `AGENTIC_GOV_`
3. **CLI flags** — e.g. `--sensitivity Tier2`

If no config file exists at the default path, the collector searches
platform-specific locations before falling back to code defaults:

| Platform | Search paths |
|----------|-------------|
| macOS | `~/Library/Application Support/Detec/collector.json`, `~/Library/Application Support/Detec/agent.env` |
| Windows | `%PROGRAMDATA%\Detec\collector.json` |
| Linux | `~/.config/detec/collector.json`, `~/.config/detec/agent.env` |

Both JSON (`.json`) and environment (`.env`, KEY=VALUE format with `AGENTIC_GOV_` prefix) files are supported. These platform paths are where the server-generated agent download places its pre-filled config, enabling zero-touch setup after install. See [DEPLOY.md](../DEPLOY.md) for the dashboard download flow.

### Config file

Copy the example and edit to taste:

```bash
cp collector/config/collector.example.json collector/config/collector.json
```

See [`collector/config/collector.example.json`](config/collector.example.json)
for all supported keys and their defaults.  Keys set to `null` are resolved at
runtime (e.g. `endpoint_id` defaults to the hostname).

### Environment variables

Every config key can be overridden with an `AGENTIC_GOV_`-prefixed variable:

| Config key               | Environment variable                 | Type    |
|--------------------------|--------------------------------------|---------|
| `output`                 | `AGENTIC_GOV_OUTPUT`                 | string  |
| `endpoint_id`            | `AGENTIC_GOV_ENDPOINT_ID`            | string  |
| `actor_id`               | `AGENTIC_GOV_ACTOR_ID`               | string  |
| `sensitivity`            | `AGENTIC_GOV_SENSITIVITY`            | string  |
| `network_allowlist_path` | `AGENTIC_GOV_NETWORK_ALLOWLIST_PATH` | string  |
| `interval`               | `AGENTIC_GOV_INTERVAL`               | integer |
| `api_url`                | `AGENTIC_GOV_API_URL`                | string  |
| `api_key`                | `AGENTIC_GOV_API_KEY`                | string  |
| `report_all`             | `AGENTIC_GOV_REPORT_ALL`             | boolean |
| `protocol`               | `AGENTIC_GOV_PROTOCOL`               | string  |
| `gateway_host`           | `AGENTIC_GOV_GATEWAY_HOST`           | string  |
| `gateway_port`           | `AGENTIC_GOV_GATEWAY_PORT`           | integer |
| `telemetry_provider`     | `AGENTIC_GOV_TELEMETRY_PROVIDER`     | string  |
| `verbose`                | `AGENTIC_GOV_VERBOSE`                | boolean |
| `dry_run`                | `AGENTIC_GOV_DRY_RUN`                | boolean |

`protocol` selects the transport: `http` (default, uses HttpEmitter) or `tcp` (uses TcpEmitter with binary wire protocol on port 8001). When `protocol=tcp`, `gateway_host` defaults to the hostname from `api_url` and `gateway_port` defaults to `8001`.

`telemetry_provider` controls how the agent collects telemetry: `auto` (default, probe for native OS frameworks then fall back to polling), `native` (require native OS framework, fail if unavailable), or `polling` (force psutil polling only). Currently only the polling provider is implemented; native providers (ESF, ETW, eBPF) are on the roadmap (ROADMAP).

Booleans accept `1`, `true`, `yes`, or `on` (case-insensitive) as truthy.

### CLI flags

All existing CLI flags continue to work unchanged.  They take the highest
priority and override both the config file and environment variables.

```bash
cd collector && python main.py --sensitivity Tier2 --dry-run
```

## Running tests

From the **repository root** (path bootstrap is in `collector/tests/conftest.py`; prefer `pip install -e .` so the package is on the path):

```bash
python -m pytest collector/tests/ -v
```

Avoid running `python main.py` from inside `collector/`; use `python -m collector.main` from repo root or `detec-agent` after install.

Tests cover the confidence engine, policy engine, schema validation, and NDJSON emitter. They do not require real tool installs; scanner tests use mocks where applicable.

# Agentic-governance collector

Endpoint telemetry collector for agentic AI tool detection. Scans for tools (Claude Code, Ollama, Cursor, Copilot, Open Interpreter), computes confidence, evaluates policy, and emits NDJSON events.

## Running tests

From the **repository root** (with `collector` on the Python path):

```bash
PYTHONPATH=collector python -m unittest discover -s collector/tests -p 'test_*.py' -t .
```

Or with pytest (if installed):

```bash
PYTHONPATH=collector python -m pytest collector/tests/ -v
```

From the **collector directory** (no `PYTHONPATH` needed):

```bash
cd collector && python -m unittest discover -s tests -p 'test_*.py'
```

Tests cover the confidence engine, policy engine, schema validation, and NDJSON emitter. They do not require real tool installs; scanner tests use mocks where applicable.

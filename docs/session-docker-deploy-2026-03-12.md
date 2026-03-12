# Session: Docker Compose Deployment and Windows Agent Test

**Date:** 2026-03-12  
**Goal:** Get the Detec server running via Docker Compose on Mac, with the Windows agent on a VM reporting to it.

## Outcome

Full end-to-end pipeline verified: Windows endpoint agent (with system tray GUI) scanning and reporting to a Dockerized server stack on macOS.

- **Server** (Mac, Docker Compose): PostgreSQL + API + Dashboard + Binary Gateway
- **Agent** (Windows VM 192.168.64.4): CLI daemon and GUI tray app, ETW telemetry provider
- **Result:** 12+ events flowing, endpoint registered as active, heartbeats every 5 minutes

## Docker Fixes (6 issues resolved)

### 1. Stale requirements.lock

`api/requirements.lock` was missing 8+ packages added since it was generated (python-json-logger, authlib, jsonschema, msgpack, prometheus-client, reportlab, stripe, psycopg2-binary). Deleted the lock file so Docker uses `requirements.txt` directly.

### 2. psycopg2-binary commented out

`api/requirements.txt` had `psycopg2-binary` commented out with a note "only needed if using PostgreSQL." Docker Compose always uses PostgreSQL, so this was uncommented.

### 3. Build context mismatch

Both `api` and `dashboard` services in `docker-compose.yml` used subdirectory contexts (`./api`, `./dashboard`), but both Dockerfiles reference paths relative to the repo root (`branding/`, `dashboard/`, `protocol/`). Fixed both to use `.` (repo root) as context.

### 4. Missing protocol package

`Dockerfile.api` did not copy the `protocol/` directory into the image. The binary gateway (`gateway.py`) imports from `protocol.connection`, causing a silent lifespan crash on startup. Added `COPY protocol/ ./protocol/`.

### 5. Postgres boolean default

Migration `0003_webhooks.py` used `server_default=sa.text("1")` for the `is_active` boolean column. SQLite accepts this but PostgreSQL rejects it (type mismatch). Changed to `sa.text("true")`.

### 6. Healthcheck timing

API healthcheck was too aggressive for a cold start (10s start_period, 5 retries). Increased to 30s start_period and 10 retries to accommodate migration runs on first boot.

## Windows Agent Setup

1. Collector package (`collector/`, `protocol/`, `schemas/`, `branding/`) copied via SCP
2. Installed via `pip install -e .` (editable mode)
3. `agent.env` placed at `C:\ProgramData\Detec\Agent\agent.env` with API URL and key
4. Desktop launcher (`Detec Agent.bat`) created for GUI tray app
5. GUI uses `pystray` + `tkinter` for system tray icon and status window

## Key Learnings

- **Gateway crash was silent:** The lifespan function in `main.py` caught the `ImportError` for `protocol` but the exception propagated and killed the ASGI lifespan without any log output. Only visible via uvicorn exit code 3.
- **Changes-only mode:** In daemon mode without `--report-all`, the agent suppresses events when no AI tools are detected (no change from baseline). First-time deployments on clean machines need `--report-all` to see initial scan results.
- **SSH vs desktop:** GUI tray apps launched via SSH cannot access the interactive desktop session. They must be started from within the desktop (e.g., double-click a batch file, scheduled task with "interact with desktop").

## Files Changed

| File | Change |
|------|--------|
| `Dockerfile.api` | Add `COPY protocol/` for gateway support |
| `docker-compose.yml` | Fix build contexts, increase healthcheck tolerances |
| `api/requirements.txt` | Uncomment `psycopg2-binary` |
| `api/requirements.lock` | Deleted (stale, missing packages) |
| `api/alembic/versions/0003_webhooks.py` | Fix boolean default for Postgres |

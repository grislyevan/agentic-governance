# Agent Handoff: Docker Compose Deployment + Windows Agent E2E

**Date:** 2026-03-12  
**Previous handoff:** `docs/handoff-2026-03-12.md` (forward priorities execution)  
**Session detail:** `docs/session-docker-deploy-2026-03-12.md`

---

## Current State

The full stack is running and verified end-to-end.

### Server (Mac, Docker Compose)

Three containers, all healthy, running on the developer Mac:

| Container | Port | Status |
|-----------|------|--------|
| `agentic-governance-db-1` | 5432 (internal) | PostgreSQL 16, healthy |
| `agentic-governance-api-1` | 8000 | API + binary gateway (port 8001 inside container) |
| `agentic-governance-dashboard-1` | 3001 | React dashboard (static server) |

**Start/stop:**

```bash
cd /path/to/agentic-governance
docker compose up -d        # start
docker compose down          # stop (preserves data)
docker compose down -v       # stop and wipe database
docker compose up -d --build # rebuild after code changes
```

**Credentials:**

| What | Value |
|------|-------|
| Dashboard URL | http://localhost:3001 (Mac) or http://192.168.64.1:3001 (from VM) |
| API URL | http://localhost:8000 (Mac) or http://192.168.64.1:8000 (from VM) |
| Admin login | `admin@example.com` / `DetecAdmin2026!` |
| Tenant agent key | `34d6d294630f85a103c33f7bd43904067eade547cd4407fa85ec01bd7ae23571` |
| Postgres password | In `.env` file (`POSTGRES_PASSWORD`) |
| JWT secret | In `.env` file (`JWT_SECRET`) |

**Config:** Root `.env` file drives all Docker settings. The `DATABASE_URL` in `.env` points to `localhost`, but `docker-compose.yml` overrides it to `db:5432` inside the container network.

### Agent (Windows VM)

| Detail | Value |
|--------|-------|
| VM IP | 192.168.64.4 |
| SSH | `administrator` / `1925Bundy` |
| Agent install | `C:\Detec\Agent\` (editable pip install) |
| Config | `C:\ProgramData\Detec\Agent\agent.env` |
| GUI launcher | `C:\Users\Administrator\Desktop\Detec Agent.bat` |
| Endpoint name | Detec-01 |
| Telemetry | ETW provider (ctypes backend not compiled, falls back gracefully) |

**Agent is currently running** as a GUI tray app in the desktop session, scanning every 300 seconds with `--report-all`. As of this handoff, 24 events have been received by the server.

**To restart the agent:** Double-click "Detec Agent.bat" on the VM desktop. Or via SSH:

```bash
sshpass -p '1925Bundy' ssh administrator@192.168.64.4 \
  "detec-agent --api-url http://192.168.64.1:8000/api \
   --api-key 34d6d294630f85a103c33f7bd43904067eade547cd4407fa85ec01bd7ae23571 \
   --interval 300 --report-all"
```

(SSH-launched agent runs headless; no tray icon.)

---

## What Was Done This Session

### 1. Attempted Docker on Windows VM (failed)

Windows Server 2022 on UTM (macOS) does not support nested Hyper-V. Linux containers cannot run without Hyper-V or WSL2 (which also needs VM Platform). Pivoted to running Docker on the Mac host instead.

### 2. Fixed 6 Docker Compose Issues

The `docker-compose.yml` and related files had never been tested against a fresh PostgreSQL database. Six issues were found and fixed (see `docs/session-docker-deploy-2026-03-12.md` for details):

1. **Stale `requirements.lock`** (deleted; missing 8+ packages)
2. **`psycopg2-binary` commented out** (uncommented)
3. **Wrong build contexts** (both services now use repo root)
4. **Missing `protocol/` in API image** (added COPY to Dockerfile)
5. **Postgres boolean default** (migration 0003: `"1"` to `"true"`)
6. **Healthcheck too aggressive** (30s start_period, 10 retries)

### 3. Deployed Agent to Windows VM

Copied `collector/`, `protocol/`, `schemas/`, `branding/` via SCP. Installed with `pip install -e .`. Created `agent.env` and desktop launcher for the GUI tray app.

### 4. Verified E2E Pipeline

24 events flowing from Windows agent to Dockerized server. Endpoint registered, heartbeats active, policy evaluations running.

---

## Git State

```
6c12c8c fix: Docker Compose deployment (6 issues blocking fresh Postgres boot)
ea21a53 feat: add EU AI Act compliance mapping, AI data flow visibility, and MCP scanner
b96fa42 chore: add CISO security log to .gitignore
ee609e9 test: add 33 integration tests for collector scan pipeline
```

Branch `main`, pushed to origin. Tags `v0.1.0` and `v0.2.0` on remote.

**Uncommitted:** ~80 files in `.cursor/commands/` (unrelated command templates, not project code). No uncommitted project changes.

---

## Known Issues and Gotchas

1. **`.env` has CORS origins for `192.168.64.1`** (the Mac's IP on the VM network). If the Mac's IP changes, update `CORS_ORIGINS` in `.env` and restart Docker.

2. **No `.dockerignore` at repo root.** The Docker build context sends the entire repo (~68MB) on every build. Adding a `.dockerignore` excluding `node_modules/`, `.git/`, `lab-runs/`, etc. would speed up builds significantly.

3. **`requirements.lock` was deleted.** Builds now use `requirements.txt` with unpinned ranges. For production, regenerate a lock file: `cd api && pip install -r requirements.txt && pip freeze > requirements.lock`.

4. **Agent uses editable install.** The VM agent is installed via `pip install -e .` pointing at `C:\Detec\Agent`. Changes to files in that directory take effect immediately. For a production install, use `pip install .` (non-editable) or the Inno Setup installer.

5. **ETW ctypes backend not compiled.** The Windows agent logs `ETW ctypes backend unavailable: No module named 'providers._etw_ctypes'`. This is non-fatal; the agent falls back to psutil-based polling. Building the native ETW module requires a C compiler on Windows.

6. **PID file stale on crash.** If the agent daemon crashes, `~/.agentic-gov/agent.pid` can contain a stale PID. On Windows, `os.kill(old_pid, 0)` raises `SystemError` for certain PIDs. Workaround: delete `C:\Users\Administrator\.agentic-gov\agent.pid` before restarting.

7. **Binary gateway port 8001 not exposed.** `docker-compose.yml` only exposes port 8000 (HTTP API). If agents need TCP protocol (`--protocol tcp`), add `"8001:8001"` to the API service's `ports:` list.

---

## What's Next (suggested priorities)

### Immediate (unblocks demos and testing)

| Task | Why | Effort |
|------|-----|--------|
| Add `.dockerignore` | Cuts build context from 68MB to ~5MB | 15 min |
| Regenerate `requirements.lock` | Reproducible builds for production | 15 min |
| Expose gateway port 8001 in compose | TCP protocol support for agents | 5 min |
| Fix Windows `os.kill` PID check | Agent crashes on restart if stale PID | 30 min |

### Short-term (production readiness)

| Task | Why | Effort |
|------|-----|--------|
| TLS termination (nginx/caddy reverse proxy or compose labels) | HTTPS for dashboard and API | 2-4 hrs |
| Persistent agent install on Windows (scheduled task or service) | Survives reboots | 1-2 hrs |
| Health/readiness probes for Kubernetes migration | If scaling beyond single-node Docker | 1-2 hrs |
| Dashboard proxy config (API URL) for Docker networking | Dashboard currently connects to API via browser-side fetch | 1-2 hrs |

### Medium-term (from previous handoff, still pending)

| Task | Why | Effort |
|------|-----|--------|
| CrowdStrike EDR live integration | Requires vendor sandbox | 1-2 days |
| Live lab validation for 5 newer scanners | Synthetic done, live pending | 2-3 days |
| Playbook v0.5 | Incorporate Docker deployment, new lab findings | 2-3 days |

---

## Key Files for Context

| File | Purpose |
|------|---------|
| `AGENTS.md` | Architecture overview, key paths, conventions |
| `docs/handoff-2026-03-12.md` | Previous handoff (forward priorities, all features) |
| `docs/session-docker-deploy-2026-03-12.md` | This session's technical detail (6 Docker fixes) |
| `docker-compose.yml` | Server orchestration (db, api, dashboard) |
| `Dockerfile.api` | API image build (includes protocol/ and dashboard/dist/) |
| `dashboard/Dockerfile` | Dashboard multi-stage build |
| `.env` | All server secrets and config |
| `.env.example` | Documented template for `.env` |
| `collector/gui/tray.py` | Windows system tray app |
| `collector/gui/daemon_bridge.py` | GUI-to-daemon integration (reads agent.env) |

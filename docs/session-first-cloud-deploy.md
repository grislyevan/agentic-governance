# Session: First Cloud Deploy

**Date:** 2026-03-12
**Status:** Complete (deployed to Windows VM, bare-metal Python)

## Pre-deploy Preparation

### Version alignment
- `pyproject.toml`: 0.3.0 -> 0.1.0
- `collector/_version.py`: 0.3/0.3.0 -> 0.1/0.1.0

### Release workflow fix
- Fixed GitHub Actions "workflow file issue" caused by `secrets.*` in step-level `if:` conditions
- Changed to job-level `env` block + `env.*` reference pattern (GitHub docs recommended approach)

### Deploy script
- Created `deploy/fly-deploy.sh` with `--setup` (first-time) and `--skip-build` flags
- Automates: dashboard build, fly deploy, health check, credential setup

## Deploy Steps (to run on VM)

```bash
# 1. Install Fly CLI
curl -L https://fly.io/install.sh | sh

# 2. Authenticate
fly auth login

# 3. First-time setup (creates app, database, secrets)
./deploy/fly-deploy.sh --setup

# 4. Deploy
./deploy/fly-deploy.sh

# 5. Verify
curl -s https://detec-api.fly.dev/api/health | python3 -m json.tool

# 6. Test login
# Open https://detec-api.fly.dev in browser
# Login with: admin@example.com / <password from step 3>
```

## Agent Connection Test

```bash
# From local machine or VM with collector installed
pip install -e .
detec-agent --api-url https://detec-api.fly.dev --api-key <key> --dry-run --verbose
```

## Actual Deployment

Deployed to Windows VM (192.168.64.4) instead of Fly.io. Bare-metal Python + Node.js setup via SSH.

```powershell
# On VM (PowerShell): build dashboard, set env vars, start server
cd C:\Detec\src\dashboard
npm run build
cd C:\Detec\src\api
$env:JWT_SECRET = "<generated>"
$env:SEED_ADMIN_PASSWORD = "<password>"
$env:DEMO_MODE = "true"
$env:ALLOWED_ORIGINS = "*"
Start-Process python -ArgumentList "-m", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"
```

```bash
# From macOS (agent E2E test):
detec-agent --api-url http://192.168.64.4:8000/api --interval 30 --verbose
```

## Issues Found

1. **HTTP 405 (Method Not Allowed):** Agent was sending events to `http://192.168.64.4:8000/events` but the API routes are under `/api`. The `--api-url` argument needed the full prefix.
2. **HTTP 429 (Too Many Requests):** After fixing the URL, the agent attempted to flush a backlog of 272 events from previous failed attempts, triggering the server's rate limiter.
3. **Stale agent.pid:** An orphaned `~/.agentic-gov/agent.pid` file from a previous agent run blocked the new instance from starting.
4. **Trailing space in env var:** Windows CMD `set DEMO_MODE=true ` included a trailing space, causing Pydantic boolean parsing to fail. Switched to PowerShell for clean env var handling.

## Fixes Applied

1. Changed `--api-url` to include `/api` prefix: `http://192.168.64.4:8000/api`
2. Rate limit resolved itself once the backlog drained (expected behavior)
3. Removed stale `agent.pid` file
4. Used PowerShell `$env:VAR = "value"` syntax which doesn't introduce trailing whitespace

## Result

- [x] `/api/health` returns healthy
- [x] Dashboard loads at root URL
- [x] Admin can log in
- [x] Demo data visible (DEMO_MODE=true): 3 endpoints, 54 events
- [x] Agent heartbeat received, events ingested from macOS collector

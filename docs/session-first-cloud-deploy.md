# Session: First Cloud Deploy

**Date:** 2026-03-12
**Status:** Prepared, pending VM execution

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

## Issues Found

<!-- Fill in after deploy -->

## Fixes Applied

<!-- Fill in after deploy -->

## Result

<!-- Fill in after deploy -->
- [ ] `/api/health` returns healthy
- [ ] Dashboard loads at root URL
- [ ] Admin can log in
- [ ] Demo data visible (if DEMO_MODE=true)
- [ ] Agent heartbeat received

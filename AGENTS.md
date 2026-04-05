# Agent brief — read this first

**What this repo is:** Detec (agentic-governance) — discover and control autonomous AI tools on developer endpoints. An endpoint agent (collector) scans machines for tools (Claude Code, Cursor, Ollama, Copilot, etc.), scores confidence, evaluates policy, and sends events to a central API. A React dashboard and FastAPI backend complete the stack.

**Architecture:** Endpoint agent → `POST /api/events`, `POST /api/endpoints/heartbeat` (HTTP) or persistent binary/msgpack connection on port 8001 (TCP) → FastAPI (API + serves dashboard) + DetecGateway → SQLite or PostgreSQL.

---

## Key paths (open only when the task needs them)

| Path | Purpose |
|------|---------|
| `collector/` | Python agent: scanners, confidence engine, policy, enforcement (`collector/enforcement/`), orchestrator + coordinator sub-packages, HTTP + TCP + adaptive emitters, telemetry providers. Entry: `main.py`; daemon flags: `--interval` `--api-url` `--api-key` `--protocol auto\|tcp\|http` `--telemetry-provider auto\|native\|polling`. Config: `config_loader.py` + `config/collector.json` + `AGENTIC_GOV_*` env. |
| `collector/telemetry/` | Event store (thread-safe ring buffer) and typed event classes (`ProcessExecEvent`, `NetworkConnectEvent`, `FileChangeEvent`). |
| `collector/providers/` | Telemetry provider interface and implementations. `PollingProvider` (psutil, always available). Native: `ESFProvider` (macOS), `ETWProvider` (Windows, ctypes + pywintrace), `EBPFProvider` (Linux, roadmap). Registry: `get_best_provider()`. |
| `collector/scanner/` | 13 tool scanners + behavioral/evasion/MCP scanners. Base class: `scanner/base.py`. |
| `collector/compat/` | Cross-platform shims: `find_processes()`, `get_connections()`, `get_process_info()`, `get_app_version()`. Use these instead of calling `pgrep`/`lsof`/`ps` directly. |
| `api/` | FastAPI backend: auth (JWT + API key, invite, password reset), events, endpoints, policies, users, webhooks, billing (Stripe), EDR enrichment. Gateway: `gateway.py` port 8001. Config: `core/config.py` + `.env`. |
| `api/core/` | `config.py` (Settings), `database.py`, `auth.py`, `tenant.py`, `audit_logger.py`, `approval_bus.py` (SSE pub/sub), `demo_seed.py`. |
| `api/alembic/` | Migrations. Run automatically on startup via `bootstrap.apply_migrations()`. |
| `protocol/` | Shared binary wire protocol (msgpack framing). Imported by both `api/` and `collector/`. |
| `dashboard/` | React/Vite SOC UI. Build: `npm run build`; dev: `npm run dev`. Served by FastAPI from `dashboard/dist/`. |
| `docs/` | MDM deployment, architecture, calibration, security, CI docs. |

---

## Build / test commands

```bash
# Bootstrap once (installs project + dev extras + API deps)
make bootstrap-dev

# Run all three suites
make test-all-safe

# Per suite (run separately — package name conflicts exist between suites)
make test-collector          # collector/tests/ — no Postgres needed
make test-api                # api/tests/ — needs DATABASE_URL + JWT_SECRET + SEED_ADMIN_PASSWORD
make test-protocol           # protocol/tests/

# Single test — collector
python -m pytest collector/tests/test_calibration.py -v
python -m pytest collector/tests/test_scanner_claude_code.py::TestClaudeCodeScanner::test_positive_detection -v

# Single test — API (run from api/ dir or with cd)
cd api && python -m pytest tests/test_policies.py::test_list_policies -v
cd api && python -m pytest tests/test_approvals.py -v

# Single test — protocol
python -m pytest protocol/tests/test_messages.py -v

# Calibration regression (run before touching confidence weights)
python -m pytest collector/tests/test_calibration.py -v

# Skip slow / benchmark / evasion tests (CI default)
python -m pytest collector/tests/ -m 'not benchmark and not slow' -x -q

# Full local stack (API :8000 + Vite :5173)
make dev

# Dashboard build
make build-dashboard
```

**API test env vars** (set in shell or `api/.env`):
```
DATABASE_URL=postgresql://user:pass@localhost/detec_test
JWT_SECRET=any-32-char-string
SEED_ADMIN_PASSWORD=anything
```

---

## Code style — Python (collector + api + protocol)

**General:**
- Python 3.11+. `from __future__ import annotations` at top of every file.
- Type hints on all function signatures. Use `str | None` (union syntax), not `Optional[str]`.
- Max line length: ~100 chars (no enforced linter; match surrounding code).
- Docstrings: module-level triple-quoted string for public modules; inline comments for non-obvious logic.

**Imports order** (match existing files exactly):
```python
from __future__ import annotations  # always first

# stdlib
import asyncio
import logging
from pathlib import Path

# third-party
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

# local (absolute within package)
from core.config import settings
from core.database import get_db
```
No relative imports in `api/`. Relative imports (`from .base import`) are used in `collector/scanner/`.

**Naming:**
- Classes: `PascalCase`. Functions/variables: `snake_case`. Constants: `UPPER_SNAKE`.
- Pydantic models: `ThingResponse`, `ThingCreate`, `ThingUpdate` (noun + verb suffix).
- SQLAlchemy models: `Thing` (noun only, in `api/models/`).
- Test files: `test_<module>.py`. Test classes: `TestThingBehavior`. Test methods: `test_<what>_<condition>`.

**Error handling:**
- API routers: raise `HTTPException(status_code=..., detail="...")`. Never let unhandled exceptions propagate — the global handler returns a generic 500.
- Collector: log at `WARNING` for recoverable issues, `ERROR` for unrecoverable. Broad `except Exception` is acceptable in scanner `_scan_*` methods to prevent one scanner crashing the full run — but always log it.
- Never swallow exceptions silently in non-scanner code.

**Logging:**
```python
logger = logging.getLogger(__name__)   # collector
logger = logging.getLogger("agentic_governance")  # api (module-level)
```

**API routers pattern:**
```python
router = APIRouter(prefix="/things", tags=["things"])
limiter = Limiter(key_func=get_remote_address)

@router.get("", response_model=ThingListResponse)
@limiter.limit("60/minute")
def list_things(
    request: Request,
    db: Session = Depends(get_db),
    authorization: str | None = Depends(get_authorization),
    x_api_key: str | None = Header(default=None),
) -> ThingListResponse:
    auth = resolve_auth(authorization, x_api_key, db)
    ...
```

**Audit logging** — call after every mutation, before `db.commit()`:
```python
audit_record(db, tenant_id=auth.tenant_id, actor_id=auth.user_id,
             action="thing.created", resource_type="thing",
             resource_id=thing.id, detail={...}, ip_address=...)
```
Never include secrets, tokens, or passwords in `detail`.

**Alembic migrations:** One file per schema change in `api/alembic/versions/`. Naming: `NNNN_description.py`. Migrations run automatically on API startup — no manual step needed locally.

---

## Code style — JavaScript/React (dashboard)

**Stack:** React 18, Vite, Tailwind CSS (custom `detec-*` tokens — see `branding/tailwind-colors.js` and `.interface-design/system.md`).

**Imports order:**
```js
import { useState, useEffect } from 'react';        // React first
import { useNavigate } from 'react-router-dom';      // router
import useAuth from '../hooks/useAuth';              // local hooks
import { fetchThings } from '../lib/api';            // API client
import ComponentName from '../components/...';       // components
```

**Component conventions:**
- Functional components only. `export default function ThingPage() {}`.
- State at top, handlers next, JSX last.
- API calls go in `useEffect` or `useCallback`; never inline in JSX.
- Use `usePolling(callback, interval)` for pages that refresh data periodically. Use `EventSource` + `usePolling` fallback for real-time pages (see `ApprovalsPage.jsx` for the SSE pattern).
- Error state: `ApiErrorBanner` component. Loading state: `ApertureSpinner` or `LoadingState` component.

**Styling:**
- Tailwind only — no inline styles, no CSS modules.
- Use semantic tokens (`text-detec-ui-muted`, `bg-detec-ui-surface`, `border-detec-ui-border`) not raw colors.
- Dark theme always. See `.interface-design/system.md` for the full design system (spacing, radius, button patterns, badge patterns, drawer shell).
- Responsive hiding: `hidden md:table-cell` for secondary table columns.

**API client (`dashboard/src/lib/api.js`):**
- All API calls go through `apiFetch()` or `apiMutate()`. Never use `fetch()` directly in components.
- Auth headers are injected automatically by `buildAuthHeaders()` — do not pass tokens manually.
- Add new endpoints as named exports at the bottom of `api.js`.

---

## Conventions

- **Config:** Collector: `config_loader.py` + `config/collector.json` + `AGENTIC_GOV_*` env. API: `core/config.py` + `.env`. Production: `ENV=production` + strong `JWT_SECRET` / `SEED_ADMIN_PASSWORD`.
- **Cross-platform:** Always use `collector/compat/` functions (`find_processes`, `get_connections`) instead of `pgrep`, `lsof`, `ps` — these don't exist on Windows.
- **Calibration:** Run `pytest collector/tests/test_calibration.py -v` before changing confidence weights in `engine/confidence.py`. CI blocks merges that shift calibration scores without updated fixtures.
- **Baseline policies:** 15 rules seeded per tenant (`api/core/baseline_policies.py`). `is_baseline=True` rules cannot be deleted; reset via `POST /api/policies/restore-defaults`.
- **Telemetry badge:** `telemetry_provider` field sent in every heartbeat, persisted on `Endpoint` model, displayed in `EndpointsTable` as Native/Polling badge.
- **SSE approvals:** `api/core/approval_bus.py` is the in-process pub/sub bus. Call `approval_bus.publish_sync(tenant_id, payload)` after any approval lifecycle mutation.
- **Vocabulary:** Session report terms use canonical machine values everywhere; display wording is layered in CLI/dashboard only.
- **Brand:** Official domain is detecadg.com. Do not use detec.io.
- **Commits:** One logical change per commit. Message explains *why*, not just what. Format: `type(scope): description` (e.g. `feat(approvals): ...`, `fix(collector): ...`, `docs: ...`).

---

## How to use this file

1. Read this file first. Do not re-scan the whole repo unless the task requires it.
2. Do the user's task. Open other files only when needed.
3. Run the relevant test suite before and after changes. For collector changes: `make test-collector`. For API: `make test-api`. For calibration-touching changes: also run `pytest collector/tests/test_calibration.py -v`.
4. Check `PARKING-LOT.md` for known issues before adding workarounds that may already be tracked.
5. When adding a scanner: follow `collector/scanner/base.py` + an existing scanner (e.g. `claude_code.py`), register it in `collector/main.py`, add calibration fixture if live-tested.
6. When adding an API endpoint: add router + Pydantic schemas + `audit_record` call + rate limit. Register router in `api/startup/app_factory.py`.

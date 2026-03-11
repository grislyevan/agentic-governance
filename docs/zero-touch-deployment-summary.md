# Zero-Touch Agent Deployment: Implementation Summary

## Problem

After installing the Detec agent, admins had to manually run `detec-agent setup --api-url ... --api-key ...` on every endpoint. This required copying the server URL and a personal API key to each machine, which doesn't scale for fleet deployments.

## Solution

The central server now generates fully pre-configured agent packages. Agents connect automatically after install with no manual configuration. Three deployment paths are available:

1. **Direct download** from the dashboard (admin clicks a button)
2. **Email enrollment** (admin enters an employee's email, they get a download link)
3. **API-driven download** for scripted/MDM deployments

All paths embed a server-managed tenant agent key automatically. No user API keys are exposed or required.

## What Was Built

### 1. Tenant Agent Key (Server-Managed Credential)

Each tenant gets a shared agent key stored on the `Tenant` model. This key is:

- Auto-generated on first agent download (or at initial server seed)
- Embedded in every agent package the server produces
- Used by agents to authenticate for event submission and heartbeats
- Rotatable by admins via `POST /api/agent/key/rotate`

**Files changed:**
- `api/models/tenant.py` - Added `agent_key` column and `generate_agent_key()` helper
- `api/alembic/versions/0004_tenant_agent_key.py` - Migration adding the column
- `api/core/tenant.py` - `resolve_auth()` now recognizes tenant agent keys as a third auth method (after JWT and user API keys), assigning the `"agent"` role
- `api/main.py` - Seed function generates an agent key for the default tenant

### 2. Reworked Agent Download Router

The `GET /api/agent/download` endpoint was reworked to accept JWT authentication (previously required a raw `X-Api-Key` header). The server now looks up the tenant's agent key internally and embeds it in the package. No API key needs to leave the server.

**New endpoints added:**

| Endpoint | Auth | Purpose |
|---|---|---|
| `GET /api/agent/download` | JWT or API key (owner/admin) | Download a pre-configured agent zip |
| `GET /api/agent/download/{token}` | None (token is auth) | Token-based download from email enrollment |
| `POST /api/agent/enroll-email` | JWT or API key (owner/admin) | Send a download link to an end user via email |
| `GET /api/agent/key` | JWT or API key (owner/admin) | View the tenant agent key prefix |
| `POST /api/agent/key/rotate` | JWT or API key (owner/admin) | Rotate the tenant agent key |

**File:** `api/routers/agent_download.py`

### 3. Email Enrollment

Admins can send a pre-configured download link to any email address. The flow:

1. Admin enters an employee email in the dashboard (or calls the API)
2. Server creates a time-limited, single-use `AuthToken` (72-hour expiry, purpose `"agent_download"`)
3. Server sends an HTML email with a download button linking to `GET /api/agent/download/{token}`
4. Employee clicks the link, downloads the pre-configured agent, installs it
5. Agent connects automatically

Requires SMTP configuration (`SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASSWORD`, `SMTP_FROM`, `SMTP_USE_TLS`).

**Files created:**
- `api/core/email.py` - SMTP email delivery utility

**Files changed:**
- `api/core/config.py` - Added SMTP settings to `Settings`
- `api/models/auth_token.py` - Added `"agent_download"` purpose, `DOWNLOAD_TOKEN_EXPIRY_HOURS`, and `create_download_token()` classmethod

### 4. Dashboard Updates

The Settings page now has a unified "Deploy Agent" section with:

- Platform, interval, and protocol selectors (unchanged)
- **Download Agent** button (now uses JWT auth instead of requiring a raw API key)
- **Email to User** subsection with email input and "Send Download Link" button
- Success/error feedback for both actions

**Files changed:**
- `dashboard/src/lib/api.js` - `downloadAgent()` uses `buildAuthHeaders()` (JWT); added `enrollAgentByEmail()`
- `dashboard/src/pages/SettingsPage.jsx` - Added email enrollment UI, updated section header and description

### 5. Config Loader (Agent Side)

The collector's config loader searches platform-specific paths so configs dropped by the installer are auto-discovered:

| Platform | Search paths |
|---|---|
| macOS | `~/Library/Application Support/Detec/agent.env`, `~/Library/Application Support/Detec/collector.json` |
| Windows | `%PROGRAMDATA%\Detec\collector.json` |
| Linux | `~/.config/detec/agent.env`, `~/.config/detec/collector.json` |

Both `.json` and `.env` (KEY=VALUE) formats are supported. Precedence: CLI > env vars > config file > code defaults.

**File changed:** `collector/config_loader.py`

### 6. Build Script Updates

**macOS** (`packaging/macos/build-pkg.sh`): Accepts `API_URL`, `API_KEY`, `AGENT_INTERVAL`, `AGENT_PROTOCOL` env vars. When set, bakes an `agent.env` into the `.app` bundle. The `postinstall` script copies it to `~/Library/Application Support/Detec/`.

**Windows** (`packaging/windows/build-agent.ps1`): Accepts `-ApiUrl` and `-ApiKey` parameters. When provided, writes a `collector.json` into the PyInstaller dist folder.

### 7. Tests

23 tests covering:

- JWT authentication (no X-Api-Key needed)
- Role restrictions (viewer blocked, owner/admin allowed)
- Tenant key auto-generation and consistency across downloads
- Agent authentication using the tenant key (heartbeat endpoint)
- Platform-specific downloads (macOS, Windows, Linux) with custom interval/protocol
- Token-based download (single-use, expiry, invalid token)
- Email enrollment (auth, SMTP errors, success with mock)
- Key management (view prefix, rotate, role restrictions)
- Input validation (invalid platform, missing platform, interval bounds)

**File:** `api/tests/test_agent_download.py` (23 tests, 105 total API tests passing)

### 8. Documentation Updates

| File | Changes |
|---|---|
| `DEPLOY.md` | Updated "Download from Dashboard" section, added email enrollment instructions, updated API examples to use JWT |
| `SERVER.md` | Updated agent downloads section with new endpoints table, added tenant agent key explanation, added SMTP config table |
| `PROGRESS.md` | Added tenant agent key and email enrollment as completed M2 items |
| `.env.example` | Added SMTP configuration variables |
| `api/.env.example` | Added SMTP configuration variables |
| `docs/mdm-deployment.md` | Updated references from "API key" to "tenant agent key," added email enrollment mention |
| `packaging/windows/README.md` | Updated configure section with tenant agent key terminology |
| `collector/README.md` | Documented platform-specific config paths and `.env` support |

## Architecture

```
Admin (Dashboard)                    End User (Email)
    |                                      |
    | JWT auth                             | Click link
    v                                      v
GET /api/agent/download          GET /api/agent/download/{token}
    |                                      |
    +---------- Server embeds -------------+
    |        tenant agent key              |
    v                                      v
  ZIP bundle: installer + agent.env + collector.json + README
    |
    v
  Agent installs, reads config from platform path
    |
    v
  POST /api/events (X-Api-Key: tenant_agent_key)
  POST /api/endpoints/heartbeat
```

## Commits

1. `c96eba9` - feat: add zero-touch agent deployment via server-generated packages
2. `e0990f6` - feat: tenant agent key, email enrollment, and token-based download
3. `431a27e` - fix: remove stale hashed agent key columns from previous session
4. fix: use ZIP_STORED for agent packages to prevent download timeouts (the inner installer is already compressed; re-deflating wasted CPU for zero savings)

# Central Server Runbook

This document covers deploying and operating the **Detec central server**: the FastAPI API and its database. Endpoint agents (`detec-agent`) call the API at `POST /api/events` and `POST /api/endpoints/heartbeat`. The dashboard is served by the same FastAPI process.

For agent deployment, see [DEPLOY.md](DEPLOY.md).

---

## Architecture overview

```
                              ┌──────────────────┐
                         HTTP │  FastAPI API      │
┌─────────────┐──POST :8000──▶  /api/events      │──SQL──▶┌──────────────┐
│ detec-agent  │              │  /api/heartbeat   │        │ SQLite or    │
│  (endpoint)  │──TCP :8001──▶│                   │        │ PostgreSQL   │
└─────────────┘     binary    │  DetecGateway     │──SQL──▶└──────────────┘
                    protocol  └────────┬──────────┘
                                       │
                                ┌──────▼───────┐
                                │  Dashboard   │
                                │  (separate)  │
                                └──────────────┘
```

Agents can connect via either transport:
- **HTTP** (default): REST calls to `POST /api/events` and `POST /api/endpoints/heartbeat` on port 8000.
- **TCP binary protocol**: Persistent msgpack-framed connection to the DetecGateway on port 8001. Lower overhead, supports server-push (policy updates, commands), and automatic reconnection. Enable with `--protocol tcp` on the agent and `GATEWAY_ENABLED=true` on the server.

**Note:** In Docker Compose the dashboard runs as a separate service (e.g. port 3001). When running the API bare metal, FastAPI serves the pre-built dashboard at the root URL (no separate process).

- **API** (`api/`): FastAPI application providing auth, event ingestion, endpoint tracking, and policy management.
- **Database**: SQLite (default, zero configuration) or PostgreSQL 16+. The API runs Alembic migrations automatically on startup (falling back to `create_all` if Alembic is unavailable).
- **Dashboard** (`dashboard/dist/`): Pre-built React SPA, served by FastAPI at the root URL. Build with `cd dashboard && npm run build`. API routes live under `/api/`, dashboard assets under `/assets/`, and all other paths fall through to `index.html` for client-side routing.

### Database options

| | SQLite (default) | PostgreSQL |
|---|---|---|
| **Setup** | Zero. Database file created automatically. | Requires install or Docker. |
| **Scale** | 1-10 endpoints (ideal for on-prem, small teams) | 10-1000+ endpoints |
| **Concurrency** | WAL mode handles moderate concurrent writes | Full MVCC concurrency |
| **Data location** | `C:\ProgramData\Detec\detec.db` (Windows), `~/Library/Application Support/Detec/detec.db` (macOS), `~/.local/share/detec/detec.db` (Linux) | Server-managed |
| **Backup** | Copy the `.db` file | `pg_dump` |

To use PostgreSQL instead of SQLite, set `DATABASE_URL` to a PostgreSQL connection string (e.g., `postgresql://user:pass@host:5432/agentic_governance`).

---

## Option A: Docker (recommended for evaluation)

The repo root contains a `docker-compose.yml` that runs the database, API, and dashboard.

```bash
docker compose up -d
```

This starts:
- **db** (PostgreSQL 16 on an internal network, not exposed to the host by default)
- **api** (FastAPI on port 8000)
- **dashboard** (on port 3001)

A `docker-compose.dev.yml` is included for development convenience (adds `--reload`, volume mount, and exposes the DB port). It is not auto-loaded; use `docker compose -f docker-compose.yml -f docker-compose.dev.yml up` for development.

The compose file reads credentials from a `.env` file (via variable substitution) and will refuse to start if required secrets are missing. Copy the template and fill in real values:

```bash
cp .env.example .env
# Edit .env: set POSTGRES_PASSWORD, JWT_SECRET, SEED_ADMIN_PASSWORD
```

Then start:

```bash
docker compose up -d
```

For production, also set `ENV=production` in `.env` so the API rejects insecure defaults on startup:

```dotenv
ENV=production
POSTGRES_PASSWORD=<strong random password>
JWT_SECRET=<output of openssl rand -hex 32>
SEED_ADMIN_PASSWORD=<strong password>
SEED_ADMIN_EMAIL=admin@yourorg.com
```

The API container runs Alembic migrations automatically before starting (see `api/entrypoint.sh`). Set `RUN_MIGRATIONS=false` to skip this if you prefer manual migration control.

---

## Option B: Windows Installer (recommended for Windows)

The easiest way to deploy on Windows. Ship a single `DetecServerSetup.exe` to the target machine; no prerequisites required.

### GUI installer (recommended)

Build the installer on your build machine (requires Python 3.11+, Node.js 22+, and [Inno Setup 6](https://jrsoftware.org/isdl.php)):

```powershell
powershell -ExecutionPolicy Bypass -File packaging\windows\build-installer.ps1
```

This produces `packaging/windows/dist/DetecServerSetup-0.1.0.exe`. The wizard handles license acceptance, pre-flight checks, server configuration (port, database), admin account creation, service installation, firewall rules, and a desktop shortcut. See [packaging/windows/README.md](packaging/windows/README.md) for full details.

### Manual build (alternative)

If you prefer to build without the installer wrapper:

#### Prerequisites

- Python 3.11+
- Node.js 20.19+ or 22.12+ (for building the dashboard; Vite requires these versions)

#### Build the server

```powershell
powershell -ExecutionPolicy Bypass -File packaging/windows/build.ps1
```

Or build manually (see [packaging/windows/README.md](packaging/windows/README.md)).

### 2. First-run setup

```powershell
cd packaging\windows\dist\detec-server
.\detec-server.exe setup --admin-email admin@yourorg.com
```

This generates secrets and writes config to `C:\ProgramData\Detec\server.env`. Save the admin password shown on screen.

### 3. Install and start the service

From an **elevated** (Administrator) command prompt:

```powershell
.\detec-server.exe install
.\detec-server.exe start
```

The service runs in the background, survives logoff, and starts automatically on boot. A "Detec Dashboard" shortcut is placed on the desktop during deployment. Open http://localhost:8000 to access the dashboard. Service output is logged to `C:\ProgramData\Detec\server.log`; crash tracebacks are also written to the Windows Event Log (Application, source "DetecServer").

### Service management

```powershell
.\detec-server.exe status    # show config, DB size, service state
.\detec-server.exe stop      # stop the service
.\detec-server.exe start     # start the service
.\detec-server.exe remove    # unregister the service
```

For full details, see [packaging/windows/README.md](packaging/windows/README.md).

---

## Option C: Bare metal / VM (SQLite)

The fastest way to get the server running. No database install required.

### Prerequisites

- Python 3.11+

### 1. Set environment variables

```bash
export JWT_SECRET="$(openssl rand -hex 32)"
export SEED_ADMIN_PASSWORD="change-me-to-something-strong"
```

The API will create a SQLite database automatically at the platform-appropriate location. See [Production environment variables](#production-environment-variables) for the full list.

### 2. Install dependencies

```bash
cd api
pip install -r requirements.txt
```

### 3. Start the API

```bash
cd api
uvicorn main:app --host 0.0.0.0 --port 8000
```

For development, add `--reload`. For production, use a process manager (systemd, supervisord) or a container.

---

## Option D: Bare metal / VM (PostgreSQL)

Use this option when you need higher concurrency or are managing 100+ endpoints.

### Prerequisites

- Python 3.11+
- PostgreSQL 16+ (running and accessible)

### 1. Create the database

```bash
createdb agentic_governance
```

### 2. Set environment variables

```bash
export DATABASE_URL="postgresql://postgres:yourpassword@localhost:5432/agentic_governance"
export JWT_SECRET="$(openssl rand -hex 32)"
export SEED_ADMIN_PASSWORD="change-me-to-something-strong"
```

### 3. Install dependencies

```bash
cd api
pip install -r requirements.txt
```

Migrations run automatically when the server starts. To run them manually instead:

```bash
cd api
alembic upgrade head
```

### 4. Start the API

```bash
cd api
uvicorn main:app --host 0.0.0.0 --port 8000
```

---

## Production checklist

### TLS

In production, run the API behind a TLS-terminating reverse proxy or load balancer (nginx, Caddy, AWS ALB, etc.). The API itself serves plain HTTP on port 8000; HTTPS termination happens at the proxy layer.

For the binary protocol gateway (port 8001), you can either provide TLS certificates directly via `GATEWAY_TLS_CERT` and `GATEWAY_TLS_KEY`, or terminate TLS at the proxy layer and forward plain TCP to the gateway.

### Network / firewall

Open the following ports:

| Port | Protocol | Service |
|------|----------|---------|
| 8000 | TCP (HTTP) | FastAPI API + dashboard |
| 8001 | TCP (binary) | DetecGateway (when `GATEWAY_ENABLED=true`) |

### Environment enforcement

When `ENV=production` or `ENV=staging`, the API rejects startup if `JWT_SECRET` or `SEED_ADMIN_PASSWORD` are still set to their insecure defaults. This is enforced in `api/core/config.py`.

### Migrations

The server runs `alembic upgrade head` automatically during startup, so no separate migration step is required. If Alembic is unavailable or the migration fails, it falls back to `create_all` (which cannot track schema changes over time). You can also run migrations manually with `cd api && alembic upgrade head`.

### Process management

Run the API under a process manager that restarts on failure:
- **Docker**: `restart: unless-stopped` (already set in `docker-compose.yml`)
- **systemd**: create a unit file similar to the agent's (see `deploy/linux/`)
- **Cloud**: use your platform's container service (ECS, Cloud Run, etc.)

---

## Security hardening

The API includes several hardening measures for production use.

### API key hashing

API keys are hashed (SHA-256) before storage. The raw key is displayed **once** at creation time (in the seed log on first startup, or in the registration API response). It cannot be recovered from the database. If you lose the key, delete the user row and restart the API to re-seed, or register a new user.

### Invite and password reset

Admin-created users can be onboarded without sharing temporary passwords. When an admin creates a user via `POST /users` without a `password` field, the API generates a one-time invite token (24-hour expiry) and returns it in the response. The admin shares the invite link with the new user, who visits the link to set their password and activate their account.

Password reset uses a similar flow: `POST /auth/forgot-password` creates a reset token (1-hour expiry). Until email delivery is configured, the token is returned in the response body. `POST /auth/reset-password` validates the token and updates the password. `POST /auth/accept-invite` works the same way for invite tokens.

On login, the response includes a `password_reset_required` flag. The dashboard checks this and redirects the user to the set-password page if true.

All token operations are audit-logged (`password.reset_requested`, `password.reset_completed`, `invite.accepted`).

### Rate limiting

Auth endpoints are rate-limited to prevent brute-force attacks:
- Login, register, forgot-password, reset-password, accept-invite: 5 requests per minute per IP
- Token refresh: 10 requests per minute per IP

Rate limiting is provided by `slowapi`. Clients that exceed the limit receive HTTP 429 (Too Many Requests).

### Role-based access control

Users have a `role` field with four possible values:

| Role | Description |
|------|-------------|
| `owner` | Tenant creator. Full access. Cross-tenant read visibility. Cannot be demoted or deactivated by other users. |
| `admin` | Full access. Cross-tenant read visibility. Can manage users (create, update, deactivate) but cannot modify the owner. |
| `analyst` | Read/write access to events and endpoints. Read-only for policies. Scoped to own tenant. |
| `viewer` | Read-only access everywhere. Scoped to own tenant. |

Sensitive endpoints enforce role checks:

- **Owner only**: `DELETE /users/{id}` (deactivate user)
- **Owner or admin**: `GET /users`, `POST /users`, `PATCH /users/{id}`, `POST /policies`, `PATCH /policies/{id}`, `POST /endpoints/enroll`, `GET/POST/PATCH/DELETE /webhooks`
- **Owner, admin, or analyst**: `GET /audit-log`
- **Any authenticated user**: read endpoints, read events, heartbeat
- **Unauthenticated**: `POST /auth/forgot-password`, `POST /auth/reset-password`, `POST /auth/accept-invite`

Users with insufficient privileges receive HTTP 403.

The seed user and self-registered users receive the `owner` role (they are tenant creators). New users created via the admin panel can be assigned `admin`, `analyst`, or `viewer`.

#### Cross-tenant read visibility

Owner and admin roles can read data across all tenants on query endpoints (events, endpoints, endpoint status, audit log, policies, users). This is read-only visibility for operational oversight; write and ingest endpoints remain strictly tenant-scoped so agents can only write to their own tenant. Analyst and viewer roles see only their own tenant's data. The logic is centralized in `get_tenant_filter()` in `api/core/tenant.py`.

### Webhook alerts

The API supports outbound HTTP webhooks for real-time event notifications. Configure webhooks via the dashboard Settings page or the REST API:

- `GET /webhooks` - list webhooks for the tenant
- `POST /webhooks` - create a webhook (URL, event types, active toggle)
- `PATCH /webhooks/{id}` - update URL, events, or active state
- `DELETE /webhooks/{id}` - remove a webhook
- `POST /webhooks/{id}/test` - send a test payload to verify the endpoint

Each webhook has an HMAC signing secret (auto-generated, prefixed `whsec_`). Deliveries include:
- `X-Detec-Signature: sha256=<hmac>` header for payload verification
- `X-Detec-Delivery-Id` header for idempotency
- Retry: up to 3 attempts with exponential backoff (1s, 4s, 16s)

Subscribe to specific event types (e.g., `enforcement.block`, `enforcement.approval_required`) or leave the events list empty to receive all events. Webhooks are dispatched when events are ingested via both the HTTP API and the TCP gateway.

Webhook management requires the `owner` or `admin` role.

### Audit log

All security-relevant actions are recorded in the `audit_log` table with actor, tenant, action, resource, IP address, and timestamp. Audited actions include:

- `user.registered`, `user.login` (auth events)
- `user.created`, `user.updated`, `user.deactivated` (user management)
- `password.reset_requested`, `password.reset_completed`, `invite.accepted` (auth token events)
- `policy.created`, `policy.updated` (policy changes)
- `endpoint.enrolled`, `endpoint.key_rotated` (enrollment events)
- `webhook.created`, `webhook.updated`, `webhook.deleted`, `webhook.tested` (webhook management)

Query the audit log via `GET /audit-log` (requires admin or analyst role).

### Tenant isolation

Write operations and event ingestion are strictly scoped by `tenant_id`. Event deduplication checks are tenant-scoped to prevent cross-tenant data leakage. Endpoint creation uses a unique constraint on `(tenant_id, hostname)` to prevent duplicates.

Read-only query endpoints allow owner and admin roles to see data across all tenants for operational oversight. Analyst and viewer roles remain scoped to their own tenant on all endpoints. See [Cross-tenant read visibility](#cross-tenant-read-visibility) above for details.

### Docker security

- **No secrets in compose**: `docker-compose.yml` uses `${VARIABLE}` substitution from `.env`. Required variables (`POSTGRES_PASSWORD`, `JWT_SECRET`) use the `:?` syntax so Docker Compose fails immediately with a clear error if they are not set.
- **Non-root containers**: Both the API and dashboard containers run as an unprivileged `appuser`.
- **Network segmentation**: The database is on an internal-only `backend` network (not exposed to the host by default). The API bridges `backend` and `frontend` networks. The dashboard is on `frontend` only and cannot reach the database directly.
- **Dev overrides**: Development settings (volume mounts, `--reload`, DB port exposure, `DEBUG=true`) live in `docker-compose.dev.yml`. Use `docker compose -f docker-compose.yml -f docker-compose.dev.yml up` to apply them. They are not auto-loaded.
- **Health checks**: The API service has a Docker health check that calls `GET /health`, which verifies database connectivity and returns 503 if the DB is unreachable.

### JWT tokens

Access and refresh tokens include `iat` (issued-at) and `jti` (unique token ID) claims for audit trails and future revocation support.

### Input validation

All user-facing inputs have length limits enforced at the schema level (passwords capped at 128 characters, hostnames at 255, etc.) to prevent oversized payloads.

---

## Production environment variables

All settings are defined in `api/core/config.py` (pydantic-settings). Field names map to uppercase environment variables (e.g., `database_url` reads `DATABASE_URL`). The API also reads from an `.env` file in the `api/` working directory.

### Required

| Variable | Description |
|---|---|
| `JWT_SECRET` | Secret key for signing JWTs. Generate with `openssl rand -hex 32`. Must not be a default value when `ENV` is `production` or `staging`. |
| `SEED_ADMIN_PASSWORD` | Password for the seed admin user created on first startup. Must not be `change-me` when `ENV` is `production` or `staging`. |

### Database

| Variable | Default | Description |
|---|---|---|
| `DATABASE_URL` | SQLite (platform-appropriate path) | Connection string. Defaults to a local SQLite file. Set to `postgresql://user:pass@host:5432/dbname` for PostgreSQL. |

### Optional

| Variable | Default | Description |
|---|---|---|
| `ENV` | `development` | Environment name. Set to `production` or `staging` to enable security guards. |
| `SEED_ADMIN_EMAIL` | `admin@example.com` | Email for the seed admin user. |
| `SEED_TENANT_NAME` | `Default` | Name of the seed tenant. |
| `CORS_ORIGINS` | `http://localhost:5173,http://localhost:3000,http://localhost:3001` | Comma-separated list of allowed CORS origins. Set to your dashboard URL in production. |
| `API_HOST` | `0.0.0.0` | Bind address for uvicorn. |
| `API_PORT` | `8000` | Bind port for uvicorn. |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | `60` | JWT access token lifetime. |
| `REFRESH_TOKEN_EXPIRE_DAYS` | `30` | JWT refresh token lifetime. |
| `DEFAULT_HEARTBEAT_INTERVAL` | `300` | Default heartbeat interval in seconds for new endpoints. |
| `DEBUG` | `false` | Enable debug mode. Do not use in production. |
| `RUN_MIGRATIONS` | `true` | (Docker only) Set to `false` to skip automatic Alembic migrations on container start. |

### Webhooks

| Variable | Default | Description |
|---|---|---|
| `WEBHOOK_DELIVERY_TIMEOUT` | `10` | HTTP timeout in seconds for webhook delivery requests. |
| `WEBHOOK_MAX_RETRIES` | `3` | Maximum retry attempts for failed webhook deliveries. |

### Binary protocol gateway

| Variable | Default | Description |
|---|---|---|
| `GATEWAY_ENABLED` | `true` | Start the TCP gateway alongside the HTTP API. Set to `false` to disable. |
| `GATEWAY_HOST` | `0.0.0.0` | Bind address for the gateway listener. |
| `GATEWAY_PORT` | `8001` | TCP port for the binary protocol gateway. |
| `GATEWAY_TLS_CERT` | _(none)_ | Path to a PEM certificate file for TLS. When both cert and key are set, the gateway uses TLS; otherwise plain TCP. |
| `GATEWAY_TLS_KEY` | _(none)_ | Path to the PEM private key file for TLS. |

When enabled, the gateway listens for persistent agent connections using the Detec wire protocol (length-prefixed msgpack frames). Agents authenticate with the same API key used for HTTP. In production, provide TLS certificates or terminate TLS at the network layer (load balancer, reverse proxy). See [DEPLOY.md](DEPLOY.md) for agent-side configuration.

### EDR integration

Server-side enrichment of detection events using enterprise EDR platforms (CrowdStrike Falcon, SentinelOne, Microsoft Defender). When enabled, the server queries the configured EDR for process and network events around each detection, removes polling-related confidence penalties where EDR evidence exists, and rescores confidence. Enrichment runs as an async background task and does not block event ingestion.

| Variable | Default | Description |
|---|---|---|
| `EDR_PROVIDER` | _(none)_ | EDR provider name (`crowdstrike`). Leave empty to disable. |
| `EDR_API_BASE` | _(none)_ | EDR API base URL (e.g., `https://api.crowdstrike.com`). |
| `EDR_CLIENT_ID` | _(none)_ | OAuth2 client ID for the EDR API. |
| `EDR_CLIENT_SECRET` | _(none)_ | OAuth2 client secret for the EDR API. |
| `EDR_ENRICHMENT_ENABLED` | `false` | Master switch for EDR enrichment. Set to `true` to enable. |
| `EDR_QUERY_WINDOW_BEFORE_SECONDS` | `300` | Seconds before the detection timestamp to query EDR events (default: 5 minutes). |
| `EDR_QUERY_WINDOW_AFTER_SECONDS` | `60` | Seconds after the detection timestamp to query EDR events (default: 1 minute). |

All four credentials (`EDR_PROVIDER`, `EDR_API_BASE`, `EDR_CLIENT_ID`, `EDR_CLIENT_SECRET`) must be set and `EDR_ENRICHMENT_ENABLED` must be `true` for enrichment to activate. The agent requires no changes for EDR enrichment; it continues to emit events via the existing HTTP or TCP transport.

### SMTP (email enrollment)

| Variable | Default | Description |
|---|---|---|
| `SMTP_HOST` | _(none)_ | SMTP server hostname. Required for email enrollment. |
| `SMTP_PORT` | `587` | SMTP server port. |
| `SMTP_USER` | _(none)_ | SMTP username for authentication. |
| `SMTP_PASSWORD` | _(none)_ | SMTP password for authentication. |
| `SMTP_FROM` | _(none)_ | "From" address for outgoing emails. Required for email enrollment. |
| `SMTP_USE_TLS` | `true` | Use STARTTLS for the SMTP connection. |

When `SMTP_HOST` and `SMTP_FROM` are set, admins can send agent download links directly to end users via the dashboard or the `POST /api/agent/enroll-email` endpoint.

---

## Agent downloads

The server generates pre-configured agent packages via the dashboard or the API. Each package includes a tenant-level agent key (managed server-side), so agents connect automatically after install.

### Setup

**Windows installer:** The `build-installer.ps1` pipeline automatically builds the Windows agent, zips it, and bundles it into the installer. Agent downloads work from the dashboard immediately after install with no extra steps.

**Docker / bare metal:** Place pre-built agent packages in `dist/packages/` relative to the API working directory (or the server exe directory for PyInstaller builds):

| Platform | Expected filename | How to build |
|----------|------------------|--------------|
| Windows | `detec-agent.zip` | `build-agent.ps1` then zip the `dist/detec-agent/` folder |
| macOS | `DetecAgent-latest.pkg` or `DetecAgent.pkg` | `bash packaging/macos/build-pkg.sh` (macOS only) |
| Linux | `detec-agent-linux.tar.gz` | PyInstaller on Linux, then tar the output |

### Endpoints

| Endpoint | Auth | Description |
|----------|------|-------------|
| `GET /api/agent/download?platform=...` | JWT or API key (owner/admin) | Download a pre-configured agent package |
| `GET /api/agent/download/{token}?platform=...` | None (token is auth) | Token-based download from email enrollment |
| `POST /api/agent/enroll-email` | JWT or API key (owner/admin) | Send a download link via email |
| `GET /api/agent/key` | JWT or API key (owner/admin) | View the tenant agent key prefix |
| `POST /api/agent/key/rotate` | JWT or API key (owner/admin) | Rotate the tenant agent key |

### Tenant agent key

Each tenant has a server-managed agent key used to authenticate agents for event submission and heartbeats. The key is generated automatically on the first agent download (or on tenant seed) and embedded in every agent package. Admins can rotate the key via `POST /api/agent/key/rotate` (existing agents will need reconfiguration).

See [DEPLOY.md](DEPLOY.md) for full usage including email enrollment.

---

## First API key

On first startup, the API seeds one tenant and one admin user with a randomly generated API key. The **raw key is printed once in the server log** and cannot be recovered from the database afterward (it is stored as a SHA-256 hash).

### Retrieve the seeded API key

**Option 1: Check startup logs.** Look for the line:

```
[seed] Admin API key (save this, it will not be shown again): <key>
```

Copy this key immediately.

**Option 2: Re-seed.** If you lost the key, delete the admin user row and restart the API. A new key will be generated and printed.

**Option 3: Register a new user.** `POST /auth/register` returns the raw API key in the response body. This is the only time the key is visible.

### Using the key

Pass the key in the `X-Api-Key` header for agent and API requests:

```bash
curl -H "X-Api-Key: <key>" http://localhost:8000/api/endpoints
```

Configure agents with this key via `--api-key`, `AGENTIC_GOV_API_KEY`, or the config file. See [DEPLOY.md](DEPLOY.md) for agent configuration.

---

## Schema migrations with Alembic

The `api/` directory contains an Alembic setup for versioned schema migrations.

### Running migrations

```bash
cd api
alembic upgrade head
```

### Creating a new migration

After modifying models in `api/models/`, generate a migration:

```bash
cd api
alembic revision --autogenerate -m "describe the change"
```

Review the generated file in `api/alembic/versions/` before applying it.

### Existing databases

If you have an existing database created by `create_all` (before Alembic was added), stamp it to mark the initial migration as applied without re-running it:

```bash
cd api
alembic stamp 0001
```

Then future migrations will apply cleanly on top.

---

## Health check

The API exposes `GET /health` (and `GET /api/health`) which verifies database connectivity and returns:

- `{"status": "ok", "version": "0.1.0", "db": "ok"}` (HTTP 200) when healthy
- `{"status": "degraded", "version": "0.1.0", "db": "unreachable"}` (HTTP 503) when the database is down

Use this for load balancer health checks and container orchestrator probes. The Docker compose file includes an API health check that uses this endpoint.

---

## Troubleshooting

| Symptom | Likely cause | Fix |
|---|---|---|
| API refuses to start with "JWT_SECRET must be set" | `ENV=production` but using default secret | Set `JWT_SECRET` to output of `openssl rand -hex 32` |
| API refuses to start with "SEED_ADMIN_PASSWORD must be changed" | `ENV=production` but using default password | Set `SEED_ADMIN_PASSWORD` to a strong value |
| `Connection refused` on database | PostgreSQL not running or wrong `DATABASE_URL` | Verify PostgreSQL is running; check host/port/credentials |
| Tables exist but Alembic says "Target database is not up to date" | Database was created by `create_all`, not Alembic | Run `alembic stamp 0001` to mark the baseline |
| Agent gets 401 / 403 | Wrong or missing API key | Check the seed log for the raw key; verify `X-Api-Key` header |
| HTTP 429 on login | Rate limit exceeded | Wait 60 seconds and retry; limit is 5 requests/minute per IP |
| Health check returns 503 | Database unreachable | Check `DATABASE_URL` and PostgreSQL status |
| Lost the admin API key | Keys are hashed and not recoverable | Delete the admin user row and restart the API, or register a new user |

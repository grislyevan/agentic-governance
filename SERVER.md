# Central Server Runbook

This document covers deploying and operating the **Detec central server**: the FastAPI API and its database. Endpoint agents (`detec-agent`) call the API at `POST /api/events` and `POST /api/endpoints/heartbeat`. The dashboard is served by the same FastAPI process.

For agent deployment, see [DEPLOY.md](DEPLOY.md).

---

## Architecture overview

```
┌─────────────┐        ┌──────────────┐        ┌──────────────┐
│ detec-agent  │──POST──▶  FastAPI API  │──SQL──▶│ SQLite or    │
│  (endpoint)  │        │  :8000       │        │ PostgreSQL   │
└─────────────┘        └──────┬───────┘        └──────────────┘
                              │
                       ┌──────▼───────┐
                       │  Dashboard   │
                       │  (separate)  │
                       └──────────────┘
```

- **API** (`api/`): FastAPI application providing auth, event ingestion, endpoint tracking, and policy management.
- **Database**: SQLite (default, zero configuration) or PostgreSQL 16+. The API creates tables on first startup or via Alembic migrations.
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

## Option B: Bare metal / VM (SQLite)

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

## Option C: Bare metal / VM (PostgreSQL)

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

### 3. Install dependencies and run migrations

```bash
cd api
pip install -r requirements.txt
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

### Environment enforcement

When `ENV=production` or `ENV=staging`, the API rejects startup if `JWT_SECRET` or `SEED_ADMIN_PASSWORD` are still set to their insecure defaults. This is enforced in `api/core/config.py`.

### Migrations

For production, run `alembic upgrade head` before starting the API (or use the Docker entrypoint, which does this automatically). The `create_all` call on startup is a convenience for development; it is a no-op when the tables already exist but cannot track schema changes over time.

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

### Rate limiting

Auth endpoints (`/api/auth/login`, `/api/auth/register`, `/api/auth/refresh`) are rate-limited to prevent brute-force attacks:
- Login and register: 5 requests per minute per IP
- Token refresh: 10 requests per minute per IP

Rate limiting is provided by `slowapi`. Clients that exceed the limit receive HTTP 429 (Too Many Requests).

### Role-based access control

Users have a `role` field with four possible values:

| Role | Description |
|------|-------------|
| `owner` | Tenant creator. Full access. Cannot be demoted or deactivated by other users. |
| `admin` | Full access. Can manage users (create, update, deactivate) but cannot modify the owner. |
| `analyst` | Read/write access to events and endpoints. Read-only for policies. |
| `viewer` | Read-only access everywhere. |

Sensitive endpoints enforce role checks:

- **Owner only**: `DELETE /users/{id}` (deactivate user)
- **Owner or admin**: `GET /users`, `POST /users`, `PATCH /users/{id}`, `POST /policies`, `PATCH /policies/{id}`, `POST /endpoints/enroll`
- **Owner, admin, or analyst**: `GET /audit-log`
- **Any authenticated user**: read endpoints, read events, heartbeat

Users with insufficient privileges receive HTTP 403.

The seed user and self-registered users receive the `owner` role (they are tenant creators). New users created via the admin panel can be assigned `admin`, `analyst`, or `viewer`.

### Audit log

All security-relevant actions are recorded in the `audit_log` table with actor, tenant, action, resource, IP address, and timestamp. Audited actions include:

- `user.registered`, `user.login` (auth events)
- `user.created`, `user.updated`, `user.deactivated` (user management)
- `policy.created`, `policy.updated` (policy changes)
- `endpoint.enrolled`, `endpoint.key_rotated` (enrollment events)

Query the audit log via `GET /audit-log` (requires admin or analyst role).

### Tenant isolation

All data queries are scoped by `tenant_id`. Event deduplication checks are tenant-scoped to prevent cross-tenant data leakage. Endpoint creation uses a unique constraint on `(tenant_id, hostname)` to prevent duplicates.

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

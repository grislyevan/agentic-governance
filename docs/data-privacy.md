# Data Privacy and Retention

This document describes what personal and system data Detec collects, how long it is retained, and how to purge it.

## PII Collected

The system collects and stores the following data that may identify individuals or devices:

| Data | Source | Stored In |
|------|--------|-----------|
| Endpoint hostname | Agent (default: `socket.gethostname()`) | Endpoint table, event payload |
| Username (process owner) | Agent (default: `getpass.getuser()`) | Event payload (actor.id), scan evidence |
| User email | Dashboard registration, invite flow | User table |
| User first/last name | Dashboard registration | User table |

The canonical event payload (`events.payload`) stores the full event envelope, including `actor.id` (often the OS username) and `endpoint.id` (hostname). The server does not add PII beyond what the agent sends.

## Agent vs Server

**Agent (collector):**

- EventStore retains 120 seconds or 10,000 events (configurable)
- Telemetry includes process names, cmdlines, usernames, network connections, file paths
- Only canonical events (detection, policy, enforcement, lifecycle) are emitted to the server
- Raw telemetry is never sent; it is used locally for attribution and then discarded

**Server (API):**

- Stores canonical events indefinitely until purged
- Stores endpoint records (hostname, os_info, last_seen_at)
- Stores user accounts (email, name, role)
- Audit log records actions (actor_id, resource_id, detail)

## Retention Periods

- **Events:** Configurable per tenant. Default 90 days. Set via `PUT /api/retention/settings` (owner only) or `DEFAULT_RETENTION_DAYS` in config.
- **Endpoints:** No automatic deletion. Endpoints are marked `is_stale` when `last_seen_at` is older than `stale_threshold_days` (default 30). This is informational only.
- **Users, audit log, policies:** No automatic retention; managed by tenant.

## Purging Data

**Automatic purge:** A background task runs on startup and every 6 hours. It deletes events older than each tenant's `retention_days` (or global default) in batches of 1000.

**Manual purge:** `POST /api/events/purge` (owner only). Optional body: `{ "older_than_days": 30 }` to override the tenant retention for this run. Returns `{ "deleted": N }`. The action is logged to the audit log.

## Configuration

| Setting | Default | Description |
|---------|---------|-------------|
| `DEFAULT_RETENTION_DAYS` | 90 | Global default when tenant has no retention_days |
| `stale_threshold_days` | 30 | Days after which endpoints are marked stale |

Tenant retention is validated: minimum 7 days, maximum 365 days.

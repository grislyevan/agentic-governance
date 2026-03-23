# EDR Credential Security Guide

## Overview

Detec's EDR enforcement integration (Phase 6) requires API credentials for
CrowdStrike Falcon (and future providers like SentinelOne). These credentials
grant powerful capabilities: process termination, network containment, and
endpoint quarantine. Protecting them is critical.

## Current Configuration

Credentials are loaded from environment variables via `api/core/config.py`:

| Variable | Purpose |
|----------|---------|
| `EDR_PROVIDER` | Provider name (e.g. `crowdstrike`) |
| `EDR_API_BASE` | API base URL (e.g. `https://api.crowdstrike.com`) |
| `EDR_CLIENT_ID` | OAuth2 client ID |
| `EDR_CLIENT_SECRET` | OAuth2 client secret |
| `EDR_ENFORCEMENT_ENABLED` | Master switch for delegated enforcement |
| `EDR_ENFORCEMENT_FALLBACK` | Fallback behavior: `local` or `none` |

When `EDR_ENFORCEMENT_ENABLED=true` and the EDR credentials are set, the
API server registers the `CrowdStrikeEnforcementProvider` at startup
(in the lifespan handler in `api/main.py`). If the provider is not
registered, enforcement falls back to the local agent path.

For development and testing, `.env` files are convenient. For production,
environment variables alone are insufficient.

## Production Recommendations

### 1. Use a Secrets Manager

Store `EDR_CLIENT_ID` and `EDR_CLIENT_SECRET` in a dedicated secrets manager:

- **HashiCorp Vault**: Use the `vault` agent or `envconsul` to inject secrets
  at process start
- **AWS Secrets Manager**: Use the AWS SDK or ECS/EKS native secret injection
- **Azure Key Vault**: Use managed identity + Key Vault references
- **Google Secret Manager**: Use workload identity + secret volumes

The Detec API server should read credentials from the secrets manager at
startup and never persist them to disk.

### 2. Scope API Credentials Minimally

CrowdStrike Falcon API credentials should be scoped to the minimum required
permissions:

| Scope | Required For |
|-------|-------------|
| **Hosts (Read)** | `resolve_endpoint_id()` to map hostnames to device IDs |
| **Real Time Response (Admin)** | RTR sessions: kill processes, run commands |
| **Host Actions (Write)** | Network containment (contain/uncontain hosts) |

Do not grant broader scopes (e.g., full admin, policy management,
detection management) unless those features are explicitly used.

### 3. Rotate Credentials Regularly

- Set a rotation schedule (90 days recommended for OAuth2 client secrets)
- Use your secrets manager's rotation feature if available
- The `CrowdStrikeProvider` caches tokens with a 60-second safety margin
  before expiry, so credential rotation does not cause downtime

### 4. Restrict File Permissions

If you must use `.env` files (e.g., single-server deployments):

```bash
# Restrict to the service account only
chmod 600 /path/to/api/.env
chown detec-api:detec-api /path/to/api/.env
```

Never commit `.env` files to version control. The repository includes
`.env` in `.gitignore`.

### 5. Audit Credential Access

- Enable audit logging on your secrets manager
- Monitor for unexpected `EDR_CLIENT_ID` / `EDR_CLIENT_SECRET` reads
- All enforcement actions are logged in Detec's audit log with the
  provider name, action, and outcome

## Threat Model Considerations

### Credential Theft

If an attacker obtains the CrowdStrike API credentials, they could:

- Kill processes on any managed endpoint
- Network-contain (isolate) endpoints, causing denial of service
- Open RTR sessions to execute commands on endpoints

**Mitigations:**

- Secrets manager with access control and audit logging
- Minimal API scope (no full admin access)
- Network segmentation (API server can reach CrowdStrike, but other
  hosts cannot)
- IP allowlisting on the CrowdStrike API client if supported

### Server Compromise

If the Detec API server is compromised:

- Credentials in memory are exposed regardless of storage method
- The attacker gains the same enforcement capabilities as Detec
- Containment: monitor for anomalous enforcement patterns (mass
  containment, unusual process kills) via the audit log and webhook
  alerts

### RTR Session Hijacking

CrowdStrike limits concurrent RTR sessions per host. An attacker with
credentials could open sessions to block legitimate enforcement.

- The enforcement router handles 409 Conflict (session in use) gracefully
  and falls back to local enforcement
- Rate-limit RTR session creation if possible via CrowdStrike policy

## Environment-Specific Configuration

### Docker / Kubernetes

```yaml
# Kubernetes Secret
apiVersion: v1
kind: Secret
metadata:
  name: detec-edr-credentials
type: Opaque
stringData:
  EDR_CLIENT_ID: "your-client-id"
  EDR_CLIENT_SECRET: "your-client-secret"
---
# Pod spec
envFrom:
  - secretRef:
      name: detec-edr-credentials
```

### systemd Service

```ini
# /etc/systemd/system/detec-api.service.d/edr.conf
[Service]
Environment=EDR_PROVIDER=crowdstrike
Environment=EDR_API_BASE=https://api.crowdstrike.com
Environment=EDR_ENFORCEMENT_ENABLED=true
EnvironmentFile=/etc/detec/edr-credentials.env
```

Where `/etc/detec/edr-credentials.env` is mode 0600 and contains only:

```
EDR_CLIENT_ID=...
EDR_CLIENT_SECRET=...
```

## Validation Status (Task 8c, 2026-03-12)

A codebase audit confirmed:

- **No EDR credentials are stored in any tracked file.** The root `.env`
  is in `.gitignore`. The `.env.example` files contain commented-out
  placeholders with empty values only.
- **No credentials are hardcoded in source code.** `CrowdStrikeProvider`
  receives credentials as constructor arguments, sourced from
  `Settings` (env vars / `.env`).
- **`collector.json` does not contain EDR credentials.** The collector
  agent has no need for them; EDR enforcement is server-side.
- **Provider registration happens at startup** when
  `edr_enforcement_configured` is true, so credentials are only read
  once and held in memory.
- **Token caching** in `CrowdStrikeProvider._ensure_token()` minimizes
  credential use: tokens are refreshed only when expired (with a
  60-second safety margin).

### Recommended production credential flow

1. Store `EDR_CLIENT_ID` and `EDR_CLIENT_SECRET` in a secrets manager
   (Vault, AWS Secrets Manager, Azure Key Vault, or GCP Secret Manager).
2. Inject as environment variables at process start (via sidecar,
   init container, or systemd `EnvironmentFile`).
3. Never write credentials to disk in plaintext on the API server.
4. Rotate client secrets every 90 days.
5. Scope CrowdStrike API credentials to Hosts (Read), RTR (Admin),
   and Host Actions (Write) only.

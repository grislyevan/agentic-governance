# Secrets Management

**Created:** 2026-03-12
**Status:** Decision documented. Implementation complete for current deployment target (Windows bare-metal VM).

---

## Evaluation

Three approaches were evaluated for managing production secrets: platform-native environment variables, Doppler, and AWS Secrets Manager.

| Criteria | Platform Env Vars | Doppler | AWS Secrets Manager |
|----------|-------------------|---------|---------------------|
| Cost | Free | Free tier (5 projects) | ~$0.40/secret/month |
| Complexity | Low | Medium | High |
| Rotation | Manual | Built-in, auto-sync | Built-in, Lambda rotation |
| CI/CD integration | Native (GitHub Actions secrets) | CLI + integrations | SDK + IAM roles |
| Team fit (solo/small) | Excellent | Good | Overkill |
| Audit trail | OS-level only | Full history | CloudTrail |

### Decision: Platform-native environment variables

**Rationale:** The current deployment target is a bare-metal Windows VM (192.168.64.4) running Python directly. For this setup:

1. **Windows**: System-level environment variables set via `setx /M` or the System Properties GUI persist across reboots and are scoped to the machine account. The Detec server runs as a Windows service under SYSTEM, which reads these variables automatically.
2. **Docker**: Docker Compose reads from `.env` (gitignored) and uses `${VAR:?error}` syntax to fail fast on missing values.
3. **Fly.io**: `fly secrets set` stores encrypted values in the Fly platform, injected as env vars at runtime.
4. **Kubernetes**: `Secret` resources (base64-encoded, optionally sealed with SealedSecrets or external-secrets-operator).

This approach works across all current deployment targets with zero additional dependencies. The production validator in `api/core/config.py` already rejects insecure defaults when `ENV=production`.

### Migration path

When the team grows beyond 3 people or the deployment spans multiple environments needing synchronized secrets:

1. **Doppler** (recommended next step): Install `doppler` CLI, create a project, import existing env vars with `doppler import`. The free tier supports 5 projects. Update CI to use `doppler run -- <command>`.
2. **AWS Secrets Manager**: Only when running on AWS infrastructure. Use `boto3` to fetch secrets at startup; cache with TTL for rotation support.

---

## Secrets Inventory

All secrets the Detec server requires in production:

| Secret | Purpose | Rotation frequency |
|--------|---------|-------------------|
| `JWT_SECRET` | Signs access and refresh tokens | On compromise; rotate invalidates all sessions |
| `SEED_ADMIN_PASSWORD` | Initial admin account password | One-time setup; user should change after first login |
| `DATABASE_URL` | Database connection string (contains password) | On DB password rotation |
| `STRIPE_SECRET_KEY` | Stripe API authentication | Via Stripe dashboard; rotate on key compromise |
| `STRIPE_WEBHOOK_SECRET` | Validates inbound Stripe webhook signatures | On endpoint recreation in Stripe |
| `EDR_CLIENT_ID` / `EDR_CLIENT_SECRET` | CrowdStrike / EDR OAuth2 credentials | Per EDR vendor policy (typically 90 days) |
| `SMTP_PASSWORD` | Email relay authentication | Per SMTP provider policy |
| `GATEWAY_TLS_KEY` | TCP gateway TLS private key | On certificate renewal |
| `SEED_API_KEY` / `SEED_AGENT_KEY` | Pinned API keys for stable agent config | On compromise; rotate via `POST /api/agent/key/rotate` |

---

## Implementation: Windows VM (current target)

### Setting secrets

From an elevated PowerShell prompt:

```powershell
# Generate a strong JWT secret
$jwt = -join ((1..32) | ForEach-Object { '{0:x2}' -f (Get-Random -Max 256) })
[System.Environment]::SetEnvironmentVariable('JWT_SECRET', $jwt, 'Machine')
[System.Environment]::SetEnvironmentVariable('SEED_ADMIN_PASSWORD', 'your-strong-password', 'Machine')
[System.Environment]::SetEnvironmentVariable('ENV', 'production', 'Machine')

# Stripe (when ready)
[System.Environment]::SetEnvironmentVariable('STRIPE_SECRET_KEY', 'sk_live_...', 'Machine')
[System.Environment]::SetEnvironmentVariable('STRIPE_WEBHOOK_SECRET', 'whsec_...', 'Machine')
```

Restart the Detec service after setting variables so the process picks up the new environment.

### Verification

```powershell
# Confirm variables are set (without exposing values)
[System.Environment]::GetEnvironmentVariable('JWT_SECRET', 'Machine').Length
# Should return 64 (32 hex bytes)
```

### Security notes

- Never store secrets in `.env` files on production VMs. Use system-level environment variables.
- The `.env.example` files contain placeholder values only and are safe to commit.
- Windows system environment variables are readable by administrators and the SYSTEM account. Restrict RDP/SSH access to the VM.
- The production validator (`api/core/config.py`) rejects startup if `JWT_SECRET` or `SEED_ADMIN_PASSWORD` are set to known insecure defaults when `ENV=production`.

---

## Implementation: Docker

Secrets are stored in a `.env` file (gitignored) and referenced in `docker-compose.yml` via `${VAR:?error}` syntax:

```bash
cp .env.example .env
# Edit .env with real values
chmod 600 .env
```

For Docker Swarm or Kubernetes, use their native secrets mechanisms instead of `.env` files.

---

## Implementation: CI/CD (GitHub Actions)

Secrets for CI are stored in GitHub repository settings under Settings > Secrets and variables > Actions. Referenced in workflows as `${{ secrets.SECRET_NAME }}`. Never echo secrets in workflow logs.

Current CI secrets needed:
- `JWT_SECRET` (for API test runs)
- None of the Stripe/EDR secrets are needed in CI (tests use mocks)

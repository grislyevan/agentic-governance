# Incident Response Runbook

Procedures for responding to Detec operational incidents. For pilot-specific procedures, see [docs/pilot-runbook.md](pilot-runbook.md). For enforcement safety details, see [docs/enforcement-safety-matrix.md](enforcement-safety-matrix.md).

---

## Severity Classification

| Severity | Condition | Response time |
|----------|-----------|---------------|
| **P1 Critical** | Enforcement actively killing legitimate processes; data loss or production impact | Immediate |
| **P2 High** | API unreachable; agents cannot report; approval queue stalled | Within 30 minutes |
| **P3 Medium** | False positives generating alerts but not blocking work; dashboard degraded | Within 4 hours |
| **P4 Low** | Cosmetic dashboard issues; non-critical alerts; stale data | Next business day |

---

## P1: False Positive Enforcement (Agent Killing Legitimate Processes)

### Immediate response (< 5 minutes)

1. **Set all endpoints to passive posture** via the dashboard:
   - Navigate to Admin > Server Settings
   - Set Default Enforcement Posture to **Passive**
   - This stops all enforcement actions immediately — agents continue monitoring but take no blocking actions

2. **If dashboard is unreachable**, use the API directly:
   ```bash
   curl -X PATCH -H "Authorization: Bearer $TOKEN" \
     -H "Content-Type: application/json" \
     -d '{"default_enforcement_posture": "passive"}' \
     https://your-server/api/server-settings
   ```

3. **Identify the offending policy** from the audit log:
   ```bash
   curl -H "Authorization: Bearer $TOKEN" \
     "https://your-server/api/audit-log?action=enforcement&limit=20"
   ```

4. **Disable the specific policy**:
   ```bash
   curl -X PATCH -H "Authorization: Bearer $TOKEN" \
     -H "Content-Type: application/json" \
     -d '{"is_active": false}' \
     https://your-server/api/policies/<policy-id>
   ```

### Investigation

- Check the events page for the detection that triggered enforcement
- Review confidence scores — were they accurate or inflated?
- Check if the tool was recently updated (signature drift)
- Review the endpoint's telemetry provider (Native vs Polling — polling may miss context)

### Recovery

1. Fix or tune the offending policy
2. Re-enable enforcement on a single test endpoint first
3. Monitor for 1 hour before rolling back to active posture fleet-wide
4. Document the incident in the audit log

---

## P2: API Unreachable

### Diagnosis

```bash
# Check health endpoint
curl -s https://your-server/api/health | jq .

# Expected: {"status": "ok", "version": "...", "db": "ok"}
# Degraded: {"status": "degraded", "db": "unreachable"}
```

### Common causes and fixes

| Symptom | Cause | Fix |
|---------|-------|-----|
| Connection refused | API process crashed | Restart: `systemctl restart detec-server` or `docker compose restart api` |
| Health returns `degraded` | Database unreachable | Check PostgreSQL: `systemctl status postgresql` or `docker compose logs db` |
| HTTP 502 from Caddy | API not responding | Check API logs; restart API process |
| Gateway (8001) unreachable | Gateway crash or TLS cert issue | Check `GATEWAY_TLS_CERT` / `GATEWAY_TLS_KEY`; restart API |

### Log locations

| Deployment | Log location |
|------------|-------------|
| Docker | `docker compose logs api` |
| Bare metal (systemd) | `journalctl -u detec-server` |
| Windows | `C:\ProgramData\Detec\server.log` + Windows Event Log (Application, source "DetecServer") |

### Agent impact

When the API is unreachable, agents queue events locally in the EventStore ring buffer (10,000 events max). Events are delivered when connectivity resumes. No data is lost unless the buffer fills (at 60s scan interval, this is ~80 minutes of buffer).

---

## P2: Compromised API Key or JWT Secret

### API key compromised

1. **Identify the compromised key type** (user API key vs tenant agent key)

2. **User API key** — deactivate the user:
   ```bash
   curl -X PATCH -H "Authorization: Bearer $ADMIN_TOKEN" \
     -H "Content-Type: application/json" \
     -d '{"is_active": false}' \
     https://your-server/api/users/<user-id>
   ```

3. **Tenant agent key** — rotate immediately:
   ```bash
   curl -X POST -H "Authorization: Bearer $ADMIN_TOKEN" \
     https://your-server/api/tenants/agent-key/rotate
   ```
   Then reconfigure all agents with the new key. Agents using the old key will receive 401 errors and stop reporting until reconfigured.

4. **Review the audit log** for unauthorized activity:
   ```bash
   curl -H "Authorization: Bearer $ADMIN_TOKEN" \
     "https://your-server/api/audit-log?limit=100"
   ```

### JWT secret compromised

This is a critical security incident — all tokens are compromised.

1. **Generate a new secret**: `openssl rand -hex 32`
2. **Update the `JWT_SECRET` environment variable** on the server
3. **Restart the API** — all existing JWTs are immediately invalidated
4. **All users must re-authenticate** (existing sessions are terminated)
5. **Agent API keys are NOT affected** — they use hash-based auth, not JWT
6. Review audit log for unauthorized access during the exposure window

---

## P3: Approval Queue Stalled

If approvals are not appearing or SSE stream is disconnected:

1. Check the stream status badge on the Approvals page (Live / Polling / Connecting)
2. If stuck on "Connecting", check the API health and SSE endpoint:
   ```bash
   curl -N -H "Authorization: Bearer $TOKEN" \
     https://your-server/api/approvals/stream
   ```
3. If the API is healthy but SSE is not working, approvals fall back to 30-second polling automatically
4. Check for pending approvals directly:
   ```bash
   curl -H "Authorization: Bearer $TOKEN" \
     "https://your-server/api/approvals?status=pending"
   ```

---

## P3: False Positive Detections (Non-Blocking)

When the enforcer is in passive posture, false positives generate alerts but don't block work.

1. Review the detection on the Events page — check confidence score and signals
2. If the tool is legitimate, add it to the allow list:
   - Dashboard > Exceptions > Add Exception
   - Scope: per-endpoint or fleet-wide
   - Set an expiry date for temporary exceptions
3. If the scanner needs tuning, file an issue with the detection details (tool name, PID, confidence score, signals matched)

---

## Escalation contacts

| Role | Responsibility |
|------|---------------|
| On-call operator | First response, posture changes, policy toggles |
| Security admin | Policy review, allow-list governance, audit log analysis |
| Platform engineer | API/infrastructure issues, database recovery, TLS cert rotation |

*Update this table with your organization's contacts before deploying to production.*

---

*Related: [docs/pilot-runbook.md](pilot-runbook.md) | [docs/enforcement-safety-matrix.md](enforcement-safety-matrix.md) | [docs/rollback.md](rollback.md) | [docs/backup-restore.md](backup-restore.md)*

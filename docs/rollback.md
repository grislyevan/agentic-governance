# Rollback: Restore to Original State

After penetration testing or after running automated response playbooks, you can restore the system as follows.

## Playbook rollback

- **API**: `POST /api/playbooks/restore-defaults` (owner or admin).
- Removes all custom playbooks for the calling tenant. Built-in default playbooks remain available.
- The action is recorded in the audit log (`playbooks.restore_defaults`).

## Enforcement posture rollback

- Use the enforcement API to set posture back to a safe baseline:
  - **Endpoint posture**: `PUT /api/enforcement/endpoints/{endpoint_id}/posture` with `enforcement_posture: "passive"`.
  - **Tenant-wide posture**: `PUT /api/enforcement/tenant/posture` with `enforcement_posture: "passive"` (owner only).
- Audit log entries for posture changes use `enforcement.posture` or `posture.changed`; filter by these to see what was changed.

## Audit log

- To see what was reverted or changed: **Audit Log** in the dashboard, or `GET /api/audit-log?action=playbooks.restore_defaults` and `?action=playbook` for playbook responses.
- Filter by `resource_type=playbook` for playbook-related entries.

## Checklist

1. Stop or disable any custom playbooks: call `POST /api/playbooks/restore-defaults` if you want to remove all custom playbooks.
2. Restore enforcement posture to `passive` for affected endpoints or the tenant if it was changed during testing.
3. If tests wrote to a shared database, clear or isolate test data (tenants, users, events) as needed.
4. If the API or gateway config was changed for testing (e.g. rate limits, TLS), restart the service after reverting config.

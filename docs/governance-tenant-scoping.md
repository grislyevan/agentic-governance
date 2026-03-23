# Governance: Tenant scoping and cross-tenant visibility

**Status:** Accepted  
**Last updated:** Sprint 3 (Big-Ole Remediation Program)

## Intended behavior

- **Owner and admin:** Read-only cross-tenant visibility on list/count queries. They see data across all tenants. Mutations and get-by-id still require the resource to belong to the authenticated user's tenant or membership (no cross-tenant write or get-by-id from another tenant).
- **Analyst and viewer:** Scoped strictly to their own tenant. They cannot list, read, or modify resources in other tenants.
- **Agent (tenant API key):** Scoped to the tenant that owns the key; no cross-tenant access.

This behavior is implemented in `api/core/tenant.py` via `get_tenant_filter()` and `require_role()`. List/count queries use `get_tenant_filter(auth, model)`; owner/admin get `model.tenant_id.isnot(None)` (read-only cross-tenant). Mutations and get-by-id use explicit tenant checks (path parameter or resource ownership).

## Security / governance sign-off

Cross-tenant read for owner/admin is **intended product behavior** for platform operators and tenant admins who need a single pane of glass. It is read-only; no mutation or get-by-id is allowed across tenant boundaries without explicit tenant context. Analyst and viewer roles have no cross-tenant visibility. This design is accepted from a governance and security perspective for the current product scope.

## Automated tests

- `api/tests/test_tenant_isolation.py`: Owner cross-tenant visibility (endpoints, events, policies); analyst and viewer restricted to own tenant.
- `api/tests/test_enforcement_posture_rbac.py`: RBAC for enforcement endpoints.
- Additional RBAC/tenant-boundary tests in `api/tests/test_rbac_tenant_boundaries.py` (Sprint 3) cover owner/admin/analyst/viewer access matrix.

## Audit integrity observability

Audit log writes are fail-open (request continues if write fails). To make failures visible:

- **Metric:** `detec_audit_write_failures_total` (Prometheus counter) is incremented on each write failure in `api/core/audit_logger.py`. Scrape `/metrics` and alert when this counter increases.
- **Logs:** Failures are logged at WARNING with exc_info.
- An admin dashboard or report for audit write error rate can be added later; the metric is the source of truth.

## Future options

If product requirements change (e.g. strict single-tenant view for all roles), a feature flag or org setting can be added to scope owner/admin to a single tenant and applied in `get_tenant_filter()`.

# API Mutation Route Inventory (Tenant Guard Matrix)

Scope: write/delete/mutation routes for endpoints, enforcement, policies, users, webhooks, tenants, endpoint profiles, and events.

Legend:
- **Guard type** = role gate + tenant scoping strategy used in router implementation.
- **BOLA test** = covered by `api/tests/test_bola_mutation_matrix.py` cross-tenant mutation checks.

| Area | Method | Route | Guard type | BOLA test |
|---|---|---|---|---|
| endpoints | POST | `/api/endpoints` | `require_role(owner/admin/analyst?)` + tenant from auth context (`tenant_id` on create) | N/A (no foreign object id) |
| endpoints | PATCH | `/api/endpoints/{endpoint_id}` | `require_role(owner,admin)` + `strict_tenant_filter` | ✅ |
| endpoints | POST | `/api/endpoints/enroll` | `require_role(owner,admin)` + `Endpoint.tenant_id == auth.tenant_id` | N/A (hostname-scoped create/update) |
| enforcement | PUT | `/api/enforcement/endpoints/{endpoint_id}/posture` | `require_role(owner/admin)` (or owner-only for `active`) + `strict_tenant_filter` | ✅ |
| enforcement | PUT | `/api/enforcement/tenant-posture` | `require_role(owner)` + implicit current tenant update only | N/A (no foreign object id) |
| enforcement | POST | `/api/enforcement/allow-list` | `require_role(owner,admin)` + create with `tenant_id=auth.tenant_id` | N/A (no foreign object id) |
| enforcement | DELETE | `/api/enforcement/allow-list/{entry_id}` | `require_role(owner,admin)` + `AllowListEntry.tenant_id == auth.tenant_id` | (gap) |
| enforcement | POST | `/api/enforcement/restore-services` | `require_role(owner,admin)` + `strict_tenant_filter` on endpoint | (gap) |
| policies | POST | `/api/policies` | `require_role(owner,admin)` + create with `tenant_id=auth.tenant_id` | N/A (no foreign object id) |
| policies | POST | `/api/policies/from-event` | `require_role(owner,admin)` + event lookup `Event.tenant_id == auth.tenant_id` | (indirect) |
| policies | PATCH | `/api/policies/{policy_id}` | `require_role(owner,admin)` + `Policy.tenant_id == auth.tenant_id` | ✅ |
| policies | DELETE | `/api/policies/{policy_id}` | `require_role(owner,admin)` + `Policy.tenant_id == auth.tenant_id` | ✅ |
| policies | POST | `/api/policies/apply-preset` | `require_role(owner,admin)` + applies to `auth.tenant_id` | N/A (no foreign object id) |
| policies | POST | `/api/policies/restore-defaults` | `require_role(owner,admin)` + applies to `auth.tenant_id` | N/A (no foreign object id) |
| users | POST | `/api/users` | `require_role(owner,admin)` + create with `tenant_id=auth.tenant_id` | N/A (no foreign object id) |
| users | POST | `/api/users/me/api-key/rotate` | `require_role(owner,admin)` + user lookup in `auth.tenant_id` | N/A (self route) |
| users | PATCH | `/api/users/{user_id}` | `require_role(owner,admin)` + `User.tenant_id == auth.tenant_id` | ✅ |
| users | DELETE | `/api/users/{user_id}` | `require_role(owner)` + `User.tenant_id == auth.tenant_id` | ✅ |
| webhooks | POST | `/api/webhooks` | `require_role(owner,admin)` + create with `tenant_id=auth.tenant_id` | N/A (no foreign object id) |
| webhooks | POST | `/api/webhooks/from-template` | `require_role(owner,admin)` + create with `tenant_id=auth.tenant_id` | N/A (no foreign object id) |
| webhooks | PATCH | `/api/webhooks/{webhook_id}` | `require_role(owner,admin)` + `Webhook.tenant_id == auth.tenant_id` | ✅ |
| webhooks | DELETE | `/api/webhooks/{webhook_id}` | `require_role(owner,admin)` + `Webhook.tenant_id == auth.tenant_id` | ✅ |
| webhooks | POST | `/api/webhooks/{webhook_id}/test` | `require_role(owner,admin)` + `Webhook.tenant_id == auth.tenant_id` | (gap) |
| tenants | POST | `/api/tenants` | `require_role(owner,admin)` + explicit membership creation | N/A (new tenant) |
| tenants | PATCH | `/api/tenants/{tenant_id}` | membership check: caller must be owner in target tenant | ✅ |
| tenants | POST | `/api/tenants/switch` | membership check: caller must belong to target tenant | N/A (membership-bound action) |
| endpoint profiles | POST | `/api/endpoint-profiles` | `require_role(owner,admin)` + create with `tenant_id=auth.tenant_id` | N/A (no foreign object id) |
| endpoint profiles | PATCH | `/api/endpoint-profiles/{profile_id}` | `require_role(owner,admin)` + `EndpointProfile.tenant_id == auth.tenant_id` | ✅ |
| endpoint profiles | DELETE | `/api/endpoint-profiles/{profile_id}` | `require_role(owner,admin)` + `EndpointProfile.tenant_id == auth.tenant_id` | ✅ |
| events | POST | `/api/events` | tenant derived from auth/API key and persisted | N/A (ingest create) |
| events | POST | `/api/events/purge` | `require_role(owner)` + purge for `auth.tenant_id` | N/A (no foreign object id) |
| events | POST | `/api/events/{event_id}/block` | `require_role(owner,admin)` + `strict_tenant_filter` event lookup | ✅ closed (cross-tenant block-by-ID prevented; owner/admin receive 404 for foreign tenant event IDs) — fixed in commit `994608c9` |

## Notes
- “N/A” indicates no user-supplied foreign tenant object identifier is accepted; route mutates only the caller’s current tenant scope.
- “(gap)” indicates mutation route not yet directly asserted in cross-tenant object-id tests in this pass.

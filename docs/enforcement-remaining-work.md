# Enforcement Roadmap: Remaining Work

**Created:** 2026-03-12
**Reference:** [Enforcement Roadmap](enforcement-roadmap.md) (the architecture and design doc)
**Purpose:** Agent-actionable task list. Each task has scope, files, acceptance criteria, and dependencies. Pick a task and go.

---

## Implementation Status

The enforcement roadmap describes six phases of work spanning 19-27 weeks. A codebase audit on 2026-03-12 found that nearly all backend and agent code is implemented. The remaining work is concentrated in three areas: dashboard UI, one network-block stub, and hardening/testing gaps.

| Phase | Status | Remaining |
|-------|--------|-----------|
| Phase 1: Admin Posture | Backend complete, dashboard missing | **Tasks 1-5** |
| Phase 2: Behavioral Scanner | Complete | None |
| Phase 3: Enforcement Hardening | ~95% complete | **Task 6** |
| Phase 4: Webhook Orchestration | Complete | None |
| Phase 5: Native Telemetry | Code complete, untested in CI | **Task 7** |
| Phase 6: EDR Integration | Interfaces complete | **Task 8** (validation only) |
| Cross-cutting | Task 10 complete, 11c complete | **Tasks 9, 11a, 11b** |

**Total remaining effort estimate:** 2-3 weeks.

---

## Task 1: Posture API Client Functions

**Phase:** 1 (Admin Posture)
**Priority:** High (blocks Tasks 2-5)
**Effort:** 1-2 hours
**Assignee role:** Frontend Developer

The API routes exist in `api/routers/enforcement.py`. The dashboard API client (`dashboard/src/lib/api.js`) has EDR functions but no posture or allow-list functions.

### What to build

Add to `dashboard/src/lib/api.js`:

```javascript
// Posture
export async function fetchPostureSummary() { ... }
export async function updateEndpointPosture(endpointId, { posture, auto_enforce_threshold }) { ... }
export async function updateTenantPosture({ posture, auto_enforce_threshold }) { ... }

// Allow-list
export async function fetchAllowList() { ... }
export async function addAllowListEntry({ pattern, pattern_type, description }) { ... }
export async function deleteAllowListEntry(entryId) { ... }
```

### API routes to call

| Function | Method | Route |
|----------|--------|-------|
| `fetchPostureSummary` | GET | `/enforcement/posture-summary` |
| `updateEndpointPosture` | PUT | `/enforcement/endpoints/{id}/posture` |
| `updateTenantPosture` | PUT | `/enforcement/tenant-posture` |
| `fetchAllowList` | GET | `/enforcement/allow-list` |
| `addAllowListEntry` | POST | `/enforcement/allow-list` |
| `deleteAllowListEntry` | DELETE | `/enforcement/allow-list/{entry_id}` |

### Files to modify

- `dashboard/src/lib/api.js`

### Acceptance criteria

- [ ] All six functions exported and call the correct routes
- [ ] Functions follow the existing `apiFetch` / `apiMutate` patterns in the file
- [ ] Error handling matches existing EDR functions in the same file

---

## Task 2: Endpoint Posture Toggle

**Phase:** 1 (Admin Posture)
**Priority:** High
**Effort:** 3-5 hours
**Depends on:** Task 1
**Assignee role:** Frontend Developer

The `EndpointContextBar` component (`dashboard/src/components/dashboard/EndpointContextBar.jsx`) currently shows a `posture` badge (Conformant/Nonconformant) based on the `posture` column (managed/unmanaged). It does not display or control the `enforcement_posture` column (passive/audit/active).

### What to build

Add an enforcement posture control to the endpoint detail area. This can be a new component or an extension of `EndpointContextBar`.

**Requirements:**
- Display current `enforcement_posture` (passive, audit, active) as a labeled badge.
- Display current `auto_enforce_threshold` value.
- Provide a selector to change posture (three states: Passive, Audit, Active).
- Provide a threshold slider (range 0.50 to 1.00, step 0.05) visible when posture is audit or active.
- Switching TO active requires a confirmation modal:
  - Shows the endpoint hostname.
  - Shows the current threshold value.
  - Requires the user to type the hostname to confirm (destructive action pattern).
  - Explains that active mode enables autonomous process termination.
- On confirm, calls `updateEndpointPosture(endpointId, { posture, auto_enforce_threshold })`.
- Success/error feedback via toast or inline message.

**UX context:** The existing `posture` badge (Conformant/Nonconformant) and the new `enforcement_posture` control are different things. `posture` is the management state. `enforcement_posture` is whether the agent acts on block decisions. Both should be visible, clearly labeled, and not confused with each other.

### Files to create or modify

- `dashboard/src/components/dashboard/EndpointContextBar.jsx` (extend) or create `dashboard/src/components/enforcement/PostureControl.jsx`

### Acceptance criteria

- [ ] Admin can switch an endpoint to active posture entirely from the dashboard
- [ ] Passive-to-active transition requires confirmation dialog with hostname entry
- [ ] Threshold is editable and transmitted with the posture change
- [ ] API errors surface in the UI
- [ ] Posture change appears in the audit log (server-side, already wired; verify it shows on `AuditLogPage`)

---

## Task 3: Tenant Default Posture Setting

**Phase:** 1 (Admin Posture)
**Priority:** Medium
**Effort:** 2-3 hours
**Depends on:** Task 1
**Assignee role:** Frontend Developer

The `SettingsPage` (`dashboard/src/pages/SettingsPage.jsx`) has webhook configuration but no tenant-level enforcement settings.

### What to build

Add a section to `SettingsPage` (or a new tab within it) for enforcement defaults:

- **Default posture selector** (Passive / Audit / Active) for new endpoints in the tenant.
- **Default threshold** slider (0.50 to 1.00).
- Active requires the same confirmation treatment as Task 2.
- "Apply to all existing endpoints" checkbox (calls `updateTenantPosture` which updates all endpoints in the tenant).
- Save button calls `updateTenantPosture()`.

### Files to modify

- `dashboard/src/pages/SettingsPage.jsx`

### Acceptance criteria

- [ ] Owner can set tenant default posture
- [ ] "Apply to all" updates existing endpoints (confirmed in endpoint list after save)
- [ ] Active requires confirmation dialog

---

## Task 4: Allow-List Management UI

**Phase:** 1 (Admin Posture)
**Priority:** Medium
**Effort:** 3-5 hours
**Depends on:** Task 1
**Assignee role:** Frontend Developer

No UI exists for the allow-list. The API supports CRUD. The `AuditLogPage` already renders `enforcement.allow_list_added` / `enforcement.allow_list_removed` events, so audit trail is handled.

### What to build

A section in `SettingsPage` or a standalone page/panel:

- **Table** of current allow-list entries: pattern, type (name/path/hash), description, created by, created at.
- **Add entry form**: pattern (text input), type (dropdown: Name / Path / Hash), description (optional text).
- **Delete** button per row, with confirmation.
- Empty state message when no entries exist.

### Files to create or modify

- `dashboard/src/pages/SettingsPage.jsx` (add section) or create `dashboard/src/components/enforcement/AllowListPanel.jsx`

### Acceptance criteria

- [ ] Admin can add an allow-list entry from the UI
- [ ] Admin can delete an allow-list entry from the UI
- [ ] Table refreshes after add/delete
- [ ] Pattern type selector works correctly (name, path, hash)

---

## Task 5: Posture Summary Dashboard Widget

**Phase:** 1 (Admin Posture)
**Priority:** Low
**Effort:** 2-3 hours
**Depends on:** Task 1
**Assignee role:** Frontend Developer

The `DashboardPage` (`dashboard/src/pages/DashboardPage.jsx`) has endpoint counts and tool detection summaries. It does not show posture distribution.

### What to build

A widget (card or small chart) showing:

- Count of endpoints in each posture: passive, audit, active.
- Visual breakdown (bar, donut, or three stat cards).
- Optional: "Set All Passive" emergency button (calls `updateTenantPosture({ posture: 'passive' })` with confirmation). This is the dashboard-level kill switch described in the roadmap's "Operational Safety" section.

### Files to modify

- `dashboard/src/pages/DashboardPage.jsx`

### Acceptance criteria

- [ ] Posture distribution is visible on the main dashboard
- [ ] Data comes from `GET /enforcement/posture-summary`
- [ ] Kill switch button (if included) requires confirmation and works

---

## Task 6: Linux cgroup v2 Network Blocking

**Phase:** 3 (Enforcement Hardening)
**Priority:** Medium
**Effort:** 1-2 days
**Assignee role:** Senior Developer or Platform Engineer

`collector/enforcement/network_block.py` has `_cgroup_v2_block()` at line 60, which is stubbed to always return `False` with "not yet implemented." The UID-owner iptables fallback works but blocks all processes for a UID, which is a blast-radius problem.

### What to build

Implement `_cgroup_v2_block(pid)`:

1. Check `/sys/fs/cgroup/cgroup.controllers` for `net_cls` support (the check function `_has_cgroup_v2()` already exists at line 56).
2. Create a cgroup for the target PID: `/sys/fs/cgroup/detec-block-{pid}/`.
3. Write the PID into `cgroup.procs`.
4. Assign a `net_cls.classid` to the cgroup.
5. Add an iptables rule matching the classid: `iptables -A OUTPUT -m cgroup --cgroup {classid} -j DROP`.
6. Return `True` on success.

Also implement cleanup in `collector/enforcement/cleanup.py`:
- On startup, remove stale `detec-block-*` cgroups and their associated iptables rules.

### Files to modify

- `collector/enforcement/network_block.py` (implement `_cgroup_v2_block`)
- `collector/enforcement/cleanup.py` (add cgroup cleanup)

### Acceptance criteria

- [ ] On Linux with cgroup v2 + net_cls, network block scopes to the target process only
- [ ] On Linux without cgroup v2, UID-owner fallback is used with a warning log
- [ ] `cleanup_orphaned_rules()` removes stale cgroup-based rules on agent startup
- [ ] Unit tests cover both cgroup path and fallback path

### Reference

Roadmap Phase 3, Section 3.4 ("Network Block Improvements").

---

## Task 7: Native Telemetry CI Pipeline

**Phase:** 5 (Native Telemetry)
**Priority:** Medium (blocks production deployment of native providers)
**Effort:** 2-3 days
**Assignee role:** DevOps / Infrastructure

The three native providers (`esf_provider.py`, `etw_provider.py`, `ebpf_provider.py`) exist in code. The ESF helper binary (`collector/providers/esf_helper/esf_helper.m`) has source and a Makefile. None of this is tested in CI and the ESF helper has no build/signing pipeline.

### Subtasks

**7a. Mock-based unit tests per provider**
- Each provider's `available()` can be tested with mocked platform detection.
- ESF: mock the Unix domain socket read/write.
- ETW: mock the `StartTrace`/`ProcessTrace` calls.
- eBPF: mock the BCC bindings.
- Run these on the standard CI runner (no platform privileges needed).

**7b. CI platform matrix (future)**
- macOS runner for ESF tests (mocked; real ESF requires System Extension approval).
- Windows runner for ETW tests (mocked; real ETW requires admin).
- Linux runner for eBPF tests (mocked; real eBPF requires `CAP_BPF`).

**7c. ESF helper build pipeline**
- CI step to compile `esf_helper.m` with `clang` on macOS.
- Code sign with Developer ID (requires Apple signing credentials in CI secrets).
- Bundle into the macOS .app/.pkg in `packaging/macos/`.

**7d. Telemetry mode in heartbeat**
- Add `telemetry_provider` field to heartbeat payload so the server knows which provider each endpoint is using.
- Display provider type (Native/Polling) per endpoint in the dashboard.

### Files to create or modify

- `collector/tests/test_esf_provider.py` (create)
- `collector/tests/test_etw_provider.py` (create)
- `collector/tests/test_ebpf_provider.py` (create)
- CI config (`.github/workflows/` or equivalent)
- `packaging/macos/` (ESF helper bundling)

### Acceptance criteria

- [ ] Mock-based provider tests run in CI on every push
- [ ] ESF helper compiles in CI on macOS runner
- [ ] Heartbeat includes `telemetry_provider` field

---

## Task 8: EDR Integration Validation

**Phase:** 6 (EDR Integration)
**Priority:** Low
**Effort:** 1-2 days (dependent on CrowdStrike sandbox access)
**Assignee role:** Security Engineer / Backend Architect

The `EnforcementProvider` interface, `enforcement_router.py` orchestration, and CrowdStrike RTR methods all exist. They have not been validated against a live or sandbox CrowdStrike environment.

### Subtasks

**8a. CrowdStrike sandbox test**
- If sandbox API access is available: run `initiate_rtr_session`, `rtr_kill_process`, `close_rtr_session` against a test host.
- Verify token refresh, session lifecycle, and error handling.
- Document latency (session init + kill command round-trip).

**8b. Fallback path test**
- Simulate CrowdStrike unreachable (timeout/connection refused).
- Verify `enforcement_router` falls back to local agent enforcement.
- Verify `enforcement.failed` event is emitted with the correct detail.

**8c. Credential storage review**
- Verify CrowdStrike API credentials are not stored in config files or `.env` on disk.
- Document the intended production credential flow (Vault, AWS Secrets Manager, etc.).

### Acceptance criteria

- [ ] At least one successful RTR session test (sandbox or mock)
- [ ] Fallback path produces `enforcement.failed` event
- [ ] Credential storage approach is documented

---

## Task 9: Cross-Phase End-to-End Test

**Priority:** Medium
**Effort:** 1-2 days
**Assignee role:** Senior Developer

No single test exercises the full detection-to-enforcement-to-audit path. Each phase was tested in isolation.

### Test scenario

1. Seed an `EventStore` with synthetic process/network/file events matching BEH-001 + BEH-002 (shell fan-out + LLM API calls).
2. Run `BehavioralScanner` against the store. Assert detection with confidence >= 0.65.
3. Run `evaluate_policy()` against the scan result. Assert `block` decision.
4. Set `PostureManager` to `active` with threshold 0.60.
5. Call `Enforcer.enforce()` in dry-run mode. Assert `enforcement.simulated` event emitted.
6. Set `PostureManager` to `active` (real). Call `Enforcer.enforce()` with mocked `psutil.Process`. Assert kill attempted.
7. Assert enforcement event payload matches `canonical-event-schema.json` enforcement schema.
8. Assert webhook dispatcher would fire for the event type.

### Files to create

- `collector/tests/test_enforcement_e2e.py`

### Acceptance criteria

- [ ] Single test file exercises behavioral detection through enforcement through event emission
- [ ] Runs in CI without root/admin privileges (uses mocks for kill/network block)
- [ ] Validates event schema compliance

---

## Task 10: Resolve `posture` vs `enforcement_posture` Columns ✅

**Status:** Complete (2026-03-12)
**Decision:** Option A (orthogonal columns).

**What was done:**
- Renamed `posture` column to `management_state` in `api/models/endpoint.py`.
- Alembic migration `0008_rename_posture_to_management_state.py` renames the column, preserving data.
- All ORM code updated (`api/routers/endpoints.py`, `api/routers/events.py`, `api/schemas/endpoints.py`). Ingestion has backward-compat fallback for old collectors that send `posture` in event payloads.
- `EndpointContextBar.jsx` reads `management_state`.
- Docstring on `Endpoint` model documents the distinction.
- `endpoint.posture` in the canonical event schema is kept as the wire-format field name for stability; the mapping to `management_state` happens at ingestion.

### Acceptance criteria

- [x] The relationship between the two columns is documented in code
- [x] Dashboard displays both concepts without confusion
- [x] Decision is noted in the enforcement roadmap

---

## Task 11: Security Hardening Items

**Priority:** Medium
**Effort:** 1-2 days across subtasks
**Assignee role:** Security Engineer

Three security concerns from the engineering review that need decisions or fixes.

### 11a. Allow-list delivery timing for HTTP-only agents

**Problem:** HTTP-only agents poll every 300s. If an admin adds an allow-list entry, the agent won't receive it for up to 5 minutes. During that window, the agent could enforce against the newly-exempted tool.

**Options:**
1. Accept the risk (5 minutes is short; most enforcement is on active infrastructure with TCP).
2. Add allow-list version to posture state. Agent skips enforcement if its allow-list version is stale by more than N seconds.
3. Shorten the default HTTP heartbeat interval for active-posture endpoints.

**Decision needed.** Document in the roadmap.

### 11b. Anti-resurrection service recovery

**Problem:** `enforcer.py` escalates repeated kills by disabling systemd units or launchd plists. This is a boot-surviving change with no built-in recovery path.

**Fix:**
- Track disabled units in `collector/agent/state.py` (the `EnforcementRuleTracker` already tracks active rules).
- Add `POST /api/enforcement/restore-services` endpoint that pushes a restore command to the agent.
- Agent re-enables the unit on receiving the command.
- Dashboard shows disabled services with a restore button.

### 11c. RBAC for active posture ✅

**Status:** Complete (2026-03-12)
**Decision:** Yes, restrict to owner only.

`api/routers/enforcement.py` `set_endpoint_posture` now checks: `active` requires `owner` role; `passive`/`audit` allows `owner` or `admin`. Tenant-wide posture (`set_tenant_posture`) already required `owner`.

### Acceptance criteria

- [ ] Each item has an explicit decision documented
- [ ] Implemented fixes have tests
- [ ] Decisions are reflected in the enforcement roadmap's "Cross-Cutting Concerns" section

---

## Dependency Graph

```
Task 1 (API client)
  ├── Task 2 (posture toggle)
  ├── Task 3 (tenant posture)
  ├── Task 4 (allow-list UI)
  └── Task 5 (posture summary widget)

Task 6 (cgroup v2) ── standalone
Task 7 (CI pipeline) ── standalone
Task 8 (EDR validation) ── standalone
Task 9 (E2E test) ── standalone (but best done after Tasks 1-6)
Task 10 (column resolution) ── ✅ complete
Task 11 (security) ── 11c ✅ complete; 11a, 11b standalone
```

### Recommended order

1. ~~**Task 10** (column decision, 1 hour). Unblocks clear dashboard design.~~ ✅ Done.
2. **Task 1** (API client, 1-2 hours). Unblocks all dashboard tasks.
3. **Tasks 2 + 4** in parallel (posture toggle + allow-list, each 3-5 hours).
4. **Task 3** (tenant posture, 2-3 hours).
5. **Task 5** (summary widget, 2-3 hours).
6. **Tasks 6, 7, 9, 11** can run in parallel with dashboard work.
7. **Task 8** when CrowdStrike sandbox access is available.

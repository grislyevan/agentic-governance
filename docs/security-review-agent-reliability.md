# Security and Engineering Review: Agent Reliability and Admin Control

**Document version:** 1.0  
**Date:** 2025-03-13  
**Scope:** Post-implementation review of the Agent Reliability and Admin Control plan (Phase 1 packaging/persistence, Phase 2 tamper controls, Phase 3 endpoint profiles). Combined Dev-Eng, Security Engineer, and CISO perspective.

---

## Executive summary

Implementation is **sound from a security and architecture standpoint**. Tenant isolation, auth, and input validation are consistently applied to new surfaces. Three issues were identified and addressed in this review: TCP gateway did not return profile-derived `interval_seconds` (consistency with HTTP heartbeat), endpoint profile schema allowed arbitrary `enforcement_posture` values, and macOS uninstall did not explicitly require root when LaunchDaemon is present. Remediations are in place. Manual validation (Phase 1.1.4, 1.2.4) and optional tamper event (2.1.4) remain pending.

---

## 1. Threat model snapshot (new surface)

| Boundary | Component | Trust | Notes |
|----------|-----------|--------|-------|
| User/Admin → API | Endpoint profiles CRUD, PATCH endpoint (profile assign) | JWT or API key; owner/admin for mutations | Same auth as existing routers. |
| Agent → API | Heartbeat (HTTP + TCP) | API key (tenant-scoped) | Profile-derived config returned; agent applies interval/posture. |
| Installer → OS | macOS pkg (postinstall), Windows (Inno + set-recovery) | Runs as root (pkg) or elevated (Inno) | LaunchDaemon and service recovery extend persistence. |
| Uninstall | macOS uninstall.sh, Windows Add/Remove | Root/sudo or admin | Tamper policy: uninstall restricted; root check added for LaunchDaemon. |

**STRIDE (new/updated):**

| Threat | Component | Risk | Mitigation |
|--------|-----------|------|------------|
| Spoofing | Profile assignment | Low | `resolve_auth` + `get_tenant_filter`; PATCH endpoint and profile ID checked against tenant. |
| Tampering | Profile config (interval, posture) | Low | Pydantic validation (interval 30–86400, posture enum); audit log for create/update/delete. |
| Repudiation | Profile and endpoint changes | Low | Audit log: endpoint_profile.created/updated/deleted, endpoint updates. |
| Info disclosure | Profile list/detail | Low | Tenant-scoped queries only; no cross-tenant leakage. |
| DoS | Profile CRUD, heartbeat | Low | Rate limits (20/min) on create/update/delete; heartbeat 60/min. |
| Elevation | Assign profile to endpoint in other tenant | Low | Endpoint and profile both filtered by auth tenant; 404 if profile not in tenant. |

---

## 2. Security findings (post-remediation)

| ID | Title | Severity | Component | Remediation | Status |
|----|--------|----------|-----------|-------------|--------|
| R-001 | TCP gateway did not return profile interval | Medium | Gateway | Gateway now loads endpoint with `endpoint_profile`, returns `interval_seconds` and uses it for `next_expected_in` in HEARTBEAT_ACK when profile is set. | Fixed |
| R-002 | Endpoint profile posture not validated | Low | API schemas | `enforcement_posture` in Create/Update/Config now has `pattern="^(passive\|audit\|active)$"` to match enforcement router. | Fixed |
| R-003 | macOS uninstall without root when LaunchDaemon present | Low | Tamper | uninstall.sh now checks: if LaunchDaemon plist exists and effective uid is not 0, exit with message pointing to docs/tamper-controls.md. | Fixed |

**Positive observations:**

- Endpoint profile CRUD and PATCH endpoint use `resolve_auth`, `get_tenant_filter`, and `require_role`; no IDOR on profile or endpoint.
- Heartbeat (HTTP) and gateway (TCP) do not expose secrets; agent state file (`~/.agentic-gov/agent_state.json`) holds only `interval_seconds` (non-secret).
- Tamper policy doc clearly scopes to uninstall and defers stop/kill to OS (SCM, launchd).
- LaunchDaemon runs as root with config under `/Library/Application Support/Detec`; no sensitive data in plist.
- Windows failure recovery uses standard `ChangeServiceConfig2`; no new privilege escalation path.

---

## 3. CISO governance layer mapping

| Control | Implementation | Coverage |
|---------|----------------|----------|
| **SOC 2 CC6.1** (Logical access) | Profile CRUD and endpoint assignment restricted to owner/admin; audit log for profile and endpoint changes. | Profile and assignment changes are access-controlled and auditable. |
| **SOC 2 CC7.2** (Monitoring) | Heartbeat and profile-derived interval; agents report and receive config; LaunchDaemon/service persistence. | Fleet monitoring and config push aligned with persistence. |
| **NIST CSF ID.AM** (Asset management) | Endpoint profiles as logical grouping (e.g. Critical Server vs Standard Workstation); assignment visible in dashboard. | Asset grouping supports policy-by-profile. |
| **Proportional enforcement** | Profile stores `enforcement_posture` and `auto_enforce_threshold`; agents receive and apply them. | Different profiles can enforce different postures/thresholds. |

**Known limits (unchanged):**

- Container/remote dev: host-level telemetry still limited.
- Tamper event (2.1.4) is documented as future work; no server-side tamper signal yet.

---

## 4. Cross-cutting checklist (Dev-Eng)

| Concern | Status | Notes |
|---------|--------|-------|
| **Security** | OK | Auth and tenant isolation on all new endpoints; posture enum validated; tamper doc and root check in place. |
| **Performance** | OK | Profile loaded with `joinedload` in gateway; no N+1. List profiles paginated (default 50, max 200). |
| **Reliability** | OK | Gateway heartbeat failure path unchanged; state file write is best-effort (agent continues if write fails). |
| **Operability** | OK | Audit log and existing logging; profile CRUD and assignment visible in dashboard. |
| **Testability** | OK | Existing API and collector tests; profile and heartbeat behavior covered. Add gateway unit test for profile interval in HEARTBEAT_ACK if desired. |

---

## 5. Recommendations

1. **Manual QA:** Complete Phase 1.1.4 (clean macOS install, reboot, heartbeats) and 1.2.4 (clean Windows install, reboot, service and heartbeats) and record results in the install-failure-notes docs.
2. **Gateway test:** Add a test that, for an endpoint with a profile, HEARTBEAT_ACK payload includes `interval_seconds` and `next_expected_in` matches profile interval.
3. **Tamper event (backlog):** When implementing 2.1.4, define a dedicated event type and dashboard alert; avoid overloading existing event schema.
4. **Dashboard:** Ensure endpoint list and profile assignment flows are available only to owner/admin (already gated by `canManage` in the implementation).

---

## 6. References

- [docs/tamper-controls.md](tamper-controls.md) – Tamper policy and Windows/macOS behavior.
- [docs/security-findings.md](security-findings.md) – Existing findings (F-001–F-014).
- [docs/hardening-checklist.md](hardening-checklist.md) – Security headers, errors, secrets.
- [.cursor/plans/agent_reliability_admin_control.plan.md](../.cursor/plans/agent_reliability_admin_control.plan.md) – Plan and success criteria.

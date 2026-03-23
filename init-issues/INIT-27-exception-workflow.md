# INIT-27 — Exception Workflow (Full Deep Revision)

## Scope
Issue: **INIT-27**
Objective: define a secure, auditable, and abuse-resistant exception workflow for AI governance controls that enables limited operational flexibility without collapsing policy integrity.

This workflow governs temporary deviations from baseline policy in a way that is:
- explicit,
- bounded,
- reviewable,
- revocable,
- and forensically traceable.

---

## 1) Why Exception Workflow Is Critical
In real enterprise environments, strict policy-only systems fail adoption if they cannot accommodate legitimate edge cases.

But poorly designed exceptions become the primary attack path:
- overbroad scope,
- no expiry,
- weak approver controls,
- undocumented rationale,
- no revalidation.

The goal is to allow exceptions as controlled risk instruments, not policy bypasses.

---

## 2) Exception Object Model (Canonical)
Each exception record must include:

### Identity & Ownership
- `exception_id`
- `requester_id`
- `approver_id`
- `owner_team`

### Scope
- `tool_class` (A/B/C)
- `actions_allowed` (normalized action classes)
- `target_scope` (repo/path/host/destination)
- `environment_scope` (prod/non-prod/dev only)

### Time Bounds
- `created_at`
- `effective_from`
- `expires_at`
- `max_duration_policy`

### Justification & Risk
- `business_justification`
- `risk_assessment`
- `compensating_controls`
- `residual_risk_statement`

### Governance Linkage
- `linked_policy_rule_ids[]`
- `approval_ticket_id`
- `change_request_id` (if applicable)

### State
- `status` (pending/active/expired/revoked/rejected)
- `revoked_by` (nullable)
- `revocation_reason` (nullable)

### Audit
- `created_event_id`
- `approved_event_id`
- `activation_event_id`
- `revocation_event_id` (nullable)

---

## 3) Exception Lifecycle States

### 1) Draft/Pending
- requester submits scoped request,
- automated prechecks validate completeness,
- no enforcement bypass granted yet.

### 2) Review
- approver/risk owner evaluates necessity and blast radius,
- system computes policy diff (baseline vs exception behavior).

### 3) Active
- exception token generated with strict scope + expiry,
- enforcement engine references token for matching actions only.

### 4) Expired
- automatic deactivation at `expires_at`,
- fallback to baseline policy,
- optional post-expiry summary generated.

### 5) Revoked
- immediate deactivation (manual or automatic trigger),
- revocation reason mandatory,
- high-priority event emitted for SOC visibility.

### 6) Rejected
- request denied with reason,
- no policy bypass allowed.

---

## 4) Approval Model and Separation of Duties

### Approval tiers
- Low-risk scope: single approver (team lead/security delegate)
- Medium-risk scope: security + service owner review
- High-risk scope (Class C / privileged actions / sensitive assets): dual approval required

### Separation of duties rules
- requester cannot self-approve,
- approver must have policy authority for target scope,
- high-risk exceptions require independent reviewer.

### Mandatory checks before approval
- policy alternatives exhausted,
- scope is minimal and specific,
- expiry is as short as practical,
- compensating controls are active and verifiable.

---

## 5) Scope Constraints (Anti-Abuse)
Exceptions must be narrow by default:
- no wildcard global action exceptions for Class C,
- no open-ended destination/path scopes,
- no infinite duration,
- no transitive inheritance to other repos/hosts/environments.

Scope dimensions to constrain explicitly:
1. action type(s)
2. target paths/repos/destinations
3. actor(s)
4. environment(s)
5. time window

---

## 6) Runtime Enforcement Semantics
At enforcement time:
1. baseline policy evaluates first,
2. exception lookup checks exact-scope match,
3. if matched and valid, decision can downgrade from Block/Approval to allowed action per exception policy,
4. if unmatched/expired, baseline decision applies.

Required runtime checks:
- token validity,
- scope exactness,
- actor match,
- expiration,
- revocation status.

Every exception-mediated allow action must emit:
- `exception_id`,
- matched scope attributes,
- decision reason code,
- evidence references.

---

## 7) Expiry, Renewal, and Reapproval

### Expiry defaults
- short durations by default (hours/days, not months) for high-risk classes.

### Renewal rules
- no silent auto-renewal for high-risk exceptions,
- renewals require fresh justification and current risk context,
- repeated renewals trigger governance review.

### Reapproval triggers
- policy changes,
- scope expansion request,
- change in endpoint trust posture,
- repeated exception-mediated risky actions.

---

## 8) Monitoring and Alerting
Generate alerts for:
- soon-to-expire active exceptions,
- high-risk exceptions created outside standard windows,
- exception usage spikes,
- repeated denied actions followed by exception requests,
- stale exceptions with no recent usage.

Operational dashboards should show:
- active exceptions by class,
- age distribution,
- usage frequency,
- upcoming expirations,
- revocation trends.

---

## 9) Failure Modes and Safeguards

### Failure Mode 1: Exception sprawl
Safeguard:
- periodic recertification,
- stale exception cleanup automation,
- hard cap on concurrent high-risk exceptions per scope.

### Failure Mode 2: Overbroad approvals
Safeguard:
- scope linting and policy diff checks,
- deny approvals with wildcard or unrestricted targets in high-risk classes.

### Failure Mode 3: Hidden policy bypass
Safeguard:
- mandatory exception linkage in every affected audit event,
- exception usage reports in regular governance reviews.

### Failure Mode 4: Approval fatigue / rubber-stamping
Safeguard:
- tiered approval with workload distribution,
- anomaly detection on approver behavior,
- random quality audits of approved exceptions.

---

## 10) Data and Audit Requirements
Minimum audit fields for exception events:
- exception lifecycle event type,
- actor/requester/approver IDs,
- scope details,
- policy baseline decision vs exception-adjusted decision,
- rule IDs,
- evidence linkage,
- timestamp chain.

Compliance posture depends on ability to reconstruct:
- why exception was granted,
- exactly what actions it allowed,
- whether usage stayed in scope,
- when and why it ended.

---

## 11) Validation Plan

### Functional tests
1. create/approve/activate/expire lifecycle correctness.
2. scope-matched allow behavior only.
3. out-of-scope action remains blocked.

### Security tests
1. self-approval attempts rejected.
2. expired exception token usage denied.
3. revoked exception cannot be reused.

### Governance tests
1. renewal without justification blocked.
2. high-risk class requires dual approval.
3. reporting accurately reflects active/expired/revoked states.

Required outputs:
- lifecycle conformance report,
- scope-leak test results,
- exception usage audit samples,
- residual risk summary.

---

## 12) Buyer-Credibility Statement
"Our exception workflow is tightly scoped, time-bound, and fully auditable. Exceptions provide controlled flexibility without creating silent policy bypasses, and every exception-mediated action remains traceable to owner, rationale, and evidence."

---

## 13) Acceptance Checklist
- [x] Exception object model and lifecycle defined.
- [x] Approval/separation-of-duties model documented.
- [x] Scope constraints and runtime semantics specified.
- [x] Expiry/renewal/reapproval rules defined.
- [x] Failure modes and safeguards documented.
- [x] Validation and audit requirements specified.
- [ ] Empirical lifecycle replay evidence attached.

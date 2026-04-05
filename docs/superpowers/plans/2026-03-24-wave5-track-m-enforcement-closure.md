# Wave 5 Track M — Enforcement Closure Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Close the approval_required enforcement loop so held actions are truly blocked pending an analyst decision, and implement PATCH allow-list editing.

**Architecture:** The collector currently calls `enforcer.enforce()` immediately for `approval_required` decisions. This plan: (1) adds a hold manager in the collector that posts an ApprovalRequest and polls for a decision before enforcing; (2) adds `PATCH /enforcement/allow-list/:id` on the backend; (3) wires the ExceptionsPage drawer to use PATCH for edits; (4) polishes the pending queue UI with SLA timers.

**Tech Stack:** FastAPI + SQLAlchemy (backend), Python (collector), React + Vitest (dashboard), pytest (API tests)

---

## File Map

### New files
- `collector/enforcement/approval_hold.py` — Hold state manager: posts ApprovalRequest, polls for decision, respects timeout config
- `collector/tests/test_approval_hold.py` — Unit tests for approval_hold
- `api/tests/test_enforcement_allow_list_patch.py` — API tests for PATCH endpoint

### Modified files
- `collector/orchestrator.py:658` — Skip immediate enforcement for `approval_required`; call hold manager instead
- `collector/config/collector.example.json` — Add `approval_hold` config block
- `api/routers/enforcement.py` — Add `PATCH /enforcement/allow-list/:id` endpoint + `AllowListPatch` schema
- `api/routers/approvals.py` — Add `event_id` query param filter to `list_approvals`
- `dashboard/src/lib/api.js` — Implement `updateAllowListEntry(id, data)` → PATCH
- `dashboard/src/pages/ExceptionsPage.jsx` — Use PATCH in drawer submit for edit mode (not POST)
- `dashboard/src/pages/ApprovalsPage.jsx` — Add age/SLA display; sort pending by oldest first; status badge in detail drawer

---

## Task 1: Collector — approval_hold module

**Files:**
- Create: `collector/enforcement/approval_hold.py`
- Create: `collector/tests/test_approval_hold.py`

- [ ] **Step 1.1: Write failing tests**

```python
# collector/tests/test_approval_hold.py
from unittest.mock import MagicMock, patch
import pytest
from enforcement.approval_hold import ApprovalHoldManager, HoldConfig, HoldResult


def test_hold_config_defaults():
    cfg = HoldConfig()
    assert cfg.poll_interval_seconds == 10
    assert cfg.timeout_seconds == 300
    assert cfg.timeout_behavior == "deny"
    assert cfg.offline_behavior == "deny"


def test_hold_result_approved():
    result = HoldResult(decision="approved", approval_id="abc")
    assert result.decision == "approved"
    assert not result.timed_out


def test_hold_result_timed_out():
    result = HoldResult(decision="denied", approval_id=None, timed_out=True)
    assert result.timed_out


def test_hold_config_from_dict():
    cfg = HoldConfig.from_dict({
        "poll_interval_seconds": 5,
        "timeout_seconds": 60,
        "timeout_behavior": "approve",
        "offline_behavior": "deny",
    })
    assert cfg.poll_interval_seconds == 5
    assert cfg.timeout_seconds == 60
    assert cfg.timeout_behavior == "approve"


def test_manager_offline_returns_deny_when_create_fails():
    """When POST /approvals fails (offline), offline_behavior=deny returns denied."""
    config = HoldConfig(offline_behavior="deny")
    manager = ApprovalHoldManager(api_url="http://localhost:8000/api", api_key="k", config=config)

    with patch.object(manager, "_create_approval_request", side_effect=Exception("conn refused")):
        result = manager.wait_for_decision(
            event_id="evt-1", tool_name="cursor", tool_class="B",
            confidence_band="medium", confidence_score=0.6, policy_rule_id="RULE-3",
        )

    assert result.decision == "denied"
    assert result.timed_out is False


def test_manager_returns_approved_after_polling():
    """When server returns approved on second poll, decision is approved."""
    config = HoldConfig(poll_interval_seconds=0, timeout_seconds=10)
    manager = ApprovalHoldManager(api_url="http://localhost:8000/api", api_key="k", config=config)

    call_count = 0
    def _fake_poll(approval_id):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return "pending"
        return "approved"

    with patch.object(manager, "_create_approval_request", return_value="ar-99"), \
         patch.object(manager, "_poll_decision", side_effect=_fake_poll), \
         patch("enforcement.approval_hold.time.sleep"):
        result = manager.wait_for_decision(
            event_id="evt-2", tool_name="claude_code", tool_class="D",
            confidence_band="high", confidence_score=0.9, policy_rule_id="D01",
        )

    assert result.decision == "approved"
    assert result.approval_id == "ar-99"
    assert call_count == 2


def test_manager_timeout_returns_configured_behavior():
    """Timeout returns timeout_behavior decision."""
    config = HoldConfig(poll_interval_seconds=0, timeout_seconds=0, timeout_behavior="deny")
    manager = ApprovalHoldManager(api_url="http://localhost:8000/api", api_key="k", config=config)

    with patch.object(manager, "_create_approval_request", return_value="ar-1"), \
         patch.object(manager, "_poll_decision", return_value="pending"), \
         patch("enforcement.approval_hold.time.sleep"):
        result = manager.wait_for_decision(
            event_id="evt-3", tool_name="x", tool_class="A",
            confidence_band="low", confidence_score=0.3, policy_rule_id="RULE-1",
        )

    assert result.decision == "denied"
    assert result.timed_out is True
```

- [ ] **Step 1.2: Run tests to confirm they fail**

```bash
cd /Users/echance/Documents/Cursor/agentic-governance/collector
python -m pytest tests/test_approval_hold.py -v 2>&1 | head -30
```

Expected: `ModuleNotFoundError` or `ImportError` — `approval_hold` doesn't exist yet.

- [ ] **Step 1.3: Implement approval_hold module**

```python
# collector/enforcement/approval_hold.py
"""Approval hold manager: posts ApprovalRequest to server, polls for decision."""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Any

import requests

logger = logging.getLogger(__name__)


@dataclass
class HoldConfig:
    poll_interval_seconds: int = 10
    timeout_seconds: int = 300
    timeout_behavior: str = "deny"   # "deny" | "approve"
    offline_behavior: str = "deny"   # "deny" | "approve"

    @classmethod
    def from_dict(cls, d: dict) -> HoldConfig:
        return cls(
            poll_interval_seconds=int(d.get("poll_interval_seconds", 10)),
            timeout_seconds=int(d.get("timeout_seconds", 300)),
            timeout_behavior=d.get("timeout_behavior", "deny"),
            offline_behavior=d.get("offline_behavior", "deny"),
        )


@dataclass
class HoldResult:
    decision: str           # "approved" | "denied"
    approval_id: str | None
    timed_out: bool = False


class ApprovalHoldManager:
    """Blocks local enforcement until a server-side approval decision arrives."""

    def __init__(self, api_url: str, api_key: str, config: HoldConfig | None = None) -> None:
        self._api_url = api_url.rstrip("/")
        self._api_key = api_key
        self.config = config or HoldConfig()

    def _headers(self) -> dict[str, str]:
        return {"X-Api-Key": self._api_key, "Content-Type": "application/json"}

    def _create_approval_request(
        self,
        event_id: str,
        tool_name: str,
        tool_class: str,
        confidence_band: str,
        confidence_score: float,
        policy_rule_id: str,
        endpoint_id: str | None = None,
    ) -> str:
        """POST /approvals. Returns approval_id."""
        payload: dict[str, Any] = {
            "event_id": event_id,
            "tool_name": tool_name,
            "confidence_band": confidence_band,
            "confidence_score": confidence_score,
            "policy_rule_id": policy_rule_id,
        }
        if endpoint_id:
            payload["endpoint_id"] = endpoint_id
        resp = requests.post(
            f"{self._api_url}/approvals",
            json=payload,
            headers=self._headers(),
            timeout=10,
        )
        resp.raise_for_status()
        return resp.json()["id"]

    def _poll_decision(self, approval_id: str) -> str:
        """GET /approvals/:id. Returns status string."""
        resp = requests.get(
            f"{self._api_url}/approvals/{approval_id}",
            headers=self._headers(),
            timeout=10,
        )
        resp.raise_for_status()
        return resp.json()["status"]

    def wait_for_decision(
        self,
        event_id: str,
        tool_name: str,
        tool_class: str,
        confidence_band: str,
        confidence_score: float,
        policy_rule_id: str,
        endpoint_id: str | None = None,
    ) -> HoldResult:
        """Block until an approval decision arrives or timeout expires."""
        try:
            approval_id = self._create_approval_request(
                event_id=event_id,
                tool_name=tool_name,
                tool_class=tool_class,
                confidence_band=confidence_band,
                confidence_score=confidence_score,
                policy_rule_id=policy_rule_id,
                endpoint_id=endpoint_id,
            )
        except Exception:
            logger.warning(
                "Could not create approval request for event %s (offline?); "
                "applying offline_behavior=%s",
                event_id, self.config.offline_behavior,
            )
            return HoldResult(decision=self.config.offline_behavior, approval_id=None)

        logger.info(
            "Approval hold started: approval_id=%s event_id=%s tool=%s",
            approval_id, event_id, tool_name,
        )

        deadline = time.monotonic() + self.config.timeout_seconds
        while time.monotonic() < deadline:
            try:
                status = self._poll_decision(approval_id)
            except Exception:
                logger.warning("Poll failed for approval %s; retrying", approval_id)
                time.sleep(self.config.poll_interval_seconds)
                continue

            if status in ("approved", "denied"):
                logger.info("Approval decision: %s for approval_id=%s", status, approval_id)
                return HoldResult(decision=status, approval_id=approval_id)

            # still pending
            time.sleep(self.config.poll_interval_seconds)

        logger.warning(
            "Approval hold timed out for approval_id=%s; applying timeout_behavior=%s",
            approval_id, self.config.timeout_behavior,
        )
        return HoldResult(
            decision=self.config.timeout_behavior,
            approval_id=approval_id,
            timed_out=True,
        )
```

- [ ] **Step 1.4: Run tests**

```bash
cd /Users/echance/Documents/Cursor/agentic-governance/collector
python -m pytest tests/test_approval_hold.py -v
```

Expected: All tests pass.

- [ ] **Step 1.5: Commit**

```bash
cd /Users/echance/Documents/Cursor/agentic-governance
git add collector/enforcement/approval_hold.py collector/tests/test_approval_hold.py
git commit -m "feat(collector): add ApprovalHoldManager for approval_required hold semantics"
```

---

## Task 2: Collector — wire hold into orchestrator

**Files:**
- Modify: `collector/orchestrator.py` (line 658 area)
- Modify: `collector/config/collector.example.json`

- [ ] **Step 2.1: Add approval_hold config to collector.example.json**

Find `collector/config/collector.example.json`. Add after the last config field:

```json
"approval_hold": {
  "poll_interval_seconds": 10,
  "timeout_seconds": 300,
  "timeout_behavior": "deny",
  "offline_behavior": "deny"
}
```

- [ ] **Step 2.2: Modify _process_detection in orchestrator.py**

Find the block starting at line 658:
```python
if enforcer and policy_decision.decision_state in ("block", "approval_required"):
```

Replace the logic so `approval_required` waits for an approval decision before enforcing:

```python
    should_enforce = False
    hold_result = None

    if enforcer:
        if policy_decision.decision_state == "block":
            should_enforce = True
        elif policy_decision.decision_state == "approval_required":
            # Hold enforcement: post to server and wait for analyst decision.
            hold_cfg_dict = (config or {}).get("approval_hold", {})
            from enforcement.approval_hold import ApprovalHoldManager, HoldConfig
            hold_mgr = ApprovalHoldManager(
                api_url=(config or {}).get("api_url", ""),
                api_key=(config or {}).get("api_key", ""),
                config=HoldConfig.from_dict(hold_cfg_dict),
            )
            hold_result = hold_mgr.wait_for_decision(
                event_id=detection_event["event_id"],
                tool_name=scan.tool_name or "unknown",
                tool_class=scan.tool_class or "A",
                confidence_band=conf_class.lower(),
                confidence_score=confidence,
                policy_rule_id=policy_decision.rule_id,
                endpoint_id=endpoint_id,
            )
            # Only enforce (block) if denied; on approval, allow through.
            should_enforce = hold_result.decision == "denied"
            if verbose:
                outcome = "denied → enforcing" if should_enforce else "approved → allowing"
                print(f"  Approval hold resolved: {outcome} (timed_out={hold_result.timed_out})")

    if should_enforce and enforcer:
        network_elevated = "NET" in (policy_decision.rule_id or "")
        enf_result = enforcer.enforce(
            decision=policy_decision,
            tool_name=scan.tool_name or "unknown",
            tool_class=scan.tool_class or "A",
            pids=pids or None,
            network_elevated=network_elevated,
            process_patterns=scan.process_patterns,
        )
```

Note: `_process_detection` currently takes a `config` parameter that may need to be threaded through if not already present. Check the function signature at line ~489. If `config` is not a parameter, add it: `config: dict | None = None`.

- [ ] **Step 2.3: Verify existing tests still pass**

```bash
cd /Users/echance/Documents/Cursor/agentic-governance/collector
python -m pytest tests/test_policy.py tests/test_enforcement_e2e.py -v
```

Expected: All pass. If `config` parameter change breaks call sites, update them.

- [ ] **Step 2.4: Commit**

```bash
cd /Users/echance/Documents/Cursor/agentic-governance
git add collector/orchestrator.py collector/config/collector.example.json
git commit -m "feat(collector): enforce approval_required hold before local enforcement"
```

---

## Task 3: Backend — add event_id filter to approvals list

**Files:**
- Modify: `api/routers/approvals.py`

The collector's `_poll_decision` calls `GET /approvals/:id` directly (it already has the approval_id). But confirming list also works for monitoring.

The spec requires "approval decision transitions state" (already done — 409 is already implemented). One gap: `list_approvals` doesn't support `event_id` filter, which is useful for the collector to verify its hold state.

- [ ] **Step 3.1: Write failing test**

Add to `api/tests/test_approvals.py`:

```python
def test_list_approvals_by_event_id(client):
    """event_id filter returns only matching records."""
    headers, _ = _register_admin(client)
    # create two approvals with different event_ids
    r1 = client.post(f"{API}/approvals", json={"event_id": "evt-aaa"}, headers=headers)
    r2 = client.post(f"{API}/approvals", json={"event_id": "evt-bbb"}, headers=headers)
    assert r1.status_code == 201
    assert r2.status_code == 201

    resp = client.get(f"{API}/approvals?event_id=evt-aaa", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 1
    assert data["items"][0]["event_id"] == "evt-aaa"
```

- [ ] **Step 3.2: Run test to confirm it fails**

```bash
cd /Users/echance/Documents/Cursor/agentic-governance/api
python -m pytest tests/test_approvals.py::test_list_approvals_by_event_id -v
```

Expected: FAIL — event_id filter not supported.

- [ ] **Step 3.3: Add event_id filter to list_approvals**

In `api/routers/approvals.py`, in `list_approvals`, add `event_id` query param and filter:

```python
@router.get("", response_model=ApprovalListResponse)
@limiter.limit("60/minute")
def list_approvals(
    request: Request,
    status_filter: str | None = Query(default=None, alias="status"),
    event_id: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    ...
):
    ...
    q = db.query(ApprovalRequest).filter(get_tenant_filter(auth, ApprovalRequest))
    if status_filter and status_filter != "all":
        q = q.filter(ApprovalRequest.status == status_filter)
    if event_id:
        q = q.filter(ApprovalRequest.event_id == event_id)
    ...
```

- [ ] **Step 3.4: Run test**

```bash
cd /Users/echance/Documents/Cursor/agentic-governance/api
python -m pytest tests/test_approvals.py -v
```

Expected: All pass including new test.

- [ ] **Step 3.5: Commit**

```bash
cd /Users/echance/Documents/Cursor/agentic-governance
git add api/routers/approvals.py api/tests/test_approvals.py
git commit -m "feat(api): add event_id filter to list_approvals endpoint"
```

---

## Task 4: Backend — PATCH /enforcement/allow-list/:id

**Files:**
- Modify: `api/routers/enforcement.py`
- Create: `api/tests/test_enforcement_allow_list_patch.py`

- [ ] **Step 4.1: Write failing tests**

```python
# api/tests/test_enforcement_allow_list_patch.py
"""Tests for PATCH /enforcement/allow-list/:id."""

from tests.conftest import API, _auth_header, register_user


def _register_admin(client, email="patch-admin@test.com", tenant="PatchOrg"):
    tokens = register_user(client, email, tenant_name=tenant)
    return _auth_header(tokens["access_token"]), tokens


def _create_entry(client, headers, pattern="cursor.exe"):
    from datetime import datetime, timezone, timedelta
    expires = (datetime.now(timezone.utc) + timedelta(days=30)).isoformat()
    resp = client.post(f"{API}/enforcement/allow-list", headers=headers, json={
        "pattern": pattern,
        "pattern_type": "process_name",
        "reason_code": "known_safe",
        "expires_at": expires,
    })
    assert resp.status_code == 201
    return resp.json()


class TestAllowListPatch:
    def test_patch_reason_code(self, client):
        headers, _ = _register_admin(client)
        entry = _create_entry(client, headers)
        resp = client.patch(
            f"{API}/enforcement/allow-list/{entry['id']}",
            headers=headers,
            json={"reason_code": "updated_reason"},
        )
        assert resp.status_code == 200
        assert resp.json()["reason_code"] == "updated_reason"

    def test_patch_scope(self, client):
        headers, _ = _register_admin(client, email="patch2@test.com", tenant="PatchOrg2")
        entry = _create_entry(client, headers)
        resp = client.patch(
            f"{API}/enforcement/allow-list/{entry['id']}",
            headers=headers,
            json={"scope": "endpoint"},
        )
        assert resp.status_code == 200
        assert resp.json()["scope"] == "endpoint"

    def test_patch_requires_admin(self, client):
        from core.database import get_db
        from models.user import User
        admin_h, _ = _register_admin(client, email="patch-admin3@test.com", tenant="PatchOrg3")
        viewer_tokens = register_user(client, "patch-viewer@test.com", tenant_name="PatchOrg3v")
        viewer_h = _auth_header(viewer_tokens["access_token"])
        db = next(get_db())
        u = db.query(User).filter(User.email == "patch-viewer@test.com").first()
        u.role = "viewer"
        db.commit()
        entry = _create_entry(client, admin_h)
        resp = client.patch(
            f"{API}/enforcement/allow-list/{entry['id']}",
            headers=viewer_h,
            json={"reason_code": "bad"},
        )
        assert resp.status_code == 403

    def test_patch_cross_tenant_denied(self, client):
        headers_a, _ = _register_admin(client, email="patch-a@test.com", tenant="OrgA")
        headers_b, _ = _register_admin(client, email="patch-b@test.com", tenant="OrgB")
        entry = _create_entry(client, headers_a)
        resp = client.patch(
            f"{API}/enforcement/allow-list/{entry['id']}",
            headers=headers_b,
            json={"reason_code": "steal"},
        )
        assert resp.status_code == 404  # strict_tenant_filter → not found

    def test_patch_immutable_fields_ignored(self, client):
        headers, _ = _register_admin(client, email="patch-imm@test.com", tenant="ImmOrg")
        entry = _create_entry(client, headers)
        original_id = entry["id"]
        original_tenant = entry["tenant_id"]
        resp = client.patch(
            f"{API}/enforcement/allow-list/{entry['id']}",
            headers=headers,
            json={"id": "hacked", "tenant_id": "hacked", "reason_code": "safe"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == original_id
        assert data["tenant_id"] == original_tenant
        assert data["reason_code"] == "safe"

    def test_patch_nonexistent_returns_404(self, client):
        headers, _ = _register_admin(client, email="patch-404@test.com", tenant="Org404")
        resp = client.patch(
            f"{API}/enforcement/allow-list/nonexistent-id",
            headers=headers,
            json={"reason_code": "x"},
        )
        assert resp.status_code == 404
```

- [ ] **Step 4.2: Run tests to confirm they fail**

```bash
cd /Users/echance/Documents/Cursor/agentic-governance/api
python -m pytest tests/test_enforcement_allow_list_patch.py -v 2>&1 | head -20
```

Expected: `405 Method Not Allowed` or similar.

- [ ] **Step 4.3: Add AllowListPatch schema and PATCH endpoint to enforcement.py**

After the existing `AllowListCreate` schema (or wherever schemas are defined in enforcement.py), add:

```python
class AllowListPatch(BaseModel):
    scope: str | None = Field(default=None, max_length=128)
    expires_at: datetime | None = None
    reason_code: str | None = Field(default=None, max_length=128)
    owner_id: str | None = Field(default=None, max_length=128)
    description: str | None = Field(default=None, max_length=1024)
    no_expiry_override: bool | None = None
```

Add the endpoint after the existing `DELETE /enforcement/allow-list/{entry_id}` handler. Find the `AllowListOut` schema (or equivalent) that the existing list/create endpoints return, and reuse it here:

```python
@router.patch("/allow-list/{entry_id}")
@limiter.limit("30/minute")
def patch_allow_list_entry(
    request: Request,
    entry_id: str,
    body: AllowListPatch,
    authorization: str | None = Depends(get_authorization),
    x_api_key: str | None = Header(default=None),
    db: Session = Depends(get_db),
):
    """Partially update an allow-list entry. Owner/admin only."""
    auth = resolve_auth(authorization, x_api_key, db)
    require_role(auth, "owner", "admin")

    entry = db.query(AllowListEntry).filter(
        AllowListEntry.id == entry_id,
        strict_tenant_filter(auth, AllowListEntry),
    ).first()
    if not entry:
        raise HTTPException(status_code=404, detail="Allow-list entry not found")

    before_snapshot = {
        "scope": entry.scope,
        "expires_at": entry.expires_at.isoformat() if entry.expires_at else None,
        "reason_code": entry.reason_code,
        "owner_id": entry.owner_id,
        "description": getattr(entry, "description", None),
        "no_expiry_override": getattr(entry, "no_expiry_override", False),
    }

    update_data = body.model_dump(exclude_unset=True)
    for field_name, value in update_data.items():
        setattr(entry, field_name, value)

    after_snapshot = {
        "scope": entry.scope,
        "expires_at": entry.expires_at.isoformat() if entry.expires_at else None,
        "reason_code": entry.reason_code,
        "owner_id": entry.owner_id,
        "description": getattr(entry, "description", None),
        "no_expiry_override": getattr(entry, "no_expiry_override", False),
    }

    audit_record(
        db,
        tenant_id=auth.tenant_id,
        actor_id=auth.user_id,
        action="allow_list.updated",
        resource_type="allow_list_entry",
        resource_id=entry.id,
        detail={"before": before_snapshot, "after": after_snapshot},
    )

    db.commit()
    db.refresh(entry)

    # Return the same shape as list/create endpoints
    return _serialize_allow_list_entry(entry)
```

Note: Check what `_serialize_allow_list_entry` is called (or inline the dict if there's no helper — match the existing list endpoint's return shape). Look at how `GET /enforcement/allow-list` serializes entries and replicate that.

- [ ] **Step 4.4: Run tests**

```bash
cd /Users/echance/Documents/Cursor/agentic-governance/api
python -m pytest tests/test_enforcement_allow_list_patch.py -v
```

Expected: All pass.

- [ ] **Step 4.5: Run full enforcement test suite**

```bash
cd /Users/echance/Documents/Cursor/agentic-governance/api
python -m pytest tests/test_enforcement_posture_rbac.py -v
```

Expected: All pass (no regression).

- [ ] **Step 4.6: Commit**

```bash
cd /Users/echance/Documents/Cursor/agentic-governance
git add api/routers/enforcement.py api/tests/test_enforcement_allow_list_patch.py
git commit -m "feat(api): add PATCH /enforcement/allow-list/:id with audit trail"
```

---

## Task 5: Dashboard — wire ExceptionsPage drawer to PATCH

**Files:**
- Modify: `dashboard/src/lib/api.js`
- Modify: `dashboard/src/pages/ExceptionsPage.jsx`

- [ ] **Step 5.1: Wire updateAllowListEntry in api.js**

In `dashboard/src/lib/api.js`, find the `updateAllowListEntry` stub (likely a no-op or TODO comment) and replace with:

```javascript
export async function updateAllowListEntry(id, data) {
  return apiMutate('PATCH', `/enforcement/allow-list/${id}`, data);
}
```

- [ ] **Step 5.2: Update ExceptionsPage drawer submit**

In `ExceptionsPage.jsx`, find the drawer's submit/save handler. Currently it calls `createAllowListEntry` for both create and edit. Change it so:
- If `editingEntry` (or equivalent state) is set → call `updateAllowListEntry(editingEntry.id, formData)`
- If creating new → call `createAllowListEntry(formData)`

Map the response back into the entries list (replace or append as appropriate).

Ensure validation error messages from the PATCH response (field-level `detail`) surface as field-level UI messages.

- [ ] **Step 5.3: Run existing Vitest tests**

```bash
cd /Users/echance/Documents/Cursor/agentic-governance/dashboard
npm run test -- ExceptionsPage 2>&1 | tail -20
```

Fix any failures. If no test file exists for ExceptionsPage, create `src/tests/ExceptionsPage.test.jsx` covering:
- Happy path create (calls POST)
- Happy path edit (calls PATCH, not POST)
- Error state shows field-level message

- [ ] **Step 5.4: Commit**

```bash
cd /Users/echance/Documents/Cursor/agentic-governance
git add dashboard/src/lib/api.js dashboard/src/pages/ExceptionsPage.jsx
git commit -m "feat(dashboard): wire ExceptionsPage edit to PATCH allow-list endpoint"
```

---

## Task 6: Dashboard — ApprovalsPage SLA timer + age sort

**Files:**
- Modify: `dashboard/src/pages/ApprovalsPage.jsx`

The pending queue currently shows "Requested at" timestamp. Add:
1. Age display next to each row (e.g., "3 min ago", "2h 15m ago")
2. Pending tab sorted by oldest first (triage by age urgency)
3. Detail drawer status badge: "Execution held pending approval" for pending items

- [ ] **Step 6.1: Add age utility**

In `ApprovalsPage.jsx` (or in a shared `dashboard/src/lib/time.js`), add a pure function:

```javascript
export function formatAge(isoString) {
  const diffMs = Date.now() - new Date(isoString).getTime();
  const diffMin = Math.floor(diffMs / 60000);
  if (diffMin < 1) return 'just now';
  if (diffMin < 60) return `${diffMin}m ago`;
  const hours = Math.floor(diffMin / 60);
  if (hours < 24) return `${hours}h ${diffMin % 60}m ago`;
  return `${Math.floor(hours / 24)}d ago`;
}
```

- [ ] **Step 6.2: Sort pending items and show age**

In the pending tab render:
```javascript
const sortedPending = [...pendingItems].sort(
  (a, b) => new Date(a.requested_at) - new Date(b.requested_at)  // oldest first
);
```

Add an "Age" column to the pending table: `<td>{formatAge(item.requested_at)}</td>`.

- [ ] **Step 6.3: Add hold status badge in detail drawer**

In the drawer's status section for pending approvals, add:
```jsx
{approval.status === 'pending' && (
  <span className="inline-flex items-center px-2 py-0.5 rounded bg-amber-50 text-amber-700 border border-amber-200 text-xs font-semibold">
    Execution held pending approval
  </span>
)}
```

- [ ] **Step 6.4: Run tests**

```bash
cd /Users/echance/Documents/Cursor/agentic-governance/dashboard
npm run test -- ApprovalsPage 2>&1 | tail -20
```

- [ ] **Step 6.5: Commit**

```bash
cd /Users/echance/Documents/Cursor/agentic-governance
git add dashboard/src/pages/ApprovalsPage.jsx
git commit -m "feat(dashboard): add SLA timer, age sort, and hold badge to ApprovalsPage"
```

---

## Task 7: Final verification

- [ ] **Step 7.1: Run full API test suite**

```bash
cd /Users/echance/Documents/Cursor/agentic-governance/api
python -m pytest tests/ -v --tb=short 2>&1 | tail -40
```

Expected: All pass.

- [ ] **Step 7.2: Run full collector test suite**

```bash
cd /Users/echance/Documents/Cursor/agentic-governance/collector
python -m pytest tests/ -v --tb=short 2>&1 | tail -40
```

Expected: All pass.

- [ ] **Step 7.3: Run dashboard tests**

```bash
cd /Users/echance/Documents/Cursor/agentic-governance/dashboard
npm run test 2>&1 | tail -20
```

Expected: All pass.

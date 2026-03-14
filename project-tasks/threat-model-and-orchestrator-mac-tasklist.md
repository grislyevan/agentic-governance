# Threat Model and Orchestrator Roles — Development Tasks (Mac)

## Specification Summary

**Original requirements (from threat model and plan):**

- Threat model doc ([docs/threat-model.md](../docs/threat-model.md)) must reference real code paths and tests; STRIDE and mitigations must align with auth, gateway, and response orchestrator.
- Orchestrator and playbook roles: response_orchestrator chains enforcement, webhooks, and audit on event ingest; playbook definitions are tenant-scoped; only default playbooks run in code today (per finding F-005).
- Validation: Security Engineer implements; Code Reviewer or EvidenceQA validates doc vs code/tests.

**Technical stack:** Python (FastAPI, pytest), React/Vite dashboard, SQLite or PostgreSQL, binary gateway (msgpack/TCP). No Laravel/FluxUI (Detec stack per AGENTS.md).

**Target:** Complete the remaining threat-model review and ensure orchestrator/playbook alignment is documented and test-validated. Mac (darwin) is the development environment.

---

## Mac Environment Assumptions

- **Workspace:** `/Users/echance/Documents/Cursor/agentic-governance`
- **Shell:** zsh (default on macOS)
- **Python:** `pip` / `venv`; run tests with `pytest` from repo root or component dirs
- **Node:** Used for dashboard; `npm run build` and `npm run dev` from `dashboard/`
- **Paths:** All paths below are relative to repo root unless noted as absolute

---

## Development Tasks

### [x] Task 1: Validate threat model references to auth and tenant code

**Description:** Confirm every auth/tenant reference in [docs/threat-model.md](../docs/threat-model.md) points to existing code and that STRIDE mitigations match current behavior.

**Acceptance criteria:**

- Each mention of [api/core/auth.py](../api/core/auth.py) and [api/core/tenant.py](../api/core/tenant.py) in the threat model corresponds to real symbols (e.g. `resolve_auth`, `require_role`, `get_tenant_filter`).
- At least one test in [api/tests/test_security_pentest.py](../api/tests/test_security_pentest.py) is cited for auth (e.g. `TestAPI2BrokenAuth`) and for tenant isolation (e.g. `TestAPI1BrokenObjectLevelAuth`); run those tests on Mac and note any failures.
- No broken or outdated file paths in the doc.

**Commands (run from repo root on Mac):**

```bash
cd /Users/echance/Documents/Cursor/agentic-governance
pytest api/tests/test_security_pentest.py -v -k "BrokenAuth or BrokenObjectLevelAuth"
```

**Files to edit:** [docs/threat-model.md](../docs/threat-model.md) (fix references only if wrong).

**Reference:** Threat model Section 2.1 (API STRIDE), Section 4 (Key scenarios), Section 5 (Mitigation table).

---

### [x] Task 2: Validate threat model references to gateway code and tests

**Description:** Ensure gateway STRIDE and mitigation table entries match [api/gateway.py](../api/gateway.py) and [api/tests/test_gateway_security.py](../api/tests/test_gateway_security.py).

**Acceptance criteria:**

- Doc references to `_verify_api_key`, `_handle_auth`, `_ingest_event`, connection limits, and idle timeout exist and match current implementation.
- Gateway security tests run on Mac; any test that validates auth bypass or msgpack handling is referenced correctly in the doc.

**Commands (run from repo root on Mac):**

```bash
cd /Users/echance/Documents/Cursor/agentic-governance
pytest api/tests/test_gateway_security.py -v
```

**Files to edit:** [docs/threat-model.md](../docs/threat-model.md) if references are wrong or missing.

**Reference:** Threat model Section 2.2 (Gateway STRIDE), Section 5 (mitigations 6–9).

---

### [x] Task 3: Validate threat model references to response orchestrator and playbooks

**Description:** Align playbook/orchestrator section and mitigation table with [api/core/response_orchestrator.py](../api/core/response_orchestrator.py), [api/core/response_playbooks.py](../api/core/response_playbooks.py), and [api/routers/response_playbooks.py](../api/routers/response_playbooks.py).

**Acceptance criteria:**

- Doc states that only default playbooks run on ingest (or update doc if custom playbooks are now executed); align with [docs/security-findings.md](../docs/security-findings.md) F-005 if that finding is still open.
- References to event validation before orchestration point to [api/core/event_validator.py](../api/core/event_validator.py) and orchestrator usage of it.
- Audit/repudiation references point to [api/core/audit_logger.py](../api/core/audit_logger.py) and [docs/rollback.md](../docs/rollback.md).

**Commands (run from repo root on Mac):**

```bash
cd /Users/echance/Documents/Cursor/agentic-governance
pytest api/tests/ -v -k "playbook or orchestrator or response_playbook" --ignore=api/tests/test_security_pentest.py --ignore=api/tests/test_gateway_security.py --ignore=api/tests/test_rate_limits.py
```

**Files to edit:** [docs/threat-model.md](../docs/threat-model.md), and optionally [docs/security-findings.md](../docs/security-findings.md) if F-005 is resolved.

**Reference:** Threat model Section 2.5 (Playbook/Orchestrator STRIDE), Section 5 mitigation #12, Section 6 (References).

---

### [x] Task 4: Run full security test suite on Mac and document status

**Description:** Run all security-related tests from the threat model (pentest, gateway, rate limits, collector) on your Mac and record pass/fail and any env-specific notes.

**Acceptance criteria:**

- All of the following pass (or failures are documented with cause and next steps):
  - `pytest api/tests/test_security_pentest.py -v`
  - `pytest api/tests/test_gateway_security.py -v`
  - `pytest api/tests/test_rate_limits.py -v`
  - `pytest collector/tests/test_agent_security.py -v`
- If any test is skipped or fails only on darwin, add a one-line note to the task list or to [docs/threat-model.md](../docs/threat-model.md) (e.g. “Rate limit tests require TESTING=0; see test_rate_limits.py”).

**Commands (run from repo root on Mac):**

```bash
cd /Users/echance/Documents/Cursor/agentic-governance
pytest api/tests/test_security_pentest.py api/tests/test_gateway_security.py api/tests/test_rate_limits.py -v
pytest collector/tests/test_agent_security.py -v
```

**Deliverable:** Updated task list with “[x]” for this task and a short “Mac test run” note (pass/fail, env quirks).

**Mac test run (darwin):** All four suites pass. Pentest 30, gateway 7, rate limits 4, collector agent security 7. Rate limit tests require the `client_with_ratelimit` fixture (limiter enabled); added in `api/tests/conftest.py` so they run without env changes.

**Reference:** Threat model Section 6 (References), [project-tasks/threat-model-tasklist.md](../project-tasks/threat-model-tasklist.md).

---

### [x] Task 5: Mark threat-model review complete and update task list

**Description:** After Tasks 1–4, mark item 9 in [project-tasks/threat-model-tasklist.md](../project-tasks/threat-model-tasklist.md) complete and add a one-sentence summary of what was validated.

**Acceptance criteria:**

- [project-tasks/threat-model-tasklist.md](../project-tasks/threat-model-tasklist.md) shows `- [x] 9. Review: ...` with optional parenthetical, e.g. “(validated auth, gateway, orchestrator refs and ran security suites on Mac).”
- No em dashes in the summary (per workspace rules).

**Files to edit:** [project-tasks/threat-model-tasklist.md](../project-tasks/threat-model-tasklist.md).

**Reference:** Threat model deliverable in task list.

---

## Quality Requirements

- [ ] All file paths in the threat model resolve to existing files (relative to repo root).
- [ ] STRIDE mitigations and mitigation table match current code and tests.
- [ ] Security test commands run in zsh on macOS without modification (except `cd` to workspace if needed).
- [ ] No background processes in any command (no `&`).
- [ ] No server startup in task steps; assume API/collector are run separately when needed for manual checks.

---

## Technical Notes

**Stack:** FastAPI, pytest, React/Vite, SQLite/PostgreSQL, TCP gateway (port 8001).  
**Mac specifics:** Use `cd /Users/echance/Documents/Cursor/agentic-governance` when running from a fresh terminal; `pytest` may use repo root or `api/` / `collector/` depending on imports.  
**Orchestrator roles:** Response orchestrator runs on event ingest; playbook definitions in code and (if implemented) DB; tenant-scoped; audit and rollback documented in [docs/rollback.md](../docs/rollback.md).

---

## Summary

| Task | Focus | Est. (min) |
|------|--------|------------|
| 1 | Auth/tenant doc vs code + tests | 30–45 |
| 2 | Gateway doc vs code + tests | 30–45 |
| 3 | Orchestrator/playbooks doc vs code | 30–45 |
| 4 | Full security suite on Mac | 15–30 |
| 5 | Mark review complete | 5–10 |

**Total:** about 2–3 hours. One logical change per commit; commit message should explain *why* (e.g. “Threat model review: align STRIDE and mitigation refs with auth and gateway”).

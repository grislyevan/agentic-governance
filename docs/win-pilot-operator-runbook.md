# Windows Pilot Operator Runbook

**Release:** `windows-pilot-rc1` (commit `4af7921`)  
**Date:** 2026-03-21  
**Status:** GO — controlled pilot with scheduled-task workaround on Windows; ETW is an optional enhancement, not required for baseline operation.

---

## Scope

Controlled pilot: 5 endpoints → 10 → 25.  
AI tool governance only (Ollama, Aider, and equivalents). Not a generic EDR.  
Windows agent runs as scheduled task under user account — not a system service.

---

## Pilot Kickoff Packet (share these three docs only)

1. `lab-runs/LAB-RUN-WINDOWS-STRESS-002-RESULTS.md` — evidence
2. `docs/win-pilot-go-no-go-memo.md` — GO verdict + gate summary
3. This document — operator runbook + hard-stop triggers

---

## Deployment

### Install (per endpoint)

```powershell
# 1. Install agent (as evan or equivalent local admin)
pip install agentic-governance==0.2.0

# 2. Create config
mkdir C:\ProgramData\Detec\Agent
# Write agent.env with API URL, API key, endpoint registration

# 3. Register scheduled task (onlogon, run as user account)
schtasks /create /tn DetecAgent /tr "python -m collector.agent" /sc onlogon /ru <username> /f

# 4. Verify
tasklist | findstr python
curl http://<api-server>:8000/api/events?endpoint_id=<id>
```

### Verify telemetry within 10 minutes of logon

```bash
curl -H "X-API-Key: <key>" "http://<api-server>:8000/api/events?endpoint_id=<id>&limit=10"
# Expect: detection.observed events for any AI tools present
# If 0 events after 10 min: see Troubleshooting below
```

---

## Rollout Stages

| Stage | Endpoints | Gate to advance |
|---|---|---|
| 1 | 5 | Zero hard-stop triggers after 48h; events flowing on all 5 |
| 2 | 10 | Same; enforcement metrics reviewed |
| 3 | 25 | Same; residual risks re-evaluated |

Do not advance a stage if any hard-stop condition is active.

---

## Hard-Stop Triggers (halt rollout immediately)

| Trigger | Action |
|---|---|
| Any endpoint reverts to 0 events after working | Stop rollout, diagnose before continuing |
| `enforcement.admin_block` on a process not in AI tool list | Stop rollout, review policy baseline |
| `success=True` returned for block with no PIDs | Stop rollout, re-verify enforcer fix (`11a2b5e`) |
| Agent crashes on install on any new endpoint | Stop rollout, check Python/schema packaging |
| API unreachable from >1 endpoint simultaneously | Stop rollout, check network/API health |

---

## Residual Risk Register

| Risk | Severity | Owner | Target Date | Notes |
|---|---|---|---|---|
| Windows Service non-functional (LocalSystem/PYTHONPATH) | Medium | **TBD** | **TBD** | Workaround: scheduled task as user account. Fix: grant "Log on as a service" right or system-wide Python |
| ETW ctypes backend missing (`_etw_ctypes`) | Low | **TBD** | **TBD** | Polling works. ETW improves signal fidelity. Non-blocking for pilot. |
| Allow-list staleness gate in lab context | Low | **TBD** | **TBD** | Set `AGENTIC_GOV_ALLOW_LIST_MAX_AGE` env var or pre-sync allow-list |

**Action required:** assign owners and dates before advancing past Stage 1.

---

## Troubleshooting

**0 events after install:**
1. Check agent is running: `tasklist | findstr python`
2. Check schema present: `python -c "import collector.schema.validator; print('ok')"`
3. Check API reachable from endpoint: `curl http://<api-server>:8000/api/health`
4. Check `agent.env` config exists at `C:\ProgramData\Detec\Agent\agent.env`
5. Check any AI tools are installed — agent only emits events when it detects something

**Agent not starting:**
1. Run manually: `python -m collector.agent` — capture full output
2. If schema error: reinstall with `pip install --force-reinstall agentic-governance==0.2.0`
3. If PYTHONPATH issue: verify install is in user site-packages, not system path

**Enforcement not firing:**
1. Check enforcement posture in API: `GET /api/endpoints/<id>` — look for `enforcement_posture`
2. Check allow-list age: if in audit/simulate, set `AGENTIC_GOV_ALLOW_LIST_MAX_AGE=999999` for lab
3. Verify `evan` (or equivalent) is local admin: `net localgroup administrators | findstr <username>`

---

## Key Environment Reference

| Item | Value |
|---|---|
| API server | `http://192.168.0.54:8000` |
| Dashboard | `http://192.168.0.54:8000` → login `Evan@detecadg.com` |
| PC11 (pilot endpoint 1) | `192.168.0.83` — agent confirmed running |
| PC11 endpoint ID | `71f167d2-9e59-4509-abfd-d22dfd722728` |
| Agent version | `agentic-governance==0.2.0` |
| Release tag | `windows-pilot-rc1` @ `4af7921` |

---

## What This Is (and Isn't)

**GO for:** controlled pilot, scheduled-task agent mode, polling-based telemetry, AI tool detection (Ollama, Aider, and equivalents).

**Not yet validated for:** Windows Service mode (LocalSystem PYTHONPATH conflict), ETW native telemetry, non-admin endpoints, endpoints without AI tools installed.

**Not in scope:** generic EDR, Windows persistence/evasion detection, LOLBin blocking.

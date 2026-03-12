# Enforcement Roadmap: Passive Detection to Active Defense

**Created:** 2026-03-11
**Status:** Draft (approved direction, not yet in progress)
**Context:** [Enforcement architecture discussion](../agent-transcripts/) from 2026-03-11
**Depends on:** Playbook v0.4, Milestone M2 (complete), baseline policies (seeded)

---

## Executive Summary

Detec currently excels at **detection**: the five-layer confidence model, 12 scanners, and deterministic policy engine reliably identify agentic AI tools and classify risk. What's missing is the ability to **act** on those decisions without manual intervention.

This roadmap takes Detec from passive governance reporting to two distinct operating modes:

- **Workstation mode (passive):** Current behavior. Detect, report, alert. No autonomous enforcement. Suitable for developer laptops where false positives carry reputational cost.
- **Infrastructure mode (active defense):** Autonomous hunt-and-kill. The agent detects agentic entities by behavioral pattern (not just tool name), enforces `block` decisions immediately (process kill, network block), and reports back. Suitable for servers, CI runners, and crown-jewel infrastructure where an unknown agentic entity at 3 AM is a threat, not a curiosity.

The mode is configured centrally by the admin, pushed to agents, and enforced locally. There is no CLI flag for active enforcement in production; the posture comes from the server.

---

## What Exists Today (Baseline for All Phases)

Every phase spec references these files. Read them before starting work.

### Detection (working, no changes needed unless noted)

| Component | File(s) | Notes |
|-----------|---------|-------|
| 12 tool scanners | `collector/scanner/*.py` | Each extends `BaseScanner` (`scanner/base.py`). Returns `ScanResult` with `LayerSignals`, penalties, evidence. |
| Confidence engine | `collector/engine/confidence.py` | `compute_confidence(scan)` applies per-tool weights, penalties, evasion boost. `classify_confidence(score)` returns Low/Medium/High. |
| Policy engine | `collector/engine/policy.py` | `evaluate_policy()` runs deterministic rules ENFORCE-001 through ENFORCE-D03 plus overlays NET-001, NET-002, ISO-001. Returns `PolicyDecision(decision_state, rule_id, ...)`. |
| 15 baseline policies | `api/core/baseline_policies.py` | Seeded per tenant. `is_baseline=True`, restorable. |
| Telemetry event store | `collector/telemetry/event_store.py` | Thread-safe ring buffer: `ProcessExecEvent`, `NetworkConnectEvent`, `FileChangeEvent`. 120s retention, 10k max. |
| Polling provider | `collector/providers/polling.py` | `PollingProvider.poll()` snapshots psutil processes and TCP connections into the event store. Called each scan cycle. |
| Provider interface | `collector/providers/base.py` | Abstract `TelemetryProvider`: `name`, `available()`, `start(store)`, `stop()`. No `poll()` in the base (designed for event-driven). |

### Enforcement (exists but limited)

| Component | File | Current State | Gap |
|-----------|------|---------------|-----|
| Enforcer dispatcher | `collector/enforcement/enforcer.py` | Routes `block` decisions to `process_kill` or `network_block`. `approval_required` returns a label ("hold_pending_approval") with no actual action. Only runs if `--enforce` CLI flag is set. | No server-controlled posture. No child-process recursion. No PID verification on kill. |
| Process kill | `collector/enforcement/process_kill.py` | SIGTERM then SIGKILL after 3s grace. Has `expected_pattern` param for cmdline verification, but the enforcer **does not pass it**. Skips PID <= 1. | Pattern not wired. No recursive child kill. No process-group kill. |
| Network block | `collector/enforcement/network_block.py` | `pfctl` anchors (macOS), `iptables` UID-owner (Linux). `unblock_outbound()` exists. Windows not supported. | Linux blocks ALL processes for a UID (not just target). No cleanup on agent exit. No Windows support. |
| Proxy inject | `collector/enforcement/proxy_inject.py` | Sets `HTTP_PROXY`/`HTTPS_PROXY` env vars. | Not wired into the enforcer. |

### Communication (working, extensible)

| Component | File | Notes |
|-----------|------|-------|
| Wire protocol | `protocol/wire.py` | msgpack framing, length-prefixed TCP. `MessageType` enum includes `POLICY_PUSH (0x30)`, `COMMAND (0x31)`, `COMMAND_ACK (0x32)`. |
| Message constructors | `protocol/messages.py` | `command_msg(command, command_id, params)` supports `scan_now`, `update_config`, `shutdown`. Does **not** yet support `kill`, `block`, or `posture_push`. |
| TCP gateway | `api/gateway.py` | `DetecGateway` with `SessionRegistry`. `push_to_endpoint(endpoint_id, msg)` and `broadcast(msg)` exist and work. `AgentSession` handles `COMMAND_ACK`. |
| Agent session handler | `api/gateway.py:118-140` | Message dispatch: `EVENT`, `EVENT_BATCH`, `HEARTBEAT`, `COMMAND_ACK`. No handler for receiving enforcement results or posture requests. |

### Configuration

| Component | File | Notes |
|-----------|------|-------|
| Agent config | `collector/config_loader.py` | Precedence: CLI > env (`AGENTIC_GOV_*`) > config file > code defaults. Keys include `interval`, `api_url`, `api_key`, `protocol`, `telemetry_provider`. No `posture` or `enforce_mode` key yet. |
| Server config | `api/core/config.py` | Pydantic `Settings` from env/.env. Has EDR, gateway, SMTP, JWT settings. No enforcement posture settings yet. |
| Endpoint model | `api/models/endpoint.py` | Has `posture` column (String(32), default "unmanaged"). Currently written once on creation, never updated by policy. |

### Main scan loop

| File | Key lines | What happens |
|------|-----------|-------------|
| `collector/main.py:427-457` | Enforcement block | `if enforcer and policy_decision.decision_state == "block"`: calls `enforcer.enforce()`, emits `enforcement.applied` event. `enforcer` only exists when `--enforce` flag is set. |
| `collector/main.py:583-590` | Daemon loop | `while not stop_event.is_set()`: flush buffer, `run_scan()`, `stop_event.wait(timeout=interval)`. Purely interval-driven. |

---

## Phase 1: Admin-Controlled Enforcement Posture

**Objective:** Remove the `--enforce` CLI flag as the production enforcement switch. Replace it with a server-controlled posture enum that the admin configures per-endpoint (or tenant-wide), pushed to agents over the existing TCP channel.

**Effort:** ~2 weeks
**Prerequisites:** None (builds on existing M2 infra)
**Delivers:** Central control over which endpoints can enforce, without touching agent config or redeploying.

### 1.1 Data Model

**Posture enum (shared):**

```python
# New file: protocol/posture.py (or extend protocol/messages.py)
class EnforcementPosture(str, Enum):
    PASSIVE = "passive"          # detect + report only (current behavior)
    AUDIT = "audit"              # log what WOULD be enforced, but don't act
    ACTIVE = "active"            # enforce block decisions autonomously
```

**Server-side changes:**

- `api/models/endpoint.py`: Change `posture` column default from `"unmanaged"` to `"passive"`. Add `enforcement_posture` column (String(16), default `"passive"`, one of `passive`/`audit`/`active`). Add `auto_enforce_threshold` column (Float, default `0.75`, the minimum confidence for auto-enforcement in `active` mode).
- `api/core/config.py`: Add `default_enforcement_posture: str = "passive"` (tenant-wide default for new endpoints).
- New API routes in a new router `api/routers/enforcement.py`:
  - `PUT /api/endpoints/{id}/posture` (admin/owner only): Set posture + threshold for one endpoint.
  - `PUT /api/enforcement/tenant-posture` (owner only): Set default posture for all endpoints in the tenant.
  - `GET /api/enforcement/posture-summary`: Return posture distribution across endpoints.

**Agent-side changes:**

- `collector/config_loader.py`: Add `enforcement_posture` key (default `"passive"`), `auto_enforce_threshold` key (default `0.75`). These are overridden by server push.
- `collector/main.py`: Replace `if enforcer and ...` with posture check:
  - `passive`: Never enforce. Existing behavior.
  - `audit`: Run enforcement logic, emit `enforcement.simulated` event with what would have happened, but don't call `os.kill()` or `pfctl`.
  - `active`: Enforce as current code does, but only when `confidence >= auto_enforce_threshold`.
- The `Enforcer` class gains a `dry_run` mode that logs the action and returns a result without executing it (this already half-exists via the constructor param).

### 1.2 Posture Push via TCP

**New message type:**

```python
# In protocol/wire.py, add:
POSTURE_PUSH = 0x33  # Server -> Agent: enforcement posture update

# In protocol/messages.py, add:
def posture_push_msg(
    posture: str,
    auto_enforce_threshold: float,
    allow_list: list[str] | None = None,
    *,
    seq: int = 0,
) -> dict[str, Any]:
    """Server -> Agent: set enforcement posture."""
    return _envelope(MessageType.POSTURE_PUSH, seq, {
        "posture": posture,
        "auto_enforce_threshold": auto_enforce_threshold,
        "allow_list": allow_list or [],
    })
```

**Gateway integration:**

- `api/gateway.py`: When admin changes posture via API, the route calls `gateway.push_to_endpoint(endpoint_id, posture_push_msg(...))`. If the agent is connected via TCP, it receives the update immediately. If HTTP-only, the agent picks it up on next heartbeat response (add posture to heartbeat_ack payload).
- For HTTP-only agents: extend `POST /api/endpoints/heartbeat` response to include `enforcement_posture` and `auto_enforce_threshold`. The agent applies these on receipt.

**Agent message handler:**

- `collector/main.py` or a new `collector/enforcement/posture.py`: Handle `POSTURE_PUSH` messages. Store the received posture in memory (thread-safe) and optionally persist to the config file so it survives agent restarts.

### 1.3 Allow-List

The posture push includes an `allow_list` of process name patterns (or binary hashes) that should never be enforced against, even in `active` mode. This is the primary false-positive safety valve.

- Stored server-side per tenant: new `allow_list_entries` table (id, tenant_id, pattern, pattern_type ["name", "hash", "path"], created_by, created_at).
- API routes: `GET/POST/DELETE /api/enforcement/allow-list` (admin/owner).
- Agent-side: `Enforcer.enforce()` checks the allow-list before executing any tactic. If a tool matches, the decision is downgraded to `audit` and an `enforcement.allow_listed` event is emitted.

### 1.4 Dashboard UI

- Endpoint detail page: posture toggle (Passive / Audit / Active) with confirmation dialog for Active.
- Tenant settings: default posture selector.
- Allow-list management: table with add/remove.

### 1.5 Acceptance Criteria

1. Admin can set endpoint posture to `active` from the dashboard without touching the agent.
2. Agent in `passive` posture never calls `os.kill()` or firewall commands, regardless of policy decision.
3. Agent in `audit` posture emits `enforcement.simulated` events for every `block` decision, with the tactic that would have been applied.
4. Agent in `active` posture kills processes matching `block` decisions when confidence >= threshold.
5. Allow-listed tools are never enforced against, and `enforcement.allow_listed` events are emitted.
6. Posture changes propagate to TCP-connected agents within 5 seconds.
7. HTTP-only agents pick up posture on next heartbeat (default 300s, configurable).
8. `--enforce` CLI flag is deprecated with a warning; it sets local posture to `active` but server push overrides it.

### 1.6 Test Plan

- Unit: `Enforcer` respects posture enum (passive/audit/active). Allow-list blocks enforcement.
- Unit: `posture_push_msg` encode/decode roundtrip.
- Integration: API route sets posture, gateway pushes to connected agent session.
- Integration: Heartbeat response includes posture for HTTP-only agents.
- API: RBAC checks (only admin/owner can set posture).

### 1.7 Files to Create or Modify

| Action | File | What |
|--------|------|------|
| Create | `protocol/posture.py` | `EnforcementPosture` enum |
| Create | `api/routers/enforcement.py` | Posture + allow-list API routes |
| Create | `api/models/allow_list.py` | Allow-list DB model |
| Create | `collector/enforcement/posture.py` | Posture state manager (thread-safe, persistence) |
| Modify | `protocol/wire.py` | Add `POSTURE_PUSH = 0x33` |
| Modify | `protocol/messages.py` | Add `posture_push_msg()` |
| Modify | `api/models/endpoint.py` | Add `enforcement_posture`, `auto_enforce_threshold` columns |
| Modify | `api/core/config.py` | Add `default_enforcement_posture` setting |
| Modify | `api/gateway.py` | Handle posture push after API call; add posture to heartbeat ack |
| Modify | `collector/config_loader.py` | Add `enforcement_posture`, `auto_enforce_threshold` keys |
| Modify | `collector/main.py` | Replace `--enforce` flag logic with posture-based dispatch |
| Modify | `collector/enforcement/enforcer.py` | Check allow-list; support `audit` dry-run mode |
| Modify | `dashboard/` | Posture toggle, allow-list management UI |

### 1.8 Agent Assignments

- **Backend Architect:** Data model, API routes, gateway integration, Alembic migration
- **Senior Developer:** Agent-side posture handler, config loader changes, main.py refactor
- **Security Engineer:** Allow-list design, RBAC on posture routes, audit logging for posture changes
- **Frontend Developer:** Dashboard posture toggle, allow-list UI

---

## Phase 2: Behavioral Anomaly Scanner

**Objective:** Detect agentic AI entities by behavioral pattern rather than tool name. The current 12 scanners match known tools (Claude Code, Ollama, Cursor, etc.). An unknown Chinese open-source bot at 3 AM won't match any of them. The behavioral scanner catches it by looking for patterns common to all agentic AI: shell fan-out, LLM API call cadence, multi-file burst writes, and feedback loops.

**Effort:** ~4-6 weeks
**Prerequisites:** None (can run in parallel with Phase 1)
**Delivers:** Detection of unknown/unnamed agentic tools. This is the "white blood cell" scanner.

### 2.1 Behavioral Patterns to Detect

These are the agentic behavioral signatures, derived from lab-run observations across all 12 known tools:

| Pattern ID | Name | Signal | Layer |
|------------|------|--------|-------|
| BEH-001 | Shell fan-out | Parent process spawns 5+ child shells within 60s | Process + Behavior |
| BEH-002 | LLM API cadence | Repeated HTTPS connections to known LLM API endpoints (OpenAI, Anthropic, Google, Groq, etc.) at regular intervals | Network + Behavior |
| BEH-003 | Multi-file burst write | 10+ file writes across 3+ directories within 30s, from a single process tree | File + Behavior |
| BEH-004 | Read-modify-write loop | Process reads file, makes HTTPS call, writes same file (or nearby file), repeats | File + Network + Behavior |
| BEH-005 | Autonomous session duration | Single process tree active for 10+ minutes with continuous shell/file/network activity | Behavior |
| BEH-006 | Config/credential access | Process reads `.env`, `.ssh/`, credential stores, then makes network calls | File + Network + Identity |
| BEH-007 | Git automation | Rapid `git add/commit/push` sequences not preceded by interactive editor sessions | Process + File + Behavior |
| BEH-008 | Process resurrection | Killed process restarts within 10s (watchdog/supervisor pattern) | Process + Behavior |

### 2.2 Architecture

**New scanner:** `collector/scanner/behavioral.py`

```python
class BehavioralScanner(BaseScanner):
    """Detect agentic entities by behavioral pattern, not tool name."""

    @property
    def tool_name(self) -> str:
        return "Unknown Agent"  # Overridden with best-guess if patterns match known profiles

    @property
    def tool_class(self) -> str:
        return "C"  # Default to autonomous executor; upgraded to D if BEH-008 matches

    def scan(self, verbose: bool = False) -> ScanResult:
        # 1. Query EventStore for recent process, network, file events
        # 2. Build process trees (pid -> ppid relationships)
        # 3. Score each pattern (BEH-001 through BEH-008) against the tree
        # 4. Aggregate pattern matches into LayerSignals
        # 5. If aggregate exceeds detection threshold, return detected=True
        ...
```

**Key design decisions:**

- The behavioral scanner runs AFTER all named scanners. If a named scanner already detected the same process tree, the behavioral scanner skips it (deduplication by PID set).
- The behavioral scanner is tool-name-agnostic. It sets `tool_name` to `"Unknown Agent"` and populates `evidence_details` with which behavioral patterns matched.
- Pattern thresholds are configurable via `collector/config/behavioral.json` (shipped with defaults, overridable by admin push).
- Each pattern contributes to one or more detection layers. The behavioral scanner produces `LayerSignals` and `penalties` just like any named scanner, so the existing confidence engine scores it the same way.

### 2.3 LLM Endpoint Registry

For BEH-002, the scanner needs a list of known LLM API hostnames. Ship a default list, make it extensible:

```python
# collector/scanner/behavioral_patterns.py
LLM_API_HOSTS: set[str] = {
    "api.openai.com",
    "api.anthropic.com",
    "generativelanguage.googleapis.com",
    "api.groq.com",
    "api.mistral.ai",
    "api.cohere.ai",
    "api.together.xyz",
    "api.replicate.com",
    "api.deepseek.com",
    "api.fireworks.ai",
    # Local inference endpoints
    "localhost:11434",   # Ollama default
    "localhost:1234",    # LM Studio default
    "127.0.0.1:8080",   # llama.cpp default
}
```

This list is updatable via `POSTURE_PUSH` (add an `llm_hosts` field) so the server can push new endpoints without agent redeployment.

### 2.4 Process Tree Builder

The behavioral scanner needs to reconstruct process trees from the EventStore's flat list of `ProcessExecEvent`s:

```python
# collector/scanner/process_tree.py
@dataclass
class ProcessNode:
    pid: int
    ppid: int
    name: str
    cmdline: str
    children: list["ProcessNode"]
    network_events: list[NetworkConnectEvent]
    file_events: list[FileChangeEvent]

def build_trees(store: EventStore) -> list[ProcessNode]:
    """Build process trees from recent telemetry.
    Returns root nodes (ppid=0 or ppid not in known PIDs)."""
    ...
```

### 2.5 Confidence Scoring Integration

The behavioral scanner returns a `ScanResult` like any other scanner. The confidence engine needs:

- New weight profile in `collector/engine/confidence.py`:

```python
BEHAVIORAL_WEIGHTS: dict[str, float] = {
    "process": 0.20,
    "file": 0.15,
    "network": 0.20,
    "identity": 0.10,
    "behavior": 0.35,  # Behavior layer is dominant for pattern-based detection
}

TOOL_WEIGHTS["Unknown Agent"] = BEHAVIORAL_WEIGHTS
```

- A new penalty: `behavioral_only_no_file_artifact` (if only process + network patterns match, no file evidence, reduce by 0.15). This prevents false positives from legitimate automation tools (cron jobs, CI pipelines) that happen to call APIs.

### 2.6 Acceptance Criteria

1. An unnamed Python script that spawns 10 shells, calls `api.openai.com` in a loop, and writes to 15 files is detected with confidence >= 0.65.
2. A legitimate cron job that calls one API endpoint and writes one log file is NOT detected (confidence < 0.45).
3. The behavioral scanner does not duplicate detections from named scanners (PID dedup).
4. Pattern thresholds are configurable without code changes.
5. New LLM API hosts can be pushed from the server.
6. The scanner completes within 500ms even with 10k events in the store.

### 2.7 Test Plan

- Unit: Each pattern detector (BEH-001 through BEH-008) with synthetic EventStore data.
- Unit: Process tree builder correctness.
- Unit: Confidence scoring with `BEHAVIORAL_WEIGHTS`.
- Unit: PID dedup with named scanner results.
- Integration: Full scan cycle with behavioral scanner producing events.
- Calibration: Add behavioral scanner fixtures to `collector/tests/fixtures/lab_runs/`.

### 2.8 Files to Create or Modify

| Action | File | What |
|--------|------|------|
| Create | `collector/scanner/behavioral.py` | Behavioral anomaly scanner |
| Create | `collector/scanner/behavioral_patterns.py` | Pattern definitions, LLM host list, thresholds |
| Create | `collector/scanner/process_tree.py` | Process tree builder from EventStore |
| Create | `collector/config/behavioral.json` | Default pattern thresholds |
| Create | `collector/tests/test_behavioral_scanner.py` | Unit + integration tests |
| Create | `collector/tests/fixtures/lab_runs/behavioral_*.json` | Calibration fixtures |
| Modify | `collector/engine/confidence.py` | Add `BEHAVIORAL_WEIGHTS` |
| Modify | `collector/main.py` | Register behavioral scanner, run after named scanners, pass PID exclusion set |
| Modify | `protocol/messages.py` | Add `llm_hosts` to posture push payload (optional) |

### 2.9 Agent Assignments

- **Senior Developer:** Scanner implementation, process tree builder, EventStore queries
- **Backend Architect:** Pattern threshold config push, LLM host list management API
- **Security Engineer:** False positive analysis, threshold tuning, calibration fixtures
- **QA/Lab:** Lab runs with unknown agentic tools to validate detection

---

## Phase 3: Enforcement Hardening

**Objective:** Make process kill and network block reliable enough for autonomous use in `active` posture. The current implementation has known gaps that are acceptable for manual enforcement but dangerous for automated enforcement.

**Effort:** ~2-3 weeks
**Prerequisites:** Phase 1 (posture enum must exist so hardened enforcement only runs in `active` mode)
**Delivers:** Production-grade enforcement that won't kill the wrong process, leave orphaned firewall rules, or be trivially evaded.

### 3.1 PID Verification Before Kill

**Problem:** Between detection and enforcement, a process can exit and its PID can be reused by an unrelated process. The current `process_kill.py` has an `expected_pattern` parameter that does cmdline verification, but `enforcer.py` **does not pass it** (line 103: `killed = kill_processes(pids)` with no pattern).

**Fix:**

- `enforcer.py`: Pass `expected_pattern` derived from the scanner's `tool_name` and `evidence_details`. Each named scanner should provide a pattern (e.g., Claude Code scanner provides `"claude"`, Ollama provides `"ollama"`). The behavioral scanner provides the matched process name from the tree.
- Add a new field to `ScanResult`: `process_patterns: list[str]` containing substrings expected in the process cmdline. Each scanner populates this.
- `main.py`: Pass `process_patterns` through to `enforcer.enforce()`.

### 3.2 Recursive Child Process Kill

**Problem:** Killing a parent process (e.g., `node` running an agentic framework) leaves child processes alive. The children continue executing (shell commands, file writes, network calls).

**Fix:**

- `process_kill.py`: Before sending SIGTERM to the parent, enumerate the process group and all descendant PIDs using `psutil.Process(pid).children(recursive=True)`.
- Kill order: children first (leaf to root), then parent. This prevents the parent from respawning children before it dies.
- Add `os.killpg(pgid, signal.SIGTERM)` as a first attempt (kills the whole process group). Fall back to individual PID kill if process group kill fails (not all processes share a group).

### 3.3 Process Group Kill

```python
# Updated process_kill.py
def kill_process_tree(
    pid: int,
    expected_pattern: str | None = None,
    grace_period: float = 3.0,
) -> KillResult:
    """Kill a process and all its descendants."""
    try:
        parent = psutil.Process(pid)
    except psutil.NoSuchProcess:
        return KillResult(pid=pid, success=True, detail="already gone")

    if expected_pattern:
        cmdline = " ".join(parent.cmdline())
        if expected_pattern.lower() not in cmdline.lower():
            return KillResult(pid=pid, success=False, detail="cmdline mismatch, PID reuse suspected")

    children = parent.children(recursive=True)
    all_pids = [c.pid for c in children] + [pid]

    # SIGTERM wave
    for p in children + [parent]:
        try:
            p.send_signal(signal.SIGTERM)
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass

    gone, alive = psutil.wait_procs(children + [parent], timeout=grace_period)

    # SIGKILL survivors
    for p in alive:
        try:
            p.kill()
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass

    return KillResult(pid=pid, success=True, killed_pids=all_pids, detail=f"killed {len(all_pids)} processes")
```

### 3.4 Network Block Improvements

**Problem 1 (Linux):** `iptables --uid-owner` blocks ALL processes for a UID, not just the target. This is a blast radius problem.

**Fix:** On Linux 4.15+, use `cgroup` v2 net_cls to tag the target PID's cgroup, then filter by cgroup tag in iptables. Fall back to UID-owner with a prominent warning if cgroup is unavailable.

**Problem 2 (Windows):** Network blocking is not supported.

**Fix:** Implement `_block_windows()` using Windows Filtering Platform (WFP) via `netsh advfirewall` rules scoped to the process path. Requires admin privileges.

**Problem 3 (Orphaned rules):** If the agent crashes after adding firewall rules, the rules persist forever.

**Fix:**
- On agent startup, clean up stale rules with the `agentic-gov-block` comment/anchor prefix.
- Add a cleanup function that runs on `SIGTERM`/`SIGINT` (graceful shutdown).
- For macOS: `pfctl -a com.agentic-gov.block -F rules` on startup.
- For Linux: `iptables -S OUTPUT | grep agentic-gov-block | ...` on startup.
- Store active rules in agent state (`collector/agent/state.py`) so cleanup knows what to remove.

### 3.5 Enforcement Rate Limiting

**Problem:** A false-positive storm in `active` mode could kill dozens of legitimate processes in rapid succession.

**Fix:**
- Add `max_enforcements_per_minute: int = 5` to posture config.
- The enforcer tracks recent enforcement actions in a sliding window. When the limit is hit, subsequent `block` decisions are downgraded to `audit` and an `enforcement.rate_limited` event is emitted.
- The server is notified via event, and can alert the admin.

### 3.6 Anti-Resurrection (BEH-008 Handling)

**Problem:** A tool with a watchdog/supervisor respawns after being killed. The agent kills it, the watchdog restarts it, the agent detects it again, and the cycle continues.

**Fix:**
- Track "kill history" per process name in agent state. If the same process name is killed 3 times within 5 minutes, escalate:
  1. Kill the supervisor/parent process (identified via ppid chain).
  2. If the process has a systemd unit or launchd plist, disable the unit (requires root).
  3. Emit `enforcement.escalated` event with the full kill chain.

### 3.7 Acceptance Criteria

1. PID verification prevents killing a process whose cmdline doesn't match the expected pattern.
2. Killing a parent process also kills all descendants (verified with a test process tree).
3. Orphaned firewall rules are cleaned up on agent startup.
4. Rate limiting caps enforcement at configured max per minute.
5. A process that respawns 3x is escalated (parent kill + unit disable).
6. Windows network blocking works via `netsh advfirewall`.
7. Linux network blocking uses cgroup tagging when available.

### 3.8 Test Plan

- Unit: `kill_process_tree()` with mock psutil processes. Verify child kill order.
- Unit: PID verification rejects mismatched cmdline.
- Unit: Rate limiter caps enforcement count.
- Unit: Orphaned rule cleanup on startup.
- Integration: End-to-end kill of a multi-process tree (spawn a test tree, kill it, verify all gone).
- Integration: Network block + unblock cycle on macOS and Linux.
- Integration: Resurrection detection and escalation.

### 3.9 Files to Create or Modify

| Action | File | What |
|--------|------|------|
| Create | `collector/enforcement/rate_limiter.py` | Sliding-window rate limiter |
| Create | `collector/enforcement/cleanup.py` | Orphaned rule cleanup on startup |
| Modify | `collector/enforcement/process_kill.py` | `kill_process_tree()`, psutil-based recursive kill, cmdline verification always wired |
| Modify | `collector/enforcement/network_block.py` | Windows support (`netsh`), Linux cgroup tagging, orphaned rule cleanup |
| Modify | `collector/enforcement/enforcer.py` | Pass `expected_pattern`, rate limiting, resurrection tracking |
| Modify | `collector/scanner/base.py` | Add `process_patterns: list[str]` to `ScanResult` |
| Modify | `collector/scanner/*.py` | Each scanner populates `process_patterns` |
| Modify | `collector/main.py` | Pass `process_patterns` to enforcer; call cleanup on startup |
| Modify | `collector/agent/state.py` | Store active enforcement rules for cleanup |

### 3.10 Agent Assignments

- **Senior Developer:** Process tree kill, psutil integration, rate limiter, main.py wiring
- **Security Engineer:** PID verification design, anti-resurrection logic, blast radius analysis
- **Backend Architect:** State persistence for active rules, cleanup on startup
- **Platform Engineer (if available):** Windows WFP integration, Linux cgroup v2 net_cls

---

## Phase 4: Webhook Orchestration and SOC Integration

**Objective:** Connect enforcement events to external SOC tooling so that automated enforcement generates the right alerts, tickets, and audit trail for compliance. The webhook system exists but is only wired to raw events, not enforcement decisions.

**Effort:** ~1-2 weeks
**Prerequisites:** Phase 1 (posture and enforcement events must exist)
**Delivers:** SOC teams can trigger runbooks, create tickets, and page on-call when Detec enforces. Compliance teams get audit-ready enforcement logs.

### 4.1 Enforcement Webhook Events

The existing webhook system (`api/webhooks/dispatcher.py`) dispatches on event type. Add these new event types:

| Event Type | Trigger | Payload Includes |
|------------|---------|-----------------|
| `enforcement.applied` | Agent enforced a `block` decision | Tactic, PIDs killed, tool name, confidence, rule_id, endpoint |
| `enforcement.simulated` | Agent in `audit` mode would have enforced | Same as above, plus `simulated: true` |
| `enforcement.allow_listed` | Enforcement skipped due to allow-list | Tool name, allow-list entry that matched |
| `enforcement.rate_limited` | Rate limiter triggered | Count of suppressed enforcements, time window |
| `enforcement.escalated` | Anti-resurrection escalation | Kill chain, supervisor PID, unit disabled |
| `enforcement.failed` | Enforcement tactic failed (permission denied, etc.) | Tactic, error detail, endpoint |
| `posture.changed` | Admin changed endpoint posture | Old posture, new posture, changed_by, endpoint |

### 4.2 Webhook Payload Schema

Enforcement webhooks use the existing webhook delivery pipeline (HMAC-signed, retry with backoff). The payload is the canonical event JSON with enforcement-specific fields:

```json
{
  "event_type": "enforcement.applied",
  "event_id": "...",
  "observed_at": "2026-03-11T03:14:22Z",
  "endpoint": { "hostname": "prod-db-01", "posture": "active" },
  "tool": { "name": "Unknown Agent", "class": "C", "attribution_confidence": 0.82 },
  "policy": { "decision_state": "block", "rule_id": "ENFORCE-004" },
  "enforcement": {
    "tactic": "process_kill",
    "success": true,
    "pids_killed": [12345, 12346, 12347],
    "process_name": "python3",
    "cmdline_snippet": "python3 agent.py --target prod-db",
    "rate_limited": false
  }
}
```

### 4.3 Pre-Built Webhook Templates

Provide example webhook configurations for common SOC integrations:

- **PagerDuty:** `enforcement.applied` and `enforcement.failed` trigger incidents.
- **Slack/Teams:** `enforcement.simulated` posts to a channel for review.
- **Jira/ServiceNow:** `enforcement.applied` creates a ticket.
- **Splunk HEC:** All enforcement events forwarded for SIEM correlation.

These are documentation examples (`docs/webhook-recipes.md`), not code. The webhook system is already generic enough.

### 4.4 Enforcement Audit Log

The existing audit log (`api/models/audit_log.py`) records API actions (policy changes, user management). Extend it to record:

- Every enforcement action (applied, simulated, failed, escalated).
- Every posture change (who changed it, when, from what to what).
- These entries are queryable from the dashboard audit log page.

### 4.5 Acceptance Criteria

1. Webhooks fire for all enforcement event types.
2. Webhook payloads include full enforcement context (tactic, PIDs, confidence, rule).
3. Posture changes appear in the audit log with the acting user.
4. HMAC signatures validate correctly for enforcement payloads.
5. Webhook delivery retries work for enforcement events (same retry policy as existing events).

### 4.6 Test Plan

- Unit: Webhook dispatcher handles all new event types.
- Unit: Enforcement event payloads match schema.
- Integration: End-to-end: enforcement action triggers webhook delivery.
- Integration: Audit log entries created for posture changes and enforcement actions.

### 4.7 Files to Create or Modify

| Action | File | What |
|--------|------|------|
| Create | `docs/webhook-recipes.md` | PagerDuty, Slack, Jira, Splunk examples |
| Modify | `api/webhooks/dispatcher.py` | Register new enforcement event types |
| Modify | `api/models/audit_log.py` | Enforcement and posture change entries |
| Modify | `api/routers/events.py` | Ensure enforcement events are queryable with type filter |
| Modify | `dashboard/src/pages/AuditLog.tsx` | Show enforcement and posture entries |
| Modify | `schemas/event-schema.json` | Add enforcement event type definitions |

### 4.8 Agent Assignments

- **Backend Architect:** Webhook event types, dispatcher changes, audit log integration
- **Senior Developer:** Event schema extensions, API route updates
- **Frontend Developer:** Audit log UI for enforcement entries
- **Security Engineer:** HMAC verification for enforcement payloads, compliance review

---

## Phase 5: Native OS Telemetry Providers

**Objective:** Replace interval-based polling with event-driven telemetry from native OS security frameworks. This is the difference between "we check every 60 seconds" and "we know within milliseconds." For infrastructure mode, polling is not fast enough: a bot can exfiltrate data in the 60-second gap between polls.

**Effort:** ~8-12 weeks (one provider per platform, staggered)
**Prerequisites:** Phase 2 (behavioral scanner needs richer event data to reach full potential)
**Delivers:** Real-time detection. Sub-second response time from process spawn to enforcement.

### 5.1 Provider Architecture

The `TelemetryProvider` interface (`collector/providers/base.py`) is already designed for this. The `start(store)` method is meant to launch a background thread/process that continuously pushes events into the `EventStore`. The `PollingProvider` is the fallback that uses `poll()` instead.

Each native provider:

1. Runs in a background thread or subprocess.
2. Pushes `ProcessExecEvent`, `NetworkConnectEvent`, `FileChangeEvent` into the shared `EventStore` as they occur.
3. Sets `source` to `"esf"`, `"etw"`, or `"ebpf"` so the behavioral scanner can distinguish real-time from polled events.

### 5.2 macOS: Endpoint Security Framework (ESF)

**File:** `collector/providers/esf_provider.py`

ESF requires a system extension or uses `es_new_client()` via a privileged helper process. The provider:

- Subscribes to `ES_EVENT_TYPE_NOTIFY_EXEC`, `ES_EVENT_TYPE_NOTIFY_OPEN`, `ES_EVENT_TYPE_AUTH_CONNECT`.
- The helper is a small C or Swift binary (`collector/providers/esf_helper/`) that opens the ESF client, receives events, and writes them to a Unix domain socket. The Python provider reads from the socket.
- Requires Full Disk Access (already documented in `docs/macos-permissions.md`) and System Extension approval (requires Apple Developer certificate for distribution).

**Phases within this phase:**
1. Build ESF helper binary (C, ~200 lines).
2. Build `ESFProvider` Python class that reads from the helper's socket.
3. Package helper into the macOS .app bundle.
4. Update PPPC profile for MDM deployment.

**Events captured:**

| ESF Event | Maps To | Detail |
|-----------|---------|--------|
| `ES_EVENT_TYPE_NOTIFY_EXEC` | `ProcessExecEvent` | pid, ppid, binary path, cmdline, username, codesigning info |
| `ES_EVENT_TYPE_NOTIFY_OPEN` | `FileChangeEvent` | path, flags (read/write/create), pid |
| `ES_EVENT_TYPE_AUTH_CONNECT` | `NetworkConnectEvent` | pid, remote addr, remote port, protocol |

### 5.3 Windows: Event Tracing for Windows (ETW)

**File:** `collector/providers/etw_provider.py`

ETW uses kernel trace sessions. The provider:

- Opens a real-time trace session subscribing to:
  - `Microsoft-Windows-Kernel-Process` (process create/terminate)
  - `Microsoft-Windows-Kernel-Network` (TCP connect/disconnect)
  - `Microsoft-Windows-Kernel-File` (file create/write/delete)
- Uses the `pywintrace` or `etw` Python package (or ctypes to `StartTrace`/`ProcessTrace` Win32 APIs).
- Requires admin privileges (the agent service already runs as SYSTEM).

### 5.4 Linux: eBPF

**File:** `collector/providers/ebpf_provider.py`

eBPF programs attach to kernel tracepoints. The provider:

- Attaches eBPF programs to `tracepoint/sched/sched_process_exec`, `tracepoint/net/net_dev_queue`, `tracepoint/syscalls/sys_enter_openat`.
- Uses the `bcc` Python bindings (BPF Compiler Collection) or `libbpf` with a pre-compiled `.o`.
- Requires `CAP_BPF` + `CAP_PERFMON` (or root).
- Falls back to `PollingProvider` if BPF is unavailable (containers without `--privileged`, older kernels).

### 5.5 Provider Registry Changes

`collector/providers/__init__.py` currently has `get_best_provider()` which returns `PollingProvider`. Update to:

```python
def get_best_provider() -> TelemetryProvider:
    """Return the best available provider for the current platform."""
    if sys.platform == "darwin":
        from .esf_provider import ESFProvider
        if ESFProvider().available():
            return ESFProvider()
    elif sys.platform == "win32":
        from .etw_provider import ETWProvider
        if ETWProvider().available():
            return ETWProvider()
    elif sys.platform == "linux":
        from .ebpf_provider import EBPFProvider
        if EBPFProvider().available():
            return EBPFProvider()
    return PollingProvider()
```

### 5.6 Scan Loop Adaptation

With event-driven telemetry, the scan loop changes:

- **Polling mode (current):** `provider.poll()` called each cycle, then scanners run.
- **Event-driven mode:** Provider pushes events continuously. The scan loop still runs on an interval, but the EventStore already has fresh data. No `poll()` call needed.
- **Hybrid trigger:** When the EventStore receives a `ProcessExecEvent` that matches a high-priority pattern (e.g., BEH-001 shell fan-out), it can trigger an immediate out-of-cycle scan. This is the "probe" model: events trigger scans, not timers.

Implementation: Add an optional callback to `EventStore.push_process()`:

```python
class EventStore:
    def __init__(self, ..., on_alert: Callable[[ProcessExecEvent], None] | None = None):
        self._on_alert = on_alert

    def push_process(self, event: ProcessExecEvent) -> None:
        with self._lock:
            self._process_events.append(event)
        if self._on_alert and self._should_alert(event):
            self._on_alert(event)
```

The `_should_alert()` method checks fast heuristics (process name matches known agentic patterns, or shell fan-out threshold exceeded). The callback wakes up the scan loop.

### 5.7 Acceptance Criteria

1. On macOS with ESF available, process exec events appear in EventStore within 100ms of the process starting.
2. On Windows with ETW, same 100ms target.
3. On Linux with eBPF, same 100ms target.
4. If native provider is unavailable, `PollingProvider` is used transparently.
5. The `--telemetry-provider` flag can force a specific provider (`auto|native|polling`).
6. Event-driven scan triggering reduces detection latency from interval (default 60s) to under 5s for high-priority patterns.

### 5.8 Test Plan

- Unit: Each provider's `available()` correctly detects platform support.
- Unit: EventStore alert callback fires for matching events.
- Integration: ESF provider captures real process exec on macOS (requires test VM with SIP partially disabled or approved system extension).
- Integration: ETW provider captures process create on Windows (requires admin).
- Integration: eBPF provider captures exec on Linux (requires privileged container or root).
- Fallback: Verify `PollingProvider` is selected when native is unavailable.

### 5.9 Files to Create or Modify

| Action | File | What |
|--------|------|------|
| Create | `collector/providers/esf_provider.py` | macOS ESF provider |
| Create | `collector/providers/esf_helper/` | C/Swift ESF helper binary + Makefile |
| Create | `collector/providers/etw_provider.py` | Windows ETW provider |
| Create | `collector/providers/ebpf_provider.py` | Linux eBPF provider |
| Create | `collector/providers/ebpf_programs/` | Pre-compiled eBPF .o files or BCC scripts |
| Modify | `collector/providers/__init__.py` | Update `get_best_provider()` registry |
| Modify | `collector/telemetry/event_store.py` | Add `on_alert` callback and `_should_alert()` |
| Modify | `collector/main.py` | Wire alert callback to trigger out-of-cycle scans |
| Modify | `packaging/macos/` | Bundle ESF helper, update entitlements |
| Modify | `docs/macos-permissions.md` | Document System Extension requirement |

### 5.10 Agent Assignments

- **Senior Developer:** ESF helper (C), ESF provider (Python), EventStore callback
- **Platform Engineer:** ETW provider (Windows), eBPF provider (Linux)
- **Backend Architect:** Scan loop adaptation, hybrid trigger design
- **Security Engineer:** Permission model review (SIP, FDA, CAP_BPF), deployment documentation
- **Build Engineer:** Package ESF helper into .app, eBPF programs into Linux packages

### 5.11 Platform Priority

Start with **macOS ESF** (most mature framework, Detec already has macOS .app/.pkg packaging, MDM docs, and FDA requirements documented). Then **Linux eBPF** (server infrastructure is the primary target for active defense). Windows ETW last (enterprise Windows servers are less common as agentic AI targets today).

---

## Phase 6: EDR/MDM Integration for Delegated Enforcement

**Objective:** On endpoints where a full-featured EDR (CrowdStrike, SentinelOne, Defender ATP) or MDM (Jamf, Intune) is already deployed, delegate enforcement to that tool instead of doing it locally. This leverages existing security infrastructure, avoids permission conflicts (two tools trying to kill the same process), and provides defense-in-depth.

**Effort:** Ongoing (one integration at a time)
**Prerequisites:** Phase 1 (posture enum), Phase 4 (webhook orchestration for non-API integrations)
**Delivers:** Detec becomes the "brain" (detection + policy), existing EDR becomes the "muscle" (enforcement).

### 6.1 Architecture

```
Detec Agent (detection)
    ↓ event: block decision
Detec Server (policy, orchestration)
    ↓ API call
EDR/MDM (enforcement)
    ↓ action
Target endpoint (process killed, network blocked, device quarantined)
```

Two integration patterns:

**Pattern A: Server-side API call**
The Detec server calls the EDR's API to enforce. Example: CrowdStrike Real Time Response API to kill a process on a managed host.

**Pattern B: Webhook-triggered**
Detec fires a webhook to an orchestration layer (SOAR, n8n, custom lambda) that calls the EDR/MDM. This uses Phase 4's webhook system.

### 6.2 CrowdStrike Falcon Integration (First Target)

The `api/integrations/` directory already has a CrowdStrike stub for EDR enrichment. Extend it for enforcement:

**Existing:** `api/integrations/crowdstrike.py` (OAuth2 auth, token caching, host lookup for enrichment).

**New capabilities:**
- `initiate_rtr_session(host_id)`: Open a Real Time Response session.
- `rtr_kill_process(session_id, pid)`: Kill a process via RTR.
- `rtr_network_contain(host_id)`: Network-contain the host (complete network isolation except CrowdStrike cloud).
- `rtr_run_script(session_id, script)`: Execute a custom response script.

**Integration flow:**
1. Detec agent detects agentic entity, emits event.
2. Detec server receives event, evaluates server-side policy (may differ from agent-side).
3. If enforcement is needed and the endpoint has EDR configured:
   a. Server looks up the endpoint's CrowdStrike `host_id` (stored in endpoint metadata or queried via hostname).
   b. Server calls CrowdStrike RTR to kill the process or contain the host.
   c. Server records the delegated enforcement in the audit log.
4. If no EDR, falls back to agent-side enforcement (Phase 1/3).

### 6.3 Enforcement Provider Interface

```python
# api/integrations/enforcement_provider.py
class EnforcementProvider(ABC):
    """Interface for delegated enforcement via external security tools."""

    @abstractmethod
    async def kill_process(self, hostname: str, pid: int, process_name: str) -> bool: ...

    @abstractmethod
    async def block_network(self, hostname: str) -> bool: ...

    @abstractmethod
    async def quarantine_endpoint(self, hostname: str) -> bool: ...

    @abstractmethod
    async def available_for_endpoint(self, hostname: str) -> bool: ...
```

### 6.4 MDM Integration (Jamf, Intune)

MDM tools can't kill individual processes, but they can:

- Push a config profile that blocks specific binaries (Jamf restricted software).
- Trigger a remote lock or wipe (extreme response for compromised infrastructure).
- Deploy a script that removes the offending tool.

These are slower (minutes, not seconds) and coarser-grained, but useful as a secondary enforcement layer.

### 6.5 Acceptance Criteria

1. When CrowdStrike is configured and the endpoint is managed, `block` decisions use CrowdStrike RTR to kill the process.
2. If CrowdStrike RTR fails (timeout, permission denied), the system falls back to agent-side enforcement and logs the failure.
3. EDR enforcement actions appear in the Detec audit log.
4. The `EnforcementProvider` interface supports adding new EDR integrations without changing core code.
5. Admin can configure which endpoints use EDR vs. local enforcement from the dashboard.

### 6.6 Test Plan

- Unit: `EnforcementProvider` interface contract tests.
- Unit: CrowdStrike RTR mock tests (token refresh, session lifecycle, kill command).
- Integration: End-to-end with CrowdStrike sandbox API (if available).
- Integration: Fallback path when EDR is unreachable.

### 6.7 Files to Create or Modify

| Action | File | What |
|--------|------|------|
| Create | `api/integrations/enforcement_provider.py` | Abstract enforcement provider interface |
| Create | `api/integrations/enforcement_router.py` | Server-side enforcement orchestration (decide local vs. EDR) |
| Modify | `api/integrations/crowdstrike.py` | Add RTR session management and enforcement methods |
| Modify | `api/models/endpoint.py` | Add `edr_host_id`, `enforcement_provider` columns |
| Modify | `api/core/config.py` | Add EDR enforcement settings (enabled, fallback behavior) |
| Modify | `api/routers/enforcement.py` (from Phase 1) | Add endpoint EDR configuration routes |
| Modify | `dashboard/` | Endpoint detail: EDR status, enforcement provider selector |

### 6.8 Agent Assignments

- **Backend Architect:** Enforcement provider interface, orchestration logic, CrowdStrike RTR integration
- **Security Engineer:** RTR permission scoping, fallback behavior, audit logging
- **Senior Developer:** Endpoint model changes, config extensions
- **Frontend Developer:** EDR status display, enforcement provider config UI

---

## Cross-Cutting Concerns

These apply to all phases and should be maintained throughout implementation.

### Security Threat Model

| Threat | Mitigation | Phase |
|--------|-----------|-------|
| Agent impersonation: attacker sends fake `enforcement.applied` events | Events are authenticated via API key / TCP session. Verify `tenant_id` matches on ingestion. | Existing |
| Privilege escalation: agent runs as root for enforcement | Minimize root usage. Process kill needs kill permission for target UID only. Network block needs firewall access. Use OS capability systems (`CAP_KILL`, `CAP_NET_ADMIN` on Linux) instead of full root. | 3 |
| False positive kill storm | Rate limiter (Phase 3). Allow-list (Phase 1). `audit` mode for burn-in (Phase 1). Confidence threshold (Phase 1). | 1, 3 |
| Enforcement evasion: tool renames binary or changes cmdline | Behavioral scanner (Phase 2) doesn't rely on names. PID verification uses cmdline pattern, not exact match. | 2, 3 |
| Orphaned firewall rules: agent crashes mid-enforcement | Cleanup on startup (Phase 3). Rules tagged with agent identifier for recovery. | 3 |
| EDR credential theft: CrowdStrike API keys stored in Detec server | Store EDR credentials in secrets manager (Vault, AWS Secrets Manager). Never in config files or env vars on disk. Encrypt at rest in DB. | 6 |
| Lateral movement via TCP gateway: attacker compromises one agent, sends commands to others | Agents only receive, never initiate, commands via TCP. Commands require server-side authentication. Agent validates command signatures (future: mTLS on gateway). | 1 |

### Operational Safety: Kill Switches

Every phase includes an immediate way to disable enforcement without redeployment:

| Kill Switch | Scope | How |
|-------------|-------|-----|
| Set endpoint posture to `passive` | Single endpoint | Dashboard toggle or `PUT /api/endpoints/{id}/posture` |
| Set tenant default posture to `passive` | All endpoints in tenant | Dashboard or `PUT /api/enforcement/tenant-posture` |
| Agent `--posture passive` CLI override | Single agent instance | Restart agent with flag (emergency) |
| Rate limiter triggers | Automatic per-agent | After N enforcements/minute, auto-downgrade to audit |
| Server broadcast `POSTURE_PUSH passive` | All connected agents | API call broadcasts passive posture via TCP gateway |

### Event Schema Extensions

The canonical event schema (`schemas/event-schema.json`) needs these additions across phases:

```json
{
  "enforcement": {
    "tactic": "process_kill | network_block | delegated_edr | hold_pending_approval | log_and_alert",
    "success": true,
    "simulated": false,
    "rate_limited": false,
    "allow_listed": false,
    "pids_killed": [12345],
    "process_name": "python3",
    "provider": "local | crowdstrike | sentinelone | webhook",
    "detail": "string"
  },
  "posture": {
    "mode": "passive | audit | active",
    "auto_enforce_threshold": 0.75,
    "source": "server_push | cli_override | config_file"
  }
}
```

### Migration Path

All phases use Alembic migrations for database changes. The migration should be backwards-compatible:

- New columns with defaults (never `NOT NULL` without a default).
- New tables can be added freely.
- Existing API routes are never broken; new routes are added alongside.

### Configuration Compatibility

The agent config loader (`collector/config_loader.py`) already handles graceful fallback for unknown keys. New keys (`enforcement_posture`, `auto_enforce_threshold`) have defaults that match current behavior (`passive`, `0.75`), so existing deployed agents continue to work without config changes.

---

## Recommended Implementation Order

```
Phase 1 (Admin Posture)    ████████████████  2 weeks
Phase 2 (Behavioral)       ████████████████████████████████  4-6 weeks (parallel with P1)
Phase 3 (Hardening)            ████████████████████  2-3 weeks (after P1)
Phase 4 (Webhooks)                 ████████████  1-2 weeks (after P1)
Phase 5 (Native Telemetry)            ████████████████████████████████████████████████  8-12 weeks
Phase 6 (EDR Integration)                                     ████████████████████████  ongoing
```

Phase 1 and Phase 2 can start in parallel because they touch different code paths (enforcement control vs. scanner). Phase 3 depends on Phase 1 (needs the posture enum). Phase 4 depends on Phase 1 (needs enforcement events). Phase 5 is the longest effort and can start after Phase 2 ships (the behavioral scanner benefits most from real-time data). Phase 6 is ongoing and can start after Phase 1 and Phase 4 are in place.

---

## Milestone Integration

This roadmap maps to a new **Milestone M2.5: Active Defense** in `PROGRESS.md`, sitting between M2 (Backend API) and M3 (Frontend SaaS). Phases 1-4 are the core of M2.5. Phases 5 and 6 are long-horizon efforts that extend into M3 and M4.

| Phase | Milestone | Rationale |
|-------|-----------|-----------|
| Phase 1: Admin Posture | M2.5 | Core enforcement control, required for everything else |
| Phase 2: Behavioral Scanner | M2.5 | Detection of unknown agents, the "white blood cell" |
| Phase 3: Enforcement Hardening | M2.5 | Production-grade enforcement safety |
| Phase 4: Webhook Orchestration | M2.5 | SOC integration for enforcement events |
| Phase 5: Native Telemetry | M3/M4 | Long build, requires platform-specific expertise |
| Phase 6: EDR Integration | M4/M5 | Enterprise feature, requires partner APIs |

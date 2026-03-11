# Event-Driven Telemetry Architecture

**Status:** Design  
**Date:** 2026-03-11  
**Scope:** Collector agent, API server, confidence engine, scanner pipeline

---

## 1. Problem

The five-layer detection model (Process, File, Network, Identity, Behavior) is Detec's differentiator. The playbook defines it. The confidence engine scores it. But the collector that feeds it is polling-only: `psutil` snapshots at a configurable interval. This creates three structural gaps that suppress detection fidelity.

### 1.1 Process layer gap

The collector uses `psutil.process_iter()` to enumerate running processes (see `collector/compat/processes.py`). This captures what is running *now*, not what *ran*. Claude Code's child process chains (`claude -> bash -> git -> python`) are sub-second transient. At typical polling intervals they are invisible. The playbook (Section 4.1) acknowledges this: "requires ESF or <1s polling to capture directly." The scanner falls back to artifact-based confirmation (finding `.pytest_cache/`, `.pyc` files), which is really using the File layer as a proxy for Process evidence.

### 1.2 Network layer gap

The collector uses `psutil.net_connections(kind="tcp")` for network snapshots (see `collector/compat/network.py`). Persistent listeners (Ollama `:11434`, OpenClaw `:18789`) and long-lived TLS connections (Cursor, Claude Cowork) are reliably captured. But short-lived HTTPS bursts (Claude Code to `api.anthropic.com`, Copilot to GitHub APIs) complete between polling intervals. The playbook applies a `-0.05` penalty for "polling-based network capture only" and notes repeatedly: "polling-based capture (lsof) cannot reliably attribute to claude PID."

### 1.3 Behavior layer gap

Behavior detection requires observing temporal sequences: prompt-edit-commit loops, shell command orchestration, inference burst cadence, multi-file fan-out writes. A polling agent sees snapshots, not sequences. Each scanner's `_scan_behavior()` method currently infers behavioral patterns from file artifact timestamps (e.g., "3 files created within <5 seconds" deduced from `stat()` results). This is forensic reconstruction, not observation. If the activity happened between scans and left no durable file traces, it is missed entirely.

### 1.4 Confidence impact

These gaps suppress scores below what the evidence warrants. Lab-validated projections from the playbook (Appendix B):

| Tool | Current (polling) | Projected (event-driven) | Band Change |
|------|-------------------|--------------------------|-------------|
| Claude Code | 0.71 (Medium) | ~0.82 (High) | Yes |
| Ollama | 0.69 (Medium) | ~0.79 (High) | Yes |
| Cursor | 0.79 (High) | ~0.85 (High) | No (already High) |
| Copilot (unauth) | 0.45 (Medium) | ~0.55 (Medium) | No |
| Open Interpreter | 0.525 (Medium) | ~0.68 (Medium) | No |

The cross-layer correlation requirement (minimum two aligned layers, at least one Process or Behavior) is weakened when both of those layers have structural collection gaps.

---

## 2. Architecture: Three Telemetry Tiers

The design introduces a **Telemetry Provider** abstraction that decouples scanners from how telemetry is collected. Three provider tiers feed the same event store and scanner interface.

```
┌─────────────────────────────────────────────────────────────────────┐
│                     TELEMETRY PROVIDERS                             │
│                                                                     │
│  ┌───────────────┐  ┌───────────────────┐  ┌────────────────────┐  │
│  │  Tier 1: EDR  │  │  Tier 2: Native   │  │  Tier 3: Polling   │  │
│  │  Integration  │  │  OS Frameworks    │  │  (psutil, always   │  │
│  │  (server-side │  │  ESF / ETW / eBPF │  │  available)        │  │
│  │  enrichment)  │  │  (agent-side)     │  │                    │  │
│  └───────┬───────┘  └────────┬──────────┘  └─────────┬──────────┘  │
└──────────┼───────────────────┼───────────────────────┼──────────────┘
           │                   │                       │
           └───────────────────┼───────────────────────┘
                               │
                    ┌──────────▼──────────┐
                    │    EVENT STORE      │
                    │    (ring buffer)    │
                    │    Typed events:    │
                    │    ProcessExec      │
                    │    NetworkConnect   │
                    │    FileChange       │
                    └──────────┬──────────┘
                               │
              ┌────────────────┼────────────────┐
              │                │                │
    ┌─────────▼──────┐ ┌──────▼───────┐ ┌──────▼───────┐
    │   Scanners     │ │  Behavioral  │ │  PID-to-     │
    │   (query store │ │  Sequence    │ │  Socket      │
    │   not psutil)  │ │  Engine      │ │  Correlation │
    └─────────┬──────┘ └──────┬───────┘ └──────┬───────┘
              │               │                │
              └───────────────┴────────────────┘
                              │
                    ┌─────────▼──────────┐
                    │  SCAN PIPELINE     │
                    │  ScanResult →      │
                    │  Confidence →      │
                    │  Policy → Emit     │
                    └────────────────────┘
```

The scan pipeline (`ScanResult` -> `compute_confidence()` -> `evaluate_policy()` -> emit) is unchanged. The improvement is in the *quality of data* that feeds the scanners.

---

## 3. Tier 1: EDR Integration (Server-Side Enrichment)

Most target organizations already run an EDR (CrowdStrike Falcon, SentinelOne, Microsoft Defender for Endpoint). These platforms collect exactly the telemetry Detec's polling agent cannot: process exec events with full parent-child chains, network connection events attributed to PIDs, and file change events with timestamps. Rather than rebuild this collection infrastructure, Detec consumes it.

### 3.1 Why server-side, not agent-side

EDR platforms expose cloud/server APIs, not local agent APIs. CrowdStrike's Streaming API, SentinelOne's Deep Visibility, and Defender's Advanced Hunting are all queried from a central server. Placing the integration on the Detec API server keeps EDR credentials centralized (not distributed to every endpoint agent), avoids coupling the agent to EDR vendor SDKs, and lets the server correlate EDR telemetry across the fleet.

### 3.2 Integration architecture

New package: `api/integrations/`

```python
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime


@dataclass
class ProcessExecEvent:
    """A process execution event from an external telemetry source."""
    timestamp: datetime
    pid: int
    ppid: int
    name: str
    cmdline: str
    username: str | None = None
    binary_path: str | None = None
    binary_hash: str | None = None


@dataclass
class NetworkConnectEvent:
    """A network connection event from an external telemetry source."""
    timestamp: datetime
    pid: int
    process_name: str
    remote_addr: str
    remote_port: int
    local_port: int
    protocol: str = "tcp"
    sni: str | None = None


@dataclass
class FileChangeEvent:
    """A file system change event from an external telemetry source."""
    timestamp: datetime
    pid: int | None
    path: str
    action: str  # created, modified, deleted, renamed
    process_name: str | None = None


class EDRProvider(ABC):
    """Abstract interface for EDR telemetry providers."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Provider identifier (e.g., 'crowdstrike', 'sentinelone')."""
        ...

    @abstractmethod
    async def query_process_events(
        self,
        endpoint_id: str,
        start: datetime,
        end: datetime,
    ) -> list[ProcessExecEvent]:
        ...

    @abstractmethod
    async def query_network_events(
        self,
        endpoint_id: str,
        start: datetime,
        end: datetime,
    ) -> list[NetworkConnectEvent]:
        ...

    @abstractmethod
    async def query_file_events(
        self,
        endpoint_id: str,
        start: datetime,
        end: datetime,
    ) -> list[FileChangeEvent]:
        ...

    @abstractmethod
    async def resolve_endpoint_id(
        self,
        hostname: str,
        mac_address: str | None = None,
    ) -> str | None:
        """Map a Detec endpoint identifier to the EDR's internal ID."""
        ...
```

### 3.3 Initial provider targets

| EDR | API | Process Events | Network Events | Notes |
|-----|-----|---------------|----------------|-------|
| CrowdStrike Falcon | Streaming API, Event Search API | `ProcessRollup2` events with full parent chain | `NetworkConnectIP4` / `NetworkConnectIP6` with PID | Most common in enterprise. Streaming API provides near-real-time. |
| SentinelOne | Deep Visibility API | Process creation events with lineage | Network connection events with process context | Good process tree visualization. |
| Microsoft Defender | Advanced Hunting (KQL) | `DeviceProcessEvents` table | `DeviceNetworkEvents` table | Native to Microsoft 365 E5 environments. KQL queries are flexible. |

### 3.4 Enrichment flow

When the API server receives a `detection.observed` event from an agent:

1. Extract `endpoint_id` and `observed_at` timestamp from the event
2. Resolve the endpoint in the configured EDR via `resolve_endpoint_id()`
3. Query process exec events and network connect events for a window around `observed_at` (default: 5 minutes before, 1 minute after)
4. Match EDR events against the detection's `tool_name` and `evidence_details` (process names, PIDs, network destinations)
5. Attach matching EDR events to the detection as enrichment
6. Rescore confidence using the enriched signal strengths (higher Process and Network signals, removed penalties)
7. If the rescore crosses a confidence band boundary, re-evaluate policy and emit an `attribution.updated` event

### 3.5 Schema extension

The canonical event schema (`schemas/canonical-event-schema.json`) already has `tool.attribution_sources` as an array of layer names (`["process", "file", "network", "identity", "behavior"]`). The enrichment adds a new top-level field to the event envelope:

```json
{
  "telemetry_providers": [
    {
      "name": "detec-agent",
      "type": "polling",
      "layers": ["process", "file", "network", "identity", "behavior"]
    },
    {
      "name": "crowdstrike",
      "type": "edr",
      "layers": ["process", "network"],
      "query_window": "2026-03-11T10:00:00Z/2026-03-11T10:06:00Z"
    }
  ]
}
```

This makes it explicit which providers contributed to each detection, enabling analysts to understand the evidence chain and its provenance.

### 3.6 Configuration

EDR integration is configured on the Detec server, not the agent. Configuration in `api/.env` or via the dashboard settings UI:

```
EDR_PROVIDER=crowdstrike
EDR_API_BASE=https://api.crowdstrike.com
EDR_CLIENT_ID=<client-id>
EDR_CLIENT_SECRET=<client-secret>
EDR_ENRICHMENT_ENABLED=true
EDR_QUERY_WINDOW_BEFORE_SECONDS=300
EDR_QUERY_WINDOW_AFTER_SECONDS=60
```

The agent requires no changes for Tier 1 enrichment. It continues to emit events via the existing HTTP or TCP transport. The server enriches them transparently.

---

## 4. Tier 2: Native OS Frameworks (Agent-Side)

For environments without an EDR (or as a complement to EDR enrichment), the agent collects event-driven telemetry directly from OS security frameworks. This gives the agent full five-layer fidelity as a standalone sensor.

### 4.1 Platform frameworks

| Platform | Framework | Process Events | Network Events | File Events | Privileges Required |
|----------|-----------|---------------|----------------|-------------|-------------------|
| macOS | Endpoint Security Framework (ESF) | `ES_EVENT_TYPE_NOTIFY_EXEC` with full parent chain, binary path, code signing info | `ES_EVENT_TYPE_NOTIFY_CONNECT` with PID, destination, port | `ES_EVENT_TYPE_NOTIFY_CREATE`, `NOTIFY_WRITE`, `NOTIFY_RENAME`, `NOTIFY_UNLINK` | System extension + `com.apple.developer.endpoint-security.client` entitlement (requires Apple approval) |
| Windows | Event Tracing for Windows (ETW) | `Microsoft-Windows-Kernel-Process` provider: process start/stop with full command line and parent PID | `Microsoft-Windows-Kernel-Network` or WFP: TCP connect with PID | `Microsoft-Windows-Kernel-File` provider | Elevated privileges (Administrator) |
| Linux | eBPF / auditd | `sched_process_exec` tracepoint (eBPF) or `execve` audit rule (auditd) | `tcp_connect` / `inet_sock_set_state` (eBPF) or `connect` audit rule | `inotify` / `fanotify` for targeted directory watches | root for eBPF (kernel 4.18+); root for auditd rule installation |

### 4.2 Provider interface

New package: `collector/providers/`

```python
from abc import ABC, abstractmethod
from typing import Callable

from collector.telemetry.event_store import (
    EventStore,
    ProcessExecEvent,
    NetworkConnectEvent,
    FileChangeEvent,
)


class TelemetryProvider(ABC):
    """Interface for agent-side telemetry providers.

    Providers run in a background thread and push events into the
    shared EventStore. The scan loop queries the store each cycle.
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Provider identifier (e.g., 'esf', 'etw', 'ebpf', 'polling')."""
        ...

    @abstractmethod
    def available(self) -> bool:
        """Check whether this provider can run on the current platform."""
        ...

    @abstractmethod
    def start(self, store: EventStore) -> None:
        """Begin streaming events into the store."""
        ...

    @abstractmethod
    def stop(self) -> None:
        """Stop the provider and release resources."""
        ...
```

### 4.3 Provider negotiation

On startup, the agent probes for available providers and activates the highest-tier one:

```
1. Check for native OS framework availability:
   - macOS: Does the process have ESF entitlement? (check via Security framework)
   - Windows: Can we open an ETW trace session? (attempt to start trace)
   - Linux: Can we load eBPF programs? (check kernel version + CAP_BPF)
   - Fallback Linux: Is auditd available and are we root?

2. If native provider is available and --telemetry-provider is not "polling":
   - Activate native provider
   - Also activate polling provider (as a complement for layers
     the native provider doesn't cover, e.g., Identity)

3. Otherwise:
   - Activate polling provider only (current behavior, no degradation)
```

Config override via `collector/config/collector.json`:

```json
{
  "telemetry_provider": "auto"
}
```

Valid values: `"auto"` (default, probe and pick best), `"native"` (require native, fail if unavailable), `"polling"` (force polling only, useful for testing or constrained environments).

CLI override: `--telemetry-provider native|polling|auto`

### 4.4 ESF implementation notes (macOS)

ESF is the highest-priority native provider because macOS is the primary developer platform for Detec's target market.

The ESF client requires a native binary (C/Objective-C/Swift) linked against the `EndpointSecurity.framework`. Since the Detec collector is Python, the ESF component will be a small companion binary (`detec-esf-helper`) that:

1. Subscribes to `ES_EVENT_TYPE_NOTIFY_EXEC`, `ES_EVENT_TYPE_NOTIFY_CONNECT`, and selected `NOTIFY_*` file events
2. Filters events to relevant process names and paths (to avoid flooding the store with unrelated OS activity)
3. Writes events to a Unix domain socket or named pipe that the Python collector reads
4. The Python `ESFProvider` class connects to the socket, deserializes events, and pushes them into the `EventStore`

This architecture keeps the ESF-specific native code minimal and isolated while letting the rest of the collector remain pure Python.

**Entitlement requirement:** The `com.apple.developer.endpoint-security.client` entitlement requires applying to Apple's developer program. This is the same process that EDR vendors (CrowdStrike, SentinelOne) go through. It is a one-time approval step, not a per-release gate.

### 4.5 Relationship to existing ConfigWatcher

The collector already has an event-driven component: `collector/watchers/config_watcher.py`. It uses `watchdog` to monitor sensitive file paths (`~/.ssh/`, `~/.aws/`, etc.) and queues `ConfigAccessAlert` events when a Class C/D tool is active. This component is currently not wired into `main.py`.

Under the new architecture, `ConfigWatcher` becomes a specialized `FileChangeEvent` source that feeds into the same `EventStore`. Its role narrows to sensitive-path monitoring (a policy concern), while the broader `TelemetryProvider` handles general file system events for tool detection.

---

## 5. Tier 3: Polling (Fallback)

The current `psutil`-based approach (`collector/compat/`) becomes the `PollingProvider`. It implements the same `TelemetryProvider` interface and pushes snapshot-derived events into the `EventStore` each scan cycle.

### 5.1 Mapping polling snapshots to events

When the polling provider runs, it converts `psutil` snapshots into the same typed events that native providers produce:

| psutil call | Event type | Fidelity note |
|-------------|-----------|---------------|
| `psutil.process_iter()` | `ProcessExecEvent` (synthetic) | No parent-child ordering; no events for processes that started and stopped between polls |
| `psutil.net_connections()` | `NetworkConnectEvent` (synthetic) | Only currently-active connections; ephemeral connections missed |
| File `stat()` checks | `FileChangeEvent` (synthetic) | Timestamp-based change detection; no PID attribution |

Events produced by the polling provider carry a `source: "polling"` tag so the confidence engine can apply appropriate penalties (unchanged from current behavior).

### 5.2 When polling is the only provider

In polling-only mode, the system behaves identically to today. The `EventStore` receives polling-derived events, scanners query them, and the confidence engine applies the same penalties it does now. There is no regression.

---

## 6. Agent-Side Event Store

The event store is the central data structure that decouples telemetry collection from telemetry consumption.

### 6.1 Design

New module: `collector/telemetry/event_store.py`

```python
from dataclasses import dataclass, field
from datetime import datetime, timezone
from collections import deque
from threading import Lock
from typing import Literal


@dataclass
class ProcessExecEvent:
    timestamp: datetime
    pid: int
    ppid: int
    name: str
    cmdline: str
    username: str | None = None
    binary_path: str | None = None
    source: str = "unknown"  # "esf", "etw", "ebpf", "polling"


@dataclass
class NetworkConnectEvent:
    timestamp: datetime
    pid: int
    process_name: str
    remote_addr: str
    remote_port: int
    local_port: int
    protocol: str = "tcp"
    sni: str | None = None
    source: str = "unknown"


@dataclass
class FileChangeEvent:
    timestamp: datetime
    path: str
    action: str  # "created", "modified", "deleted", "renamed"
    pid: int | None = None
    process_name: str | None = None
    source: str = "unknown"


class EventStore:
    """Thread-safe ring buffer for telemetry events.

    Providers push events from background threads. Scanners query
    the store during scan cycles. Events older than the retention
    window are automatically evicted.
    """

    def __init__(
        self,
        max_events: int = 10_000,
        retention_seconds: float = 120.0,
    ) -> None:
        self._process_events: deque[ProcessExecEvent] = deque(maxlen=max_events)
        self._network_events: deque[NetworkConnectEvent] = deque(maxlen=max_events)
        self._file_events: deque[FileChangeEvent] = deque(maxlen=max_events)
        self._retention = retention_seconds
        self._lock = Lock()

    def push_process(self, event: ProcessExecEvent) -> None: ...
    def push_network(self, event: NetworkConnectEvent) -> None: ...
    def push_file(self, event: FileChangeEvent) -> None: ...

    def get_process_events(
        self,
        name_pattern: str | None = None,
        since: datetime | None = None,
    ) -> list[ProcessExecEvent]: ...

    def get_network_events(
        self,
        pid: int | None = None,
        remote_addr: str | None = None,
        since: datetime | None = None,
    ) -> list[NetworkConnectEvent]: ...

    def get_file_events(
        self,
        path_prefix: str | None = None,
        since: datetime | None = None,
    ) -> list[FileChangeEvent]: ...

    def has_event_driven_source(self) -> bool:
        """True if any events came from a non-polling source."""
        ...
```

### 6.2 Capacity and eviction

The ring buffer defaults to 10,000 events per event type. At a busy endpoint generating 100 events/second across all types, this covers roughly 100 seconds of history, well beyond a typical scan interval (60-300 seconds).

Events older than `retention_seconds` (default: 120s) are lazily evicted on query. This prevents the store from consuming unbounded memory if the scan loop stalls.

### 6.3 Thread safety

Providers push events from background threads (ESF helper reader, ETW trace callback, `watchdog` observer). Scanners query from the main scan loop thread. The store uses a single lock for all mutations and reads. At expected event volumes (tens to low hundreds per second), lock contention is negligible.

---

## 7. Scanner Integration Changes

Scanners continue to implement `BaseScanner.scan() -> ScanResult` (defined in `collector/scanner/base.py`). The confidence engine and policy engine are unchanged. The change is how scanners access telemetry.

### 7.1 Current scanner pattern

Every scanner follows this pattern (visible in `collector/scanner/claude_code.py`, `cursor.py`, `ollama.py`, etc.):

```python
def scan(self, verbose: bool = False) -> ScanResult:
    result = ScanResult(detected=False, tool_name=self.tool_name, ...)

    # Process layer: direct psutil call
    procs = compat.find_processes(r"claude|claude-cli")
    if procs:
        result.signals.process = 0.85
        result.evidence_details["pids"] = [p.pid for p in procs]

    # Network layer: direct psutil call
    conns = compat.get_connections(pids={p.pid for p in procs})
    if conns:
        result.signals.network = 0.60

    # File layer: os.path / pathlib checks
    # Identity layer: config file parsing
    # Behavior layer: file timestamp inference

    return result
```

### 7.2 Proposed scanner pattern

Scanners receive the `EventStore` and query it for richer data:

```python
def scan(self, verbose: bool = False) -> ScanResult:
    result = ScanResult(detected=False, tool_name=self.tool_name, ...)
    store = self._event_store  # injected via constructor

    # Process layer: event store query (includes exec events from
    # ESF/ETW, not just currently-running processes)
    proc_events = store.get_process_events(
        name_pattern=r"claude|claude-cli",
        since=self._last_scan_time,
    )
    running_procs = compat.find_processes(r"claude|claude-cli")

    if proc_events or running_procs:
        result.signals.process = 0.85
        # With exec events, we can verify parent-child chains
        # that polling alone misses
        if self._has_child_chain(proc_events, parent="claude"):
            result.signals.process = 0.95
            # No missing_parent_child_chain penalty needed

    # Network layer: event store query (includes completed
    # connections that are no longer active)
    net_events = store.get_network_events(
        pid=main_pid,
        since=self._last_scan_time,
    )
    if any(e.remote_addr and "anthropic" in (e.sni or "") for e in net_events):
        result.signals.network = 0.80
        # No unresolved_proc_net_linkage penalty: PID is attributed

    # File, Identity: unchanged (already work well with polling)
    # Behavior: can now use event sequences, not just file timestamps

    return result
```

### 7.3 Injection mechanism

The `EventStore` is created in `main.py` at startup and passed to scanners via constructor injection:

```python
# main.py (modified)
from collector.telemetry.event_store import EventStore
from collector.providers import get_best_provider

store = EventStore()
provider = get_best_provider(args.telemetry_provider)
provider.start(store)

scanners = [
    ClaudeCodeScanner(event_store=store),
    OllamaScanner(event_store=store),
    CursorScanner(event_store=store),
    # ...
]
```

`BaseScanner` gains an optional `event_store` constructor parameter:

```python
class BaseScanner(ABC):
    def __init__(self, event_store: EventStore | None = None) -> None:
        self._event_store = event_store
```

Scanners that haven't been updated to use the event store continue to call `compat.*` directly and behave identically to today.

### 7.4 Backward compatibility

The `EventStore` parameter is optional. If `None`, scanners fall back to direct `compat.*` calls. This means:

- All existing scanners work without modification
- Scanners can be migrated incrementally
- Tests that construct scanners without an event store continue to pass
- The `--telemetry-provider polling` flag produces identical behavior to current code

---

## 8. Behavioral Sequence Engine

A new component that constructs temporal sequences from the event stream and scores behavioral patterns. This replaces the current approach where each scanner infers behavior independently from file artifact timestamps.

### 8.1 Design

New module: `collector/engine/behavior.py`

```python
@dataclass
class BehavioralPattern:
    name: str
    confidence: float  # 0.0 - 1.0
    events: list[ProcessExecEvent | NetworkConnectEvent | FileChangeEvent]
    description: str


class BehaviorEngine:
    """Detects agentic behavioral patterns from event sequences."""

    def analyze(
        self,
        tool_name: str,
        store: EventStore,
        since: datetime,
    ) -> list[BehavioralPattern]:
        ...

    def compute_signal(self, patterns: list[BehavioralPattern]) -> float:
        """Aggregate matched patterns into a single behavior signal."""
        ...
```

### 8.2 Pattern library

| Pattern | Detection Logic | Agentic Indicator |
|---------|----------------|-------------------|
| Shell command orchestration | Parent AI process PID spawns 3+ shell children (`bash`, `sh`, `zsh`) within 10 seconds | Class C autonomous execution |
| Multi-file fan-out write | 3+ `FileChangeEvent(action="created"\|"modified")` with distinct paths within 5 seconds, all from the same parent PID | Agentic code generation |
| Prompt-edit-commit loop | File writes followed by `git add` + `git commit` exec events within 30 seconds, repeating 2+ times | AI-assisted development cycle |
| Inference burst cadence | 3+ `NetworkConnectEvent` to the same endpoint within 10 seconds, with 30-120 second gaps between bursts | LLM API interaction pattern |
| Model download | Large file write to known model storage path (Ollama blobs, LM Studio models) following network transfer | Model provisioning |

### 8.3 Fallback to artifact inference

When the event store contains only polling-derived events (no exec events, no real-time file events), the behavior engine falls back to the current artifact-based approach: checking file modification timestamps, git log history, and other persistent evidence. This is what scanners do today in their `_scan_behavior()` methods. The engine centralizes and standardizes it.

### 8.4 Scanner integration

Scanners that adopt the behavior engine delegate their `_scan_behavior()` logic:

```python
def _scan_behavior(self, result: ScanResult) -> None:
    if self._event_store and self._event_store.has_event_driven_source():
        patterns = self._behavior_engine.analyze(
            self.tool_name, self._event_store, self._last_scan_time
        )
        result.signals.behavior = self._behavior_engine.compute_signal(patterns)
        result.evidence_details["behavioral_patterns"] = [
            p.name for p in patterns
        ]
    else:
        # Existing artifact-based inference (unchanged)
        self._scan_behavior_from_artifacts(result)
```

---

## 9. Process-to-Socket Correlation

The network attribution gap (which PID connected to which endpoint) is a specific, critical problem that warrants dedicated design.

### 9.1 The problem in detail

Claude Code connects to `api.anthropic.com` via short-lived HTTPS requests. By the time the polling agent runs `psutil.net_connections()`, the connection is closed. The scanner sees the Claude Code process running and knows the Anthropic API exists, but cannot prove *this process* connected to *that endpoint*. The playbook applies `-0.10` penalty for "unresolved process-network linkage."

### 9.2 Solution: PID-connection map

With event-driven telemetry (Tier 1 or Tier 2), every network connection event includes the PID that initiated it. The event store accumulates these, and scanners can query: "Did PID 12345 connect to any address matching `*.anthropic.com` in the last 120 seconds?"

The `EventStore.get_network_events(pid=12345)` query returns all connection events for that PID within the retention window, regardless of whether the connection is still active. This is the fundamental difference from polling: the event was recorded when it happened, not when we looked.

### 9.3 Confidence impact

When process-to-socket correlation is available (event-driven source present):

- The `-0.10` "unresolved process-network linkage" penalty is not applied
- The `-0.05` "polling-based network capture only" penalty is not applied
- Network signal strength can increase (scanner has positive evidence of connection, not absence of evidence)

The confidence engine does not need modification. The penalties are applied by scanners (via `BaseScanner._penalize_*` helpers and scanner-specific logic). When scanners have better data, they simply don't add the penalties.

---

## 10. Server-Side EDR Enrichment Pipeline

This section details how the API server processes EDR-enriched detections.

### 10.1 Enrichment as an async pipeline stage

The enrichment is not synchronous with event ingestion. The API server:

1. Receives and stores the agent's detection event immediately (no latency added to the agent)
2. Queues an async enrichment task
3. The enrichment worker queries the configured EDR provider
4. If corroborating evidence is found, the worker creates an `attribution.updated` event linked to the original detection
5. The updated event carries rescored confidence and (if applicable) an updated policy decision

This keeps event ingestion fast and avoids blocking on EDR API latency.

### 10.2 Enrichment data model

```python
@dataclass
class EnrichmentResult:
    provider: str  # "crowdstrike", "sentinelone", "defender"
    query_window_start: datetime
    query_window_end: datetime
    process_events_matched: int
    network_events_matched: int
    file_events_matched: int
    enriched_signals: LayerSignals  # rescored signal strengths
    penalties_removed: list[str]  # penalties no longer applicable
    original_confidence: float
    enriched_confidence: float
    band_changed: bool
```

### 10.3 When enrichment changes the outcome

If the enriched confidence crosses a band boundary (e.g., Medium to High), the server:

1. Re-evaluates policy using the enriched confidence band
2. Emits an `attribution.updated` event with the new confidence and signals
3. If the policy decision changes (e.g., Warn to Approval Required), emits a new `policy.evaluated` event
4. The dashboard reflects the enriched state

If the enriched confidence stays within the same band, the enrichment is recorded but no new policy evaluation is triggered.

---

## 11. Confidence Engine Adjustments

The confidence engine (`collector/engine/confidence.py`) requires minimal changes. The formula (`base_score = sum(weight * signal) - penalties + evasion_boost`) is unchanged. The improvements flow through:

### 11.1 Higher signal strengths from scanners

When scanners have event-driven data, they report higher signal strengths for Process and Network layers because they have positive evidence rather than absence-of-contradiction:

| Layer | Polling Signal (typical) | Event-Driven Signal (typical) | Why |
|-------|-------------------------|-------------------------------|-----|
| Process | 0.85 (running, no child chain) | 0.95 (running + child chain confirmed) | Exec events capture transient children |
| Network | 0.30 (no connections seen) | 0.80 (connections attributed to PID) | Connection events persist beyond socket lifetime |
| Behavior | 0.75 (inferred from artifacts) | 0.90 (observed sequences) | Temporal patterns directly observed |

### 11.2 Fewer penalties

Penalties that exist because of polling limitations are not applied when event-driven data is available. This is handled in scanner code, not in the confidence engine itself:

| Penalty | Value | Removed When |
|---------|-------|-------------|
| `missing_parent_child_chain` | -0.15 | Event-driven source provides exec events with parent PID |
| `unresolved_proc_net_linkage` | -0.10 | Event-driven source provides PID-attributed network events |
| `stale_artifact_only` | -0.10 | Event-driven source confirms tool ran (not just file artifacts) |
| Polling-only network penalty | -0.05 | Event-driven source provides connection events |

### 11.3 Telemetry source tracking in ScanResult

`ScanResult` gains an optional field to indicate what telemetry sources contributed:

```python
@dataclass
class ScanResult:
    # ... existing fields ...
    telemetry_sources: list[str] = field(default_factory=list)
    # e.g., ["esf", "polling"] or ["polling"]
```

This propagates into the event payload via the `telemetry_providers` schema extension (Section 3.5), giving analysts full provenance.

---

## 12. Phasing

### Phase 1: EDR integration on the server side

**Scope:** `api/integrations/` package, CrowdStrike provider, enrichment pipeline, schema extension.

**Why first:** Highest leverage. Most target organizations already run an EDR. Server-side implementation means zero agent changes. Delivers immediate confidence improvement for the Process and Network layers that polling misses. Validates the enrichment model before investing in native OS providers.

**Deliverables:**
- `EDRProvider` interface and CrowdStrike implementation
- Async enrichment pipeline in the API server
- `attribution.updated` event type support
- `telemetry_providers` field in event schema
- Dashboard UI for EDR configuration
- Integration tests with mocked CrowdStrike responses

### Phase 2: Native macOS ESF provider in the agent

**Scope:** `detec-esf-helper` companion binary, `ESFProvider` in `collector/providers/`, `EventStore`, provider negotiation in `main.py`.

**Why second:** macOS is the primary developer platform. ESF provides the richest event data. Addresses the self-contained deployment story (no EDR required). The `EventStore` built here is reused by all subsequent providers.

**Deliverables:**
- `EventStore` implementation
- `TelemetryProvider` interface
- `PollingProvider` (wraps current `compat/` calls)
- `ESFProvider` + `detec-esf-helper` binary
- Provider negotiation logic
- Scanner migration guide (how to update a scanner to use the event store)
- At least one scanner migrated (Claude Code, as the most impacted)

### Phase 3: Windows ETW and Linux eBPF/auditd providers

**Scope:** `ETWProvider`, `EBPFProvider` / `AuditdProvider` in `collector/providers/`.

**Why third:** Completes cross-platform native coverage. ETW and eBPF are well-documented and have Python bindings. auditd provides universal Linux fallback.

**Deliverables:**
- `ETWProvider` implementation
- `EBPFProvider` implementation (kernel 4.18+)
- `AuditdProvider` fallback (all Linux)
- Cross-platform integration tests

### Phase 4: Behavioral Sequence Engine

**Scope:** `collector/engine/behavior.py`, pattern library, scanner integration.

**Why last:** Requires event-driven data to be flowing. Building behavioral pattern detection on top of polling data adds complexity without meaningful improvement over the current artifact-based approach. With Phases 1-3 delivering real event streams, the engine has the data it needs to detect temporal patterns.

**Deliverables:**
- `BehaviorEngine` implementation
- Pattern library (Section 8.2 patterns)
- Scanner migration (delegate `_scan_behavior()` to engine)
- Lab validation: re-run Claude Code and Open Interpreter with the engine active, compare behavioral signal quality to polling baseline

---

## 13. Open Questions

1. **ESF entitlement timeline.** Apple's approval process for `com.apple.developer.endpoint-security.client` can take weeks to months. Should Phase 2 begin with the entitlement application in parallel with development, using a development-only provisioning profile for testing?

2. **EDR API rate limits.** CrowdStrike's Event Search API has rate limits. If Detec processes 100 detection events per minute across a fleet, each triggering an EDR query with a 5-minute window, the query volume could be significant. Should the enrichment pipeline batch queries per endpoint, or implement a cache of recent EDR events?

3. **Dual-source confidence.** When both EDR enrichment (server-side) and native OS events (agent-side) are available for the same detection, which takes precedence? Proposed: agent-side native events are authoritative (they are local, real-time, and don't depend on EDR API availability). EDR enrichment adds corroboration but doesn't override.

4. **Scanner migration order.** Which scanners benefit most from event-driven telemetry and should be migrated first? Proposed priority based on current polling gaps: (1) Claude Code (largest Process + Network gap), (2) Open Interpreter (weakest overall signal, behavior-dependent), (3) Copilot (shared extension host ambiguity).

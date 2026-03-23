"""Thread-safe ring buffer for telemetry events."""

from __future__ import annotations

import logging
import os
import re
import time
from collections import deque
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from threading import Lock
from typing import Callable

logger = logging.getLogger(__name__)

# Rate cap: optional max events per second per type; 0 = disabled.
DEFAULT_RATE_CAP_PER_SECOND = 0
# Burst window (seconds) for smoothing; max events in this window when rate cap enabled.
DEFAULT_BURST_WINDOW_SEC = 0.1
DEFAULT_MAX_EVENTS_PER_BURST = 0  # 0 = use rate_cap_per_second * burst_window_sec


@dataclass
class ProcessExecEvent:
    """A process execution event from a telemetry source."""

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
    """A network connection event from a telemetry source."""

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
    """A file system change event from a telemetry source."""

    timestamp: datetime
    path: str
    action: str  # "created", "modified", "deleted", "renamed"
    pid: int | None = None
    process_name: str | None = None
    source: str = "unknown"


@dataclass
class FileReadEvent:
    """A file read event from a telemetry source (e.g. ESF NOTIFY_OPEN read-only)."""

    timestamp: datetime
    path: str
    pid: int | None = None
    process_name: str | None = None
    source: str = "unknown"


# Process names associated with known agentic AI tools.  Used by
# _should_alert() as a fast heuristic to trigger out-of-cycle scans
# when an event-driven provider delivers a new exec event.
_AGENTIC_PROCESS_PATTERNS: frozenset[str] = frozenset({
    "claude",
    "cursor",
    "ollama",
    "copilot",
    "aider",
    "interpreter",
    "openclaw",
    "continue",
    "gpt-pilot",
    "lm-studio",
    "lmstudio",
    "cline",
    "codex",
    "devin",
    "smol-developer",
    "autogpt",
    "auto-gpt",
    "babyagi",
    "langchain",
    "crewai",
})

_SHELL_NAMES: frozenset[str] = frozenset({
    "bash", "sh", "zsh", "fish", "csh", "tcsh", "dash",
    "cmd", "powershell", "pwsh",
})

# Rapid shell fan-out threshold: if this many shell children from the
# same parent appear within the retention window, it's worth an alert.
_SHELL_FANOUT_ALERT_THRESHOLD = 5


def _default_max_events(max_events: int, per_type: dict[str, int] | None) -> dict[str, int]:
    """Resolve per-type max lengths; missing keys use max_events."""
    out = {
        "process": max_events,
        "network": max_events,
        "file": max_events,
        "file_read": max_events,
    }
    if per_type:
        for k, v in per_type.items():
            if k in out and v is not None and v > 0:
                out[k] = v
    return out


class EventStore:
    """Thread-safe ring buffer for telemetry events.

    Providers push events from background threads. Scanners query
    the store during scan cycles. Events older than the retention
    window are lazily evicted on query.

    When ``on_alert`` is provided, ``push_process()`` calls it (outside
    the lock) for events that match fast agentic-heuristic checks.  The
    callback is intended to wake the scan loop for an immediate
    out-of-cycle scan.

    Optional rate caps limit events per second per type (sliding window);
    when exceeded, the oldest event in the window is dropped (drop oldest
    in window policy). Burst window (e.g. 100 ms) caps spikes.
    """

    def __init__(
        self,
        max_events: int = 10_000,
        retention_seconds: float = 120.0,
        on_alert: Callable[[ProcessExecEvent], None] | None = None,
        max_events_per_type: dict[str, int] | None = None,
        rate_cap_per_second: int | None = None,
        burst_window_seconds: float | None = None,
        max_events_per_burst: int | None = None,
    ) -> None:
        per_type = _default_max_events(max_events, max_events_per_type)
        self._process_events: deque[ProcessExecEvent] = deque(maxlen=per_type["process"])
        self._network_events: deque[NetworkConnectEvent] = deque(maxlen=per_type["network"])
        self._file_events: deque[FileChangeEvent] = deque(maxlen=per_type["file"])
        self._file_read_events: deque[FileReadEvent] = deque(maxlen=per_type["file_read"])
        self._retention = retention_seconds
        self._lock = Lock()
        self._on_alert = on_alert
        # Per-ppid shell child count for fan-out heuristic
        self._shell_children_by_ppid: dict[int, int] = {}
        # Rate cap: sliding window (timestamp list) per type; drop oldest when over cap
        self._rate_cap = rate_cap_per_second if rate_cap_per_second is not None else DEFAULT_RATE_CAP_PER_SECOND
        self._burst_window = burst_window_seconds if burst_window_seconds is not None else DEFAULT_BURST_WINDOW_SEC
        self._max_per_burst = max_events_per_burst if max_events_per_burst is not None else DEFAULT_MAX_EVENTS_PER_BURST
        self._push_times: dict[str, list[float]] = {
            "process": [],
            "network": [],
            "file": [],
            "file_read": [],
        }

    def _rate_limit_allowed(self, event_type: str, now: float | None = None) -> bool:
        """Return True if push is allowed under rate cap. Caller must hold self._lock."""
        if self._rate_cap <= 0:
            return True
        t = (now if now is not None else time.monotonic())
        window = 1.0
        times = self._push_times[event_type]
        cutoff = t - window
        while times and times[0] < cutoff:
            times.pop(0)
        if len(times) >= self._rate_cap:
            return False
        times.append(t)
        if self._burst_window > 0:
            burst_cap = self._max_per_burst or max(1, int(self._rate_cap * self._burst_window))
            burst_cutoff = t - self._burst_window
            burst_count = sum(1 for x in times if x >= burst_cutoff)
            if burst_count > burst_cap:
                times.pop()
                return False
        return True

    def push_process(self, event: ProcessExecEvent) -> None:
        should_alert = False
        with self._lock:
            if not self._rate_limit_allowed("process"):
                return
            self._process_events.append(event)
            should_alert = self._should_alert(event)

        if should_alert and self._on_alert is not None:
            try:
                self._on_alert(event)
            except Exception:
                logger.debug("on_alert callback raised; ignoring", exc_info=True)

    def _should_alert(self, event: ProcessExecEvent) -> bool:
        """Fast heuristic: does this exec event warrant an out-of-cycle scan?

        Must be called while ``self._lock`` is held.  Two checks:
        1. Process name contains a known agentic tool pattern.
        2. Shell fan-out: the same parent spawned >= N shells recently.
        """
        name_lower = os.path.basename(event.name).lower()
        if name_lower.endswith(".exe"):
            name_lower = name_lower[:-4]

        for pattern in _AGENTIC_PROCESS_PATTERNS:
            if pattern in name_lower or pattern in event.cmdline.lower():
                return True

        if name_lower in _SHELL_NAMES:
            count = self._shell_children_by_ppid.get(event.ppid, 0) + 1
            self._shell_children_by_ppid[event.ppid] = count
            if count >= _SHELL_FANOUT_ALERT_THRESHOLD:
                return True

        return False

    def push_network(self, event: NetworkConnectEvent) -> None:
        with self._lock:
            if not self._rate_limit_allowed("network"):
                return
            self._network_events.append(event)

    def push_file(self, event: FileChangeEvent) -> None:
        with self._lock:
            if not self._rate_limit_allowed("file"):
                return
            self._file_events.append(event)

    def push_file_read(self, event: FileReadEvent) -> None:
        with self._lock:
            if not self._rate_limit_allowed("file_read"):
                return
            self._file_read_events.append(event)

    def _evict_old_process(self, cutoff: datetime) -> None:
        while self._process_events and self._process_events[0].timestamp < cutoff:
            self._process_events.popleft()

    def _evict_old_network(self, cutoff: datetime) -> None:
        while self._network_events and self._network_events[0].timestamp < cutoff:
            self._network_events.popleft()

    def _evict_old_file(self, cutoff: datetime) -> None:
        while self._file_events and self._file_events[0].timestamp < cutoff:
            self._file_events.popleft()

    def _evict_old_file_read(self, cutoff: datetime) -> None:
        while self._file_read_events and self._file_read_events[0].timestamp < cutoff:
            self._file_read_events.popleft()

    def get_process_events(
        self,
        name_pattern: str | None = None,
        since: datetime | None = None,
    ) -> list[ProcessExecEvent]:
        with self._lock:
            cutoff = datetime.now(timezone.utc) - timedelta(seconds=self._retention)
            self._evict_old_process(cutoff)

            events = list(self._process_events)

        if since is not None:
            events = [e for e in events if e.timestamp >= since]
        if name_pattern is not None:
            pat = re.compile(name_pattern)
            events = [e for e in events if pat.search(e.name)]
        return events

    def get_network_events(
        self,
        pid: int | None = None,
        remote_addr: str | None = None,
        since: datetime | None = None,
    ) -> list[NetworkConnectEvent]:
        with self._lock:
            cutoff = datetime.now(timezone.utc) - timedelta(seconds=self._retention)
            self._evict_old_network(cutoff)

            events = list(self._network_events)

        if since is not None:
            events = [e for e in events if e.timestamp >= since]
        if pid is not None:
            events = [e for e in events if e.pid == pid]
        if remote_addr is not None:
            events = [e for e in events if e.remote_addr == remote_addr]
        return events

    def get_file_events(
        self,
        path_prefix: str | None = None,
        since: datetime | None = None,
    ) -> list[FileChangeEvent]:
        with self._lock:
            cutoff = datetime.now(timezone.utc) - timedelta(seconds=self._retention)
            self._evict_old_file(cutoff)

            events = list(self._file_events)

        if since is not None:
            events = [e for e in events if e.timestamp >= since]
        if path_prefix is not None:
            events = [e for e in events if e.path.startswith(path_prefix)]
        return events

    def get_file_read_events(
        self,
        path_prefix: str | None = None,
        since: datetime | None = None,
    ) -> list[FileReadEvent]:
        with self._lock:
            cutoff = datetime.now(timezone.utc) - timedelta(seconds=self._retention)
            self._evict_old_file_read(cutoff)

            events = list(self._file_read_events)

        if since is not None:
            events = [e for e in events if e.timestamp >= since]
        if path_prefix is not None:
            events = [e for e in events if e.path.startswith(path_prefix)]
        return events

    def get_event_counts(self) -> dict[str, int]:
        """Return current event counts per type after retention eviction.

        Counts reflect what scanners see (post-eviction). Safe to call from
        any thread; holds the same lock as get_* methods.
        """
        with self._lock:
            cutoff = datetime.now(timezone.utc) - timedelta(seconds=self._retention)
            self._evict_old_process(cutoff)
            self._evict_old_network(cutoff)
            self._evict_old_file(cutoff)
            self._evict_old_file_read(cutoff)
            return {
                "process": len(self._process_events),
                "network": len(self._network_events),
                "file": len(self._file_events),
                "file_read": len(self._file_read_events),
            }
    def has_event_driven_source(self) -> bool:
        """True if any events came from a non-polling source."""
        with self._lock:
            for e in self._process_events:
                if e.source != "polling":
                    return True
            for e in self._network_events:
                if e.source != "polling":
                    return True
            for e in self._file_events:
                if e.source != "polling":
                    return True
            for e in self._file_read_events:
                if e.source != "polling":
                    return True
        return False

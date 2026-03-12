"""Thread-safe ring buffer for telemetry events."""

from __future__ import annotations

import logging
import os
import re
from collections import deque
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from threading import Lock
from typing import Callable

logger = logging.getLogger(__name__)


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


class EventStore:
    """Thread-safe ring buffer for telemetry events.

    Providers push events from background threads. Scanners query
    the store during scan cycles. Events older than the retention
    window are lazily evicted on query.

    When ``on_alert`` is provided, ``push_process()`` calls it (outside
    the lock) for events that match fast agentic-heuristic checks.  The
    callback is intended to wake the scan loop for an immediate
    out-of-cycle scan.
    """

    def __init__(
        self,
        max_events: int = 10_000,
        retention_seconds: float = 120.0,
        on_alert: Callable[[ProcessExecEvent], None] | None = None,
    ) -> None:
        self._process_events: deque[ProcessExecEvent] = deque(maxlen=max_events)
        self._network_events: deque[NetworkConnectEvent] = deque(maxlen=max_events)
        self._file_events: deque[FileChangeEvent] = deque(maxlen=max_events)
        self._retention = retention_seconds
        self._lock = Lock()
        self._on_alert = on_alert
        # Per-ppid shell child count for fan-out heuristic
        self._shell_children_by_ppid: dict[int, int] = {}

    def push_process(self, event: ProcessExecEvent) -> None:
        should_alert = False
        with self._lock:
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
            self._network_events.append(event)

    def push_file(self, event: FileChangeEvent) -> None:
        with self._lock:
            self._file_events.append(event)

    def _evict_old_process(self, cutoff: datetime) -> None:
        while self._process_events and self._process_events[0].timestamp < cutoff:
            self._process_events.popleft()

    def _evict_old_network(self, cutoff: datetime) -> None:
        while self._network_events and self._network_events[0].timestamp < cutoff:
            self._network_events.popleft()

    def _evict_old_file(self, cutoff: datetime) -> None:
        while self._file_events and self._file_events[0].timestamp < cutoff:
            self._file_events.popleft()

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
        return False

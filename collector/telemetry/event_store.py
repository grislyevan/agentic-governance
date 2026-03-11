"""Thread-safe ring buffer for telemetry events."""

from __future__ import annotations

import re
from collections import deque
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from threading import Lock


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


class EventStore:
    """Thread-safe ring buffer for telemetry events.

    Providers push events from background threads. Scanners query
    the store during scan cycles. Events older than the retention
    window are lazily evicted on query.
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

    def push_process(self, event: ProcessExecEvent) -> None:
        with self._lock:
            self._process_events.append(event)

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

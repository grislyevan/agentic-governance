"""Sensitive config-file watcher for agentic governance.

Uses ``watchdog`` to monitor sensitive paths (SSH keys, cloud creds, env
files).  When a Class C/D agent is active AND one of these files is
accessed/modified, the watcher queues an alert for the scan loop to emit
as an escalated detection event.
"""

from __future__ import annotations

import logging
import os
import threading
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from watchdog.events import FileSystemEvent, FileSystemEventHandler
from watchdog.observers import Observer

logger = logging.getLogger(__name__)

SENSITIVE_PATTERNS: list[str] = [
    "~/.ssh/config",
    "~/.ssh/id_rsa",
    "~/.ssh/id_ed25519",
    "~/.ssh/authorized_keys",
    "~/.aws/credentials",
    "~/.aws/config",
    "~/.env",
    "~/.gitconfig",
    "~/.netrc",
    "~/.kube/config",
    "~/.docker/config.json",
]

SENSITIVE_DIRS: list[str] = [
    "~/.ssh",
    "~/.aws",
    "~/.kube",
]


@dataclass
class ConfigAccessAlert:
    """Record of a suspicious config-file access while an agent is active."""

    path: str
    event_type: str  # modified, created, deleted, moved
    timestamp: str
    active_tools: list[str] = field(default_factory=list)


class _SensitiveFileHandler(FileSystemEventHandler):
    """Watchdog handler that records access to sensitive files."""

    def __init__(self, alerts: deque[ConfigAccessAlert], lock: threading.Lock) -> None:
        self._alerts = alerts
        self._lock = lock
        self._active_tools: list[str] = []

    def set_active_tools(self, tools: list[str]) -> None:
        with self._lock:
            self._active_tools = list(tools)

    def _record(self, event: FileSystemEvent, event_type: str) -> None:
        with self._lock:
            if not self._active_tools:
                return
            self._alerts.append(ConfigAccessAlert(
                path=str(event.src_path),
                event_type=event_type,
                timestamp=datetime.now(timezone.utc).isoformat(),
                active_tools=list(self._active_tools),
            ))

    def on_modified(self, event: FileSystemEvent) -> None:
        if not event.is_directory:
            self._record(event, "modified")

    def on_created(self, event: FileSystemEvent) -> None:
        if not event.is_directory:
            self._record(event, "created")

    def on_deleted(self, event: FileSystemEvent) -> None:
        if not event.is_directory:
            self._record(event, "deleted")


class ConfigWatcher:
    """Lifecycle wrapper around watchdog observers for sensitive paths.

    Usage::

        watcher = ConfigWatcher()
        watcher.start()

        # Each scan cycle, update which tools are currently active
        watcher.set_active_tools(["Claude Code", "Aider"])

        # Drain any alerts that occurred since last check
        for alert in watcher.drain_alerts():
            ...

        watcher.stop()
    """

    MAX_ALERTS = 500

    def __init__(self, extra_paths: list[str] | None = None) -> None:
        self._alerts: deque[ConfigAccessAlert] = deque(maxlen=self.MAX_ALERTS)
        self._lock = threading.Lock()
        self._handler = _SensitiveFileHandler(self._alerts, self._lock)
        self._observer = Observer()
        self._watch_dirs = self._resolve_watch_dirs(extra_paths or [])

    @staticmethod
    def _resolve_watch_dirs(extra: list[str]) -> list[str]:
        dirs: set[str] = set()
        for pattern in SENSITIVE_DIRS:
            expanded = os.path.expanduser(pattern)
            if os.path.isdir(expanded):
                dirs.add(expanded)
        for pattern in SENSITIVE_PATTERNS:
            expanded = os.path.expanduser(pattern)
            parent = str(Path(expanded).parent)
            if os.path.isdir(parent):
                dirs.add(parent)
        for p in extra:
            expanded = os.path.expanduser(p)
            if os.path.isdir(expanded):
                dirs.add(expanded)
            elif os.path.isdir(str(Path(expanded).parent)):
                dirs.add(str(Path(expanded).parent))
        return sorted(dirs)

    def start(self) -> None:
        for d in self._watch_dirs:
            try:
                self._observer.schedule(self._handler, d, recursive=False)
                logger.info("Watching sensitive directory: %s", d)
            except OSError as exc:
                logger.warning("Cannot watch %s: %s", d, exc)
        self._observer.start()

    def stop(self) -> None:
        self._observer.stop()
        self._observer.join(timeout=5)

    def set_active_tools(self, tools: list[str]) -> None:
        """Update the set of currently-detected Class C/D tools."""
        self._handler.set_active_tools(tools)

    def drain_alerts(self) -> list[ConfigAccessAlert]:
        """Return and clear all pending alerts."""
        with self._lock:
            alerts = list(self._alerts)
            self._alerts.clear()
        return alerts

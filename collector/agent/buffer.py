"""Local NDJSON event buffer for offline/unreachable-server scenarios.

Events that cannot be delivered to the central API are appended here.
The daemon flushes this queue at the start of each scan cycle before
sending new events, so no telemetry is permanently lost during outages.

Buffer location: ~/.agentic-gov/buffer.ndjson

All read/write operations are protected by an advisory file lock to
prevent data loss when multiple threads or processes access the buffer
concurrently (e.g. heartbeat thread + scan thread in daemon mode).
"""

from __future__ import annotations

import json
import logging
import os
import tempfile
from pathlib import Path
from typing import Any

from agent._filelock import file_lock

logger = logging.getLogger(__name__)

DEFAULT_BUFFER_DIR = Path.home() / ".agentic-gov"
DEFAULT_BUFFER_PATH = DEFAULT_BUFFER_DIR / "buffer.ndjson"
MAX_BUFFER_LINES = 10_000


class LocalBuffer:
    """Append-only NDJSON queue for events that failed HTTP delivery."""

    def __init__(self, path: Path = DEFAULT_BUFFER_PATH) -> None:
        self._path = path
        self._path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        self._lock_path = self._path.with_suffix(".lock")

    def _lock(self):
        """Acquire an advisory file lock for the buffer."""
        return file_lock(str(self._lock_path))

    # ------------------------------------------------------------------
    # Write
    # ------------------------------------------------------------------

    def append(self, event: dict[str, Any]) -> None:
        """Append a single event to the buffer. Never raises."""
        try:
            with self._lock():
                with open(self._path, "a", encoding="utf-8") as f:
                    f.write(json.dumps(event, separators=(",", ":")) + "\n")
                self._trim_if_needed_locked()
        except OSError as exc:
            logger.error("LocalBuffer: failed to write event %s: %s",
                         event.get("event_id", "?"), exc)

    # ------------------------------------------------------------------
    # Read / flush
    # ------------------------------------------------------------------

    def drain(self) -> list[dict[str, Any]]:
        """Read and atomically clear the buffer. Returns all queued events."""
        if not self._path.is_file():
            return []
        events: list[dict[str, Any]] = []
        try:
            with self._lock():
                if not self._path.is_file():
                    return []
                lines = self._path.read_text(encoding="utf-8").splitlines()
                for line in lines:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        events.append(json.loads(line))
                    except json.JSONDecodeError as exc:
                        logger.warning("LocalBuffer: skipping malformed line: %s", exc)
                self._path.unlink(missing_ok=True)
        except OSError as exc:
            logger.error("LocalBuffer: failed to drain: %s", exc)
        return events

    # ------------------------------------------------------------------
    # Housekeeping
    # ------------------------------------------------------------------

    def size(self) -> int:
        """Return number of buffered events (0 if buffer does not exist)."""
        if not self._path.is_file():
            return 0
        try:
            with open(self._path, encoding="utf-8") as f:
                return sum(1 for line in f if line.strip())
        except OSError:
            return 0

    def _trim_if_needed_locked(self) -> None:
        """Drop oldest events if the buffer exceeds MAX_BUFFER_LINES.

        Caller must hold the file lock.
        """
        try:
            if not self._path.is_file():
                return
            with open(self._path, encoding="utf-8") as f:
                lines = f.readlines()
            if len(lines) > MAX_BUFFER_LINES:
                dropped = len(lines) - MAX_BUFFER_LINES
                logger.warning(
                    "LocalBuffer: buffer exceeded %d lines, dropping %d oldest events",
                    MAX_BUFFER_LINES, dropped,
                )
                tmp_fd, tmp_path = tempfile.mkstemp(
                    dir=str(self._path.parent), suffix=".tmp"
                )
                try:
                    with os.fdopen(tmp_fd, "w", encoding="utf-8") as f:
                        f.writelines(lines[dropped:])
                    os.replace(tmp_path, str(self._path))
                except BaseException:
                    os.unlink(tmp_path)
                    raise
        except OSError as exc:
            logger.debug("Could not trim buffer file %s: %s", self._path, exc)

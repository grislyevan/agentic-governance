"""Local NDJSON event buffer for offline/unreachable-server scenarios.

Events that cannot be delivered to the central API are appended here.
The daemon flushes this queue at the start of each scan cycle before
sending new events, so no telemetry is permanently lost during outages.

Buffer location: ~/.agentic-gov/buffer.ndjson
"""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

DEFAULT_BUFFER_DIR = Path.home() / ".agentic-gov"
DEFAULT_BUFFER_PATH = DEFAULT_BUFFER_DIR / "buffer.ndjson"
MAX_BUFFER_LINES = 10_000  # guard against runaway disk usage


class LocalBuffer:
    """Append-only NDJSON queue for events that failed HTTP delivery."""

    def __init__(self, path: Path = DEFAULT_BUFFER_PATH) -> None:
        self._path = path
        self._path.parent.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------
    # Write
    # ------------------------------------------------------------------

    def append(self, event: dict[str, Any]) -> None:
        """Append a single event to the buffer. Never raises."""
        try:
            with open(self._path, "a", encoding="utf-8") as f:
                f.write(json.dumps(event, separators=(",", ":")) + "\n")
            self._trim_if_needed()
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
            lines = self._path.read_text(encoding="utf-8").splitlines()
            for line in lines:
                line = line.strip()
                if not line:
                    continue
                try:
                    events.append(json.loads(line))
                except json.JSONDecodeError as exc:
                    logger.warning("LocalBuffer: skipping malformed line: %s", exc)
            # Clear after successful read
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

    def _trim_if_needed(self) -> None:
        """Drop oldest events if the buffer exceeds MAX_BUFFER_LINES."""
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
                with open(self._path, "w", encoding="utf-8") as f:
                    f.writelines(lines[dropped:])
        except OSError:
            pass

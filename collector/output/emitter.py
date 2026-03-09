"""Writes validated NDJSON events to file or stdout."""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Any

from schema.validator import EventValidator

logger = logging.getLogger(__name__)


class EventEmitter:
    """Validates and writes canonical events as newline-delimited JSON."""

    _SAFE_EXTENSIONS = frozenset({".ndjson", ".jsonl", ".json", ".log"})

    def __init__(
        self,
        output_path: str = "./scan-results.ndjson",
        dry_run: bool = False,
        validator: EventValidator | None = None,
    ) -> None:
        resolved = Path(output_path).resolve()
        if resolved.suffix not in self._SAFE_EXTENSIONS:
            raise ValueError(
                f"Output path '{output_path}' has disallowed extension "
                f"'{resolved.suffix}'. Allowed: {sorted(self._SAFE_EXTENSIONS)}"
            )
        self._output_path = resolved
        self._dry_run = dry_run
        self._validator = validator or EventValidator()
        self._emitted: int = 0
        self._failed: int = 0

    def emit(self, event: dict[str, Any]) -> bool:
        """Validate and write a single event. Returns True on success."""
        errors = self._validator.validate(event)
        if errors:
            self._failed += 1
            logger.error(
                "Event %s failed validation (%d errors): %s",
                event.get("event_id", "unknown"),
                len(errors),
                "; ".join(errors),
            )
            return False

        line = json.dumps(event, separators=(",", ":"))

        if self._dry_run:
            print(json.dumps(event, indent=2))
        else:
            fd = os.open(
                str(self._output_path),
                os.O_WRONLY | os.O_CREAT | os.O_APPEND,
                0o600,
            )
            try:
                os.write(fd, (line + "\n").encode())
            finally:
                os.close(fd)

        self._emitted += 1
        return True

    @property
    def stats(self) -> dict[str, int]:
        return {"emitted": self._emitted, "failed": self._failed}

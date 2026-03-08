"""Writes validated NDJSON events to file or stdout."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from schema.validator import EventValidator

logger = logging.getLogger(__name__)


class EventEmitter:
    """Validates and writes canonical events as newline-delimited JSON."""

    def __init__(
        self,
        output_path: str = "./scan-results.ndjson",
        dry_run: bool = False,
        validator: EventValidator | None = None,
    ) -> None:
        self._output_path = Path(output_path)
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
            with open(self._output_path, "a") as f:
                f.write(line + "\n")

        self._emitted += 1
        return True

    @property
    def stats(self) -> dict[str, int]:
        return {"emitted": self._emitted, "failed": self._failed}

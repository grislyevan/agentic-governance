"""Thread-safe enforcement posture state manager.

Receives posture updates from the server (via TCP POSTURE_PUSH or
heartbeat response) and exposes the current posture to the enforcer
and main scan loop. Persists to disk so posture survives agent restarts.
"""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from threading import Lock
from typing import Any

logger = logging.getLogger(__name__)

_DEFAULT_STATE_DIR = Path.home() / ".agentic-gov"
_POSTURE_FILE = "posture.json"

VALID_POSTURES = frozenset({"passive", "audit", "active"})


class PostureManager:
    """Manages the agent's enforcement posture and allow-list."""

    def __init__(
        self,
        initial_posture: str = "passive",
        initial_threshold: float = 0.75,
        state_dir: Path | None = None,
    ) -> None:
        self._lock = Lock()
        self._state_dir = state_dir or _DEFAULT_STATE_DIR
        self._state_dir.mkdir(parents=True, exist_ok=True)
        self._path = self._state_dir / _POSTURE_FILE

        persisted = self._load()
        self._posture: str = persisted.get("posture", initial_posture)
        self._threshold: float = persisted.get("auto_enforce_threshold", initial_threshold)
        self._allow_list: list[str] = persisted.get("allow_list", [])
        self._source: str = persisted.get("source", "config")

        if self._posture not in VALID_POSTURES:
            logger.warning("Invalid persisted posture %r, falling back to passive", self._posture)
            self._posture = "passive"

    @property
    def posture(self) -> str:
        with self._lock:
            return self._posture

    @property
    def auto_enforce_threshold(self) -> float:
        with self._lock:
            return self._threshold

    @property
    def allow_list(self) -> list[str]:
        with self._lock:
            return list(self._allow_list)

    @property
    def source(self) -> str:
        with self._lock:
            return self._source

    def update(
        self,
        posture: str,
        auto_enforce_threshold: float | None = None,
        allow_list: list[str] | None = None,
        source: str = "server_push",
    ) -> None:
        """Apply a posture update (typically from server push)."""
        if posture not in VALID_POSTURES:
            logger.warning("Rejecting invalid posture %r", posture)
            return

        with self._lock:
            old = self._posture
            self._posture = posture
            self._source = source
            if auto_enforce_threshold is not None:
                self._threshold = auto_enforce_threshold
            if allow_list is not None:
                self._allow_list = list(allow_list)
            self._save()

        if old != posture:
            logger.info("Enforcement posture changed: %s -> %s (source=%s)", old, posture, source)

    def is_allow_listed(self, tool_name: str) -> bool:
        """Check if a tool name matches any allow-list pattern (case-insensitive substring)."""
        with self._lock:
            patterns = list(self._allow_list)
        name_lower = tool_name.lower()
        return any(p.lower() in name_lower for p in patterns)

    def _load(self) -> dict[str, Any]:
        if not self._path.is_file():
            return {}
        try:
            return json.loads(self._path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as exc:
            logger.warning("Could not load posture state from %s: %s", self._path, exc)
            return {}

    def _save(self) -> None:
        try:
            data = {
                "posture": self._posture,
                "auto_enforce_threshold": self._threshold,
                "allow_list": self._allow_list,
                "source": self._source,
            }
            self._path.write_text(json.dumps(data, indent=2), encoding="utf-8")
            os.chmod(self._path, 0o600)
        except OSError as exc:
            logger.error("Could not save posture state to %s: %s", self._path, exc)

"""Per-tool state tracking for the persistent endpoint agent.

StateDiffer compares each new scan result against the last-emitted state
and decides whether to emit events. This prevents flooding the central API
with identical observations every scan cycle.

A "material change" is defined as any of:
  - Tool newly detected (was absent, now present)
  - Tool no longer detected (was present, now absent)
  - tool_class escalated (e.g., A → C, C → D)
  - decision_state changed (e.g., warn → approval_required → block)
  - attribution_confidence crossed a band boundary (Low/Medium/High)

State is persisted to ~/.agentic-gov/state.json so it survives restarts.
"""

from __future__ import annotations

import json
import logging
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

try:
    from collector.agent._filelock import file_lock
except ImportError:
    from agent._filelock import file_lock

logger = logging.getLogger(__name__)

DEFAULT_STATE_DIR = Path.home() / ".agentic-gov"
DEFAULT_STATE_PATH = DEFAULT_STATE_DIR / "state.json"

# Class ordinal for escalation detection (higher = more autonomous)
CLASS_ORDINAL: dict[str, int] = {"A": 1, "B": 2, "C": 3, "D": 4}

# Decision state ordinal for escalation detection
DECISION_ORDINAL: dict[str, int] = {
    "detect": 1,
    "warn": 2,
    "approval_required": 3,
    "block": 4,
}

# Confidence band boundaries (matches Playbook Section 6.2)
def _confidence_band(score: float | None) -> str:
    if score is None:
        return "unknown"
    if score >= 0.75:
        return "High"
    if score >= 0.45:
        return "Medium"
    return "Low"


@dataclass
class ToolState:
    """Snapshot of the last-emitted state for a single tool."""

    tool_name: str
    tool_class: str
    confidence: float
    confidence_band: str
    decision_state: str | None
    detected: bool


class StateDiffer:
    """Tracks last-emitted tool states and filters redundant observations."""

    def __init__(
        self,
        state_path: Path = DEFAULT_STATE_PATH,
        report_all: bool = False,
    ) -> None:
        self._path = state_path
        self._report_all = report_all
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._lock_path = self._path.with_suffix(".lock")
        self._states: dict[str, ToolState] = self._load()

    def _lock(self):
        return file_lock(str(self._lock_path))

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def is_changed(
        self,
        tool_name: str,
        tool_class: str,
        confidence: float,
        decision_state: str | None,
        detected: bool,
    ) -> tuple[bool, list[str]]:
        """Return (should_emit, reasons).

        reasons is a list of human-readable change descriptions.
        When report_all=True, always returns (True, []).
        """
        if self._report_all:
            return True, []

        prev = self._states.get(tool_name)

        # Tool just appeared
        if not prev:
            if detected:
                return True, ["newly detected"]
            return False, []

        # Tool no longer detected
        if prev.detected and not detected:
            return True, ["no longer detected"]

        # Tool still absent — nothing to report
        if not prev.detected and not detected:
            return False, []

        reasons: list[str] = []

        # Class escalation
        prev_ord = CLASS_ORDINAL.get(prev.tool_class, 0)
        curr_ord = CLASS_ORDINAL.get(tool_class, 0)
        if curr_ord > prev_ord:
            reasons.append(
                f"class escalated {prev.tool_class} → {tool_class}"
            )

        # Decision state change (any direction)
        prev_dec = DECISION_ORDINAL.get(prev.decision_state or "", 0)
        curr_dec = DECISION_ORDINAL.get(decision_state or "", 0)
        if curr_dec != prev_dec:
            reasons.append(
                f"decision changed {prev.decision_state} → {decision_state}"
            )

        # Confidence band crossed
        prev_band = prev.confidence_band
        curr_band = _confidence_band(confidence)
        if curr_band != prev_band:
            reasons.append(
                f"confidence band {prev_band} → {curr_band} ({confidence:.2f})"
            )

        return (bool(reasons), reasons)

    def update(
        self,
        tool_name: str,
        tool_class: str,
        confidence: float,
        decision_state: str | None,
        detected: bool,
    ) -> None:
        """Update stored state after a successful emission."""
        self._states[tool_name] = ToolState(
            tool_name=tool_name,
            tool_class=tool_class,
            confidence=confidence,
            confidence_band=_confidence_band(confidence),
            decision_state=decision_state,
            detected=detected,
        )
        self._save()

    def cleared_tools(
        self,
        currently_detected: set[str],
        scan_failures: set[str] | None = None,
    ) -> list[str]:
        """Return names of tools that were previously detected but are now absent.

        Tools in *scan_failures* are excluded: a scanner error is not the
        same as the tool being genuinely gone.
        """
        excluded = currently_detected | (scan_failures or set())
        return [
            name
            for name, state in self._states.items()
            if state.detected and name not in excluded
        ]

    def get_last_class(self, tool_name: str) -> str:
        """Return the last-known tool_class, or 'A' if unknown."""
        state = self._states.get(tool_name)
        return state.tool_class if state else "A"

    def mark_cleared(self, tool_name: str) -> None:
        """Record that a tool is no longer detected."""
        prev = self._states.get(tool_name)
        if prev:
            self._states[tool_name] = ToolState(
                tool_name=prev.tool_name,
                tool_class=prev.tool_class,
                confidence=0.0,
                confidence_band="Low",
                decision_state=None,
                detected=False,
            )
            self._save()

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    def _load(self) -> dict[str, ToolState]:
        if not self._path.is_file():
            return {}
        try:
            raw: dict[str, Any] = json.loads(self._path.read_text(encoding="utf-8"))
            result: dict[str, ToolState] = {}
            for name, data in raw.items():
                try:
                    result[name] = ToolState(**data)
                except (TypeError, KeyError) as exc:
                    logger.warning("StateDiffer: skipping malformed entry for %s: %s", name, exc)
            logger.debug("StateDiffer: loaded %d tool states from %s", len(result), self._path)
            return result
        except (json.JSONDecodeError, OSError) as exc:
            logger.warning("StateDiffer: could not load state file %s: %s", self._path, exc)
            return {}

    def _save(self) -> None:
        try:
            data = {name: asdict(state) for name, state in self._states.items()}
            with self._lock():
                self._path.write_text(
                    json.dumps(data, indent=2), encoding="utf-8"
                )
        except OSError as exc:
            logger.error("StateDiffer: could not save state to %s: %s", self._path, exc)

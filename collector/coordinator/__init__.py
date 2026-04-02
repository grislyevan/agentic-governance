"""Coordinator sub-package: focused modules extracted from orchestrator.py.

Each coordinator handles one concern of the scan pipeline:
  scan_coordinator     -- scanner dispatch, correlation, session timelines
  scoring_coordinator  -- confidence scoring, policy evaluation, suppression
  emission_coordinator -- event building, emit, IPC broadcast, enforcement
"""

from coordinator.scan_coordinator import ScanBatch, collect_scan_batch
from coordinator.scoring_coordinator import ScoringResult, score_detection
from coordinator.emission_coordinator import emit_detection, emit_cleared_events

__all__ = [
    "ScanBatch",
    "collect_scan_batch",
    "ScoringResult",
    "score_detection",
    "emit_detection",
    "emit_cleared_events",
]

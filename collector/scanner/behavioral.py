"""Behavioral anomaly scanner: detects agentic AI entities by behavioral pattern.

Runs AFTER all named scanners. If a named scanner already detected the same
process tree, the behavioral scanner skips it (deduplication by PID set).
Sets tool_name to "Unknown Agent" and populates evidence_details with which
behavioral patterns matched.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import TYPE_CHECKING, Any

from .base import BaseScanner, LayerSignals, ScanResult
from .behavioral_patterns import (
    PatternMatch,
    detect_all_patterns,
    get_llm_hosts,
    update_llm_hosts,
)
from .process_tree import ProcessNode, build_trees, get_all_pids, tree_depth

if TYPE_CHECKING:
    from telemetry.event_store import EventStore

logger = logging.getLogger(__name__)

_CONFIG_PATH = Path(__file__).resolve().parent.parent / "config" / "behavioral.json"


def _load_behavioral_config() -> dict[str, Any]:
    """Load behavioral.json, returning empty dict on failure."""
    if not _CONFIG_PATH.is_file():
        return {}
    try:
        with open(_CONFIG_PATH) as fh:
            data = json.load(fh)
        if isinstance(data, dict):
            return data
    except (json.JSONDecodeError, OSError) as exc:
        logger.warning("Cannot read behavioral config %s: %s", _CONFIG_PATH, exc)
    return {}


def _flatten_thresholds(config: dict[str, Any]) -> dict[str, Any]:
    """Flatten nested per-pattern dicts into a single threshold dict.

    Converts {"BEH-001": {"shell_fanout_window_seconds": 60}, ...}
    into {"shell_fanout_window_seconds": 60, ...}.
    """
    flat: dict[str, Any] = {}
    for key, value in config.items():
        if isinstance(value, dict):
            flat.update(value)
        elif not key.startswith("_") and key != "config_version":
            flat[key] = value
    return flat


class BehavioralScanner(BaseScanner):
    """Detect agentic entities by behavioral pattern, not tool name."""

    def __init__(
        self,
        event_store: EventStore | None = None,
        *,
        exclude_pids: set[int] | None = None,
    ) -> None:
        super().__init__(event_store=event_store)
        self._exclude_pids = exclude_pids or set()
        self._config = _load_behavioral_config()
        self._thresholds = _flatten_thresholds(self._config)

        custom_hosts = self._config.get("custom_llm_hosts", [])
        if custom_hosts:
            update_llm_hosts(set(custom_hosts))

    @property
    def tool_name(self) -> str:
        return "Unknown Agent"

    @property
    def tool_class(self) -> str:
        return "C"

    def scan(self, verbose: bool = False) -> ScanResult:
        result = ScanResult(
            detected=False,
            tool_name=self.tool_name,
            tool_class=self.tool_class,
        )

        if not self._config.get("enabled", True):
            self._log("Behavioral scanner disabled by config", verbose)
            return result

        if self._event_store is None:
            self._log("No event store available", verbose)
            return result

        detection_threshold = self._thresholds.get("detection_threshold", 0.45)

        trees = build_trees(self._event_store)
        self._log(f"Built {len(trees)} process trees", verbose)

        # Filter out trees already detected by named scanners
        candidate_trees: list[ProcessNode] = []
        for tree in trees:
            tree_pids = get_all_pids(tree)
            if tree_pids & self._exclude_pids:
                self._log(
                    f"Skipping tree rooted at PID {tree.pid} (already detected by named scanner)",
                    verbose,
                )
                continue
            candidate_trees.append(tree)

        if not candidate_trees:
            self._log("No candidate trees after PID dedup", verbose)
            return result

        # Score each tree independently, keep the highest-scoring one
        best_score = 0.0
        best_matches: list[PatternMatch] = []
        best_tree: ProcessNode | None = None

        for tree in candidate_trees:
            matches = detect_all_patterns(tree, self._thresholds)
            if not matches:
                continue

            aggregate = self._aggregate_score(matches)
            if aggregate > best_score:
                best_score = aggregate
                best_matches = matches
                best_tree = tree

        if best_score < detection_threshold or best_tree is None:
            self._log(
                f"Best aggregate score {best_score:.2f} below threshold {detection_threshold}",
                verbose,
            )
            return result

        result.detected = True
        result.signals = self._build_signals(best_matches)
        result.evidence_details = self._build_evidence(best_matches, best_tree)
        result.process_patterns = [best_tree.name]

        # Upgrade to class D if resurrection pattern matched
        for m in best_matches:
            if m.pattern_id == "BEH-008" and m.score > 0:
                result.tool_class = "D"
                break

        result.action_type = "exec"
        result.action_risk = self._determine_risk(best_matches)
        result.action_summary = self._build_summary(best_matches)

        self._apply_penalties(result, best_matches)

        self._log(
            f"DETECTED: aggregate={best_score:.2f}, patterns={len(best_matches)}, "
            f"tree_root=PID {best_tree.pid} ({best_tree.name})",
            verbose,
        )

        return result

    def _aggregate_score(self, matches: list[PatternMatch]) -> float:
        """Weighted aggregate of pattern scores.

        Behavior-dominant patterns (BEH-001 shell fan-out, BEH-005 session
        duration) get a slight boost since they are the strongest agentic
        indicators.
        """
        if not matches:
            return 0.0

        # Weight multipliers for aggregation (not the same as confidence layer weights)
        pattern_weights = {
            "BEH-001": 1.2,
            "BEH-002": 1.0,
            "BEH-003": 1.0,
            "BEH-004": 1.1,
            "BEH-005": 1.1,
            "BEH-006": 0.9,
            "BEH-007": 0.8,
            "BEH-008": 1.0,
        }

        weighted_sum = sum(
            m.score * pattern_weights.get(m.pattern_id, 1.0)
            for m in matches
        )
        max_possible = sum(pattern_weights.values())
        return min(1.0, weighted_sum / max_possible)

    def _build_signals(self, matches: list[PatternMatch]) -> LayerSignals:
        """Map pattern matches to layer signal strengths."""
        layer_scores: dict[str, list[float]] = {
            "process": [],
            "file": [],
            "network": [],
            "identity": [],
            "behavior": [],
        }

        for m in matches:
            for layer in m.layers:
                if layer in layer_scores:
                    layer_scores[layer].append(m.score)

        return LayerSignals(
            process=max(layer_scores["process"], default=0.0),
            file=max(layer_scores["file"], default=0.0),
            network=max(layer_scores["network"], default=0.0),
            identity=max(layer_scores["identity"], default=0.0),
            behavior=max(layer_scores["behavior"], default=0.0),
        )

    def _build_evidence(
        self, matches: list[PatternMatch], tree: ProcessNode,
    ) -> dict[str, Any]:
        return {
            "behavioral_patterns": [
                {
                    "pattern_id": m.pattern_id,
                    "pattern_name": m.pattern_name,
                    "score": m.score,
                    "evidence": m.evidence,
                }
                for m in matches
            ],
            "root_process": {
                "pid": tree.pid,
                "name": tree.name,
                "cmdline": tree.cmdline,
            },
            "tree_pids": sorted(get_all_pids(tree)),
            "tree_depth": tree_depth(tree),
        }

    def _determine_risk(self, matches: list[PatternMatch]) -> str:
        pattern_ids = {m.pattern_id for m in matches}
        # Credential access or resurrection = high risk
        if "BEH-006" in pattern_ids or "BEH-008" in pattern_ids:
            return "R3"
        # Shell fan-out + LLM cadence = moderate-high
        if "BEH-001" in pattern_ids and "BEH-002" in pattern_ids:
            return "R3"
        if len(matches) >= 3:
            return "R3"
        return "R2"

    def _build_summary(self, matches: list[PatternMatch]) -> str:
        names = [m.pattern_name for m in matches]
        return f"Behavioral detection: {', '.join(names)}"

    def _apply_penalties(self, result: ScanResult, matches: list[PatternMatch]) -> None:
        """Apply behavioral-specific penalties."""
        has_file = result.signals.file > 0
        has_network = result.signals.network > 0
        has_process = result.signals.process > 0

        # behavioral_only_no_file_artifact: if only process + network patterns
        # match without file evidence, reduce confidence to limit false positives
        # from legitimate automation (CI pipelines, cron jobs)
        if has_process and has_network and not has_file:
            result.penalties.append(("behavioral_only_no_file_artifact", 0.15))

        self._penalize_weak_identity(result, threshold=0.3, amount=0.10)

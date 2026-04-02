"""scan_coordinator: scanner dispatch, correlation, and session timeline building.

Extracted from orchestrator.py to isolate all scanning concerns:
  - Running named scanners and collecting results
  - BehavioralScanner (with PID dedup)
  - EvasionScanner and tamper vector extraction
  - MCPScanner
  - Scheduler artifact injection
  - Process tree correlation (CorrelationHintsEngine, enrichment_for_tree)
  - Fragment cache / possible continuations
  - Session timeline building per detection
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from engine.correlation import compute_correlation
from correlation import CorrelationHintsEngine, enrichment_for_tree
from scanner.process_tree import ProcessNode, build_trees, get_all_pids
from session.fragment_cache import FragmentCache, fragment_from_tree
from telemetry.capabilities import get_capabilities_from_store, merge_capabilities
from telemetry.capability_drift import check_drift
from telemetry.diagnostics import DiagnosticsAccumulator
from telemetry.event_store import EventStore
from engine.session_timeline import build_session_timeline
from scanner.base import LayerSignals, ScanResult
from scanner.scheduler_artifacts import get_scheduler_evidence_by_tool

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Public result dataclass
# ---------------------------------------------------------------------------


@dataclass
class ScanBatch:
    """All outputs produced by one full scanner pass."""

    detected_scans: list[ScanResult] = field(default_factory=list)
    scan_failures: set[str] = field(default_factory=set)
    detected_tool_names: set[str] = field(default_factory=set)
    # raw scan results for special scanners (may be None if not run / exception)
    evasion_scan: ScanResult | None = None
    mcp_scan: ScanResult | None = None
    # correlation_map: tool_name -> list of correlated tool names
    correlation_context: dict[str, list[str]] = field(default_factory=dict)
    # per-scan enrichment (parallel lists aligned to detected_scans)
    cross_tree_correlation: list[dict[str, Any] | None] = field(default_factory=list)
    session_timelines: list[list[dict[str, str]]] = field(default_factory=list)
    possible_continuations: list[dict[str, Any] | None] = field(default_factory=list)
    # tamper vectors from evasion + capability drift
    tamper_vectors: list[str] = field(default_factory=list)
    # agent_status produced from diagnostics
    agent_status: dict[str, Any] = field(default_factory=dict)
    # fidelity label when telemetry was degraded
    telemetry_fidelity: str | None = None
    # diagnostics accumulator (caller may need it)
    diagnostics: DiagnosticsAccumulator | None = None


# ---------------------------------------------------------------------------
# Internal helper (also re-exported via orchestrator for backward compat)
# ---------------------------------------------------------------------------


def _normalize_pid(value: object) -> int | None:
    """Coerce a PID from int or numeric string, returning None if invalid."""
    if isinstance(value, int):
        return value if value > 1 else None
    if isinstance(value, str) and value.strip().isdigit():
        pid = int(value.strip())
        return pid if pid > 1 else None
    return None


def _extract_pids(scan: ScanResult) -> set[int]:
    """Pull process IDs from scan evidence for enforcement targeting."""
    pids: set[int] = set()
    for entry in scan.evidence_details.get("process_entries", []):
        pid = _normalize_pid(entry.get("pid"))
        if pid is not None:
            pids.add(pid)
    for key in ("listener_pid", "ipykernel_pid"):
        pid = _normalize_pid(scan.evidence_details.get(key))
        if pid is not None:
            pids.add(pid)
    return pids


# ---------------------------------------------------------------------------
# collect_scan_results (was _collect_scan_results in orchestrator.py)
# ---------------------------------------------------------------------------


def collect_scan_results(
    scanners: list[Any],
    verbose: bool,
) -> tuple[list[ScanResult], set[str], set[str]]:
    """Run all scanners and partition results into detections vs failures."""
    detected: list[ScanResult] = []
    detected_names: set[str] = set()
    failures: set[str] = set()

    for scanner in scanners:
        if verbose:
            print(f"\n--- Scanning for {scanner.tool_name} ---")

        try:
            scan = scanner.scan(verbose=verbose)
        except Exception:
            logger.warning(
                "Scanner %s raised an exception; treating as inconclusive",
                scanner.tool_name,
                exc_info=True,
            )
            failures.add(scanner.tool_name)
            continue

        if not scan.detected:
            if verbose:
                print(f"  {scanner.tool_name}: Not detected")
            continue

        detected.append(scan)
        detected_names.add(scan.tool_name)

    return detected, detected_names, failures


# ---------------------------------------------------------------------------
# collect_scan_batch: top-level entry point
# ---------------------------------------------------------------------------


def collect_scan_batch(
    scanners: list[Any],
    *,
    event_store: EventStore,
    provider: Any,
    verbose: bool,
    telemetry_fidelity: str | None = None,
    fragment_cache: FragmentCache | None = None,
    behavioral_scanner_cls: Any = None,
    evasion_scanner_cls: Any = None,
    mcp_scanner_cls: Any = None,
) -> ScanBatch:
    """Run all scanners and produce a fully-populated ScanBatch.

    Parameters
    ----------
    scanners:
        The list of named scanner instances (13 standard scanners).
    event_store:
        The telemetry event store for behavioral/evasion scanners.
    provider:
        The telemetry provider (used to extract capabilities).
    verbose:
        Whether to print scanner output.
    telemetry_fidelity:
        Optional label when the provider is degraded (e.g. "polling fallback").
    fragment_cache:
        Persistent FragmentCache across cycles. If None a temporary one is created.
    behavioral_scanner_cls / evasion_scanner_cls / mcp_scanner_cls:
        Injectable scanner classes (allows orchestrator to pass its own
        namespace references so test patches on ``orchestrator.BehavioralScanner``
        etc. are honoured).
    """
    if behavioral_scanner_cls is None:
        from scanner.behavioral import BehavioralScanner

        behavioral_scanner_cls = BehavioralScanner
    if evasion_scanner_cls is None:
        from scanner.evasion import EvasionScanner

        evasion_scanner_cls = EvasionScanner
    if mcp_scanner_cls is None:
        from scanner.mcp import MCPScanner

        mcp_scanner_cls = MCPScanner

    batch = ScanBatch(telemetry_fidelity=telemetry_fidelity)

    # ------------------------------------------------------------------
    # Stage 1a: named scanners
    # ------------------------------------------------------------------
    detected_scans, detected_tools, scan_failures = collect_scan_results(
        scanners, verbose
    )
    batch.detected_scans = detected_scans
    batch.detected_tool_names = detected_tools
    batch.scan_failures = scan_failures

    # ------------------------------------------------------------------
    # Stage 1b: BehavioralScanner (PID dedup)
    # ------------------------------------------------------------------
    named_pids: set[int] = set()
    for scan in detected_scans:
        named_pids.update(_extract_pids(scan))

    behavioral = behavioral_scanner_cls(
        event_store=event_store, exclude_pids=named_pids
    )
    provider_cap = provider.capabilities()
    store_cap = get_capabilities_from_store(event_store)
    merged_capabilities = merge_capabilities(provider_cap, store_cap)
    capability_drift_list = check_drift(merged_capabilities)

    try:
        beh_scan = behavioral.scan(
            verbose=verbose,
            capabilities_override=merged_capabilities,
        )
        if beh_scan.detected:
            batch.detected_scans.append(beh_scan)
            batch.detected_tool_names.add(beh_scan.tool_name or "Unknown Agent")
    except Exception:
        logger.warning(
            "BehavioralScanner raised an exception; treating as inconclusive",
            exc_info=True,
        )
        batch.scan_failures.add("Unknown Agent")

    # ------------------------------------------------------------------
    # Stage 1c: EvasionScanner
    # ------------------------------------------------------------------
    diagnostics_context = {
        "capability_drift": capability_drift_list if capability_drift_list else [],
        "provider_name": provider.name,
        "scan_failures": list(batch.scan_failures),
    }
    ev_scan: ScanResult | None = None
    try:
        evasion = evasion_scanner_cls(event_store=event_store)
        ev_scan = evasion.scan(verbose=verbose, diagnostics_context=diagnostics_context)
        if ev_scan.detected:
            batch.detected_scans.append(ev_scan)
            batch.detected_tool_names.add("Evasion Detection")
    except Exception:
        logger.warning(
            "EvasionScanner raised an exception; treating as inconclusive",
            exc_info=True,
        )
        ev_scan = None

    batch.evasion_scan = ev_scan

    # Extract tamper vectors from evasion findings + capability drift
    tamper_vectors_list: list[str] = []
    if ev_scan and getattr(ev_scan, "detected", False) and ev_scan.evidence_details:
        tamper_vectors_list = [
            f["vector"]
            for f in ev_scan.evidence_details.get("evasion_findings", [])
            if isinstance(f, dict) and f.get("vector")
        ]
    if capability_drift_list:
        tamper_vectors_list.append("capability_drift")
    batch.tamper_vectors = tamper_vectors_list

    # ------------------------------------------------------------------
    # Stage 1d: MCPScanner
    # ------------------------------------------------------------------
    try:
        mcp = mcp_scanner_cls(event_store=event_store)
        mcp_scan = mcp.scan(verbose=verbose)
        if mcp_scan.detected:
            batch.detected_scans.append(mcp_scan)
            batch.detected_tool_names.add("MCP Infrastructure")
        batch.mcp_scan = mcp_scan
    except Exception:
        logger.warning(
            "MCPScanner raised an exception; treating as inconclusive",
            exc_info=True,
        )

    # ------------------------------------------------------------------
    # Stage 1e: Scheduler artifact injection
    # ------------------------------------------------------------------
    try:
        scheduler_by_tool = get_scheduler_evidence_by_tool()
        for scan in batch.detected_scans:
            evidence_list = scheduler_by_tool.get(scan.tool_name or "")
            if not evidence_list:
                continue
            scan.evidence_details.setdefault("scheduler_entries", []).extend(
                evidence_list
            )
            current = scan.signals.file
            scan.signals.file = min(1.0, current + 0.15)
            if verbose:
                print(
                    f"  Scheduler artifact for {scan.tool_name}: {len(evidence_list)} entry(ies)"
                )
        for tool_name, evidence_list in scheduler_by_tool.items():
            if tool_name in batch.detected_tool_names:
                continue
            first = evidence_list[0]
            tool_class = first.get("tool_class", "C")
            new_scan = ScanResult(
                detected=True,
                tool_name=tool_name,
                tool_class=tool_class,
                signals=LayerSignals(
                    file=0.5, process=0.0, network=0.0, identity=0.0, behavior=0.0
                ),
                evidence_details={"scheduler_entries": list(evidence_list)},
                action_summary=f"Scheduled execution (cron/LaunchAgent): {len(evidence_list)} entry(ies)",
            )
            batch.detected_scans.append(new_scan)
            batch.detected_tool_names.add(tool_name)
            if verbose:
                print(
                    f"  Scheduler-only detection: {tool_name} ({len(evidence_list)} entry(ies))"
                )
    except Exception:
        logger.warning(
            "Scheduler artifact scan raised an exception; skipping",
            exc_info=True,
        )

    # ------------------------------------------------------------------
    # Stage 2: Correlation
    # ------------------------------------------------------------------
    batch.correlation_context = compute_correlation(
        batch.detected_scans, event_store, _extract_pids
    )

    # ------------------------------------------------------------------
    # Stage 3: Diagnostics accumulator
    # ------------------------------------------------------------------
    diagnostics = DiagnosticsAccumulator(rolling_scans=30)
    diagnostics.start_scan()
    batch.diagnostics = diagnostics

    # ------------------------------------------------------------------
    # Stage 4: Process tree enrichment (cross-tree correlation + fragments)
    # ------------------------------------------------------------------
    trees = build_trees(event_store)
    hints_engine = CorrelationHintsEngine()
    correlation_hints_list = hints_engine.analyze(trees)

    if fragment_cache is None:
        fragment_cache = FragmentCache(retention_seconds=1800.0, max_fragments=500)

    cross_tree_by_scan: list[dict[str, Any] | None] = []
    repo_root_by_scan: list[str | None] = []

    for scan in batch.detected_scans:
        pids = _extract_pids(scan)
        root_pid: int | None = None
        tree_for_scan: ProcessNode | None = None
        for tree in trees:
            if get_all_pids(tree) & pids:
                root_pid = tree.pid
                tree_for_scan = tree
                break
        if root_pid is not None:
            enr = enrichment_for_tree(
                root_pid, correlation_hints_list, tree=tree_for_scan
            )
            cross_tree_by_scan.append(enr)
        else:
            cross_tree_by_scan.append(None)
        frag = fragment_from_tree(tree_for_scan) if tree_for_scan else None
        repo_root_by_scan.append(frag.repo_root if frag else None)

    batch.cross_tree_correlation = cross_tree_by_scan

    # possible continuations
    possible_continuation_by_scan: list[dict[str, Any] | None] = []
    now_ts = datetime.now(timezone.utc).timestamp()
    for i in range(len(batch.detected_scans)):
        repo = repo_root_by_scan[i] if i < len(repo_root_by_scan) else None
        if not repo:
            possible_continuation_by_scan.append(None)
            continue
        continuations = fragment_cache.find_continuations(
            repo, now_ts, window_seconds=600.0
        )
        if not continuations:
            possible_continuation_by_scan.append(None)
            continue
        first = continuations[0]
        possible_continuation_by_scan.append(
            {
                "first_seen": first.first_seen,
                "patterns": first.patterns[:5],
                "sensitive_paths": first.sensitive_paths[:3],
            }
        )
    batch.possible_continuations = possible_continuation_by_scan

    # ------------------------------------------------------------------
    # Stage 5: Session timelines
    # ------------------------------------------------------------------
    scan_timelines: list[list[dict[str, str]]] = []
    for scan in batch.detected_scans:
        pids = _extract_pids(scan)
        timeline = build_session_timeline(
            event_store, scan.tool_name or "", pids, expand_tree=True
        )
        scan_timelines.append(timeline)
    batch.session_timelines = scan_timelines

    # ------------------------------------------------------------------
    # Finalize diagnostics
    # ------------------------------------------------------------------
    pattern_ids: list[str] = []
    for scan in batch.detected_scans:
        for p in scan.evidence_details.get("behavioral_patterns") or []:
            if isinstance(p, dict) and p.get("pattern_id"):
                pattern_ids.append(p["pattern_id"])
    diagnostics.end_scan(trees_count=len(trees), patterns_triggered=pattern_ids)
    event_counts = event_store.get_event_counts()
    batch.agent_status = diagnostics.get_status(
        provider_name=provider.name,
        event_counts=event_counts,
        capability_drift=capability_drift_list if capability_drift_list else None,
        tamper_vectors=tamper_vectors_list if tamper_vectors_list else None,
    )

    # Record fragment cache for next cycle
    for tree in trees:
        fragment_cache.record_tree(tree)

    return batch

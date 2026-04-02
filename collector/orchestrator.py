"""Scan pipeline: one-cycle orchestration (scan, score, policy, enforce, emit).

This module runs a single collector cycle: start telemetry, run all scanners,
correlate, score confidence, evaluate policy, optionally enforce, and emit events.
The CLI entrypoint (main.py) invokes run_scan() for one-shot or daemon loop.

Sub-modules (extracted to reduce file size):
  event_builder        -- canonical event dict assembly and severity computation
  decision_engine      -- credibility gating, session violation tracking
  coordinator/         -- scan, scoring, and emission coordinator packages
"""

from __future__ import annotations

import argparse
import logging
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Union

from config_loader import load_collector_config
from probe.models import TriggerContext

from engine.network import DEFAULT_ALLOWLIST_PATH, _matches_allowlist
from providers import get_best_provider
from telemetry.event_store import EventStore
from engine.policy import NetworkContext
from enforcement.enforcer import Enforcer
from enforcement.posture import PostureManager
from output.emitter import EventEmitter
from output.http_emitter import HttpEmitter
from output.tcp_emitter import TcpEmitter
from agent.state import StateDiffer
from scanner.base import LayerSignals, ScanResult
from session.fragment_cache import FragmentCache
from scanner.ai_extensions import AIExtensionScanner
from scanner.aider import AiderScanner
from scanner.claude_code import ClaudeCodeScanner
from scanner.claude_cowork import ClaudeCoworkScanner
from scanner.cline import ClineScanner
from scanner.continue_ext import ContinueScanner
from scanner.copilot import CopilotScanner
from scanner.cursor import CursorScanner
from scanner.gpt_pilot import GPTPilotScanner
from scanner.lm_studio import LMStudioScanner
from scanner.ollama import OllamaScanner
from scanner.open_interpreter import OpenInterpreterScanner
from scanner.behavioral import BehavioralScanner
from scanner.evasion import EvasionScanner
from scanner.mcp import MCPScanner
from scanner.openclaw import OpenClawScanner

# ---------------------------------------------------------------------------
# Re-exports from event_builder (backward compat for main.py, tests, patches)
# ---------------------------------------------------------------------------
from event_builder import (  # noqa: F401 – re-exported
    EVENT_VERSION,
    build_event,
)

# ---------------------------------------------------------------------------
# Re-exports from decision_engine (backward compat for tests)
# ---------------------------------------------------------------------------
from decision_engine import (  # noqa: F401 – re-exported
    EMISSION_MIN_CONFIDENCE,
    EMISSION_NO_SIGNALS_MAX_CONFIDENCE,
    SESSION_VIOLATION_TTL_SECONDS,
    _maybe_prune_violation_counts,
    _should_suppress_emission,
    _suppressed_reason,
    get_violation_count,
    record_violation,
)

# Import the session violation counts dict so orchestrator-level code can
# still reference it (tests may access it).
from decision_engine import _session_violation_counts  # noqa: F401

logger = logging.getLogger(__name__)

AnyEmitter = Union[EventEmitter, HttpEmitter, TcpEmitter]


# ---------------------------------------------------------------------------
# Utility helpers
# ---------------------------------------------------------------------------


def explain_native_failure(provider_name: str, error: BaseException) -> str:
    """Return a short, readable explanation for native telemetry provider startup failure."""
    msg = str(error).strip() or type(error).__name__
    if (
        "es_new_client" in msg
        or "esf_helper" in msg.lower()
        or "endpoint security" in msg.lower()
    ):
        return "Endpoint Security client initialization failed."
    if "entitlement" in msg.lower() or "permission" in msg.lower():
        return "Entitlement or permissions (e.g. Full Disk Access) required."
    if "not found" in msg.lower() or "no such file" in msg.lower():
        return "Helper binary or dependency not found."
    if msg:
        return msg[:200] if len(msg) > 200 else msg
    return f"{type(error).__name__} during startup"


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


def _load_network_allowlist(path: str | None) -> set[str] | None:
    """Load allowed destination hostnames/IPs from a newline-delimited file."""
    effective_path = path or DEFAULT_ALLOWLIST_PATH
    if not effective_path:
        return None
    p = Path(effective_path)
    try:
        entries = set()
        for line in p.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#"):
                entries.add(line.lower())
        logger.debug("Loaded %d entries from network allowlist %s", len(entries), p)
        return entries
    except (FileNotFoundError, OSError):
        return None


def _build_network_context(
    scan: ScanResult,
    allowlist: set[str] | None,
) -> NetworkContext | None:
    """Build a NetworkContext from scan evidence and the allowlist."""
    if allowlist is None:
        return None

    connections = scan.evidence_details.get("connections", [])
    if not connections:
        return None

    total = len(connections)
    unknown_dests: list[str] = []
    for conn in connections:
        dest = conn.get("remote_address") or conn.get("dest") or ""
        if isinstance(dest, str) and dest:
            host = dest.split(":")[0].lower()
            if host and not _matches_allowlist(
                addr=host, hostname=None, allowlist=allowlist
            ):
                unknown_dests.append(dest)

    if not unknown_dests:
        return NetworkContext(
            unknown_connections=0,
            unknown_destinations=[],
            total_connections=total,
        )

    return NetworkContext(
        unknown_connections=len(unknown_dests),
        unknown_destinations=unknown_dests[:10],
        total_connections=total,
    )


def print_scan_summary(
    scan_summary: dict[str, list[dict[str, Any]]],
    telemetry_fidelity: str | None = None,
) -> None:
    """Print the Detec findings summary block (HIGH / MEDIUM / LOW / SUPPRESSED)."""
    has_any = any(scan_summary.get(k) for k in ("high", "medium", "low", "suppressed"))
    if not has_any:
        return
    print("\n================= Detec Findings =================")
    for level in ("high", "medium", "low"):
        entries = scan_summary.get(level, [])
        if not entries:
            continue
        label = level.upper()
        print(f"\n{label}")
        for e in entries:
            tool = e.get("tool") or "Unknown"
            tool_class = e.get("tool_class") or "A"
            policy = e.get("policy") or "observe"
            reason = e.get("reason") or ""
            print(f"  {tool} (Class {tool_class})")
            print(f"  Policy: {policy}")
            if reason:
                print(f"  Reason: {reason}")
    suppressed = scan_summary.get("suppressed", [])
    if suppressed:
        print("\nSUPPRESSED")
        for e in suppressed:
            tool = e.get("tool") or "Unknown"
            reason = e.get("reason") or "credibility gate"
            print(f"  {tool} – {reason}")
    if telemetry_fidelity:
        print(f"\nTelemetry fidelity: {telemetry_fidelity}")
    print("==================================================")


# ---------------------------------------------------------------------------
# _collect_scan_results: delegates to scan_coordinator
# ---------------------------------------------------------------------------


def _collect_scan_results(
    scanners: list[Any],
    verbose: bool,
) -> tuple[list[ScanResult], set[str], set[str]]:
    """Run all scanners and partition results into detections vs failures."""
    from coordinator.scan_coordinator import collect_scan_results

    return collect_scan_results(scanners, verbose)


# ---------------------------------------------------------------------------
# Per-detection pipeline
# ---------------------------------------------------------------------------


def _process_detection(
    scan: ScanResult,
    *,
    sensitivity: str,
    endpoint_id: str,
    actor_id: str,
    session_id: str,
    trace_id: str,
    emitter: AnyEmitter,
    enforcer: Enforcer | None,
    state_differ: StateDiffer | None,
    network_allowlist: set[str] | None = None,
    verbose: bool,
    correlation_context: list[str] | None = None,
    scan_summary: dict[str, list[dict[str, Any]]] | None = None,
    trigger_context: TriggerContext | None = None,
    session_timeline: list[dict[str, Any]] | None = None,
    cross_tree_correlation: dict[str, Any] | None = None,
    possible_continuation: dict[str, Any] | None = None,
    agent_status: dict[str, Any] | None = None,
    config: dict | None = None,
    pipe_server: Any = None,
) -> int:
    """Score, evaluate policy, enforce, and emit events for one detection.

    Delegates to coordinator.scoring_coordinator and coordinator.emission_coordinator.
    This thin wrapper is kept for backward compatibility with existing callers and tests.
    """
    from coordinator.scoring_coordinator import score_detection
    from coordinator.emission_coordinator import emit_detection

    scoring = score_detection(
        scan,
        sensitivity=sensitivity,
        endpoint_id=endpoint_id,
        network_allowlist=network_allowlist,
        agent_status=agent_status,
    )

    return emit_detection(
        scan,
        scoring,
        endpoint_id=endpoint_id,
        actor_id=actor_id,
        session_id=session_id,
        trace_id=trace_id,
        sensitivity=sensitivity,
        emitter=emitter,
        enforcer=enforcer,
        state_differ=state_differ,
        verbose=verbose,
        scan_summary=scan_summary,
        trigger_context=trigger_context,
        session_timeline=session_timeline,
        cross_tree_correlation=cross_tree_correlation,
        possible_continuation=possible_continuation,
        agent_status=agent_status,
        config=config,
        pipe_server=pipe_server,
    )


def _emit_cleared_events(
    state_differ: StateDiffer,
    detected_tools: set[str],
    scan_failures: set[str],
    *,
    endpoint_id: str,
    actor_id: str,
    session_id: str,
    trace_id: str,
    sensitivity: str,
    emitter: AnyEmitter,
    verbose: bool,
    trigger_context: TriggerContext | None = None,
) -> int:
    """Emit detection.cleared for tools that vanished since the last cycle."""
    from coordinator.emission_coordinator import emit_cleared_events

    return emit_cleared_events(
        state_differ,
        detected_tools,
        scan_failures,
        endpoint_id=endpoint_id,
        actor_id=actor_id,
        session_id=session_id,
        trace_id=trace_id,
        sensitivity=sensitivity,
        emitter=emitter,
        verbose=verbose,
        trigger_context=trigger_context,
    )


# ---------------------------------------------------------------------------
# Main scan cycle
# ---------------------------------------------------------------------------


def run_scan(
    args: argparse.Namespace,
    emitter: AnyEmitter | None = None,
    state_differ: StateDiffer | None = None,
    posture_manager: PostureManager | None = None,
    enforcer: Enforcer | None = None,
    *,
    pipe_server: Any = None,
) -> int:
    """Execute one full scan cycle: telemetry, scanners, score, policy, enforce, emit."""
    session_id = str(uuid.uuid4())
    trace_id = f"trace-collector-{session_id[:8]}"
    endpoint_id = args.endpoint_id
    actor_id = args.actor_id
    sensitivity = args.sensitivity
    own_emitter = emitter is None

    if own_emitter:
        emitter = EventEmitter(output_path=args.output, dry_run=args.dry_run)

    if posture_manager is None:
        posture_mgr = PostureManager(
            initial_posture=getattr(args, "enforcement_posture", "passive"),
            initial_threshold=getattr(args, "auto_enforce_threshold", 0.75),
        )
        if getattr(args, "enforce", False):
            import warnings

            warnings.warn(
                "--enforce is deprecated and will be removed in a future release. "
                "Use --posture active instead, or set posture from the central server.",
                DeprecationWarning,
                stacklevel=2,
            )
            posture_mgr.update("active", source="cli_override")
        elif "--posture" in sys.argv:
            posture_mgr.update(
                getattr(args, "enforcement_posture", "passive"),
                source="cli_override",
            )
    else:
        posture_mgr = posture_manager

    if enforcer is None:
        enforcer = Enforcer(
            posture_manager=posture_mgr,
            dry_run=args.dry_run,
            allow_linux_uid_fallback=getattr(
                args, "allow_linux_uid_block_fallback", False
            ),
        )

    network_allowlist = _load_network_allowlist(
        getattr(args, "network_allowlist_path", None)
    )

    on_alert = getattr(args, "_on_alert", None)
    collector_config = load_collector_config()
    event_store_cfg = collector_config.get("event_store") or {}
    event_store = EventStore(
        max_events=event_store_cfg.get("max_events", 10_000),
        retention_seconds=event_store_cfg.get("retention_seconds", 120.0),
        on_alert=on_alert,
        max_events_per_type=event_store_cfg.get("max_events_per_type"),
        rate_cap_per_second=event_store_cfg.get("rate_cap_per_second"),
        burst_window_seconds=event_store_cfg.get("burst_window_seconds"),
        max_events_per_burst=event_store_cfg.get("max_events_per_burst"),
    )
    provider = get_best_provider(getattr(args, "telemetry_provider", "auto"))
    sentinel = getattr(args, "sentinel", None) or {}
    trigger_context: TriggerContext | None = getattr(
        args, "_pending_trigger_context", None
    )
    if hasattr(args, "_pending_trigger_context"):
        setattr(args, "_pending_trigger_context", None)

    telemetry_fidelity: str | None = None
    try:
        if sentinel.get("enabled") and provider.name == "polling":
            from probe.engine import ProbeEngine

            probe_engine = ProbeEngine(
                endpoint_id=endpoint_id,
                probe_window_seconds=sentinel.get("observation_window_seconds", 120),
                cooldown_seconds=sentinel.get("trigger_cooldown_seconds", 10),
                max_alert_scans_per_minute=sentinel.get(
                    "max_alert_scans_per_minute", 4
                ),
                max_elevations_per_5_minutes=sentinel.get(
                    "max_elevations_per_5_minutes", 10
                ),
                on_request_scan=lambda ctx: (
                    setattr(args, "_pending_trigger_context", ctx),
                    (on_alert(ctx) if on_alert else None),
                )[1],
            )
            try:
                provider.start(
                    event_store,
                    sink=probe_engine,
                    probe_interval_ms=sentinel.get("probe_interval_ms", 1000),
                )
            except TypeError:
                provider.start(event_store)
        else:
            provider.start(event_store)
    except Exception as e:
        if provider.name != "polling":
            logger.debug(
                "Native provider %s failed to start; falling back to polling: %s",
                provider.name,
                e,
                exc_info=True,
            )
            reason = explain_native_failure(provider.name.upper(), e)
            print(
                "Native telemetry provider (%s) failed to start."
                % provider.name.upper()
            )
            print("Reason:")
            print("  %s" % reason)
            print("Falling back to polling provider.")
            print("Telemetry fidelity: DEGRADED")
            print("Polling mode may miss:")
            print("  - short-lived processes")
            print("  - file system events")
            print("  - fine-grained network correlation")
            from providers.polling import PollingProvider

            provider = PollingProvider()
            provider.start(event_store)
            telemetry_fidelity = "degraded (polling fallback)"
        else:
            raise

    if args.verbose:
        print(f"Collector session: {session_id}")
        print(f"Endpoint: {endpoint_id}  Actor: {actor_id}  Sensitivity: {sensitivity}")
        if telemetry_fidelity:
            print(f"Telemetry fidelity: {telemetry_fidelity}")
        if network_allowlist:
            print(f"Network allowlist: {len(network_allowlist)} entries")
        print("-" * 60)

    # ------------------------------------------------------------------
    # Build scanner list and dispatch via scan_coordinator
    # ------------------------------------------------------------------
    scanners = [
        ClaudeCodeScanner(event_store=event_store),
        ClaudeCoworkScanner(event_store=event_store),
        OllamaScanner(event_store=event_store),
        CursorScanner(event_store=event_store),
        CopilotScanner(event_store=event_store),
        OpenInterpreterScanner(event_store=event_store),
        OpenClawScanner(event_store=event_store),
        AiderScanner(event_store=event_store),
        LMStudioScanner(event_store=event_store),
        ContinueScanner(event_store=event_store),
        GPTPilotScanner(event_store=event_store),
        ClineScanner(event_store=event_store),
        AIExtensionScanner(event_store=event_store),
    ]

    if hasattr(provider, "poll"):
        provider.poll()

    from coordinator.scan_coordinator import collect_scan_batch

    fragment_cache = FragmentCache(retention_seconds=1800.0, max_fragments=500)
    batch = collect_scan_batch(
        scanners,
        event_store=event_store,
        provider=provider,
        verbose=args.verbose,
        telemetry_fidelity=telemetry_fidelity,
        fragment_cache=fragment_cache,
        behavioral_scanner_cls=BehavioralScanner,
        evasion_scanner_cls=EvasionScanner,
        mcp_scanner_cls=MCPScanner,
    )

    detected_scans = batch.detected_scans
    detected_tools = batch.detected_tool_names
    scan_failures = batch.scan_failures
    correlation_map = batch.correlation_context
    agent_status = batch.agent_status

    if getattr(args, "session_report", False):
        from session_report import build_session_reports, format_session_report_for_cli

        for report in build_session_reports(
            event_store, detected_scans, tool_timelines=batch.session_timelines
        ):
            print(format_session_report_for_cli(report))
            print("")

    scan_summary: dict[str, list[dict[str, Any]]] = {
        "high": [],
        "medium": [],
        "low": [],
        "suppressed": [],
    }

    total_events = 0
    for i, scan in enumerate(detected_scans):
        related = correlation_map.get(scan.tool_name or "", [])
        session_timeline = (
            batch.session_timelines[i] if i < len(batch.session_timelines) else None
        )
        cross_tree = (
            batch.cross_tree_correlation[i]
            if i < len(batch.cross_tree_correlation)
            else None
        )
        total_events += _process_detection(
            scan,
            sensitivity=sensitivity,
            endpoint_id=endpoint_id,
            actor_id=actor_id,
            session_id=session_id,
            trace_id=trace_id,
            emitter=emitter,
            enforcer=enforcer,
            state_differ=state_differ,
            network_allowlist=network_allowlist or None,
            verbose=args.verbose,
            correlation_context=related if related else None,
            scan_summary=scan_summary,
            trigger_context=trigger_context,
            session_timeline=session_timeline,
            cross_tree_correlation=cross_tree,
            possible_continuation=batch.possible_continuations[i]
            if i < len(batch.possible_continuations)
            else None,
            agent_status=agent_status,
            config=collector_config,
            pipe_server=pipe_server,
        )

    if state_differ is not None:
        total_events += _emit_cleared_events(
            state_differ,
            detected_tools,
            scan_failures,
            endpoint_id=endpoint_id,
            actor_id=actor_id,
            session_id=session_id,
            trace_id=trace_id,
            sensitivity=sensitivity,
            emitter=emitter,
            verbose=args.verbose,
            trigger_context=trigger_context,
        )

    provider.stop()

    print_scan_summary(scan_summary, telemetry_fidelity)

    stats = emitter.stats
    if args.verbose:
        print(f"\n{'=' * 60}")
    print(
        f"Scan complete. Events emitted: {stats['emitted']}, "
        f"validation failures: {stats['failed']}"
    )
    if own_emitter and not args.dry_run:
        print(f"Output: {args.output}")

    return 0 if stats["failed"] == 0 else 1

"""Behavioral pattern detectors for agentic AI anomaly detection (BEH-001 through BEH-009).

Each detector examines a ProcessNode tree and returns a PatternMatch with a
score (0.0 to 1.0) indicating how strongly the tree matches the pattern.
"""

from __future__ import annotations

import os
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any

from telemetry.event_store import FileChangeEvent, NetworkConnectEvent

from .process_tree import ProcessNode

# ---------------------------------------------------------------------------
# LLM API host registry
# ---------------------------------------------------------------------------

_LLM_API_HOSTS: set[str] = {
    "api.openai.com",
    "api.anthropic.com",
    "generativelanguage.googleapis.com",
    "api.groq.com",
    "api.mistral.ai",
    "api.cohere.ai",
    "api.together.xyz",
    "api.replicate.com",
    "api.deepseek.com",
    "api.fireworks.ai",
    "localhost:11434",
    "localhost:1234",
    "127.0.0.1:8080",
}


def update_llm_hosts(hosts: set[str]) -> None:
    """Add hosts to the LLM API host registry."""
    _LLM_API_HOSTS.update(hosts)


def get_llm_hosts() -> frozenset[str]:
    return frozenset(_LLM_API_HOSTS)


# ---------------------------------------------------------------------------
# Pattern result
# ---------------------------------------------------------------------------

@dataclass
class PatternMatch:
    pattern_id: str
    pattern_name: str
    score: float
    evidence: dict[str, Any] = field(default_factory=dict)
    layers: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Tree traversal helpers
# ---------------------------------------------------------------------------

def _all_nodes(node: ProcessNode) -> list[ProcessNode]:
    """Flat list of all nodes in the tree (including root)."""
    result = [node]
    for child in node.children:
        result.extend(_all_nodes(child))
    return result


def _collect_network_events(node: ProcessNode) -> list[NetworkConnectEvent]:
    """Recursively collect all network events from a tree."""
    events = list(node.network_events)
    for child in node.children:
        events.extend(_collect_network_events(child))
    return events


def _collect_file_events(node: ProcessNode) -> list[FileChangeEvent]:
    """Recursively collect all file events from a tree."""
    events = list(node.file_events)
    for child in node.children:
        events.extend(_collect_file_events(child))
    return events


def _collect_child_processes(node: ProcessNode) -> list[ProcessNode]:
    """Recursively collect all descendant nodes (excluding root)."""
    result: list[ProcessNode] = []
    for child in node.children:
        result.append(child)
        result.extend(_collect_child_processes(child))
    return result


def _normalize_process_name(name: str) -> str:
    """Strip path prefix and common extensions for comparison."""
    base = os.path.basename(name).lower()
    if base.endswith(".exe"):
        base = base[:-4]
    return base


# ---------------------------------------------------------------------------
# Shell and editor name sets
# ---------------------------------------------------------------------------

_SHELL_NAMES: frozenset[str] = frozenset({
    "bash", "sh", "zsh", "fish", "csh", "tcsh", "dash",
    "cmd", "powershell", "pwsh",
})

# Shell or interpreter for BEH-009 execution chain (spec: bash, zsh, python, node, sh)
_SHELL_OR_INTERPRETER_NAMES: frozenset[str] = frozenset({
    "bash", "zsh", "sh", "python", "node",
})

_EDITOR_NAMES: frozenset[str] = frozenset({
    "vim", "nvim", "nano", "emacs", "code", "cursor",
    "idea", "pycharm", "webstorm", "sublime_text",
})

_SENSITIVE_PATH_FRAGMENTS: tuple[str, ...] = (
    ".env",
    os.sep + ".ssh" + os.sep,
    os.sep + ".aws" + os.sep,
    os.sep + ".config" + os.sep + "gcloud",
    os.sep + ".azure" + os.sep,
    os.sep + ".kube" + os.sep,
    "credentials",
    "secrets",
    ".netrc",
    ".npmrc",
    "keychain",
)


# ---------------------------------------------------------------------------
# Scoring helper
# ---------------------------------------------------------------------------

def _scale(value: float, low: float, mid: float, high: float,
           low_score: float, mid_score: float, high_score: float) -> float:
    """Linear interpolation across three threshold tiers, clamped to [0, high_score]."""
    if value < low:
        return 0.0
    if value >= high:
        return high_score
    if value >= mid:
        return mid_score + (high_score - mid_score) * (value - mid) / (high - mid)
    return low_score + (mid_score - low_score) * (value - low) / (mid - low)


# ---------------------------------------------------------------------------
# BEH-001: Shell fan-out
# ---------------------------------------------------------------------------

def detect_shell_fanout(
    tree: ProcessNode,
    thresholds: dict[str, Any] | None = None,
) -> PatternMatch:
    """DETEC-BEH-CORE-01: Autonomous shell fan-out from a process tree.

    Tree is 'model-linked' when it has LLM network activity (same tree);
    score is boosted slightly when model-linked to favor agent sessions over
    plain heavy terminal use.
    """
    t = thresholds or {}
    window = t.get("shell_fanout_window_seconds", 60)
    min_children = t.get("shell_fanout_min_children", 5)

    children = _collect_child_processes(tree)
    shells = [
        c for c in children
        if _normalize_process_name(c.name) in _SHELL_NAMES
    ]

    if not shells or tree.start_time is None:
        return PatternMatch("BEH-001", "Shell fan-out", 0.0, layers=["process", "behavior"])

    # Sliding window: count max shells within any `window`-second span
    shell_times = sorted(s.start_time for s in shells if s.start_time is not None)
    max_in_window = 0
    j = 0
    for i in range(len(shell_times)):
        while j < len(shell_times) and (shell_times[j] - shell_times[i]).total_seconds() <= window:
            j += 1
        max_in_window = max(max_in_window, j - i)

    if max_in_window < min_children:
        return PatternMatch("BEH-001", "Shell fan-out", 0.0, layers=["process", "behavior"])

    score = _scale(max_in_window, min_children, 8, 12, 0.5, 0.8, 1.0)

    # Model-linked: tree has LLM network activity (agent session)
    net_events = _collect_network_events(tree)
    model_linked = any(_is_llm_host(e) for e in net_events)
    if model_linked:
        score = min(1.0, score + 0.05)

    sample_commands = [s.cmdline for s in shells[:10] if s.cmdline]
    shell_timestamps = [
        s.start_time.isoformat() for s in shells[:10]
        if s.start_time is not None
    ]

    return PatternMatch(
        pattern_id="BEH-001",
        pattern_name="Shell fan-out",
        score=round(score, 2),
        evidence={
            "shell_children_in_window": max_in_window,
            "window_seconds": window,
            "shell_names": [s.name for s in shells[:10]],
            "sample_commands": sample_commands[:10],
            "shell_timestamps": shell_timestamps,
            "model_linked": model_linked,
        },
        layers=["process", "behavior"],
    )


# ---------------------------------------------------------------------------
# BEH-002: LLM API cadence
# ---------------------------------------------------------------------------

def _is_llm_host(event: NetworkConnectEvent) -> bool:
    hosts = _LLM_API_HOSTS
    addr = event.remote_addr.split(":")[0] if ":" in event.remote_addr else event.remote_addr
    addr_with_port = f"{addr}:{event.remote_port}"

    if addr in hosts or addr_with_port in hosts:
        return True
    if event.sni and event.sni in hosts:
        return True
    return False


def detect_llm_cadence(
    tree: ProcessNode,
    thresholds: dict[str, Any] | None = None,
) -> PatternMatch:
    t = thresholds or {}
    window = t.get("llm_cadence_window_seconds", 120)
    min_connections = t.get("llm_cadence_min_connections", 3)

    net_events = _collect_network_events(tree)
    llm_events = [e for e in net_events if _is_llm_host(e)]

    if len(llm_events) < min_connections:
        return PatternMatch("BEH-002", "LLM API cadence", 0.0, layers=["network", "behavior"])

    # Count connections within the window
    llm_times = sorted(e.timestamp for e in llm_events)
    max_in_window = 0
    j = 0
    for i in range(len(llm_times)):
        while j < len(llm_times) and (llm_times[j] - llm_times[i]).total_seconds() <= window:
            j += 1
        max_in_window = max(max_in_window, j - i)

    if max_in_window < min_connections:
        return PatternMatch("BEH-002", "LLM API cadence", 0.0, layers=["network", "behavior"])

    score = _scale(max_in_window, min_connections, 6, 10, 0.4, 0.7, 1.0)

    unique_hosts = {
        (e.sni or e.remote_addr.split(":")[0])
        for e in llm_events
    }

    return PatternMatch(
        pattern_id="BEH-002",
        pattern_name="LLM API cadence",
        score=round(score, 2),
        evidence={
            "llm_connections_in_window": max_in_window,
            "unique_hosts": sorted(unique_hosts),
            "window_seconds": window,
        },
        layers=["network", "behavior"],
    )


# ---------------------------------------------------------------------------
# BEH-003: Multi-file burst write
# ---------------------------------------------------------------------------

def detect_burst_write(
    tree: ProcessNode,
    thresholds: dict[str, Any] | None = None,
) -> PatternMatch:
    t = thresholds or {}
    window = t.get("burst_write_window_seconds", 30)
    min_files = t.get("burst_write_min_files", 10)
    min_dirs = t.get("burst_write_min_directories", 3)

    file_events = _collect_file_events(tree)
    writes = [e for e in file_events if e.action in ("created", "modified")]

    if len(writes) < min_files:
        return PatternMatch("BEH-003", "Multi-file burst write", 0.0, layers=["file", "behavior"])

    writes.sort(key=lambda e: e.timestamp)

    best_count = 0
    best_dirs = 0
    j = 0
    for i in range(len(writes)):
        while j < len(writes) and (writes[j].timestamp - writes[i].timestamp).total_seconds() <= window:
            j += 1
        window_writes = writes[i:j]
        dirs = {os.path.dirname(w.path) for w in window_writes}
        if len(window_writes) >= min_files and len(dirs) >= min_dirs:
            if len(window_writes) > best_count:
                best_count = len(window_writes)
                best_dirs = len(dirs)

    if best_count < min_files or best_dirs < min_dirs:
        return PatternMatch("BEH-003", "Multi-file burst write", 0.0, layers=["file", "behavior"])

    score = _scale(best_count, min_files, 20, 30, 0.5, 0.8, 1.0)

    return PatternMatch(
        pattern_id="BEH-003",
        pattern_name="Multi-file burst write",
        score=round(score, 2),
        evidence={
            "files_in_window": best_count,
            "directories": best_dirs,
            "window_seconds": window,
        },
        layers=["file", "behavior"],
    )


# ---------------------------------------------------------------------------
# BEH-004: Read-modify-write loop
# ---------------------------------------------------------------------------

def detect_rmw_loop(
    tree: ProcessNode,
    thresholds: dict[str, Any] | None = None,
) -> PatternMatch:
    """DETEC-BEH-CORE-02: Interleaved file + model-related network in short cycles.

    Only network events to LLM hosts or local inference count as "net" in
    file->net->file cycles, so the loop is tied to model use.
    """
    t = thresholds or {}
    cycle_window = t.get("rmw_loop_window_seconds", 10)
    min_cycles = t.get("rmw_loop_min_cycles", 2)

    file_events = _collect_file_events(tree)
    all_net = _collect_network_events(tree)
    net_events = [e for e in all_net if _is_llm_host(e)]

    if not file_events or not net_events:
        return PatternMatch("BEH-004", "Read-modify-write loop", 0.0,
                            layers=["file", "network", "behavior"])

    # Build a timeline of (timestamp, type) tuples; only model-related net
    timeline: list[tuple[datetime, str]] = []
    for e in file_events:
        timeline.append((e.timestamp, "file"))
    for e in net_events:
        timeline.append((e.timestamp, "net"))
    timeline.sort(key=lambda x: x[0])

    # Count file->net->file transitions within the cycle window
    cycles = 0
    i = 0
    while i < len(timeline) - 2:
        t0_ts, t0_type = timeline[i]
        if t0_type != "file":
            i += 1
            continue
        # Look for net after file
        found_net = False
        for j in range(i + 1, len(timeline)):
            if (timeline[j][0] - t0_ts).total_seconds() > cycle_window:
                break
            if timeline[j][1] == "net":
                # Look for file after net
                for k in range(j + 1, len(timeline)):
                    if (timeline[k][0] - t0_ts).total_seconds() > cycle_window:
                        break
                    if timeline[k][1] == "file":
                        cycles += 1
                        i = k + 1
                        found_net = True
                        break
                break
        if not found_net:
            i += 1

    if cycles < min_cycles:
        return PatternMatch("BEH-004", "Read-modify-write loop", 0.0,
                            layers=["file", "network", "behavior"])

    score = _scale(cycles, min_cycles, 4, 6, 0.5, 0.8, 1.0)

    # Evidence: affected dirs/files from file_events, model endpoint from net_events
    affected_dirs = sorted({os.path.dirname(e.path) for e in file_events})[:15]
    affected_files = [e.path for e in file_events[:10]]
    model_endpoint = None
    for e in net_events:
        addr = e.remote_addr.split(":")[0] if ":" in e.remote_addr else e.remote_addr
        model_endpoint = e.sni or f"{addr}:{e.remote_port}"
        break

    return PatternMatch(
        pattern_id="BEH-004",
        pattern_name="Read-modify-write loop",
        score=round(score, 2),
        evidence={
            "cycles_detected": cycles,
            "cycle_window_seconds": cycle_window,
            "affected_directories": affected_dirs,
            "affected_files": affected_files,
            "model_endpoint": model_endpoint,
        },
        layers=["file", "network", "behavior"],
    )


# ---------------------------------------------------------------------------
# BEH-005: Autonomous session duration
# ---------------------------------------------------------------------------

def detect_session_duration(
    tree: ProcessNode,
    thresholds: dict[str, Any] | None = None,
) -> PatternMatch:
    t = thresholds or {}
    min_duration = t.get("session_min_duration_seconds", 600)
    gap_max = t.get("session_activity_gap_max_seconds", 120)

    all_nodes = _all_nodes(tree)
    timestamps: list[datetime] = []
    for n in all_nodes:
        if n.start_time:
            timestamps.append(n.start_time)
        for e in n.network_events:
            timestamps.append(e.timestamp)
        for e in n.file_events:
            timestamps.append(e.timestamp)

    if len(timestamps) < 2:
        return PatternMatch("BEH-005", "Autonomous session duration", 0.0,
                            layers=["behavior"])

    timestamps.sort()
    duration = (timestamps[-1] - timestamps[0]).total_seconds()

    if duration < min_duration:
        return PatternMatch("BEH-005", "Autonomous session duration", 0.0,
                            layers=["behavior"])

    # Check for continuous activity (no gap exceeding gap_max)
    max_gap = 0.0
    for i in range(1, len(timestamps)):
        gap = (timestamps[i] - timestamps[i - 1]).total_seconds()
        max_gap = max(max_gap, gap)

    # If the largest gap is bigger than gap_max, reduce score
    continuity_factor = 1.0 if max_gap <= gap_max else max(0.3, 1.0 - (max_gap - gap_max) / gap_max)

    raw_score = _scale(duration, min_duration, 1800, 3600, 0.4, 0.7, 1.0)
    score = raw_score * continuity_factor

    return PatternMatch(
        pattern_id="BEH-005",
        pattern_name="Autonomous session duration",
        score=round(score, 2),
        evidence={
            "duration_seconds": round(duration, 1),
            "max_gap_seconds": round(max_gap, 1),
            "event_count": len(timestamps),
        },
        layers=["behavior"],
    )


# ---------------------------------------------------------------------------
# BEH-006: Config/credential access
# ---------------------------------------------------------------------------

def _is_sensitive_path(path: str) -> bool:
    lower = path.lower()
    for fragment in _SENSITIVE_PATH_FRAGMENTS:
        if fragment.lower() in lower:
            return True
    return False


def _classify_network_destinations(
    net_events: list[NetworkConnectEvent],
) -> tuple[list[str], str]:
    """Return (outbound_destinations, model_vs_unknown)."""
    destinations: list[str] = []
    has_model = False
    has_unknown = False
    seen: set[str] = set()
    for e in net_events:
        addr = e.remote_addr.split(":")[0] if ":" in e.remote_addr else e.remote_addr
        dest = e.sni or f"{addr}:{e.remote_port}"
        if dest not in seen:
            seen.add(dest)
            destinations.append(dest)
        if _is_llm_host(e):
            has_model = True
        else:
            has_unknown = True
    if has_model and has_unknown:
        classification = "both"
    elif has_model:
        classification = "model"
    else:
        classification = "unknown"
    return (destinations, classification)


def detect_credential_access(
    tree: ProcessNode,
    thresholds: dict[str, Any] | None = None,
) -> PatternMatch:
    """DETEC-BEH-CORE-03: Sensitive path access followed by outbound activity.

    Requires outbound network to occur after first sensitive file access
    within credential_network_max_seconds_after_access (temporal ordering).
    Classifies destinations as model vs unknown; score can increase for unknown.
    """
    t = thresholds or {}
    min_files = t.get("credential_access_min_files", 1)
    require_network = t.get("credential_require_network", True)
    max_seconds_after = t.get("credential_network_max_seconds_after_access", 300)

    file_events = _collect_file_events(tree)
    sensitive = [e for e in file_events if _is_sensitive_path(e.path)]

    if len(sensitive) < min_files:
        return PatternMatch("BEH-006", "Config/credential access", 0.0,
                            layers=["file", "network", "identity"])

    sensitive.sort(key=lambda e: e.timestamp)
    first_access_time = sensitive[0].timestamp

    net_events = _collect_network_events(tree)
    # Temporal ordering: only network events after first access within window
    qualifying_net = [
        e for e in net_events
        if e.timestamp >= first_access_time
        and (e.timestamp - first_access_time).total_seconds() <= max_seconds_after
    ]

    has_network = len(qualifying_net) > 0
    if require_network and not has_network:
        return PatternMatch("BEH-006", "Config/credential access", 0.0,
                            layers=["file", "network", "identity"])

    n_sensitive = len(sensitive)
    if n_sensitive >= 5 and has_network:
        base_score = 1.0
    elif n_sensitive >= 3:
        base_score = 0.7
    elif n_sensitive >= 1:
        base_score = 0.4 if not has_network else 0.6
    else:
        base_score = 0.0

    outbound_destinations, model_vs_unknown = _classify_network_destinations(
        qualifying_net
    )
    confidence_reasons: list[str] = ["sensitive_access_then_outbound"]
    if model_vs_unknown == "unknown":
        base_score = min(1.0, base_score + 0.15)
        confidence_reasons.append("sensitive_access_then_unknown_outbound")
    elif model_vs_unknown == "both":
        base_score = min(1.0, base_score + 0.1)
        confidence_reasons.append("sensitive_access_then_model_and_unknown")

    first_network_time = min(e.timestamp for e in qualifying_net) if qualifying_net else None
    interval_seconds = (
        round((first_network_time - first_access_time).total_seconds(), 1)
        if first_network_time else None
    )

    return PatternMatch(
        pattern_id="BEH-006",
        pattern_name="Config/credential access",
        score=round(base_score, 2),
        evidence={
            "sensitive_files_accessed": n_sensitive,
            "paths": [e.path for e in sensitive[:10]],
            "has_network": has_network,
            "first_access_time": first_access_time.isoformat() if first_access_time else None,
            "first_network_time": first_network_time.isoformat() if first_network_time else None,
            "interval_seconds": interval_seconds,
            "outbound_destinations": outbound_destinations[:20],
            "model_vs_unknown": model_vs_unknown,
            "confidence_reasons": confidence_reasons,
        },
        layers=["file", "network", "identity"],
    )


# ---------------------------------------------------------------------------
# BEH-007: Git automation
# ---------------------------------------------------------------------------

def detect_git_automation(
    tree: ProcessNode,
    thresholds: dict[str, Any] | None = None,
) -> PatternMatch:
    t = thresholds or {}
    min_sequences = t.get("git_automation_min_sequences", 1)
    exclude_editors = t.get("git_automation_exclude_editors", True)

    all_children = _collect_child_processes(tree)

    # Check if an editor is present in the tree (signals interactive use)
    has_editor = False
    if exclude_editors:
        for n in _all_nodes(tree):
            if _normalize_process_name(n.name) in _EDITOR_NAMES:
                has_editor = True
                break

    if has_editor:
        return PatternMatch("BEH-007", "Git automation", 0.0,
                            layers=["process", "file", "behavior"])

    # Find git processes and look for add/commit/push sequences
    git_procs = [
        c for c in all_children
        if _normalize_process_name(c.name) == "git" and c.start_time is not None
    ]
    git_procs.sort(key=lambda c: c.start_time)  # type: ignore[arg-type]

    # Extract git subcommands from cmdlines
    git_commands: list[tuple[datetime, str]] = []
    for g in git_procs:
        parts = g.cmdline.split()
        for i, part in enumerate(parts):
            if _normalize_process_name(part) == "git" and i + 1 < len(parts):
                subcmd = parts[i + 1].lower()
                if subcmd in ("add", "commit", "push"):
                    git_commands.append((g.start_time, subcmd))  # type: ignore[arg-type]
                break

    # Count add->commit->push sequences
    sequences = 0
    i = 0
    while i < len(git_commands) - 2:
        if (git_commands[i][1] == "add"
                and git_commands[i + 1][1] == "commit"
                and git_commands[i + 2][1] == "push"):
            sequences += 1
            i += 3
        else:
            i += 1

    if sequences < min_sequences:
        return PatternMatch("BEH-007", "Git automation", 0.0,
                            layers=["process", "file", "behavior"])

    if sequences >= 3:
        score = 1.0
    elif sequences >= 2:
        score = 0.8
    else:
        score = 0.6

    return PatternMatch(
        pattern_id="BEH-007",
        pattern_name="Git automation",
        score=round(score, 2),
        evidence={
            "sequences_detected": sequences,
            "git_commands": len(git_commands),
        },
        layers=["process", "file", "behavior"],
    )


# ---------------------------------------------------------------------------
# BEH-008: Process resurrection
# ---------------------------------------------------------------------------

def detect_resurrection(
    tree: ProcessNode,
    thresholds: dict[str, Any] | None = None,
) -> PatternMatch:
    t = thresholds or {}
    window = t.get("resurrection_window_seconds", 30)
    min_restarts = t.get("resurrection_min_restarts", 2)

    all_nodes_list = _all_nodes(tree)

    # Group by normalized name and check for rapid re-appearances
    by_name: dict[str, list[datetime]] = {}
    for n in all_nodes_list:
        if n.start_time is None:
            continue
        key = _normalize_process_name(n.name)
        by_name.setdefault(key, []).append(n.start_time)

    max_restarts = 0
    resurrected_name = ""
    for name, times in by_name.items():
        if len(times) < min_restarts + 1:
            continue
        times.sort()
        restarts = 0
        for i in range(1, len(times)):
            if (times[i] - times[i - 1]).total_seconds() <= window:
                restarts += 1
        if restarts > max_restarts:
            max_restarts = restarts
            resurrected_name = name

    if max_restarts < min_restarts:
        return PatternMatch("BEH-008", "Process resurrection", 0.0,
                            layers=["process", "behavior"])

    score = 0.5 if max_restarts == 2 else 0.8
    if max_restarts >= 4:
        score = 1.0

    return PatternMatch(
        pattern_id="BEH-008",
        pattern_name="Process resurrection",
        score=round(score, 2),
        evidence={
            "restarts": max_restarts,
            "process_name": resurrected_name,
            "window_seconds": window,
        },
        layers=["process", "behavior"],
    )


# ---------------------------------------------------------------------------
# BEH-009: Agent execution chain (DETEC-BEH-CORE-04)
# ---------------------------------------------------------------------------

def _llm_host_from_event(event: NetworkConnectEvent) -> str:
    """Return display host for an LLM network event (SNI or addr:port)."""
    addr = event.remote_addr.split(":")[0] if ":" in event.remote_addr else event.remote_addr
    if event.sni:
        return event.sni
    return f"{addr}:{event.remote_port}"


def _collect_git_add_commit_times(tree: ProcessNode) -> list[tuple[datetime, str]]:
    """Return (start_time, subcmd) for git add/commit child processes."""
    result: list[tuple[datetime, str]] = []
    for node in _all_nodes(tree):
        if _normalize_process_name(node.name) != "git" or node.start_time is None:
            continue
        parts = node.cmdline.split()
        for i, part in enumerate(parts):
            if _normalize_process_name(part) == "git" and i + 1 < len(parts):
                subcmd = parts[i + 1].lower()
                if subcmd in ("add", "commit"):
                    result.append((node.start_time, subcmd))
                break
    return result


def detect_agent_execution_chain(
    tree: ProcessNode,
    thresholds: dict[str, Any] | None = None,
) -> PatternMatch:
    """DETEC-BEH-CORE-04: Detect LLM call then shell/interpreter then file/git mod within window.

    Requires temporal order: t_llm <= t_shell <= t_file, all within execution_chain_window_seconds.
    """
    t = thresholds or {}
    window = t.get("execution_chain_window_seconds", 120)

    net_events = _collect_network_events(tree)
    llm_events = [(e.timestamp, _llm_host_from_event(e)) for e in net_events if _is_llm_host(e)]
    if not llm_events:
        return PatternMatch(
            "BEH-009", "Agent Execution Chain", 0.0,
            layers=["network", "process", "file"],
        )

    all_nodes_list = _all_nodes(tree)
    shell_times: list[tuple[datetime, str]] = []
    for n in all_nodes_list:
        if n.start_time is None:
            continue
        name = _normalize_process_name(n.name)
        if name in _SHELL_OR_INTERPRETER_NAMES:
            shell_times.append((n.start_time, n.name if n.name else name))

    file_events = _collect_file_events(tree)
    writes = [(e.timestamp, "file write") for e in file_events if e.action in ("created", "modified")]
    git_times = _collect_git_add_commit_times(tree)
    file_or_git: list[tuple[datetime, str]] = writes + [(ts, f"git {sc}") for ts, sc in git_times]
    file_or_git.sort(key=lambda x: x[0])

    if not shell_times or not file_or_git:
        return PatternMatch(
            "BEH-009", "Agent Execution Chain", 0.0,
            layers=["network", "process", "file"],
        )

    llm_events.sort(key=lambda x: x[0])
    shell_times.sort(key=lambda x: x[0])

    t_llm, llm_host = llm_events[0]
    window_end = t_llm + timedelta(seconds=window)

    t_shell_cand: tuple[datetime, str] | None = None
    for st, sname in shell_times:
        if t_llm <= st <= window_end:
            t_shell_cand = (st, sname)
            break
    if t_shell_cand is None:
        return PatternMatch(
            "BEH-009", "Agent Execution Chain", 0.0,
            layers=["network", "process", "file"],
        )

    t_shell, shell_name = t_shell_cand
    t_file_cand: tuple[datetime, str] | None = None
    for ft, kind in file_or_git:
        if t_shell <= ft <= window_end:
            t_file_cand = (ft, kind)
            break
    if t_file_cand is None:
        return PatternMatch(
            "BEH-009", "Agent Execution Chain", 0.0,
            layers=["network", "process", "file"],
        )

    t_file, file_kind = t_file_cand
    window_seconds = round((t_file - t_llm).total_seconds(), 1)

    if file_kind == "file write":
        seq_file = "file write detected"
    elif file_kind.startswith("git "):
        seq_file = f"git {file_kind.split()[1]} detected"
    else:
        seq_file = file_kind

    sequence = [
        f"LLM API call: {llm_host}",
        f"shell execution: {os.path.basename(shell_name).lower() if shell_name else 'shell'}",
        seq_file,
    ]

    score = 0.8  # spec: all three layers present

    return PatternMatch(
        pattern_id="BEH-009",
        pattern_name="Agent Execution Chain",
        score=score,
        evidence={
            "summary": "AI-driven command execution chain detected",
            "sequence": sequence,
            "window_seconds": window_seconds,
            "llm_host": llm_host,
            "shell_name": shell_name,
            "file_kind": file_kind,
        },
        layers=["network", "process", "file"],
    )


# ---------------------------------------------------------------------------
# Aggregate
# ---------------------------------------------------------------------------

_ALL_DETECTORS = [
    detect_shell_fanout,
    detect_llm_cadence,
    detect_burst_write,
    detect_rmw_loop,
    detect_session_duration,
    detect_credential_access,
    detect_git_automation,
    detect_resurrection,
    detect_agent_execution_chain,
]


def detect_all_patterns(
    tree: ProcessNode,
    thresholds: dict[str, Any] | None = None,
) -> list[PatternMatch]:
    """Run all BEH-001 through BEH-009 pattern detectors.

    Returns only patterns with score > 0.0.
    """
    results: list[PatternMatch] = []
    for detector in _ALL_DETECTORS:
        match = detector(tree, thresholds)
        if match.score > 0.0:
            results.append(match)
    return results

"""Cross-agent correlation: detect when multiple tools appear in the same process tree.

Used to attach correlation_context (multi_agent, related_tool_names) to events
so the SOC can see chained or coordinated agent use. See docs/cross-agent-detection-design.md.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Callable

from scanner.process_tree import build_trees, get_all_pids

if TYPE_CHECKING:
    from telemetry.event_store import EventStore
    from scanner.base import ScanResult


def compute_correlation(
    detected_scans: list[ScanResult],
    event_store: EventStore,
    extract_pids: Callable[[ScanResult], set[int]],
) -> dict[str, list[str]]:
    """Compute which detected tools are correlated (same process tree).

    For each tool, returns the list of other tool names that share at least one
    process tree (same PID set). Used to set event correlation_context.

    Args:
        detected_scans: List of ScanResult from this scan cycle.
        event_store: Current event store (process events used to build trees).
        extract_pids: Function (ScanResult) -> set[int] to get PIDs per scan.

    Returns:
        Map tool_name -> list of related_tool_names (other tools in same tree).
    """
    if len(detected_scans) < 2:
        return {s.tool_name or "": [] for s in detected_scans}

    trees = build_trees(event_store)
    tool_pids: dict[str, set[int]] = {}
    for scan in detected_scans:
        name = scan.tool_name or ""
        pids = extract_pids(scan)
        if pids:
            tool_pids[name] = pids

    related: dict[str, set[str]] = {name: set() for name in tool_pids}

    for tree in trees:
        tree_pids = get_all_pids(tree)
        if not tree_pids:
            continue
        in_tree: list[str] = []
        for name, pids in tool_pids.items():
            if pids & tree_pids:
                in_tree.append(name)
        for i, name_a in enumerate(in_tree):
            for name_b in in_tree[i + 1 :]:
                if name_a != name_b:
                    related[name_a].add(name_b)
                    related[name_b].add(name_a)

    return {name: sorted(related[name]) for name in tool_pids}

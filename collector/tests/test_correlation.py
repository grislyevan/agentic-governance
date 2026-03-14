"""Tests for cross-agent correlation (engine.correlation)."""

from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest

_COLLECTOR_DIR = str(Path(__file__).resolve().parent.parent)
if _COLLECTOR_DIR not in sys.path:
    sys.path.insert(0, _COLLECTOR_DIR)

from engine.correlation import compute_correlation
from scanner.base import LayerSignals, ScanResult
from telemetry.event_store import EventStore, ProcessExecEvent


def _make_pe(pid: int, ppid: int, name: str = "proc") -> ProcessExecEvent:
    return ProcessExecEvent(
        timestamp=datetime.now(timezone.utc),
        pid=pid,
        ppid=ppid,
        name=name,
        cmdline=name,
        source="polling",
    )


def _extract_pids(scan: ScanResult) -> set[int]:
    """Match main._extract_pids: process_entries and listener_pid/ipykernel_pid."""
    pids: set[int] = set()
    details = getattr(scan, "evidence_details", None) or {}
    for entry in details.get("process_entries", []):
        pid = entry.get("pid")
        if isinstance(pid, int):
            pids.add(pid)
        elif isinstance(pid, str) and pid.isdigit():
            pids.add(int(pid))
    for key in ("listener_pid", "ipykernel_pid"):
        pid = details.get(key)
        if isinstance(pid, int):
            pids.add(pid)
    return pids


def test_empty_scans_returns_empty_map() -> None:
    store = EventStore()
    scans: list[ScanResult] = []
    result = compute_correlation(scans, store, _extract_pids)
    assert result == {}


def test_single_scan_returns_no_related() -> None:
    store = EventStore()
    scan = ScanResult(
        detected=True,
        tool_name="Cursor",
        tool_class="A",
        signals=LayerSignals(0.5, 0.5, 0, 0, 0),
        evidence_details={"process_entries": [{"pid": 100}]},
    )
    result = compute_correlation([scan], store, _extract_pids)
    assert result == {"Cursor": []}


def test_two_tools_same_tree_correlated() -> None:
    store = EventStore()
    store.push_process(_make_pe(1, 0, "init"))
    store.push_process(_make_pe(100, 1, "cursor"))
    store.push_process(_make_pe(101, 100, "node"))
    store.push_process(_make_pe(102, 100, "oi"))
    scan_a = ScanResult(
        detected=True,
        tool_name="Cursor",
        tool_class="A",
        signals=LayerSignals(0.5, 0.5, 0, 0, 0),
        evidence_details={"process_entries": [{"pid": 100}]},
    )
    scan_b = ScanResult(
        detected=True,
        tool_name="Open Interpreter",
        tool_class="C",
        signals=LayerSignals(0.5, 0.5, 0, 0, 0),
        evidence_details={"process_entries": [{"pid": 102}]},
    )
    result = compute_correlation([scan_a, scan_b], store, _extract_pids)
    assert "Cursor" in result
    assert "Open Interpreter" in result
    assert "Open Interpreter" in result["Cursor"]
    assert "Cursor" in result["Open Interpreter"]


def test_two_tools_different_trees_not_correlated() -> None:
    store = EventStore()
    store.push_process(_make_pe(1, 0, "init1"))
    store.push_process(_make_pe(2, 0, "init2"))
    store.push_process(_make_pe(200, 1, "cursor"))
    store.push_process(_make_pe(300, 2, "claude"))
    scan_a = ScanResult(
        detected=True,
        tool_name="Cursor",
        tool_class="A",
        signals=LayerSignals(0.5, 0.5, 0, 0, 0),
        evidence_details={"process_entries": [{"pid": 200}]},
    )
    scan_b = ScanResult(
        detected=True,
        tool_name="Claude Code",
        tool_class="C",
        signals=LayerSignals(0.5, 0.5, 0, 0, 0),
        evidence_details={"process_entries": [{"pid": 300}]},
    )
    result = compute_correlation([scan_a, scan_b], store, _extract_pids)
    assert result["Cursor"] == []
    assert result["Claude Code"] == []

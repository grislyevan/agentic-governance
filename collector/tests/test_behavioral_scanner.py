"""Unit tests for Phase 2 Behavioral Anomaly Scanner."""

from __future__ import annotations

import os
import unittest
import unittest.mock
from datetime import datetime, timedelta, timezone

from engine.confidence import BEHAVIORAL_WEIGHTS, TOOL_WEIGHTS, get_weights
from scanner.behavioral import BehavioralScanner
from scanner.behavioral_patterns import (
    detect_agent_execution_chain,
    detect_all_patterns,
    detect_burst_write,
    detect_credential_access,
    detect_git_automation,
    detect_llm_cadence,
    detect_resurrection,
    detect_rmw_loop,
    detect_session_duration,
    detect_shell_fanout,
    get_llm_hosts,
    update_llm_hosts,
)
from scanner.process_tree import (
    ProcessNode,
    build_trees,
    get_all_pids,
    tree_depth,
    tree_duration,
)
from telemetry.capabilities import TelemetryCapabilities
from telemetry.event_store import (
    EventStore,
    FileChangeEvent,
    NetworkConnectEvent,
    ProcessExecEvent,
)

_BASE = datetime(2026, 3, 11, 12, 0, 0, tzinfo=timezone.utc)


def _make_tree(
    pid: int = 100,
    ppid: int = 0,
    name: str = "python3",
    cmdline: str = "python3 agent.py",
    children: list[ProcessNode] | None = None,
    network_events: list[NetworkConnectEvent] | None = None,
    file_events: list[FileChangeEvent] | None = None,
    start_time: datetime | None = None,
) -> ProcessNode:
    return ProcessNode(
        pid=pid,
        ppid=ppid,
        name=name,
        cmdline=cmdline,
        children=children or [],
        network_events=network_events or [],
        file_events=file_events or [],
        start_time=start_time or _BASE,
    )


class TestProcessTreeBuilder(unittest.TestCase):
    def test_empty_store_returns_no_trees(self) -> None:
        store = EventStore(max_events=1000, retention_seconds=86400 * 365)
        trees = build_trees(store)
        self.assertEqual(trees, [])

    def test_single_process_creates_root(self) -> None:
        store = EventStore(max_events=1000, retention_seconds=86400 * 365)
        store.push_process(
            ProcessExecEvent(
                timestamp=_BASE,
                pid=100,
                ppid=0,
                name="python3",
                cmdline="python3 agent.py",
            )
        )
        trees = build_trees(store)
        self.assertEqual(len(trees), 1)
        self.assertEqual(trees[0].pid, 100)
        self.assertEqual(trees[0].ppid, 0)
        self.assertEqual(trees[0].name, "python3")

    def test_parent_child_linking(self) -> None:
        store = EventStore(max_events=1000, retention_seconds=86400 * 365)
        store.push_process(
            ProcessExecEvent(
                timestamp=_BASE,
                pid=100,
                ppid=0,
                name="python3",
                cmdline="python3 agent.py",
            )
        )
        store.push_process(
            ProcessExecEvent(
                timestamp=_BASE + timedelta(seconds=1),
                pid=101,
                ppid=100,
                name="bash",
                cmdline="bash",
            )
        )
        trees = build_trees(store)
        self.assertEqual(len(trees), 1)
        self.assertEqual(len(trees[0].children), 1)
        self.assertEqual(trees[0].children[0].pid, 101)
        self.assertEqual(trees[0].children[0].ppid, 100)

    def test_duplicate_pids_keeps_latest(self) -> None:
        store = EventStore(max_events=1000, retention_seconds=86400 * 365)
        store.push_process(
            ProcessExecEvent(
                timestamp=_BASE,
                pid=100,
                ppid=0,
                name="python3",
                cmdline="python3 old.py",
            )
        )
        store.push_process(
            ProcessExecEvent(
                timestamp=_BASE + timedelta(seconds=5),
                pid=100,
                ppid=0,
                name="python3",
                cmdline="python3 new.py",
            )
        )
        trees = build_trees(store)
        self.assertEqual(len(trees), 1)
        self.assertEqual(trees[0].cmdline, "python3 new.py")

    def test_network_events_attached_to_correct_node(self) -> None:
        store = EventStore(max_events=1000, retention_seconds=86400 * 365)
        store.push_process(
            ProcessExecEvent(
                timestamp=_BASE,
                pid=100,
                ppid=0,
                name="python3",
                cmdline="python3 agent.py",
            )
        )
        store.push_network(
            NetworkConnectEvent(
                timestamp=_BASE + timedelta(seconds=1),
                pid=100,
                process_name="python3",
                remote_addr="api.openai.com",
                remote_port=443,
                local_port=54321,
            )
        )
        trees = build_trees(store)
        self.assertEqual(len(trees), 1)
        self.assertEqual(len(trees[0].network_events), 1)
        self.assertEqual(trees[0].network_events[0].remote_addr, "api.openai.com")

    def test_file_events_attached_to_correct_node(self) -> None:
        store = EventStore(max_events=1000, retention_seconds=86400 * 365)
        store.push_process(
            ProcessExecEvent(
                timestamp=_BASE,
                pid=100,
                ppid=0,
                name="python3",
                cmdline="python3 agent.py",
            )
        )
        store.push_file(
            FileChangeEvent(
                timestamp=_BASE + timedelta(seconds=1),
                path="/tmp/foo.txt",
                action="modified",
                pid=100,
                process_name="python3",
            )
        )
        trees = build_trees(store)
        self.assertEqual(len(trees), 1)
        self.assertEqual(len(trees[0].file_events), 1)
        self.assertEqual(trees[0].file_events[0].path, "/tmp/foo.txt")

    def test_get_all_pids_recursive(self) -> None:
        child = _make_tree(pid=101, ppid=100, name="bash", children=[])
        grandchild = _make_tree(pid=102, ppid=101, name="sh", children=[])
        child.children.append(grandchild)
        root = _make_tree(pid=100, ppid=0, children=[child])
        pids = get_all_pids(root)
        self.assertEqual(pids, {100, 101, 102})

    def test_tree_depth_single_node(self) -> None:
        root = _make_tree(pid=100, ppid=0, children=[])
        self.assertEqual(tree_depth(root), 1)

    def test_tree_depth_deep_tree(self) -> None:
        node = _make_tree(pid=103, ppid=102, name="leaf", children=[])
        node = _make_tree(pid=102, ppid=101, name="mid", children=[node])
        node = _make_tree(pid=101, ppid=100, name="child", children=[node])
        root = _make_tree(pid=100, ppid=0, children=[node])
        self.assertEqual(tree_depth(root), 4)

    def test_tree_duration_calculates_span(self) -> None:
        root = _make_tree(
            pid=100,
            ppid=0,
            start_time=_BASE,
            network_events=[
                NetworkConnectEvent(
                    timestamp=_BASE + timedelta(seconds=10),
                    pid=100,
                    process_name="python3",
                    remote_addr="x",
                    remote_port=443,
                    local_port=1000,
                ),
            ],
        )
        self.assertAlmostEqual(tree_duration(root), 10.0, places=1)


class TestBEH001ShellFanout(unittest.TestCase):
    def test_no_children_scores_zero(self) -> None:
        root = _make_tree(pid=100, ppid=0, children=[])
        self.assertEqual(detect_shell_fanout(root).score, 0.0)

    def test_below_threshold_scores_zero(self) -> None:
        children = [
            _make_tree(pid=101 + i, ppid=100, name="bash", start_time=_BASE + timedelta(seconds=i))
            for i in range(3)
        ]
        root = _make_tree(pid=100, ppid=0, children=children, start_time=_BASE)
        self.assertEqual(detect_shell_fanout(root).score, 0.0)

    def test_at_threshold_scores_positive(self) -> None:
        children = [
            _make_tree(pid=101 + i, ppid=100, name="bash", start_time=_BASE + timedelta(seconds=i))
            for i in range(5)
        ]
        root = _make_tree(pid=100, ppid=0, children=children, start_time=_BASE)
        self.assertGreater(detect_shell_fanout(root).score, 0.0)

    def test_many_shells_scores_high(self) -> None:
        children = [
            _make_tree(pid=101 + i, ppid=100, name="zsh", start_time=_BASE + timedelta(seconds=i))
            for i in range(12)
        ]
        root = _make_tree(pid=100, ppid=0, children=children, start_time=_BASE)
        self.assertGreaterEqual(detect_shell_fanout(root).score, 0.8)

    def test_custom_threshold_overrides_default(self) -> None:
        children = [
            _make_tree(pid=101 + i, ppid=100, name="bash", start_time=_BASE + timedelta(seconds=i))
            for i in range(3)
        ]
        root = _make_tree(pid=100, ppid=0, children=children, start_time=_BASE)
        self.assertEqual(detect_shell_fanout(root).score, 0.0)
        match = detect_shell_fanout(root, {"shell_fanout_min_children": 2})
        self.assertGreater(match.score, 0.0)


class TestBEH002LLMCadence(unittest.TestCase):
    def test_no_network_scores_zero(self) -> None:
        root = _make_tree(pid=100, ppid=0, network_events=[])
        self.assertEqual(detect_llm_cadence(root).score, 0.0)

    def test_below_threshold_scores_zero(self) -> None:
        net = [
            NetworkConnectEvent(
                timestamp=_BASE + timedelta(seconds=i),
                pid=100,
                process_name="python3",
                remote_addr="api.openai.com",
                remote_port=443,
                local_port=5000 + i,
            )
            for i in range(2)
        ]
        root = _make_tree(pid=100, ppid=0, network_events=net)
        self.assertEqual(detect_llm_cadence(root).score, 0.0)

    def test_multiple_llm_connections_scores_positive(self) -> None:
        net = [
            NetworkConnectEvent(
                timestamp=_BASE + timedelta(seconds=i),
                pid=100,
                process_name="python3",
                remote_addr="api.openai.com",
                remote_port=443,
                local_port=5000 + i,
            )
            for i in range(5)
        ]
        root = _make_tree(pid=100, ppid=0, network_events=net)
        self.assertGreater(detect_llm_cadence(root).score, 0.0)

    def test_sni_matching_works(self) -> None:
        net = [
            NetworkConnectEvent(
                timestamp=_BASE + timedelta(seconds=i),
                pid=100,
                process_name="python3",
                remote_addr="1.2.3.4",
                remote_port=443,
                local_port=5000 + i,
                sni="api.anthropic.com",
            )
            for i in range(2)
        ]
        root = _make_tree(pid=100, ppid=0, network_events=net)
        self.assertEqual(detect_llm_cadence(root).score, 0.0)
        net.append(
            NetworkConnectEvent(
                timestamp=_BASE + timedelta(seconds=3),
                pid=100,
                process_name="python3",
                remote_addr="1.2.3.4",
                remote_port=443,
                local_port=5003,
                sni="api.anthropic.com",
            )
        )
        root = _make_tree(pid=100, ppid=0, network_events=net)
        self.assertGreater(detect_llm_cadence(root).score, 0.0)


class TestBEH003BurstWrite(unittest.TestCase):
    def test_few_files_scores_zero(self) -> None:
        files = [
            FileChangeEvent(
                timestamp=_BASE + timedelta(seconds=i),
                path=f"/tmp{os.sep}file{i}.txt",
                action="modified",
                pid=100,
            )
            for i in range(5)
        ]
        root = _make_tree(pid=100, ppid=0, file_events=files)
        self.assertEqual(detect_burst_write(root).score, 0.0)

    def test_files_in_too_few_dirs_scores_zero(self) -> None:
        files = [
            FileChangeEvent(
                timestamp=_BASE + timedelta(seconds=i),
                path=f"/tmp{os.sep}file{i}.txt",
                action="modified",
                pid=100,
            )
            for i in range(12)
        ]
        root = _make_tree(pid=100, ppid=0, file_events=files)
        self.assertEqual(detect_burst_write(root).score, 0.0)

    def test_burst_across_dirs_scores_positive(self) -> None:
        dirs = [f"/tmp{os.sep}dir{i}{os.sep}" for i in range(4)]
        files = []
        for i in range(12):
            files.append(
                FileChangeEvent(
                    timestamp=_BASE + timedelta(seconds=i),
                    path=dirs[i % 4] + f"file{i}.txt",
                    action="modified",
                    pid=100,
                )
            )
        root = _make_tree(pid=100, ppid=0, file_events=files)
        self.assertGreater(detect_burst_write(root).score, 0.0)


class TestBEH004RMWLoop(unittest.TestCase):
    def test_no_events_scores_zero(self) -> None:
        root = _make_tree(pid=100, ppid=0, network_events=[], file_events=[])
        self.assertEqual(detect_rmw_loop(root).score, 0.0)

    def test_file_net_file_cycle_detected(self) -> None:
        file_events = [
            FileChangeEvent(
                timestamp=_BASE,
                path="/tmp/a.txt",
                action="modified",
                pid=100,
            ),
            FileChangeEvent(
                timestamp=_BASE + timedelta(seconds=4),
                path="/tmp/b.txt",
                action="modified",
                pid=100,
            ),
            FileChangeEvent(
                timestamp=_BASE + timedelta(seconds=6),
                path="/tmp/c.txt",
                action="modified",
                pid=100,
            ),
            FileChangeEvent(
                timestamp=_BASE + timedelta(seconds=8),
                path="/tmp/d.txt",
                action="modified",
                pid=100,
            ),
        ]
        net_events = [
            NetworkConnectEvent(
                timestamp=_BASE + timedelta(seconds=2),
                pid=100,
                process_name="python3",
                remote_addr="api.openai.com",
                remote_port=443,
                local_port=5000,
            ),
            NetworkConnectEvent(
                timestamp=_BASE + timedelta(seconds=7),
                pid=100,
                process_name="python3",
                remote_addr="api.openai.com",
                remote_port=443,
                local_port=5001,
            ),
        ]
        root = _make_tree(
            pid=100,
            ppid=0,
            network_events=net_events,
            file_events=file_events,
        )
        self.assertGreater(detect_rmw_loop(root).score, 0.0)


class TestBEH005SessionDuration(unittest.TestCase):
    def test_short_session_scores_zero(self) -> None:
        root = _make_tree(
            pid=100,
            ppid=0,
            start_time=_BASE,
            network_events=[
                NetworkConnectEvent(
                    timestamp=_BASE + timedelta(seconds=10),
                    pid=100,
                    process_name="python3",
                    remote_addr="x",
                    remote_port=443,
                    local_port=1000,
                ),
            ],
        )
        self.assertEqual(detect_session_duration(root).score, 0.0)

    def test_long_continuous_session_scores_positive(self) -> None:
        root = _make_tree(
            pid=100,
            ppid=0,
            start_time=_BASE,
            network_events=[
                NetworkConnectEvent(
                    timestamp=_BASE + timedelta(seconds=i * 30),
                    pid=100,
                    process_name="python3",
                    remote_addr="x",
                    remote_port=443,
                    local_port=1000 + i,
                )
                for i in range(1, 25)
            ],
        )
        match = detect_session_duration(root, {"session_min_duration_seconds": 600})
        self.assertGreater(match.score, 0.0)


class TestBEH006CredentialAccess(unittest.TestCase):
    def test_no_sensitive_files_scores_zero(self) -> None:
        files = [
            FileChangeEvent(
                timestamp=_BASE,
                path="/tmp/foo.txt",
                action="modified",
                pid=100,
            ),
        ]
        root = _make_tree(pid=100, ppid=0, file_events=files, network_events=[])
        self.assertEqual(detect_credential_access(root).score, 0.0)

    def test_sensitive_file_with_network_scores_positive(self) -> None:
        files = [
            FileChangeEvent(
                timestamp=_BASE,
                path=f"/home{os.sep}user{os.sep}.env",
                action="modified",
                pid=100,
            ),
        ]
        net = [
            NetworkConnectEvent(
                timestamp=_BASE,
                pid=100,
                process_name="python3",
                remote_addr="api.openai.com",
                remote_port=443,
                local_port=5000,
            ),
        ]
        root = _make_tree(pid=100, ppid=0, file_events=files, network_events=net)
        self.assertGreater(detect_credential_access(root).score, 0.0)

    def test_sensitive_file_without_network_scores_zero_when_required(self) -> None:
        files = [
            FileChangeEvent(
                timestamp=_BASE,
                path=f"/home{os.sep}user{os.sep}.env",
                action="modified",
                pid=100,
            ),
        ]
        root = _make_tree(pid=100, ppid=0, file_events=files, network_events=[])
        self.assertEqual(detect_credential_access(root).score, 0.0)


class TestBEH007GitAutomation(unittest.TestCase):
    def test_no_git_scores_zero(self) -> None:
        root = _make_tree(pid=100, ppid=0, children=[])
        self.assertEqual(detect_git_automation(root).score, 0.0)

    def test_add_commit_push_sequence_detected(self) -> None:
        children = [
            _make_tree(
                pid=101,
                ppid=100,
                name="git",
                cmdline="git add .",
                start_time=_BASE,
            ),
            _make_tree(
                pid=102,
                ppid=100,
                name="git",
                cmdline="git commit -m msg",
                start_time=_BASE + timedelta(seconds=1),
            ),
            _make_tree(
                pid=103,
                ppid=100,
                name="git",
                cmdline="git push",
                start_time=_BASE + timedelta(seconds=2),
            ),
        ]
        root = _make_tree(pid=100, ppid=0, children=children, start_time=_BASE)
        self.assertGreater(detect_git_automation(root).score, 0.0)

    def test_editor_presence_suppresses_detection(self) -> None:
        children = [
            _make_tree(
                pid=101,
                ppid=100,
                name="git",
                cmdline="git add .",
                start_time=_BASE,
            ),
            _make_tree(
                pid=102,
                ppid=100,
                name="git",
                cmdline="git commit -m msg",
                start_time=_BASE + timedelta(seconds=1),
            ),
            _make_tree(
                pid=103,
                ppid=100,
                name="git",
                cmdline="git push",
                start_time=_BASE + timedelta(seconds=2),
            ),
            _make_tree(
                pid=104,
                ppid=100,
                name="cursor",
                cmdline="cursor",
                start_time=_BASE + timedelta(seconds=3),
            ),
        ]
        root = _make_tree(pid=100, ppid=0, children=children, start_time=_BASE)
        self.assertEqual(detect_git_automation(root).score, 0.0)


class TestBEH008Resurrection(unittest.TestCase):
    def test_no_restarts_scores_zero(self) -> None:
        root = _make_tree(pid=100, ppid=0, start_time=_BASE, children=[])
        self.assertEqual(detect_resurrection(root).score, 0.0)

    def test_rapid_restarts_detected(self) -> None:
        children = [
            _make_tree(
                pid=101,
                ppid=100,
                name="python3",
                cmdline="python3 agent.py",
                start_time=_BASE,
            ),
            _make_tree(
                pid=102,
                ppid=100,
                name="python3",
                cmdline="python3 agent.py",
                start_time=_BASE + timedelta(seconds=5),
            ),
            _make_tree(
                pid=103,
                ppid=100,
                name="python3",
                cmdline="python3 agent.py",
                start_time=_BASE + timedelta(seconds=10),
            ),
        ]
        root = _make_tree(pid=100, ppid=0, children=children, start_time=_BASE)
        self.assertGreater(detect_resurrection(root).score, 0.0)


class TestBEH009AgentExecutionChain(unittest.TestCase):
    """Tests for BEH-009 (DETEC-BEH-CORE-04): LLM then shell then file/git within window."""

    def test_no_llm_scores_zero(self) -> None:
        """Missing LLM network activity: no match."""
        shell_child = _make_tree(
            pid=101, ppid=100, name="bash", start_time=_BASE + timedelta(seconds=5),
        )
        files = [
            FileChangeEvent(
                timestamp=_BASE + timedelta(seconds=10),
                path="/tmp/x.txt",
                action="modified",
                pid=100,
            ),
        ]
        root = _make_tree(
            pid=100, ppid=0, children=[shell_child], file_events=files, start_time=_BASE,
        )
        self.assertEqual(detect_agent_execution_chain(root).score, 0.0)

    def test_no_shell_scores_zero(self) -> None:
        """Missing shell/interpreter execution: no match."""
        net = [
            NetworkConnectEvent(
                timestamp=_BASE,
                pid=100,
                process_name="python3",
                remote_addr="api.anthropic.com",
                remote_port=443,
                local_port=5000,
            ),
        ]
        files = [
            FileChangeEvent(
                timestamp=_BASE + timedelta(seconds=10),
                path="/tmp/x.txt",
                action="modified",
                pid=100,
            ),
        ]
        root = _make_tree(
            pid=100, ppid=0, network_events=net, file_events=files, start_time=_BASE,
        )
        self.assertEqual(detect_agent_execution_chain(root).score, 0.0)

    def test_no_file_or_git_scores_zero(self) -> None:
        """Missing file write or git add/commit: no match."""
        net = [
            NetworkConnectEvent(
                timestamp=_BASE,
                pid=100,
                process_name="python3",
                remote_addr="api.openai.com",
                remote_port=443,
                local_port=5000,
            ),
        ]
        shell_child = _make_tree(
            pid=101, ppid=100, name="bash", start_time=_BASE + timedelta(seconds=5),
        )
        root = _make_tree(
            pid=100, ppid=0, children=[shell_child], network_events=net, start_time=_BASE,
        )
        self.assertEqual(detect_agent_execution_chain(root).score, 0.0)

    def test_wrong_order_scores_zero(self) -> None:
        """File write before shell: no match (requires LLM then shell then file)."""
        net = [
            NetworkConnectEvent(
                timestamp=_BASE + timedelta(seconds=20),
                pid=100,
                process_name="python3",
                remote_addr="api.openai.com",
                remote_port=443,
                local_port=5000,
            ),
        ]
        shell_child = _make_tree(
            pid=101, ppid=100, name="zsh", start_time=_BASE + timedelta(seconds=25),
        )
        files = [
            FileChangeEvent(
                timestamp=_BASE + timedelta(seconds=5),
                path="/tmp/x.txt",
                action="modified",
                pid=100,
            ),
        ]
        root = _make_tree(
            pid=100,
            ppid=0,
            children=[shell_child],
            network_events=net,
            file_events=files,
            start_time=_BASE,
        )
        self.assertEqual(detect_agent_execution_chain(root).score, 0.0)

    def test_outside_window_scores_zero(self) -> None:
        """Shell and file outside default 120s window: no match."""
        net = [
            NetworkConnectEvent(
                timestamp=_BASE,
                pid=100,
                process_name="python3",
                remote_addr="api.openai.com",
                remote_port=443,
                local_port=5000,
            ),
        ]
        shell_child = _make_tree(
            pid=101, ppid=100, name="bash", start_time=_BASE + timedelta(seconds=130),
        )
        files = [
            FileChangeEvent(
                timestamp=_BASE + timedelta(seconds=140),
                path="/tmp/x.txt",
                action="modified",
                pid=100,
            ),
        ]
        root = _make_tree(
            pid=100,
            ppid=0,
            children=[shell_child],
            network_events=net,
            file_events=files,
            start_time=_BASE,
        )
        self.assertEqual(detect_agent_execution_chain(root).score, 0.0)

    def test_llm_then_shell_then_file_matches(self) -> None:
        """LLM at t=0, shell at t=5, file at t=10 within 120s: match."""
        net = [
            NetworkConnectEvent(
                timestamp=_BASE,
                pid=100,
                process_name="python3",
                remote_addr="api.anthropic.com",
                remote_port=443,
                local_port=5000,
            ),
        ]
        shell_child = _make_tree(
            pid=101, ppid=100, name="bash", start_time=_BASE + timedelta(seconds=5),
        )
        files = [
            FileChangeEvent(
                timestamp=_BASE + timedelta(seconds=10),
                path="/tmp/main.py",
                action="modified",
                pid=100,
            ),
        ]
        root = _make_tree(
            pid=100,
            ppid=0,
            children=[shell_child],
            network_events=net,
            file_events=files,
            start_time=_BASE,
        )
        match = detect_agent_execution_chain(root)
        self.assertGreater(match.score, 0.0)
        self.assertEqual(match.pattern_id, "BEH-009")
        self.assertEqual(match.pattern_name, "Agent Execution Chain")
        ev = match.evidence
        self.assertIn("sequence", ev)
        self.assertEqual(len(ev["sequence"]), 3)
        self.assertIn("LLM API call:", ev["sequence"][0])
        self.assertIn("shell execution:", ev["sequence"][1])
        self.assertIn("file write detected", ev["sequence"][2])
        self.assertEqual(ev["window_seconds"], 10.0)
        self.assertEqual(ev["summary"], "AI-driven command execution chain detected")
        self.assertEqual(ev.get("distinct_file_count"), 1)
        self.assertEqual(ev.get("git_action_count"), 0)
        self.assertFalse(ev.get("multi_file_change", True))
        self.assertFalse(ev.get("repeated_git_activity", True))

    def test_stale_first_llm_event_still_detects_later_valid_chain(self) -> None:
        """If first LLM event is stale, detector should still match a later valid chain."""
        net = [
            # Stale / unrelated LLM call outside the chain window
            NetworkConnectEvent(
                timestamp=_BASE,
                pid=100,
                process_name="python3",
                remote_addr="api.openai.com",
                remote_port=443,
                local_port=5000,
            ),
            # Valid chain anchor closer to shell/file activity
            NetworkConnectEvent(
                timestamp=_BASE + timedelta(seconds=130),
                pid=100,
                process_name="python3",
                remote_addr="api.anthropic.com",
                remote_port=443,
                local_port=5001,
            ),
        ]
        shell_child = _make_tree(
            pid=101, ppid=100, name="bash", start_time=_BASE + timedelta(seconds=135),
        )
        files = [
            FileChangeEvent(
                timestamp=_BASE + timedelta(seconds=140),
                path="/tmp/main.py",
                action="modified",
                pid=100,
            ),
        ]
        root = _make_tree(
            pid=100,
            ppid=0,
            children=[shell_child],
            network_events=net,
            file_events=files,
            start_time=_BASE,
        )
        match = detect_agent_execution_chain(root)
        self.assertGreater(match.score, 0.0)
        ev = match.evidence
        self.assertEqual(ev.get("llm_host"), "api.anthropic.com:443")
        self.assertEqual(ev.get("window_seconds"), 10.0)

    def test_llm_then_shell_then_git_commit_matches(self) -> None:
        """LLM then shell then git commit: match."""
        net = [
            NetworkConnectEvent(
                timestamp=_BASE,
                pid=100,
                process_name="python3",
                remote_addr="api.openai.com",
                remote_port=443,
                local_port=5000,
            ),
        ]
        shell_child = _make_tree(
            pid=101, ppid=100, name="bash", start_time=_BASE + timedelta(seconds=5),
        )
        git_commit = _make_tree(
            pid=102,
            ppid=100,
            name="git",
            cmdline="git commit -m fix",
            start_time=_BASE + timedelta(seconds=15),
        )
        root = _make_tree(
            pid=100,
            ppid=0,
            children=[shell_child, git_commit],
            network_events=net,
            start_time=_BASE,
        )
        match = detect_agent_execution_chain(root)
        self.assertGreater(match.score, 0.0)
        ev = match.evidence
        self.assertIn("git commit detected", ev["sequence"][2])
        self.assertEqual(ev.get("git_action_count"), 1)
        self.assertFalse(ev.get("repeated_git_activity", True))

    def test_beh009_evidence_multi_file_change(self) -> None:
        """Multiple distinct file paths in chain window: multi_file_change True."""
        net = [
            NetworkConnectEvent(
                timestamp=_BASE,
                pid=100,
                process_name="python3",
                remote_addr="api.openai.com",
                remote_port=443,
                local_port=5000,
            ),
        ]
        shell_child = _make_tree(
            pid=101, ppid=100, name="bash", start_time=_BASE + timedelta(seconds=5),
        )
        files = [
            FileChangeEvent(
                timestamp=_BASE + timedelta(seconds=10),
                path="/tmp/main.py",
                action="modified",
                pid=100,
            ),
            FileChangeEvent(
                timestamp=_BASE + timedelta(seconds=12),
                path="/tmp/other.py",
                action="modified",
                pid=100,
            ),
        ]
        root = _make_tree(
            pid=100,
            ppid=0,
            children=[shell_child],
            network_events=net,
            file_events=files,
            start_time=_BASE,
        )
        match = detect_agent_execution_chain(root)
        self.assertGreater(match.score, 0.0)
        ev = match.evidence
        self.assertEqual(ev.get("distinct_file_count"), 2)
        self.assertTrue(ev.get("multi_file_change"))

    def test_beh009_evidence_repeated_git_activity(self) -> None:
        """Multiple git add/commit in chain window: repeated_git_activity True."""
        net = [
            NetworkConnectEvent(
                timestamp=_BASE,
                pid=100,
                process_name="python3",
                remote_addr="api.anthropic.com",
                remote_port=443,
                local_port=5000,
            ),
        ]
        shell_child = _make_tree(
            pid=101, ppid=100, name="bash", start_time=_BASE + timedelta(seconds=5),
        )
        git_add = _make_tree(
            pid=102,
            ppid=100,
            name="git",
            cmdline="git add .",
            start_time=_BASE + timedelta(seconds=10),
        )
        git_commit = _make_tree(
            pid=103,
            ppid=100,
            name="git",
            cmdline="git commit -m msg",
            start_time=_BASE + timedelta(seconds=15),
        )
        root = _make_tree(
            pid=100,
            ppid=0,
            children=[shell_child, git_add, git_commit],
            network_events=net,
            start_time=_BASE,
        )
        match = detect_agent_execution_chain(root)
        self.assertGreater(match.score, 0.0)
        ev = match.evidence
        self.assertGreaterEqual(ev.get("git_action_count", 0), 2)
        self.assertTrue(ev.get("repeated_git_activity"))

    def test_scanner_includes_detection_code_when_beh009_fires(self) -> None:
        """Full scanner run: detection_codes includes DETEC-BEH-CORE-04 when BEH-009 matches."""
        store = EventStore(max_events=1000, retention_seconds=86400 * 365)
        store.push_process(
            ProcessExecEvent(
                timestamp=_BASE,
                pid=100,
                ppid=0,
                name="python3",
                cmdline="python3 agent.py",
            )
        )
        store.push_process(
            ProcessExecEvent(
                timestamp=_BASE + timedelta(seconds=5),
                pid=101,
                ppid=100,
                name="bash",
                cmdline="bash",
            )
        )
        store.push_network(
            NetworkConnectEvent(
                timestamp=_BASE,
                pid=100,
                process_name="python3",
                remote_addr="api.anthropic.com",
                remote_port=443,
                local_port=5000,
            )
        )
        store.push_file(
            FileChangeEvent(
                timestamp=_BASE + timedelta(seconds=10),
                path="/tmp/out.txt",
                action="modified",
                pid=100,
            )
        )
        # Lower threshold so BEH-009 alone (aggregate ~0.09) still triggers detection
        with unittest.mock.patch(
            "scanner.behavioral._load_behavioral_config",
            return_value={"enabled": True, "detection_threshold": 0.05},
        ):
            scanner = BehavioralScanner(event_store=store)
            result = scanner.scan()
        self.assertTrue(result.detected)
        codes = result.evidence_details.get("detection_codes", [])
        self.assertIn("DETEC-BEH-CORE-04", codes)
        patterns = result.evidence_details.get("behavioral_patterns", [])
        beh009 = next((p for p in patterns if p.get("pattern_id") == "BEH-009"), None)
        self.assertIsNotNone(beh009)
        self.assertIn("sequence", beh009.get("evidence", {}))
        self.assertIn("window_seconds", beh009.get("evidence", {}))


class TestPatternWindowBoundaries(unittest.TestCase):
    """Tests that BEH-001, BEH-006, and BEH-009 only use events inside their detection window."""

    def test_beh001_evidence_only_from_fanout_window(self) -> None:
        """Shell names and model_linked only reflect events inside the matched fan-out window."""
        # 6 shells at 0, 5, 10, 15, 20, 25s (window 60s) then 2 shells at 85, 90s (outside)
        children = [
            _make_tree(pid=101 + i, ppid=100, name="bash", start_time=_BASE + timedelta(seconds=i * 5))
            for i in range(6)
        ]
        children.extend([
            _make_tree(pid=107 + i, ppid=100, name="zsh", start_time=_BASE + timedelta(seconds=85 + i * 5))
            for i in range(2)
        ])
        root = _make_tree(pid=100, ppid=0, children=children, start_time=_BASE)
        match = detect_shell_fanout(root)
        self.assertGreater(match.score, 0.0)
        ev = match.evidence
        self.assertEqual(ev["shell_children_in_window"], 6)
        self.assertEqual(len(ev["shell_names"]), 6)
        self.assertEqual(len(ev["shell_timestamps"]), 6)
        for name in ev["shell_names"]:
            self.assertIn("bash", name.lower())

    def test_beh001_model_linked_only_from_window(self) -> None:
        """LLM network event outside the fan-out window does not set model_linked."""
        children = [
            _make_tree(pid=101 + i, ppid=100, name="bash", start_time=_BASE + timedelta(seconds=i * 5))
            for i in range(6)
        ]
        net_outside = [
            NetworkConnectEvent(
                timestamp=_BASE + timedelta(seconds=90),
                pid=100,
                process_name="python3",
                remote_addr="api.openai.com",
                remote_port=443,
                local_port=5000,
            ),
        ]
        root = _make_tree(
            pid=100, ppid=0, children=children, network_events=net_outside, start_time=_BASE,
        )
        match = detect_shell_fanout(root)
        self.assertGreater(match.score, 0.0)
        self.assertFalse(match.evidence.get("model_linked"))

    def test_beh006_sensitive_count_and_paths_only_in_window(self) -> None:
        """Sensitive file count and paths only include events within credential window."""
        t0 = _BASE
        t1 = _BASE + timedelta(seconds=1)
        t_outside = _BASE + timedelta(seconds=400)
        file_events = [
            FileChangeEvent(timestamp=t0, path="/home/u/.env", action="modified", pid=100),
            FileChangeEvent(timestamp=t1, path="/home/u/.ssh/config", action="modified", pid=100),
            FileChangeEvent(
                timestamp=t_outside,
                path="/home/u/.aws/credentials",
                action="modified",
                pid=100,
            ),
        ]
        net = [
            NetworkConnectEvent(
                timestamp=_BASE + timedelta(seconds=10),
                pid=100,
                process_name="python3",
                remote_addr="api.openai.com",
                remote_port=443,
                local_port=5000,
            ),
        ]
        root = _make_tree(
            pid=100, ppid=0, file_events=file_events, network_events=net, start_time=_BASE,
        )
        match = detect_credential_access(root, {"credential_network_max_seconds_after_access": 300})
        self.assertGreater(match.score, 0.0)
        ev = match.evidence
        self.assertEqual(ev["sensitive_files_accessed"], 2)
        self.assertEqual(len(ev["paths"]), 2)
        self.assertIn(".env", ev["paths"][0])
        self.assertIn(".ssh", ev["paths"][1])

    def test_beh009_identical_sessions_with_different_outside_window_same_detection(self) -> None:
        """Extra file/git events outside the execution chain window do not change detection."""
        def make_base_tree(extra_file_events: list | None = None):
            net = [
                NetworkConnectEvent(
                    timestamp=_BASE,
                    pid=100,
                    process_name="python3",
                    remote_addr="api.openai.com",
                    remote_port=443,
                    local_port=5000,
                ),
            ]
            shell_child = _make_tree(
                pid=101, ppid=100, name="bash", start_time=_BASE + timedelta(seconds=5),
            )
            files = [
                FileChangeEvent(
                    timestamp=_BASE + timedelta(seconds=10),
                    path="/tmp/x.txt",
                    action="modified",
                    pid=100,
                ),
            ]
            if extra_file_events:
                files.extend(extra_file_events)
            return _make_tree(
                pid=100,
                ppid=0,
                children=[shell_child],
                network_events=net,
                file_events=files,
                start_time=_BASE,
            )

        base = make_base_tree()
        with_extra = make_base_tree([
            FileChangeEvent(
                timestamp=_BASE + timedelta(seconds=200),
                path="/tmp/later.txt",
                action="modified",
                pid=100,
            ),
        ])
        m1 = detect_agent_execution_chain(base)
        m2 = detect_agent_execution_chain(with_extra)
        self.assertGreater(m1.score, 0.0)
        self.assertGreater(m2.score, 0.0)
        self.assertEqual(m1.evidence["distinct_file_count"], 1)
        self.assertEqual(m2.evidence["distinct_file_count"], 1)
        self.assertFalse(m1.evidence.get("multi_file_change"))
        self.assertFalse(m2.evidence.get("multi_file_change"))


class TestTelemetryCapabilities(unittest.TestCase):
    """Tests that detectors respect telemetry capability flags."""

    def test_beh009_returns_zero_when_file_change_capability_missing(self) -> None:
        """When capabilities.has_file_change is False, BEH-009 returns no match."""
        caps = TelemetryCapabilities(
            has_process_exec=True,
            has_file_change=False,
            has_file_read=False,
            has_network_events=True,
            has_process_parent=True,
        )
        net = [
            NetworkConnectEvent(
                timestamp=_BASE,
                pid=100,
                process_name="python3",
                remote_addr="api.openai.com",
                remote_port=443,
                local_port=5000,
            ),
        ]
        shell_child = _make_tree(
            pid=101, ppid=100, name="bash", start_time=_BASE + timedelta(seconds=5),
        )
        files = [
            FileChangeEvent(
                timestamp=_BASE + timedelta(seconds=10),
                path="/tmp/x.txt",
                action="modified",
                pid=100,
            ),
        ]
        root = _make_tree(
            pid=100,
            ppid=0,
            children=[shell_child],
            network_events=net,
            file_events=files,
            start_time=_BASE,
        )
        match = detect_agent_execution_chain(root, None, caps)
        self.assertEqual(match.score, 0.0)

    def test_detect_all_patterns_accepts_capabilities(self) -> None:
        """detect_all_patterns with capabilities runs without error."""
        root = _make_tree(pid=100, ppid=0, children=[])
        caps = TelemetryCapabilities(has_file_change=False, has_network_events=False)
        matches = detect_all_patterns(root, None, caps)
        self.assertEqual(matches, [])

    def test_session_evidence_includes_telemetry_notes_when_capability_gaps(self) -> None:
        """When store has no file events, detection evidence includes telemetry_notes."""
        store = EventStore(max_events=1000, retention_seconds=86400 * 365)
        base = _BASE
        for i in range(7):
            store.push_process(
                ProcessExecEvent(
                    timestamp=base + timedelta(seconds=i * 5),
                    pid=100 if i == 0 else 100 + i,
                    ppid=0 if i == 0 else 100,
                    name="python3" if i == 0 else "bash",
                    cmdline="python3 agent.py" if i == 0 else "bash",
                )
            )
        for i in range(4):
            store.push_network(
                NetworkConnectEvent(
                    timestamp=base + timedelta(seconds=i),
                    pid=100,
                    process_name="python3",
                    remote_addr="api.openai.com",
                    remote_port=443,
                    local_port=5000 + i,
                )
            )
        with unittest.mock.patch(
            "scanner.behavioral._load_behavioral_config",
            return_value={"enabled": True, "detection_threshold": 0.15},
        ):
            scanner = BehavioralScanner(event_store=store)
            result = scanner.scan()
        self.assertTrue(result.detected)
        self.assertIn("telemetry_notes", result.evidence_details)
        self.assertIn("file_change", result.evidence_details["telemetry_notes"])


class TestBehavioralWeights(unittest.TestCase):
    def test_unknown_agent_uses_behavioral_weights(self) -> None:
        self.assertEqual(get_weights("Unknown Agent"), BEHAVIORAL_WEIGHTS)
        self.assertEqual(TOOL_WEIGHTS["Unknown Agent"], BEHAVIORAL_WEIGHTS)

    def test_behavioral_weights_sum_to_one(self) -> None:
        total = sum(BEHAVIORAL_WEIGHTS.values())
        self.assertAlmostEqual(total, 1.0, places=5)


class TestLLMHostRegistry(unittest.TestCase):
    def test_default_hosts_present(self) -> None:
        hosts = get_llm_hosts()
        self.assertIn("api.openai.com", hosts)
        self.assertIn("api.anthropic.com", hosts)

    def test_update_adds_hosts(self) -> None:
        before = set(get_llm_hosts())
        update_llm_hosts({"custom.llm.example.com"})
        after = get_llm_hosts()
        self.assertIn("custom.llm.example.com", after)
        self.assertGreaterEqual(len(after), len(before))

    def test_get_returns_frozenset(self) -> None:
        hosts = get_llm_hosts()
        self.assertIsInstance(hosts, frozenset)


class TestDetectAllPatterns(unittest.TestCase):
    def test_returns_only_nonzero_matches(self) -> None:
        root = _make_tree(pid=100, ppid=0, children=[])
        matches = detect_all_patterns(root)
        self.assertEqual(matches, [])

    def test_agentic_bot_scenario(self) -> None:
        shells = [
            _make_tree(
                pid=101 + i,
                ppid=100,
                name="bash",
                start_time=_BASE + timedelta(seconds=i),
            )
            for i in range(10)
        ]
        net = [
            NetworkConnectEvent(
                timestamp=_BASE + timedelta(seconds=i),
                pid=100,
                process_name="python3",
                remote_addr="api.openai.com",
                remote_port=443,
                local_port=5000 + i,
            )
            for i in range(5)
        ]
        dirs = [f"/tmp{os.sep}dir{i}{os.sep}" for i in range(4)]
        files = []
        for i in range(15):
            files.append(
                FileChangeEvent(
                    timestamp=_BASE + timedelta(seconds=i),
                    path=dirs[i % 4] + f"file{i}.txt",
                    action="modified",
                    pid=100,
                )
            )
        root = _make_tree(
            pid=100,
            ppid=0,
            children=shells,
            network_events=net,
            file_events=files,
            start_time=_BASE,
        )
        matches = detect_all_patterns(root)
        self.assertGreaterEqual(len(matches), 3)

    def test_legitimate_cron_scenario(self) -> None:
        net = [
            NetworkConnectEvent(
                timestamp=_BASE,
                pid=100,
                process_name="curl",
                remote_addr="api.example.com",
                remote_port=443,
                local_port=5000,
            ),
        ]
        files = [
            FileChangeEvent(
                timestamp=_BASE,
                path="/var/log/cron.log",
                action="modified",
                pid=100,
            ),
        ]
        root = _make_tree(
            pid=100,
            ppid=0,
            network_events=net,
            file_events=files,
            start_time=_BASE,
        )
        matches = detect_all_patterns(root)
        self.assertLessEqual(len(matches), 1)


class TestBehavioralScanner(unittest.TestCase):
    def test_scan_with_empty_store_returns_not_detected(self) -> None:
        store = EventStore(max_events=1000, retention_seconds=86400 * 365)
        scanner = BehavioralScanner(event_store=store)
        result = scanner.scan()
        self.assertFalse(result.detected)

    def test_scan_with_agentic_tree_returns_detected(self) -> None:
        store = EventStore(max_events=1000, retention_seconds=86400 * 365)
        store.push_process(
            ProcessExecEvent(
                timestamp=_BASE,
                pid=100,
                ppid=0,
                name="python3",
                cmdline="python3 agent.py",
            )
        )
        for i in range(10):
            store.push_process(
                ProcessExecEvent(
                    timestamp=_BASE + timedelta(seconds=i),
                    pid=101 + i,
                    ppid=100,
                    name="bash",
                    cmdline="bash",
                )
            )
        for i in range(6):
            store.push_network(
                NetworkConnectEvent(
                    timestamp=_BASE + timedelta(seconds=i),
                    pid=100,
                    process_name="python3",
                    remote_addr="api.openai.com",
                    remote_port=443,
                    local_port=5000 + i,
                )
            )
        dirs = [f"/tmp{os.sep}dir{j}{os.sep}" for j in range(4)]
        for i in range(15):
            store.push_file(
                FileChangeEvent(
                    timestamp=_BASE + timedelta(seconds=i),
                    path=dirs[i % 4] + f"file{i}.txt",
                    action="modified",
                    pid=100,
                )
            )
        store.push_file(
            FileChangeEvent(
                timestamp=_BASE + timedelta(seconds=2),
                path="/tmp/a.txt",
                action="modified",
                pid=100,
            )
        )
        store.push_file(
            FileChangeEvent(
                timestamp=_BASE + timedelta(seconds=6),
                path="/tmp/b.txt",
                action="modified",
                pid=100,
            )
        )
        store.push_file(
            FileChangeEvent(
                timestamp=_BASE + timedelta(seconds=8),
                path="/tmp/c.txt",
                action="modified",
                pid=100,
            )
        )
        scanner = BehavioralScanner(event_store=store)
        result = scanner.scan()
        self.assertTrue(result.detected)
        self.assertEqual(result.tool_name, "Unknown Agent")


if __name__ == "__main__":
    unittest.main()

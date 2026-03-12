"""Unit tests for Phase 2 Behavioral Anomaly Scanner."""

from __future__ import annotations

import os
import unittest
from datetime import datetime, timedelta, timezone

from engine.confidence import BEHAVIORAL_WEIGHTS, TOOL_WEIGHTS, get_weights
from scanner.behavioral import BehavioralScanner
from scanner.behavioral_patterns import (
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

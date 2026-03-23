"""Tests for cross-tree correlation hints."""

from __future__ import annotations

from datetime import datetime, timezone
from unittest import TestCase

from telemetry.event_store import NetworkConnectEvent

from correlation.correlation_hints import (
    CorrelationHint,
    CorrelationHintsEngine,
    enrichment_for_tree,
    get_destination_clusters_for_tree,
    get_working_dir_for_tree,
    hints_for_tree,
)
from scanner.process_tree import ProcessNode


def _node(
    pid: int,
    ppid: int = 0,
    name: str = "proc",
    username: str | None = None,
    file_events: list | None = None,
    file_read_events: list | None = None,
    network_events: list | None = None,
    children: list | None = None,
) -> ProcessNode:
    return ProcessNode(
        pid=pid,
        ppid=ppid,
        name=name,
        cmdline=name,
        username=username,
        file_events=file_events or [],
        file_read_events=file_read_events or [],
        network_events=network_events or [],
        children=children or [],
        start_time=datetime.now(timezone.utc),
    )


class TestCorrelationHintsEngine(TestCase):
    def test_analyze_empty_trees(self) -> None:
        engine = CorrelationHintsEngine()
        self.assertEqual(engine.analyze([]), [])

    def test_analyze_single_tree_no_hints(self) -> None:
        engine = CorrelationHintsEngine()
        trees = [_node(100, ppid=1)]
        self.assertEqual(engine.analyze(trees), [])

    def test_same_repo_root(self) -> None:
        t = datetime.now(timezone.utc)

        class MockFileEvent:
            def __init__(self, path: str) -> None:
                self.path = path
                self.timestamp = t

        tree_a = _node(100, ppid=1, file_events=[MockFileEvent("/project/.git/HEAD")])
        tree_b = _node(200, ppid=1, file_events=[MockFileEvent("/project/.git/config")])
        engine = CorrelationHintsEngine()
        hints = engine.analyze([tree_a, tree_b])
        same_repo = [h for h in hints if h.hint_type == "same_repo_root"]
        self.assertGreater(len(same_repo), 0, hints)
        self.assertEqual(same_repo[0].source_tree, 100)
        self.assertEqual(same_repo[0].target_tree, 200)

    def test_same_user(self) -> None:
        tree_a = _node(100, ppid=1, username="alice")
        tree_b = _node(200, ppid=1, username="alice")
        engine = CorrelationHintsEngine()
        hints = engine.analyze([tree_a, tree_b])
        same_user = [h for h in hints if h.hint_type == "same_user"]
        self.assertGreater(len(same_user), 0, hints)
        self.assertIn(same_user[0].evidence.get("user"), ("alice",))

    def test_hints_for_tree(self) -> None:
        hints = [
            CorrelationHint(10, 20, "same_repo_root", 0.5, {}),
            CorrelationHint(20, 30, "same_user", 0.3, {}),
        ]
        self.assertEqual(len(hints_for_tree(10, hints)), 1)
        self.assertEqual(len(hints_for_tree(20, hints)), 2)
        self.assertEqual(len(hints_for_tree(30, hints)), 1)
        self.assertEqual(len(hints_for_tree(99, hints)), 0)

    def test_enrichment_for_tree_none_when_no_hints(self) -> None:
        self.assertIsNone(enrichment_for_tree(100, []))

    def test_enrichment_for_tree_returns_dict_when_hints(self) -> None:
        hints = [
            CorrelationHint(100, 200, "temporal_proximity", 0.4, {}),
        ]
        enr = enrichment_for_tree(100, hints)
        self.assertIsNotNone(enr)
        self.assertIn("type", enr)
        self.assertIn("confidence", enr)
        self.assertIsInstance(enr.get("confidence"), (int, float))

    def test_get_destination_clusters_for_tree(self) -> None:
        t = datetime.now(timezone.utc)
        ne = NetworkConnectEvent(
            timestamp=t,
            pid=1,
            process_name="curl",
            remote_addr="api.openai.com",
            remote_port=443,
            local_port=0,
            source="polling",
        )
        tree = _node(1, ppid=0, network_events=[ne])
        clusters = get_destination_clusters_for_tree(tree)
        self.assertIn("openai.com", clusters)

    def test_get_working_dir_for_tree(self) -> None:
        t = datetime.now(timezone.utc)

        class MockFileEvent:
            def __init__(self, path: str) -> None:
                self.path = path
                self.timestamp = t

        tree = _node(1, ppid=0, file_events=[MockFileEvent("/home/user/proj/src/foo.py")])
        wd = get_working_dir_for_tree(tree)
        self.assertIsNotNone(wd)
        self.assertTrue(wd.startswith("/home") or "user" in (wd or ""))

    def test_enrichment_for_tree_includes_in_tree_attribution_when_tree_provided(self) -> None:
        t = datetime.now(timezone.utc)
        ne = NetworkConnectEvent(
            timestamp=t,
            pid=1,
            process_name="x",
            remote_addr="api.anthropic.com",
            remote_port=443,
            local_port=0,
            source="polling",
        )
        tree = _node(100, ppid=0, network_events=[ne])
        enr = enrichment_for_tree(100, [], tree=tree)
        self.assertIsNotNone(enr)
        self.assertIn("destination_clusters", enr)
        self.assertIn("anthropic.com", enr["destination_clusters"])

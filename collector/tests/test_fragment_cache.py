"""Tests for session fragment cache."""

from __future__ import annotations

from unittest import TestCase

from session.fragment_cache import (
    BehaviorFragment,
    FragmentCache,
    fragment_from_tree,
)
from scanner.process_tree import ProcessNode


def node(pid: int, ppid: int = 0, **kwargs: object) -> ProcessNode:
    return ProcessNode(
        pid=pid,
        ppid=ppid,
        name=f"p-{pid}",
        cmdline=f"p-{pid}",
        children=kwargs.get("children", []),
        file_events=kwargs.get("file_events", []),
        file_read_events=kwargs.get("file_read_events", []),
        network_events=kwargs.get("network_events", []),
        start_time=kwargs.get("start_time"),
    )


class TestFragmentFromTree(TestCase):
    def test_empty_tree_returns_none(self) -> None:
        t = node(100, ppid=1)
        self.assertIsNone(fragment_from_tree(t))

    def test_tree_with_start_time_returns_fragment(self) -> None:
        from datetime import datetime, timezone
        t = node(100, ppid=1, start_time=datetime.now(timezone.utc))
        frag = fragment_from_tree(t)
        self.assertIsNotNone(frag)
        self.assertEqual(frag.root_process, "p-100")
        self.assertIsNone(frag.repo_root)

    def test_tree_with_git_path_has_repo_root(self) -> None:
        from datetime import datetime, timezone
        class E:
            path = "/project/.git/HEAD"
            timestamp = datetime.now(timezone.utc)
        t = node(100, ppid=1, file_events=[E()])
        frag = fragment_from_tree(t)
        self.assertIsNotNone(frag)
        self.assertIsNotNone(frag.repo_root)
        self.assertIn("project", frag.repo_root or "")


class TestFragmentCache(TestCase):
    def test_record_and_find_continuations(self) -> None:
        import time
        cache = FragmentCache(retention_seconds=60.0, max_fragments=10)
        cache.record(BehaviorFragment(
            root_process="bash",
            repo_root="/repo/a",
            first_seen=time.time() - 30,
            last_seen=time.time() - 5,
            patterns=["BEH-006"],
            sensitive_paths=["/home/.ssh/id_rsa"],
            outbound_destinations=["api.openai.com"],
        ))
        found = cache.find_continuations("/repo/a", time.time(), window_seconds=60.0)
        self.assertEqual(len(found), 1)
        self.assertEqual(found[0].repo_root, "/repo/a")
        self.assertEqual(found[0].patterns, ["BEH-006"])

    def test_find_continuations_wrong_repo_empty(self) -> None:
        import time
        cache = FragmentCache(retention_seconds=60.0, max_fragments=10)
        cache.record(BehaviorFragment(
            root_process="x",
            repo_root="/repo/a",
            first_seen=time.time() - 10,
            last_seen=time.time(),
            patterns=[],
            sensitive_paths=[],
            outbound_destinations=[],
        ))
        self.assertEqual(cache.find_continuations("/repo/b", time.time()), [])

    def test_record_tree(self) -> None:
        from datetime import datetime, timezone
        cache = FragmentCache(retention_seconds=60.0, max_fragments=10)
        t = node(100, ppid=1, start_time=datetime.now(timezone.utc))
        self.assertTrue(cache.record_tree(t))
        self.assertFalse(cache.record_tree(node(101, ppid=1)))

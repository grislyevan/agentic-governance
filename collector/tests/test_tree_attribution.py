"""Tests for tree attribution (named_only, mixed, unknown_only)."""

from __future__ import annotations

from unittest import TestCase

from scanner.process_tree import ProcessNode
from scanner.tree_attribution import classify_tree, get_unknown_roots


def node(pid: int, ppid: int = 0, children: list | None = None) -> ProcessNode:
    return ProcessNode(
        pid=pid,
        ppid=ppid,
        name=f"proc-{pid}",
        cmdline=f"proc-{pid}",
        children=children or [],
    )


class TestClassifyTree(TestCase):
    def test_unknown_only(self) -> None:
        t = node(100, ppid=1)
        self.assertEqual(classify_tree(t, set()), "unknown_only")
        self.assertEqual(classify_tree(t, {200}), "unknown_only")

    def test_named_only(self) -> None:
        t = node(100, ppid=1)
        self.assertEqual(classify_tree(t, {100}), "named_only")
        t2 = node(100, ppid=1, children=[node(101, ppid=100)])
        self.assertEqual(classify_tree(t2, {100, 101}), "named_only")

    def test_mixed(self) -> None:
        t = node(100, ppid=1, children=[node(101, ppid=100), node(102, ppid=100)])
        self.assertEqual(classify_tree(t, {100}), "mixed")
        self.assertEqual(classify_tree(t, {101}), "mixed")
        self.assertEqual(classify_tree(t, {100, 101}), "mixed")


class TestGetUnknownRoots(TestCase):
    def test_unknown_only_tree_one_root(self) -> None:
        t = node(100, ppid=1)
        roots = get_unknown_roots(t, set())
        self.assertEqual(len(roots), 1)
        self.assertEqual(roots[0].pid, 100)

    def test_named_only_tree_no_roots(self) -> None:
        t = node(100, ppid=1)
        roots = get_unknown_roots(t, {100})
        self.assertEqual(len(roots), 0)

    def test_mixed_named_root_unknown_children(self) -> None:
        t = node(100, ppid=1, children=[node(101, ppid=100), node(102, ppid=100)])
        roots = get_unknown_roots(t, {100})
        self.assertEqual(len(roots), 2)
        pids = {r.pid for r in roots}
        self.assertEqual(pids, {101, 102})

    def test_mixed_unknown_root_named_child_no_unknown_branch(self) -> None:
        t = node(100, ppid=1, children=[node(101, ppid=100)])
        roots = get_unknown_roots(t, {101})
        self.assertEqual(len(roots), 0)

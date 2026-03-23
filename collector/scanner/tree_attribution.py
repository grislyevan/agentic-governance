"""Tree attribution: classify trees by named vs unknown PIDs for Unknown Agent detection.

Replaces blunt 'skip entire tree if any PID is named' with:
  named_only -> skip unknown-agent detection
  mixed -> scan unknown branches only
  unknown_only -> full scan
"""

from __future__ import annotations

from typing import Literal, TYPE_CHECKING

from .process_tree import get_all_pids

if TYPE_CHECKING:
    from .process_tree import ProcessNode


TreeClassification = Literal["named_only", "mixed", "unknown_only"]


def classify_tree(tree: "ProcessNode", named_pids: set[int]) -> TreeClassification:
    """Classify a process tree by whether it contains only named PIDs, only unknown, or both.

    named_only: every PID in the tree is in named_pids (skip for Unknown Agent).
    mixed: some PIDs named, some not (scan unknown branches only).
    unknown_only: no PIDs in named_pids (full scan).
    """
    tree_pids = get_all_pids(tree)
    if not tree_pids:
        return "named_only"
    named_in_tree = tree_pids & named_pids
    if named_in_tree == tree_pids:
        return "named_only"
    if named_in_tree:
        return "mixed"
    return "unknown_only"


def _subtree_has_named(node: "ProcessNode", named_pids: set[int]) -> bool:
    """True if this node or any descendant is in named_pids."""
    if node.pid in named_pids:
        return True
    return any(_subtree_has_named(c, named_pids) for c in node.children)


def get_unknown_roots(tree: "ProcessNode", named_pids: set[int]) -> list["ProcessNode"]:
    """Return roots of maximal subtrees that contain no named_pids.

    A node is an "unknown root" if it is not in named_pids, its parent
    (in the tree) is either a named PID or the tree root, and its entire
    subtree has no named_pids. Used for mixed trees: we score only these
    subtrees for Unknown Agent.
    """
    roots: list["ProcessNode"] = []

    def walk(node: "ProcessNode", parent_is_named: bool) -> None:
        if node.pid in named_pids:
            for c in node.children:
                walk(c, True)
            return
        if parent_is_named:
            roots.append(node)
        for c in node.children:
            walk(c, False)

    walk(tree, True)
    return [r for r in roots if not _subtree_has_named(r, named_pids)]

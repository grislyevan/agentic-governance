"""Lightweight behavioral fragment cache for continuity across event retention.

Raw events are evicted after retention_seconds (e.g. 120s). This cache keeps
minimal fragment records (10-30 min) so the session layer can state "possible
continuation of earlier fragment" when current activity matches a recent fragment
(e.g. same repo, sensitive paths, outbound).
"""

from __future__ import annotations

import time
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from scanner.process_tree import ProcessNode

_SENSITIVE_SUBSTRINGS = (".ssh", "credentials", ".env", ".aws", ".netrc", ".kube", "id_rsa", ".gitconfig")


@dataclass
class BehaviorFragment:
    """Minimal record of behavioral activity for continuity matching."""

    root_process: str
    repo_root: str | None
    first_seen: float
    last_seen: float
    patterns: list[str] = field(default_factory=list)
    sensitive_paths: list[str] = field(default_factory=list)
    outbound_destinations: list[str] = field(default_factory=list)


def _collect_paths(node: "ProcessNode", _seen: set[int] | None = None) -> set[str]:
    paths: set[str] = set()
    if _seen is None:
        _seen = set()
    if node.pid in _seen:
        return paths
    _seen.add(node.pid)
    for e in node.file_events:
        if getattr(e, "path", None):
            paths.add(e.path)
    for e in node.file_read_events:
        if getattr(e, "path", None):
            paths.add(e.path)
    for child in node.children:
        paths |= _collect_paths(child, _seen)
    return paths


def _collect_timestamps(node: "ProcessNode", _seen: set[int] | None = None) -> list[datetime]:
    out: list[datetime] = []
    if _seen is None:
        _seen = set()
    if node.pid in _seen:
        return out
    _seen.add(node.pid)
    if node.start_time is not None:
        out.append(node.start_time)
    for e in node.network_events:
        out.append(e.timestamp)
    for e in node.file_events:
        out.append(e.timestamp)
    for e in node.file_read_events:
        out.append(e.timestamp)
    for child in node.children:
        out.extend(_collect_timestamps(child, _seen))
    return out


def _collect_destinations(node: "ProcessNode", _seen: set[int] | None = None) -> set[str]:
    dests: set[str] = set()
    if _seen is None:
        _seen = set()
    if node.pid in _seen:
        return dests
    _seen.add(node.pid)
    for e in node.network_events:
        addr = getattr(e, "remote_addr", None) or ""
        sni = getattr(e, "sni", None) or ""
        if addr:
            dests.add(addr.strip())
        if sni:
            dests.add(sni.strip())
    for child in node.children:
        dests |= _collect_destinations(child, _seen)
    return dests


def _repo_root_from_paths(paths: set[str]) -> str | None:
    candidates: list[str] = []
    for p in paths:
        if ".git" in p:
            parts = p.replace("\\", "/").split("/")
            for i, part in enumerate(parts):
                if part == ".git" or part.startswith(".git"):
                    parent = "/".join(parts[:i]) if i else ""
                    if parent:
                        candidates.append(parent)
                    break
    return min(candidates, key=len) if candidates else None


def _sensitive_paths(paths: set[str]) -> list[str]:
    lower = [p.lower() for p in paths]
    out: list[str] = []
    for p in paths:
        pl = p.lower()
        if any(sub in pl for sub in _SENSITIVE_SUBSTRINGS):
            out.append(p)
    return out[:20]


def fragment_from_tree(
    tree: "ProcessNode",
    pattern_ids: list[str] | None = None,
) -> BehaviorFragment | None:
    """Build a BehaviorFragment from a process tree. Returns None if no activity."""
    paths = _collect_paths(tree)
    timestamps = _collect_timestamps(tree)
    dests = _collect_destinations(tree)
    if not timestamps and not paths and not dests:
        return None
    first = min(timestamps) if timestamps else datetime.now(timezone.utc)
    last = max(timestamps) if timestamps else datetime.now(timezone.utc)
    repo = _repo_root_from_paths(paths)
    sensitive = _sensitive_paths(paths)
    root_name = (tree.name or "").strip() or f"pid-{tree.pid}"
    return BehaviorFragment(
        root_process=root_name,
        repo_root=repo,
        first_seen=first.timestamp(),
        last_seen=last.timestamp(),
        patterns=pattern_ids or [],
        sensitive_paths=sensitive[:10],
        outbound_destinations=list(dests)[:15],
    )


class FragmentCache:
    """In-memory cache of behavioral fragments with TTL and max size."""

    def __init__(
        self,
        retention_seconds: float = 1800.0,
        max_fragments: int = 500,
    ) -> None:
        self._retention = retention_seconds
        self._max_fragments = max_fragments
        self._deque: deque[BehaviorFragment] = deque(maxlen=max_fragments)

    def record(self, fragment: BehaviorFragment) -> None:
        """Append a fragment; evicts oldest when full."""
        self._deque.append(fragment)

    def _evict_expired(self) -> None:
        now = time.time()
        while self._deque and (now - self._deque[0].last_seen) > self._retention:
            self._deque.popleft()

    def find_continuations(
        self,
        repo_root: str | None,
        after_time: float,
        window_seconds: float = 600.0,
        require_sensitive: bool = False,
    ) -> list[BehaviorFragment]:
        """Return fragments that might be continuations: same repo, last_seen within window of after_time."""
        self._evict_expired()
        if repo_root is None or not repo_root:
            return []
        out: list[BehaviorFragment] = []
        for f in self._deque:
            if f.repo_root != repo_root:
                continue
            if abs(f.last_seen - after_time) > window_seconds:
                continue
            if require_sensitive and not f.sensitive_paths:
                continue
            out.append(f)
        return out

    def record_tree(
        self,
        tree: "ProcessNode",
        pattern_ids: list[str] | None = None,
    ) -> bool:
        """Build fragment from tree and record if it has activity. Returns True if recorded."""
        frag = fragment_from_tree(tree, pattern_ids)
        if frag is None:
            return False
        self.record(frag)
        return True

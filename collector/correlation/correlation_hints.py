"""Cross-tree correlation hints: soft links between trees for analyst explanation.

Does not change detection outcome. Hint types: same_repo_root, same_user,
temporal_proximity, shared_working_dir, same_destination_cluster.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from scanner.process_tree import ProcessNode


@dataclass
class CorrelationHint:
    """A soft correlation between two process trees."""

    source_tree: int  # root PID of source tree
    target_tree: int  # root PID of target tree
    hint_type: str
    score: float
    evidence: dict[str, Any] = field(default_factory=dict)


def _collect_paths(node: "ProcessNode", _seen: set[int] | None = None) -> set[str]:
    """Recursively collect all file paths from a tree."""
    if _seen is None:
        _seen = set()
    if node.pid in _seen:
        return set()
    _seen.add(node.pid)
    paths: set[str] = set()
    for e in node.file_events:
        if e.path:
            paths.add(e.path)
    for e in node.file_read_events:
        if e.path:
            paths.add(e.path)
    for child in node.children:
        paths |= _collect_paths(child, _seen)
    return paths


def _collect_network_destinations(node: "ProcessNode", _seen: set[int] | None = None) -> set[str]:
    """Recursively collect destination clusters (host/domain) from network events."""
    if _seen is None:
        _seen = set()
    if node.pid in _seen:
        return set()
    _seen.add(node.pid)
    dests: set[str] = set()
    for e in node.network_events:
        addr = (e.remote_addr or "").strip()
        sni = (e.sni or "").strip()
        if addr:
            dests.add(addr)
        if sni:
            dests.add(sni)
    for child in node.children:
        dests |= _collect_network_destinations(child, _seen)
    return dests


def _collect_timestamps(node: "ProcessNode", _seen: set[int] | None = None) -> list[datetime]:
    """Recursively collect all event timestamps from a tree."""
    if _seen is None:
        _seen = set()
    if node.pid in _seen:
        return []
    _seen.add(node.pid)
    out: list[datetime] = []
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


def _repo_root_from_paths(paths: set[str]) -> str | None:
    """Infer a single repo root from paths containing .git."""
    candidates: list[str] = []
    for p in paths:
        if ".git" in p:
            # Take directory containing .git (or the .git segment's parent)
            parts = p.replace("\\", "/").split("/")
            for i, part in enumerate(parts):
                if part == ".git" or part.startswith(".git"):
                    parent = "/".join(parts[:i]) if i else ""
                    if parent:
                        candidates.append(parent)
                    break
    if not candidates:
        return None
    # Return first; could also return most common
    return candidates[0]


def _domain_cluster(addr: str) -> str:
    """Reduce address to a base domain for clustering."""
    addr = (addr or "").strip().lower()
    if not addr or addr in ("localhost", "127.0.0.1"):
        return addr
    # Remove port if present
    if ":" in addr:
        addr = addr.split(":")[0]
    # Simple: use last two parts for domain (e.g. api.openai.com -> openai.com)
    parts = addr.split(".")
    if len(parts) >= 2:
        return ".".join(parts[-2:])
    return addr


def _working_dir_from_paths(paths: set[str]) -> str | None:
    """Infer a shared working directory from paths (common prefix)."""
    if not paths:
        return None
    normalized = [p.replace("\\", "/") for p in paths]
    prefix = normalized[0]
    for p in normalized[1:]:
        while prefix and not p.startswith(prefix + "/") and prefix != p:
            prefix = prefix.rsplit("/", 1)[0] if "/" in prefix else ""
        if not prefix:
            return None
    return prefix if prefix else None


class CorrelationHintsEngine:
    """Computes soft correlation hints between process trees."""

    def __init__(
        self,
        temporal_window_seconds: float = 300.0,
        same_repo_score: float = 0.5,
        same_user_score: float = 0.3,
        temporal_proximity_score: float = 0.4,
        same_destination_score: float = 0.5,
    ) -> None:
        self.temporal_window_seconds = temporal_window_seconds
        self.same_repo_score = same_repo_score
        self.same_user_score = same_user_score
        self.temporal_proximity_score = temporal_proximity_score
        self.same_destination_score = same_destination_score

    def _tree_metadata(self, tree: "ProcessNode") -> dict[str, Any]:
        paths = _collect_paths(tree)
        dests = _collect_network_destinations(tree)
        timestamps = _collect_timestamps(tree)
        repo = _repo_root_from_paths(paths)
        working_dir = _working_dir_from_paths(paths) if paths else None
        users: set[str] = set()
        if tree.username:
            users.add(tree.username)
        for c in tree.children:
            if c.username:
                users.add(c.username)
        user = next(iter(users), None) if len(users) == 1 else None
        if not user and users:
            user = sorted(users)[0]
        clusters = {_domain_cluster(d) for d in dests if _domain_cluster(d)}
        first_ts = min(timestamps) if timestamps else None
        last_ts = max(timestamps) if timestamps else None
        return {
            "repo_root": repo,
            "working_dir": working_dir,
            "user": user,
            "destination_clusters": clusters,
            "first_ts": first_ts,
            "last_ts": last_ts,
        }

    def analyze(self, trees: list["ProcessNode"]) -> list[CorrelationHint]:
        """Produce correlation hints between all pairs of trees."""
        from scanner.process_tree import get_all_pids

        hints: list[CorrelationHint] = []
        meta: list[dict[str, Any]] = []
        for tree in trees:
            meta.append(self._tree_metadata(tree))

        for i, tree_a in enumerate(trees):
            pids_a = get_all_pids(tree_a)
            if not pids_a:
                continue
            root_a = tree_a.pid
            m_a = meta[i]
            for j, tree_b in enumerate(trees):
                if i >= j:
                    continue
                pids_b = get_all_pids(tree_b)
                if not pids_b or pids_a & pids_b:
                    continue
                root_b = tree_b.pid
                m_b = meta[j]

                if m_a.get("repo_root") and m_a["repo_root"] == m_b.get("repo_root"):
                    hints.append(
                        CorrelationHint(
                            source_tree=root_a,
                            target_tree=root_b,
                            hint_type="same_repo_root",
                            score=self.same_repo_score,
                            evidence={"repo_root": m_a["repo_root"]},
                        )
                    )
                if m_a.get("user") and m_a["user"] == m_b.get("user"):
                    hints.append(
                        CorrelationHint(
                            source_tree=root_a,
                            target_tree=root_b,
                            hint_type="same_user",
                            score=self.same_user_score,
                            evidence={"user": m_a["user"]},
                        )
                    )
                if m_a.get("working_dir") and m_a["working_dir"] == m_b.get("working_dir"):
                    hints.append(
                        CorrelationHint(
                            source_tree=root_a,
                            target_tree=root_b,
                            hint_type="shared_working_dir",
                            score=self.same_repo_score * 0.8,
                            evidence={"working_dir": m_a["working_dir"]},
                        )
                    )
                overlap = (m_a.get("destination_clusters") or set()) & (
                    m_b.get("destination_clusters") or set()
                )
                if overlap:
                    hints.append(
                        CorrelationHint(
                            source_tree=root_a,
                            target_tree=root_b,
                            hint_type="same_destination_cluster",
                            score=self.same_destination_score,
                            evidence={"clusters": list(overlap)[:5]},
                        )
                    )
                first_a = m_a.get("first_ts")
                last_a = m_a.get("last_ts")
                first_b = m_b.get("first_ts")
                last_b = m_b.get("last_ts")
                if first_a and last_a and first_b and last_b:
                    gap_ab = abs((last_a - first_b).total_seconds())
                    gap_ba = abs((last_b - first_a).total_seconds())
                    delta = min(gap_ab, gap_ba)
                    if delta <= self.temporal_window_seconds:
                        hints.append(
                            CorrelationHint(
                                source_tree=root_a,
                                target_tree=root_b,
                                hint_type="temporal_proximity",
                                score=self.temporal_proximity_score,
                                evidence={
                                    "window_seconds": self.temporal_window_seconds,
                                    "min_gap_seconds": round(delta, 1),
                                },
                            )
                        )
        return hints


def get_destination_clusters_for_tree(tree: "ProcessNode") -> list[str]:
    """Return domain clusters (e.g. openai.com) for outbound destinations in this tree.

    For in-tree attribution: summarizes network destinations by cluster for
    policy/analyst use. Reuses the same clustering as cross-tree same_destination_cluster.
    """
    raw = _collect_network_destinations(tree)
    clusters = {_domain_cluster(d) for d in raw if _domain_cluster(d)}
    clusters.discard("")
    clusters.discard("localhost")
    return sorted(clusters)


def get_working_dir_for_tree(tree: "ProcessNode") -> str | None:
    """Infer working directory from file paths in the tree.

    Strengthens same-tree/same-session attribution when network events lack clear PID.
    """
    paths = _collect_paths(tree)
    return _working_dir_from_paths(paths) if paths else None


def hints_for_tree(
    tree_root_pid: int,
    hints: list[CorrelationHint],
) -> list[CorrelationHint]:
    """Return hints where the given tree is source or target."""
    return [
        h for h in hints
        if h.source_tree == tree_root_pid or h.target_tree == tree_root_pid
    ]


def enrichment_for_tree(
    tree_root_pid: int,
    hints: list[CorrelationHint],
    tree: "ProcessNode | None" = None,
) -> dict[str, Any] | None:
    """Build event enrichment dict for cross_tree_correlation when tree has hints.

    When tree is provided, adds in-tree destination_clusters and working_dir
    for single-tree attribution (policy/analyst use).
    """
    relevant = hints_for_tree(tree_root_pid, hints)
    base: dict[str, Any] = {}
    if relevant:
        best = max(relevant, key=lambda h: h.score)
        types = list({h.hint_type for h in relevant})
        confidence = min(1.0, sum(h.score for h in relevant) * 0.5)
        base = {
            "type": best.hint_type if len(types) == 1 else "temporal_repo_overlap",
            "confidence": round(confidence, 2),
            "hint_types": types,
            "hint_count": len(relevant),
        }
    if tree is not None:
        clusters = get_destination_clusters_for_tree(tree)
        if clusters:
            base["destination_clusters"] = clusters
        wd = get_working_dir_for_tree(tree)
        if wd:
            base["working_dir"] = wd
    if not base:
        return None
    return base

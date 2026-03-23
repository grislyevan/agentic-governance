"""Extract the strongest suspicious subchain from a session timeline.

From a noisy timeline (llm, shell_exec, file_write, git, network, ...), finds
the contiguous subsequence that maximizes edge weights (e.g. llm->shell_exec,
shell_exec->git are high-weight). Used for session report explanation.
"""

from __future__ import annotations

from typing import Any, Protocol

# Canonical types from docs/session-report-vocabulary.md
_SKIP_TYPES = frozenset({"sequence_start", "sequence_end"})

# Edge weights: (from_type, to_type) -> weight. Higher = more suspicious.
_EDGE_WEIGHTS: dict[tuple[str, str], float] = {
    ("llm", "shell_exec"): 1.0,
    ("llm", "file_write"): 0.7,
    ("llm", "network"): 0.5,
    ("shell_exec", "git"): 1.0,
    ("shell_exec", "file_write"): 0.9,
    ("shell_exec", "network"): 0.6,
    ("file_write", "git"): 0.9,
    ("file_write", "network"): 0.5,
    ("file_write", "shell_exec"): 0.4,
    ("git", "network"): 0.5,
    ("git", "file_write"): 0.4,
    ("network", "shell_exec"): 0.5,
    ("network", "file_write"): 0.4,
}
_DEFAULT_EDGE_WEIGHT = 0.1


class _HasType(Protocol):
    type: str


def _weight(a: str, b: str) -> float:
    if a == "observe" or b == "observe":
        return 0.0
    return _EDGE_WEIGHTS.get((a, b), _DEFAULT_EDGE_WEIGHT)


def extract_strongest_subchain(
    timeline: list[Any],
    type_key: str = "type",
) -> list[str]:
    """Return the contiguous subchain of timeline types that maximizes total edge weight.

    Args:
        timeline: List of entries with a type (dict with type_key or object with .type).
        type_key: Key to read type from each entry if dict; else use getattr(entry, "type", "").

    Returns:
        List of canonical types (e.g. ["llm", "shell_exec", "file_write", "git", "network"]).
    """
    steps: list[str] = []
    for e in timeline:
        if isinstance(e, dict):
            t = (e.get(type_key) or "").strip()
        else:
            t = (getattr(e, "type", None) or "").strip()
        if t in _SKIP_TYPES:
            continue
        if t not in ("llm", "shell_exec", "exec", "file_write", "file_modified", "file_delete", "network", "git"):
            t = "observe"
        if t == "exec":
            t = "shell_exec"
        if t in ("file_modified", "file_delete"):
            t = "file_write"
        steps.append(t)
    if len(steps) < 2:
        return []
    n = len(steps)
    weights = [_weight(steps[i], steps[i + 1]) for i in range(n - 1)]
    best_sum = 0.0
    best_start = 0
    best_end = 0
    current_sum = 0.0
    start = 0
    for i in range(n - 1):
        current_sum += weights[i]
        if current_sum > best_sum:
            best_sum = current_sum
            best_start = start
            best_end = i + 1
        if current_sum <= 0:
            current_sum = 0.0
            start = i + 1
    if best_sum <= 0:
        return []
    out = steps[best_start : best_end + 1]
    return [s for s in out if s != "observe"]


def format_subchain_chain(types: list[str]) -> str:
    """Format a list of types as 'a -> b -> c' for display."""
    if not types:
        return ""
    return " -> ".join(types)

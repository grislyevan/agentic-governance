"""Assemble canonical events into behavioral sequences and derived edges."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import Any

# Canonical event: dict with observed_at, action type, etc.
CanonicalEvent = dict[str, Any]


@dataclass
class BehaviorEdge:
    """A derived causal edge between two step types in a sequence."""

    from_step: str
    to_step: str
    evidence_count: int = 1


@dataclass
class BehavioralSequence:
    """A time-bounded sequence of events with derived behavior edges."""

    sequence_id: str
    endpoint_id: str
    tool: str | None
    start_time: datetime
    end_time: datetime
    steps: list[CanonicalEvent]
    derived_edges: list[BehaviorEdge]


def _classify_step(event: CanonicalEvent) -> str:
    """Classify event into a step type for edge derivation."""
    action = event.get("action") or {}
    action_type = (action.get("type") or "").lower()
    summary = (action.get("summary") or "").lower()
    if "llm" in summary or "model" in summary or "anthropic" in summary or "openai" in summary:
        return "llm_call"
    if action_type == "exec" or "shell" in summary:
        return "shell_exec"
    if action_type in ("write", "repo"):
        return "file_write"
    if action_type == "network":
        return "outbound_activity"
    if "sensitive" in summary or "credential" in summary or ".env" in str(event):
        return "sensitive_access"
    if "git" in summary or ".git" in str(event):
        return "git_modification"
    return "observe"


def assemble_sequence(
    endpoint_id: str,
    tool: str | None,
    events: list[CanonicalEvent],
    start_time: datetime | None = None,
    end_time: datetime | None = None,
) -> BehavioralSequence:
    """Build a BehavioralSequence from a time-bounded list of events. Derives edges heuristically."""
    if not events:
        start_time = start_time or datetime.min
        end_time = end_time or datetime.max
        return BehavioralSequence(
            sequence_id=f"seq-{uuid.uuid4().hex[:12]}",
            endpoint_id=endpoint_id,
            tool=tool,
            start_time=start_time,
            end_time=end_time,
            steps=[],
            derived_edges=[],
        )
    steps = sorted(
        events,
        key=lambda e: e.get("observed_at") or e.get("timestamp") or "",
    )
    obs_times = []
    for e in steps:
        o = e.get("observed_at") or e.get("timestamp")
        if isinstance(o, str):
            try:
                obs_times.append(datetime.fromisoformat(o.replace("Z", "+00:00")))
            except ValueError:
                pass
        elif hasattr(o, "isoformat"):
            obs_times.append(o)
    start_time = start_time or (min(obs_times) if obs_times else datetime.min)
    end_time = end_time or (max(obs_times) if obs_times else datetime.max)

    step_types = [_classify_step(e) for e in steps]
    edges: list[BehaviorEdge] = []
    seen: set[tuple[str, str]] = set()
    for i in range(len(step_types) - 1):
        a, b = step_types[i], step_types[i + 1]
        if a == "observe":
            continue
        key = (a, b)
        if key not in seen:
            seen.add(key)
            edges.append(BehaviorEdge(from_step=a, to_step=b, evidence_count=1))
        else:
            for ed in edges:
                if (ed.from_step, ed.to_step) == key:
                    ed.evidence_count += 1
                    break

    return BehavioralSequence(
        sequence_id=f"seq-{uuid.uuid4().hex[:12]}",
        endpoint_id=endpoint_id,
        tool=tool,
        start_time=start_time,
        end_time=end_time,
        steps=steps,
        derived_edges=edges,
    )


def top_behavior_chains(sequence: BehavioralSequence, max_chains: int = 5) -> list[str]:
    """Return human-readable chain strings (e.g. 'llm_call -> shell_exec -> file_write')."""
    chains = [
        f"{e.from_step} -> {e.to_step}"
        for e in sequence.derived_edges
    ]
    return chains[:max_chains]

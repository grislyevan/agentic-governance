"""Lightweight trigger rules for probe deltas. Decision logic lives here, not in EventStore."""

from __future__ import annotations

import os
from collections import defaultdict
from dataclasses import dataclass
from typing import Literal

from telemetry.event_store import (
    FileChangeEvent,
    NetworkConnectEvent,
    ProcessExecEvent,
)

from probe.models import ProbeDelta

# Process names associated with known agentic AI tools (mirrored from event_store for probe use).
AGENTIC_PROCESS_PATTERNS: frozenset[str] = frozenset({
    "claude",
    "cursor",
    "ollama",
    "copilot",
    "aider",
    "interpreter",
    "openclaw",
    "continue",
    "gpt-pilot",
    "lm-studio",
    "lmstudio",
    "cline",
    "codex",
    "devin",
    "smol-developer",
    "autogpt",
    "auto-gpt",
    "babyagi",
    "langchain",
    "crewai",
})

SHELL_NAMES: frozenset[str] = frozenset({
    "bash", "sh", "zsh", "fish", "csh", "tcsh", "dash",
    "cmd", "powershell", "pwsh",
})

SHELL_FANOUT_ALERT_THRESHOLD = 5

# Path substrings that indicate sensitive or repo locations for file triggers.
SENSITIVE_PATH_SUBSTRINGS: tuple[str, ...] = (
    ".env",
    ".git/config",
    "credentials",
    "id_rsa",
    ".ssh/",
    ".netrc",
)
REPO_PATH_SUBSTRINGS: tuple[str, ...] = (".git/", ".git" + os.sep)


@dataclass
class TriggerMatch:
    """A single trigger that fired from a delta."""

    trigger_type: str
    confidence: float
    signals: list[str]


def _is_agentic_process(event: ProcessExecEvent) -> bool:
    name_lower = os.path.basename(event.name or "").lower()
    if name_lower.endswith(".exe"):
        name_lower = name_lower[:-4]
    cmdline_lower = (event.cmdline or "").lower()
    for pattern in AGENTIC_PROCESS_PATTERNS:
        if pattern in name_lower or pattern in cmdline_lower:
            return True
    return False


def _is_llm_endpoint(addr: str, port: int) -> bool:
    try:
        from scanner.behavioral_patterns import get_llm_hosts
        hosts = get_llm_hosts()
    except Exception:
        hosts = frozenset()
    host_port = f"{addr}:{port}" if port else addr
    host_only = addr.split(":")[0] if ":" in addr else addr
    for h in hosts:
        if h in host_port or h in host_only or host_only in h:
            return True
    return False


def evaluate_triggers(delta: ProbeDelta) -> list[TriggerMatch]:
    """Evaluate a probe delta against cheap trigger rules. Returns list of matches."""
    matches: list[TriggerMatch] = []

    for e in delta.process_events:
        if _is_agentic_process(e):
            matches.append(
                TriggerMatch(
                    trigger_type="ai_tool_process_start",
                    confidence=0.7,
                    signals=["process.agentic_tool"],
                )
            )

    ppid_counts: dict[int, int] = defaultdict(int)
    for e in delta.process_events:
        name_lower = (e.name or "").lower()
        if any(s in name_lower for s in SHELL_NAMES):
            ppid_counts[e.ppid] += 1
    for ppid, count in ppid_counts.items():
        if count >= SHELL_FANOUT_ALERT_THRESHOLD:
            matches.append(
                TriggerMatch(
                    trigger_type="subprocess_burst",
                    confidence=0.65,
                    signals=["process.shell_fanout"],
                )
            )
            break

    for e in delta.network_events:
        if _is_llm_endpoint(e.remote_addr or "", e.remote_port or 0):
            matches.append(
                TriggerMatch(
                    trigger_type="outbound_llm_endpoint",
                    confidence=0.75,
                    signals=["network.llm_endpoint"],
                )
            )
            break

    for e in delta.file_events:
        path_lower = (e.path or "").lower()
        if any(s in path_lower for s in SENSITIVE_PATH_SUBSTRINGS):
            matches.append(
                TriggerMatch(
                    trigger_type="sensitive_file_access",
                    confidence=0.7,
                    signals=["file.sensitive_access"],
                )
            )
            break
        if (e.action or "").lower() in ("modified", "write", "created"):
            if any(s in path_lower for s in REPO_PATH_SUBSTRINGS):
                matches.append(
                    TriggerMatch(
                        trigger_type="repo_write",
                        confidence=0.6,
                        signals=["file.repo_write"],
                    )
                )
                break

    if len(delta.file_events) >= 5:
        matches.append(
            TriggerMatch(
                trigger_type="rapid_write_burst",
                confidence=0.55,
                signals=["file.rapid_burst"],
            )
        )

    return matches

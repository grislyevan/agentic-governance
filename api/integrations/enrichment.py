"""EDR enrichment pipeline for detection events."""

from __future__ import annotations

import logging
from datetime import datetime, timezone, timedelta
from typing import Any

from .base import EDRProvider
from .types import (
    ProcessExecEvent,
    NetworkConnectEvent,
    EnrichmentResult,
)

logger = logging.getLogger(__name__)

# Penalty codes and their values (replicated from collector playbook)
PENALTY_VALUES: dict[str, float] = {
    "missing_parent_child_chain": 0.15,
    "unresolved_proc_net_linkage": 0.10,
    "stale_artifact_only": 0.10,
}

# Tool name to known network destinations for matching
TOOL_NETWORK_DESTINATIONS: dict[str, set[str]] = {
    "Ollama": {"127.0.0.1", "localhost", ":11434"},
    "LM Studio": {"127.0.0.1", "localhost", ":1234"},
    "Cursor": {"api2.cursor.sh", "cursor.sh"},
    "GitHub Copilot": {"github.com", "githubcopilot.com", "copilot-proxy.githubusercontent.com"},
    "Continue": {"api.continue.dev"},
    "Claude Code": {"api.anthropic.com", "anthropic.com"},
    "Claude Cowork": {"api.anthropic.com", "anthropic.com"},
    "Claude Cowork (Beta)": {"api.anthropic.com", "anthropic.com"},
    "Open Interpreter": {"api.openai.com", "api.anthropic.com", "openai.com", "anthropic.com"},
    "Aider": {"api.openai.com", "api.anthropic.com", ":11434", ":1234"},
    "GPT-Pilot": {"api.openai.com", "api.anthropic.com", ":11434", ":1234"},
    "Cline": {"api.openai.com", "api.anthropic.com"},
    "OpenClaw": {"127.0.0.1", "localhost", ":18789"},
}


def _classify_band(score: float) -> str:
    """Classify confidence into Low/Medium/High per Playbook Section 6.2."""
    if score >= 0.75:
        return "High"
    if score >= 0.45:
        return "Medium"
    return "Low"


def _has_parent_child_chain(
    process_events: list[ProcessExecEvent],
    tool_name: str | None,
) -> bool:
    """Check if process events form a parent-child chain matching the tool."""
    if not tool_name or not process_events:
        return False
    tool_lower = tool_name.lower()
    pids = {e.pid for e in process_events}
    for ev in process_events:
        if tool_lower in (ev.name or "").lower():
            if ev.ppid in pids:
                return True
    return False


def _has_network_with_pid(
    network_events: list[NetworkConnectEvent],
    tool_name: str | None,
) -> bool:
    """Check if network events have PID attribution matching known tool destinations."""
    if not tool_name or not network_events:
        return False
    destinations = TOOL_NETWORK_DESTINATIONS.get(tool_name, set())
    for ev in network_events:
        if ev.pid and ev.process_name:
            remote = f"{ev.remote_addr}:{ev.remote_port}"
            for d in destinations:
                if d.startswith(":"):
                    if f":{ev.remote_port}" == d or remote.endswith(d):
                        return True
                elif d in ev.remote_addr or d in (ev.sni or ""):
                    return True
    return False


def _process_events_match_tool(
    process_events: list[ProcessExecEvent],
    tool_name: str | None,
) -> bool:
    """Check if any process event matches the tool name."""
    if not tool_name or not process_events:
        return False
    tool_lower = tool_name.lower()
    for ev in process_events:
        if tool_lower in (ev.name or "").lower():
            return True
    return False


async def enrich_detection(
    event_payload: dict[str, Any],
    provider: EDRProvider,
    settings: Any,
) -> EnrichmentResult | None:
    """Enrich a detection event with EDR telemetry and rescore confidence.

    Returns None if the endpoint is not found in the EDR.
    """
    endpoint = event_payload.get("endpoint") or {}
    hostname = endpoint.get("id") or endpoint.get("hostname")
    if not hostname:
        return None

    observed_at_str = event_payload.get("observed_at")
    if not observed_at_str:
        return None
    if isinstance(observed_at_str, str):
        try:
            observed_at = datetime.fromisoformat(
                observed_at_str.replace("Z", "+00:00")
            )
        except ValueError:
            return None
    else:
        observed_at = observed_at_str
    if observed_at.tzinfo is None:
        observed_at = observed_at.replace(tzinfo=timezone.utc)

    edr_endpoint_id = await provider.resolve_endpoint_id(hostname)
    if not edr_endpoint_id:
        return None

    before_sec = getattr(
        settings, "edr_query_window_before_seconds", 300
    )
    after_sec = getattr(
        settings, "edr_query_window_after_seconds", 60
    )
    query_start = observed_at - timedelta(seconds=before_sec)
    query_end = observed_at + timedelta(seconds=after_sec)

    process_events = await provider.query_process_events(
        edr_endpoint_id, query_start, query_end
    )
    network_events = await provider.query_network_events(
        edr_endpoint_id, query_start, query_end
    )
    file_events = await provider.query_file_events(
        edr_endpoint_id, query_start, query_end
    )

    tool = event_payload.get("tool") or {}
    tool_name = tool.get("name")
    original_confidence = float(tool.get("attribution_confidence", 0.0))

    penalties_removed: list[str] = []

    if _has_parent_child_chain(process_events, tool_name):
        penalties_removed.append("missing_parent_child_chain")

    if _has_network_with_pid(network_events, tool_name):
        penalties_removed.append("unresolved_proc_net_linkage")

    if _process_events_match_tool(process_events, tool_name):
        penalties_removed.append("stale_artifact_only")

    penalty_sum = sum(
        PENALTY_VALUES.get(p, 0) for p in penalties_removed
    )
    enriched_confidence = max(
        0.0,
        min(1.0, round(original_confidence + penalty_sum, 4)),
    )

    original_band = _classify_band(original_confidence)
    enriched_band = _classify_band(enriched_confidence)
    band_changed = original_band != enriched_band

    def _process_matches(e: ProcessExecEvent) -> bool:
        return bool(
            tool_name and tool_name.lower() in (e.name or "").lower()
        )

    def _network_matches(e: NetworkConnectEvent) -> bool:
        if not e.pid or not e.process_name or not tool_name:
            return False
        dests = TOOL_NETWORK_DESTINATIONS.get(tool_name, set())
        for d in dests:
            if d.startswith(":"):
                if f":{e.remote_port}" == d:
                    return True
            elif d in e.remote_addr or d in (e.sni or ""):
                return True
        return False

    process_matched = sum(1 for e in process_events if _process_matches(e))
    network_matched = sum(1 for e in network_events if _network_matches(e))

    return EnrichmentResult(
        provider=provider.name,
        query_window_start=query_start,
        query_window_end=query_end,
        process_events_matched=process_matched,
        network_events_matched=network_matched,
        file_events_matched=len(file_events),
        original_confidence=original_confidence,
        enriched_confidence=enriched_confidence,
        band_changed=band_changed,
        penalties_removed=penalties_removed,
    )

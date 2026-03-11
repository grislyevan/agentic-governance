"""Tests for EDR enrichment pipeline."""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock

import pytest

# Ensure api/ is on path (conftest does this)
from integrations.enrichment import enrich_detection
from integrations.types import ProcessExecEvent, NetworkConnectEvent, EnrichmentResult


def _mock_settings(
    query_before: int = 300,
    query_after: int = 60,
) -> object:
    class Settings:
        edr_query_window_before_seconds = query_before
        edr_query_window_after_seconds = query_after

    return Settings()


def _minimal_event(
    hostname: str = "test-host",
    tool_name: str = "Ollama",
    confidence: float = 0.55,
    observed_at: str = "2026-03-10T12:00:00Z",
) -> dict:
    return {
        "event_id": "evt-enrich-001",
        "event_type": "detection.observed",
        "event_version": "1.0.0",
        "observed_at": observed_at,
        "endpoint": {"id": hostname, "os": "macOS 14", "posture": "unmanaged"},
        "tool": {
            "name": tool_name,
            "class": "B",
            "version": "1.0",
            "attribution_confidence": confidence,
            "attribution_sources": ["process", "file"],
        },
    }


@pytest.mark.asyncio
async def test_unresolved_endpoint_returns_none():
    """When EDR cannot resolve the endpoint, enrichment returns None."""
    provider = AsyncMock()
    provider.name = "mock-edr"
    provider.resolve_endpoint_id = AsyncMock(return_value=None)

    result = await enrich_detection(
        event_payload=_minimal_event(),
        provider=provider,
        settings=_mock_settings(),
    )
    assert result is None
    provider.resolve_endpoint_id.assert_called_once_with("test-host")


@pytest.mark.asyncio
async def test_process_events_remove_missing_parent_child_chain():
    """Process events with parent-child chain remove missing_parent_child_chain penalty."""
    provider = AsyncMock()
    provider.name = "mock-edr"
    provider.resolve_endpoint_id = AsyncMock(return_value="edr-device-1")
    provider.query_process_events = AsyncMock(
        return_value=[
            ProcessExecEvent(
                timestamp=datetime.now(timezone.utc),
                pid=1000,
                ppid=999,
                name="ollama",
                cmdline="ollama serve",
            ),
            ProcessExecEvent(
                timestamp=datetime.now(timezone.utc),
                pid=999,
                ppid=1,
                name="ollama",
                cmdline="ollama",
            ),
        ]
    )
    provider.query_network_events = AsyncMock(return_value=[])
    provider.query_file_events = AsyncMock(return_value=[])

    result = await enrich_detection(
        event_payload=_minimal_event(tool_name="Ollama", confidence=0.50),
        provider=provider,
        settings=_mock_settings(),
    )
    assert result is not None
    assert isinstance(result, EnrichmentResult)
    assert "missing_parent_child_chain" in result.penalties_removed
    assert "stale_artifact_only" in result.penalties_removed
    assert result.enriched_confidence == pytest.approx(0.75, abs=0.01)


@pytest.mark.asyncio
async def test_network_events_remove_unresolved_proc_net_linkage():
    """Network events with PID attribution remove unresolved_proc_net_linkage penalty."""
    provider = AsyncMock()
    provider.name = "mock-edr"
    provider.resolve_endpoint_id = AsyncMock(return_value="edr-device-1")
    provider.query_process_events = AsyncMock(return_value=[])
    provider.query_network_events = AsyncMock(
        return_value=[
            NetworkConnectEvent(
                timestamp=datetime.now(timezone.utc),
                pid=1000,
                process_name="ollama",
                remote_addr="127.0.0.1",
                remote_port=11434,
                local_port=54321,
            ),
        ]
    )
    provider.query_file_events = AsyncMock(return_value=[])

    result = await enrich_detection(
        event_payload=_minimal_event(tool_name="Ollama", confidence=0.50),
        provider=provider,
        settings=_mock_settings(),
    )
    assert result is not None
    assert "unresolved_proc_net_linkage" in result.penalties_removed
    assert result.enriched_confidence == pytest.approx(0.50 + 0.10, abs=0.01)


@pytest.mark.asyncio
async def test_process_events_remove_stale_artifact_only():
    """Process events matching tool remove stale_artifact_only penalty."""
    provider = AsyncMock()
    provider.name = "mock-edr"
    provider.resolve_endpoint_id = AsyncMock(return_value="edr-device-1")
    provider.query_process_events = AsyncMock(
        return_value=[
            ProcessExecEvent(
                timestamp=datetime.now(timezone.utc),
                pid=1000,
                ppid=1,
                name="Cursor",
                cmdline="/Applications/Cursor.app",
            ),
        ]
    )
    provider.query_network_events = AsyncMock(return_value=[])
    provider.query_file_events = AsyncMock(return_value=[])

    result = await enrich_detection(
        event_payload=_minimal_event(tool_name="Cursor", confidence=0.60),
        provider=provider,
        settings=_mock_settings(),
    )
    assert result is not None
    assert "stale_artifact_only" in result.penalties_removed
    assert result.enriched_confidence == pytest.approx(0.60 + 0.10, abs=0.01)


@pytest.mark.asyncio
async def test_band_change_detection():
    """Band changes from Medium to High when confidence crosses 0.75."""
    provider = AsyncMock()
    provider.name = "mock-edr"
    provider.resolve_endpoint_id = AsyncMock(return_value="edr-device-1")
    provider.query_process_events = AsyncMock(
        return_value=[
            ProcessExecEvent(
                timestamp=datetime.now(timezone.utc),
                pid=1000,
                ppid=999,
                name="ollama",
                cmdline="ollama",
            ),
            ProcessExecEvent(
                timestamp=datetime.now(timezone.utc),
                pid=999,
                ppid=1,
                name="ollama",
                cmdline="ollama serve",
            ),
        ]
    )
    provider.query_network_events = AsyncMock(
        return_value=[
            NetworkConnectEvent(
                timestamp=datetime.now(timezone.utc),
                pid=1000,
                process_name="ollama",
                remote_addr="127.0.0.1",
                remote_port=11434,
                local_port=12345,
            ),
        ]
    )
    provider.query_file_events = AsyncMock(return_value=[])

    result = await enrich_detection(
        event_payload=_minimal_event(tool_name="Ollama", confidence=0.65),
        provider=provider,
        settings=_mock_settings(),
    )
    assert result is not None
    assert result.band_changed is True
    assert result.original_confidence == 0.65
    assert result.enriched_confidence >= 0.75


@pytest.mark.asyncio
async def test_no_edr_evidence_no_penalties_removed():
    """When no EDR events match, no penalties are removed."""
    provider = AsyncMock()
    provider.name = "mock-edr"
    provider.resolve_endpoint_id = AsyncMock(return_value="edr-device-1")
    provider.query_process_events = AsyncMock(return_value=[])
    provider.query_network_events = AsyncMock(return_value=[])
    provider.query_file_events = AsyncMock(return_value=[])

    result = await enrich_detection(
        event_payload=_minimal_event(tool_name="Ollama", confidence=0.55),
        provider=provider,
        settings=_mock_settings(),
    )
    assert result is not None
    assert result.penalties_removed == []
    assert result.enriched_confidence == 0.55
    assert result.band_changed is False


@pytest.mark.asyncio
async def test_confidence_clamped_to_one():
    """Enriched confidence is clamped to 1.0."""
    provider = AsyncMock()
    provider.name = "mock-edr"
    provider.resolve_endpoint_id = AsyncMock(return_value="edr-device-1")
    provider.query_process_events = AsyncMock(
        return_value=[
            ProcessExecEvent(
                timestamp=datetime.now(timezone.utc),
                pid=1000,
                ppid=999,
                name="ollama",
                cmdline="ollama",
            ),
            ProcessExecEvent(
                timestamp=datetime.now(timezone.utc),
                pid=999,
                ppid=1,
                name="ollama",
                cmdline="ollama",
            ),
        ]
    )
    provider.query_network_events = AsyncMock(return_value=[])
    provider.query_file_events = AsyncMock(return_value=[])

    result = await enrich_detection(
        event_payload=_minimal_event(tool_name="Ollama", confidence=0.95),
        provider=provider,
        settings=_mock_settings(),
    )
    assert result is not None
    assert result.enriched_confidence <= 1.0

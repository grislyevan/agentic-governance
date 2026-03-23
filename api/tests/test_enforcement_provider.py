"""Tests for EnforcementProvider interface contract."""

from __future__ import annotations

import pytest
from integrations.enforcement_provider import EnforcementProvider, EnforcementResult


class IncompleteProvider(EnforcementProvider):
    """Deliberately incomplete to test ABC enforcement."""

    @property
    def name(self) -> str:
        return "incomplete"


class MockEnforcementProvider(EnforcementProvider):
    """Fully implemented mock for testing."""

    def __init__(self, available: bool = True, success: bool = True):
        self._available = available
        self._success = success
        self.calls: list[str] = []

    @property
    def name(self) -> str:
        return "mock"

    async def kill_process(self, hostname, pid, process_name):
        self.calls.append(f"kill:{hostname}:{pid}")
        return EnforcementResult(
            success=self._success,
            provider=self.name,
            action="kill_process",
            hostname=hostname,
            detail={"pid": pid, "process_name": process_name},
        )

    async def block_network(self, hostname):
        self.calls.append(f"block:{hostname}")
        return EnforcementResult(
            success=self._success,
            provider=self.name,
            action="block_network",
            hostname=hostname,
        )

    async def quarantine_endpoint(self, hostname):
        self.calls.append(f"quarantine:{hostname}")
        return EnforcementResult(
            success=self._success,
            provider=self.name,
            action="quarantine_endpoint",
            hostname=hostname,
        )

    async def available_for_endpoint(self, hostname):
        return self._available


def test_abc_raises_on_incomplete_implementation():
    """IncompleteProvider cannot be instantiated due to missing abstract methods."""
    with pytest.raises(TypeError):
        IncompleteProvider()


@pytest.mark.asyncio
async def test_mock_provider_kill_process():
    """Mock provider kill_process returns correct result."""
    mock = MockEnforcementProvider(success=True)
    result = await mock.kill_process("host1", 1234, "evil.exe")
    assert result.success is True
    assert result.provider == "mock"
    assert result.action == "kill_process"
    assert result.hostname == "host1"
    assert result.detail == {"pid": 1234, "process_name": "evil.exe"}
    assert mock.calls == ["kill:host1:1234"]


@pytest.mark.asyncio
async def test_mock_provider_block_network():
    """Mock provider block_network tracks calls."""
    mock = MockEnforcementProvider(success=True)
    result = await mock.block_network("host2")
    assert result.success is True
    assert result.action == "block_network"
    assert result.hostname == "host2"
    assert mock.calls == ["block:host2"]


@pytest.mark.asyncio
async def test_mock_provider_quarantine():
    """Mock provider quarantine_endpoint works."""
    mock = MockEnforcementProvider(success=True)
    result = await mock.quarantine_endpoint("host3")
    assert result.success is True
    assert result.action == "quarantine_endpoint"
    assert result.hostname == "host3"
    assert mock.calls == ["quarantine:host3"]


@pytest.mark.asyncio
async def test_mock_provider_available():
    """available_for_endpoint returns configured value."""
    mock_avail = MockEnforcementProvider(available=True)
    mock_unavail = MockEnforcementProvider(available=False)
    assert await mock_avail.available_for_endpoint("any") is True
    assert await mock_unavail.available_for_endpoint("any") is False


def test_enforcement_result_summary():
    """EnforcementResult.summary property works."""
    r1 = EnforcementResult(
        success=True,
        provider="cs",
        action="kill_process",
        hostname="laptop-01",
    )
    assert r1.summary == "cs:kill_process on laptop-01 succeeded"

    r2 = EnforcementResult(
        success=False,
        provider="cs",
        action="block_network",
        hostname="laptop-02",
    )
    assert r2.summary == "cs:block_network on laptop-02 failed"


def test_enforcement_result_default_timestamp():
    """EnforcementResult timestamp is populated automatically."""
    r = EnforcementResult(
        success=True,
        provider="mock",
        action="kill_process",
        hostname="host",
    )
    assert r.timestamp is not None
    from datetime import datetime, timezone

    now = datetime.now(timezone.utc)
    diff = abs((now - r.timestamp).total_seconds())
    assert diff < 2

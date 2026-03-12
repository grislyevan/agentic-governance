"""Integration tests for enforcement orchestration router."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from integrations import enforcement_router as enf_router
from integrations.enforcement_provider import EnforcementProvider, EnforcementResult


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


@pytest.fixture(autouse=True)
def clean_providers():
    enf_router._providers.clear()
    yield
    enf_router._providers.clear()


@pytest.fixture
def db():
    return MagicMock()


@pytest.mark.asyncio
async def test_local_enforcement_when_no_provider_configured(db):
    """enforcement_provider_name=None returns delegated=False."""
    with patch("integrations.enforcement_router.settings") as mock_settings:
        mock_settings.edr_enforcement_enabled = True
        mock_settings.edr_enforcement_fallback = "local"

        decision = await enf_router.enforce(
            db=db,
            tenant_id="tenant-1",
            endpoint_id="ep-1",
            hostname="laptop-01",
            enforcement_provider_name=None,
            action="kill_process",
            pid=1234,
            process_name="evil.exe",
        )

        assert decision.delegated is False
        assert decision.provider_name is None
        assert decision.success is True
        assert decision.detail.get("path") == "local"
        assert decision.detail.get("reason") == "no_edr_configured"


@pytest.mark.asyncio
async def test_delegated_enforcement_success(db):
    """Provider registered, available, kill succeeds, decision.delegated=True."""
    provider = MockEnforcementProvider(available=True, success=True)
    enf_router.register_provider(provider)

    with patch("integrations.enforcement_router.settings") as mock_settings:
        mock_settings.edr_enforcement_enabled = True
        mock_settings.edr_enforcement_fallback = "local"

        decision = await enf_router.enforce(
            db=db,
            tenant_id="tenant-1",
            endpoint_id="ep-1",
            hostname="laptop-01",
            enforcement_provider_name="mock",
            action="kill_process",
            pid=1234,
            process_name="evil.exe",
        )

        assert decision.delegated is True
        assert decision.provider_name == "mock"
        assert decision.success is True
        assert decision.fallback_used is False
        assert provider.calls == ["kill:laptop-01:1234"]


@pytest.mark.asyncio
async def test_fallback_to_local_when_provider_unavailable(db):
    """Provider registered but available_for_endpoint returns False, fallback_used=True."""
    provider = MockEnforcementProvider(available=False, success=True)
    enf_router.register_provider(provider)

    with patch("integrations.enforcement_router.settings") as mock_settings:
        mock_settings.edr_enforcement_enabled = True
        mock_settings.edr_enforcement_fallback = "local"

        decision = await enf_router.enforce(
            db=db,
            tenant_id="tenant-1",
            endpoint_id="ep-1",
            hostname="laptop-01",
            enforcement_provider_name="mock",
            action="kill_process",
            pid=1234,
            process_name="evil.exe",
        )

        assert decision.delegated is False
        assert decision.fallback_used is True
        assert decision.success is True
        assert decision.detail.get("path") == "fallback_to_local"
        assert provider.calls == []


@pytest.mark.asyncio
async def test_fallback_to_local_on_dispatch_failure(db):
    """Provider available but kill_process fails, falls back."""
    provider = MockEnforcementProvider(available=True, success=False)
    enf_router.register_provider(provider)

    with patch("integrations.enforcement_router.settings") as mock_settings:
        mock_settings.edr_enforcement_enabled = True
        mock_settings.edr_enforcement_fallback = "local"

        decision = await enf_router.enforce(
            db=db,
            tenant_id="tenant-1",
            endpoint_id="ep-1",
            hostname="laptop-01",
            enforcement_provider_name="mock",
            action="kill_process",
            pid=1234,
            process_name="evil.exe",
        )

        assert decision.delegated is False
        assert decision.fallback_used is True
        assert decision.success is True
        assert decision.detail.get("path") == "fallback_to_local"
        assert provider.calls == ["kill:laptop-01:1234"]


@pytest.mark.asyncio
async def test_no_fallback_when_configured_none(db):
    """edr_enforcement_fallback='none', no fallback, success=False."""
    provider = MockEnforcementProvider(available=True, success=False)
    enf_router.register_provider(provider)

    with patch("integrations.enforcement_router.settings") as mock_settings:
        mock_settings.edr_enforcement_enabled = True
        mock_settings.edr_enforcement_fallback = "none"

        decision = await enf_router.enforce(
            db=db,
            tenant_id="tenant-1",
            endpoint_id="ep-1",
            hostname="laptop-01",
            enforcement_provider_name="mock",
            action="kill_process",
            pid=1234,
            process_name="evil.exe",
        )

        assert decision.delegated is False
        assert decision.fallback_used is False
        assert decision.success is False
        assert decision.detail.get("path") == "no_fallback"


@pytest.mark.asyncio
async def test_unknown_provider_falls_back(db):
    """Endpoint references unregistered provider."""
    with patch("integrations.enforcement_router.settings") as mock_settings:
        mock_settings.edr_enforcement_enabled = True
        mock_settings.edr_enforcement_fallback = "local"

        decision = await enf_router.enforce(
            db=db,
            tenant_id="tenant-1",
            endpoint_id="ep-1",
            hostname="laptop-01",
            enforcement_provider_name="unknown_provider",
            action="kill_process",
            pid=1234,
            process_name="evil.exe",
        )

        assert decision.delegated is False
        assert decision.fallback_used is True
        assert decision.fallback_reason == "provider_not_registered"
        assert decision.success is True


@pytest.mark.asyncio
async def test_edr_enforcement_disabled_returns_local(db):
    """edr_enforcement_enabled=False returns local path."""
    provider = MockEnforcementProvider(available=True, success=True)
    enf_router.register_provider(provider)

    with patch("integrations.enforcement_router.settings") as mock_settings:
        mock_settings.edr_enforcement_enabled = False
        mock_settings.edr_enforcement_fallback = "local"

        decision = await enf_router.enforce(
            db=db,
            tenant_id="tenant-1",
            endpoint_id="ep-1",
            hostname="laptop-01",
            enforcement_provider_name="mock",
            action="kill_process",
            pid=1234,
            process_name="evil.exe",
        )

        assert decision.delegated is False
        assert decision.provider_name is None
        assert decision.success is True
        assert decision.detail.get("path") == "local"
        assert decision.detail.get("reason") == "no_edr_configured"
        assert provider.calls == []

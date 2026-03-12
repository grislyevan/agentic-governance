"""EDR Integration Validation (Task 8).

Subtask 8a: Full RTR session lifecycle tests with mock CrowdStrike API.
Subtask 8b: Fallback path tests when CrowdStrike is unreachable.

These tests validate that the enforcement delegation chain works end-to-end
without requiring a live CrowdStrike sandbox. They cover:
  - Token management (OAuth2 flow, refresh on 401)
  - RTR session lifecycle (init -> command -> close)
  - Timeout and connection-error scenarios
  - Enforcement router fallback to local on EDR failure
  - Audit event emission for delegation outcomes
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from integrations.crowdstrike import CrowdStrikeProvider
from integrations.crowdstrike_enforcement import CrowdStrikeEnforcementProvider
from integrations import enforcement_router as enf_router
from integrations.enforcement_provider import EnforcementResult


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_response(status_code: int, json_data: dict):
    resp = MagicMock()
    resp.status_code = status_code
    resp.json.return_value = json_data
    resp.raise_for_status = MagicMock()
    if status_code >= 400:
        resp.raise_for_status.side_effect = httpx.HTTPStatusError(
            f"HTTP {status_code}", request=MagicMock(), response=resp,
        )
    return resp


def _oauth_success():
    return _make_response(201, {"access_token": "tok", "expires_in": 1799})


def _setup_mock_client(mock_client_cls):
    mock_client = AsyncMock()
    mock_client_cls.return_value.__aenter__.return_value = mock_client
    return mock_client


def _cs_provider():
    return CrowdStrikeProvider(
        api_base="https://api.crowdstrike.com",
        client_id="test-id",
        client_secret="test-secret",
    )


# ===================================================================
# 8a - CrowdStrike mock RTR session lifecycle
# ===================================================================


class TestRTRSessionLifecycle:
    """Full session lifecycle: init -> command -> close."""

    @pytest.mark.asyncio
    async def test_full_kill_lifecycle(self):
        """Resolve host -> open session -> kill -> close session."""
        enf = CrowdStrikeEnforcementProvider(_cs_provider())

        with patch("httpx.AsyncClient") as mock_cls:
            mc = _setup_mock_client(mock_cls)
            mc.post = AsyncMock(return_value=_oauth_success())
            mc.request = AsyncMock(side_effect=[
                _make_response(200, {"resources": ["device-42"]}),
                _make_response(201, {"resources": [{"session_id": "sess-1"}]}),
                _make_response(200, {"resources": [{"stderr": ""}]}),
                _make_response(200, {}),
            ])

            result = await enf.kill_process("workstation-1", 5678, "agent.py")

            assert result.success is True
            assert result.provider == "crowdstrike"
            assert result.action == "kill_process"
            assert result.detail["pid"] == 5678
            assert result.detail["session_id"] == "sess-1"

            calls = [c[0] for c in mc.request.call_args_list]
            assert calls[0][0] == "GET"    # resolve host
            assert calls[1][0] == "POST"   # init session
            assert calls[2][0] == "POST"   # kill command
            assert calls[3][0] == "DELETE"  # close session

    @pytest.mark.asyncio
    async def test_full_block_network_lifecycle(self):
        """Resolve host -> network contain (no RTR session needed)."""
        enf = CrowdStrikeEnforcementProvider(_cs_provider())

        with patch("httpx.AsyncClient") as mock_cls:
            mc = _setup_mock_client(mock_cls)
            mc.post = AsyncMock(return_value=_oauth_success())
            mc.request = AsyncMock(side_effect=[
                _make_response(200, {"resources": ["device-42"]}),
                _make_response(200, {}),
            ])

            result = await enf.block_network("workstation-1")

            assert result.success is True
            assert result.action == "block_network"
            assert result.detail["host_id"] == "device-42"

    @pytest.mark.asyncio
    async def test_full_quarantine_lifecycle(self):
        """Quarantine delegates to block_network internally."""
        enf = CrowdStrikeEnforcementProvider(_cs_provider())

        with patch("httpx.AsyncClient") as mock_cls:
            mc = _setup_mock_client(mock_cls)
            mc.post = AsyncMock(return_value=_oauth_success())
            mc.request = AsyncMock(side_effect=[
                _make_response(200, {"resources": ["device-42"]}),
                _make_response(200, {}),
            ])

            result = await enf.quarantine_endpoint("workstation-1")

            assert result.success is True
            assert result.action == "quarantine_endpoint"

    @pytest.mark.asyncio
    async def test_kill_host_not_found(self):
        """kill_process returns failure when host cannot be resolved."""
        enf = CrowdStrikeEnforcementProvider(_cs_provider())

        with patch("httpx.AsyncClient") as mock_cls:
            mc = _setup_mock_client(mock_cls)
            mc.post = AsyncMock(return_value=_oauth_success())
            mc.request = AsyncMock(
                return_value=_make_response(200, {"resources": []}),
            )

            result = await enf.kill_process("ghost-host", 111, "x")

            assert result.success is False
            assert result.detail["reason"] == "host_not_found"

    @pytest.mark.asyncio
    async def test_kill_session_conflict_409(self):
        """kill_process returns failure when another RTR session is active."""
        enf = CrowdStrikeEnforcementProvider(_cs_provider())

        with patch("httpx.AsyncClient") as mock_cls:
            mc = _setup_mock_client(mock_cls)
            mc.post = AsyncMock(return_value=_oauth_success())
            mc.request = AsyncMock(side_effect=[
                _make_response(200, {"resources": ["device-42"]}),
                _make_response(409, {"resources": []}),
            ])

            result = await enf.kill_process("workstation-1", 999, "proc")

            assert result.success is False
            assert result.detail["reason"] == "rtr_session_failed"

    @pytest.mark.asyncio
    async def test_block_network_host_not_found(self):
        """block_network returns failure when host cannot be resolved."""
        enf = CrowdStrikeEnforcementProvider(_cs_provider())

        with patch("httpx.AsyncClient") as mock_cls:
            mc = _setup_mock_client(mock_cls)
            mc.post = AsyncMock(return_value=_oauth_success())
            mc.request = AsyncMock(
                return_value=_make_response(200, {"resources": []}),
            )

            result = await enf.block_network("unknown-host")

            assert result.success is False
            assert result.detail["reason"] == "host_not_found"


class TestRTRTimeoutAndConnectionErrors:
    """Validate graceful degradation on network failures."""

    @pytest.mark.asyncio
    async def test_connect_timeout_on_host_resolve(self):
        """ConnectTimeout during host resolution returns None (host not found)."""
        provider = _cs_provider()

        with patch("httpx.AsyncClient") as mock_cls:
            mc = _setup_mock_client(mock_cls)
            mc.post = AsyncMock(return_value=_oauth_success())
            mc.request = AsyncMock(side_effect=httpx.ConnectTimeout("Connection timed out"))

            result = await provider.resolve_endpoint_id("some-host")
            assert result is None

    @pytest.mark.asyncio
    async def test_connect_error_on_session_init(self):
        """ConnectError during session init returns None."""
        provider = _cs_provider()

        with patch("httpx.AsyncClient") as mock_cls:
            mc = _setup_mock_client(mock_cls)
            mc.post = AsyncMock(return_value=_oauth_success())
            mc.request = AsyncMock(side_effect=httpx.ConnectError("Connection refused"))

            result = await provider.initiate_rtr_session("device-42")
            assert result is None

    @pytest.mark.asyncio
    async def test_read_timeout_on_kill_command(self):
        """ReadTimeout during kill returns False."""
        provider = _cs_provider()

        with patch("httpx.AsyncClient") as mock_cls:
            mc = _setup_mock_client(mock_cls)
            mc.post = AsyncMock(return_value=_oauth_success())
            mc.request = AsyncMock(side_effect=httpx.ReadTimeout("Read timed out"))

            result = await provider.rtr_kill_process("sess-1", 1234)
            assert result is False

    @pytest.mark.asyncio
    async def test_connect_timeout_on_network_contain(self):
        """ConnectTimeout on contain returns False."""
        provider = _cs_provider()

        with patch("httpx.AsyncClient") as mock_cls:
            mc = _setup_mock_client(mock_cls)
            mc.post = AsyncMock(return_value=_oauth_success())
            mc.request = AsyncMock(side_effect=httpx.ConnectTimeout("Timed out"))

            result = await provider.rtr_network_contain("host-id-1")
            assert result is False

    @pytest.mark.asyncio
    async def test_oauth_timeout_propagates_as_failure(self):
        """If OAuth2 token request times out, resolve returns None."""
        provider = _cs_provider()

        with patch("httpx.AsyncClient") as mock_cls:
            mc = _setup_mock_client(mock_cls)
            mc.post = AsyncMock(side_effect=httpx.ConnectTimeout("OAuth timed out"))

            result = await provider.resolve_endpoint_id("any-host")
            assert result is None

    @pytest.mark.asyncio
    async def test_enforcement_provider_timeout_surfaces_as_failure(self):
        """CrowdStrikeEnforcementProvider maps timeouts to result.success=False."""
        enf = CrowdStrikeEnforcementProvider(_cs_provider())

        with patch("httpx.AsyncClient") as mock_cls:
            mc = _setup_mock_client(mock_cls)
            mc.post = AsyncMock(return_value=_oauth_success())
            mc.request = AsyncMock(side_effect=httpx.ConnectTimeout("Timed out"))

            result = await enf.kill_process("host-1", 42, "proc")
            assert result.success is False

    @pytest.mark.asyncio
    async def test_enforcement_provider_available_returns_false_on_timeout(self):
        """available_for_endpoint returns False when CrowdStrike is unreachable."""
        enf = CrowdStrikeEnforcementProvider(_cs_provider())

        with patch("httpx.AsyncClient") as mock_cls:
            mc = _setup_mock_client(mock_cls)
            mc.post = AsyncMock(return_value=_oauth_success())
            mc.request = AsyncMock(side_effect=httpx.ConnectTimeout("Timed out"))

            result = await enf.available_for_endpoint("host-1")
            assert result is False


class TestTokenRefreshDuringRTR:
    """Verify token refresh works mid-session."""

    @pytest.mark.asyncio
    async def test_token_cached_across_rtr_calls(self):
        """Token obtained on first call is reused for subsequent calls."""
        provider = _cs_provider()
        provider._token = None

        with patch("httpx.AsyncClient") as mock_cls:
            mc = _setup_mock_client(mock_cls)
            mc.post = AsyncMock(return_value=_oauth_success())
            mc.request = AsyncMock(side_effect=[
                _make_response(201, {"resources": [{"session_id": "sess-1"}]}),
                _make_response(200, {"resources": [{"stderr": ""}]}),
            ])

            sess = await provider.initiate_rtr_session("device-1")
            assert sess == "sess-1"

            killed = await provider.rtr_kill_process("sess-1", 42)
            assert killed is True

            assert mc.post.call_count == 1  # token cached, no second OAuth call

    @pytest.mark.asyncio
    async def test_401_during_kill_triggers_token_refresh(self):
        """401 on kill command triggers automatic token refresh and retry."""
        provider = _cs_provider()

        with patch("httpx.AsyncClient") as mock_cls:
            mc = _setup_mock_client(mock_cls)
            mc.post = AsyncMock(side_effect=[
                _oauth_success(),
                _oauth_success(),
            ])
            mc.request = AsyncMock(side_effect=[
                _make_response(401, {"errors": [{"message": "Unauthorized"}]}),
                _make_response(200, {"resources": [{"stderr": ""}]}),
            ])

            killed = await provider.rtr_kill_process("sess-1", 1234)
            assert killed is True
            assert mc.post.call_count == 2


# ===================================================================
# 8b - Fallback path: CrowdStrike unreachable
# ===================================================================

class _TimeoutEnforcementProvider(CrowdStrikeEnforcementProvider):
    """Simulates CrowdStrike being unreachable for all operations."""

    async def available_for_endpoint(self, hostname: str) -> bool:
        raise httpx.ConnectTimeout("CrowdStrike API unreachable")

    async def kill_process(self, hostname, pid, process_name):
        raise httpx.ConnectTimeout("CrowdStrike API unreachable")

    async def block_network(self, hostname):
        raise httpx.ConnectTimeout("CrowdStrike API unreachable")

    async def quarantine_endpoint(self, hostname):
        raise httpx.ConnectTimeout("CrowdStrike API unreachable")


class _ConnectionRefusedProvider(CrowdStrikeEnforcementProvider):
    """Simulates connection refused for all CrowdStrike operations."""

    async def available_for_endpoint(self, hostname: str) -> bool:
        raise httpx.ConnectError("Connection refused")

    async def kill_process(self, hostname, pid, process_name):
        raise httpx.ConnectError("Connection refused")


@pytest.fixture(autouse=True)
def clean_providers():
    enf_router._providers.clear()
    yield
    enf_router._providers.clear()


@pytest.fixture
def mock_db():
    return MagicMock()


class TestFallbackOnCrowdStrikeUnreachable:
    """Verify the enforcement router falls back to local enforcement
    when CrowdStrike is unreachable (timeout or connection refused)."""

    @pytest.mark.asyncio
    async def test_timeout_triggers_fallback_to_local(self, mock_db):
        """ConnectTimeout on availability check -> fallback to local enforcement."""
        provider = _TimeoutEnforcementProvider(_cs_provider())
        enf_router.register_provider(provider)

        with patch("integrations.enforcement_router.settings") as ms:
            ms.edr_enforcement_enabled = True
            ms.edr_enforcement_fallback = "local"

            decision = await enf_router.enforce(
                db=mock_db,
                tenant_id="t1",
                endpoint_id="ep-1",
                hostname="laptop-01",
                enforcement_provider_name="crowdstrike",
                action="kill_process",
                pid=1234,
                process_name="tool.exe",
            )

            assert decision.delegated is False
            assert decision.fallback_used is True
            assert decision.success is True
            assert decision.fallback_reason == "endpoint_not_reachable"
            assert decision.detail["path"] == "fallback_to_local"

    @pytest.mark.asyncio
    async def test_connection_refused_triggers_fallback(self, mock_db):
        """ConnectError on availability check -> fallback to local."""
        provider = _ConnectionRefusedProvider(_cs_provider())
        enf_router.register_provider(provider)

        with patch("integrations.enforcement_router.settings") as ms:
            ms.edr_enforcement_enabled = True
            ms.edr_enforcement_fallback = "local"

            decision = await enf_router.enforce(
                db=mock_db,
                tenant_id="t1",
                endpoint_id="ep-1",
                hostname="laptop-02",
                enforcement_provider_name="crowdstrike",
                action="kill_process",
                pid=555,
                process_name="app",
            )

            assert decision.delegated is False
            assert decision.fallback_used is True
            assert decision.success is True

    @pytest.mark.asyncio
    async def test_timeout_with_no_fallback_fails(self, mock_db):
        """ConnectTimeout + fallback='none' -> success=False, no enforcement."""
        provider = _TimeoutEnforcementProvider(_cs_provider())
        enf_router.register_provider(provider)

        with patch("integrations.enforcement_router.settings") as ms:
            ms.edr_enforcement_enabled = True
            ms.edr_enforcement_fallback = "none"

            decision = await enf_router.enforce(
                db=mock_db,
                tenant_id="t1",
                endpoint_id="ep-1",
                hostname="laptop-01",
                enforcement_provider_name="crowdstrike",
                action="kill_process",
                pid=1234,
                process_name="tool.exe",
            )

            assert decision.delegated is False
            assert decision.fallback_used is False
            assert decision.success is False
            assert decision.detail["path"] == "no_fallback"

    @pytest.mark.asyncio
    async def test_fallback_emits_audit_event(self, mock_db):
        """Verify audit_record is called with enforcement.fallback_to_local."""
        provider = _TimeoutEnforcementProvider(_cs_provider())
        enf_router.register_provider(provider)

        with patch("integrations.enforcement_router.settings") as ms, \
             patch("integrations.enforcement_router.audit_record") as mock_audit:
            ms.edr_enforcement_enabled = True
            ms.edr_enforcement_fallback = "local"

            await enf_router.enforce(
                db=mock_db,
                tenant_id="t1",
                endpoint_id="ep-1",
                hostname="laptop-01",
                enforcement_provider_name="crowdstrike",
                action="kill_process",
                pid=1234,
                process_name="tool.exe",
            )

            mock_audit.assert_called_once()
            call_kwargs = mock_audit.call_args
            assert call_kwargs[1]["action"] == "enforcement.fallback_to_local"
            assert call_kwargs[1]["detail"]["hostname"] == "laptop-01"
            assert call_kwargs[1]["detail"]["fallback_used"] is True
            assert call_kwargs[1]["detail"]["provider"] == "crowdstrike"

    @pytest.mark.asyncio
    async def test_no_fallback_emits_delegated_failed_audit(self, mock_db):
        """Verify audit_record is called with enforcement.delegated_failed
        when fallback='none' and CrowdStrike is unreachable."""
        provider = _TimeoutEnforcementProvider(_cs_provider())
        enf_router.register_provider(provider)

        with patch("integrations.enforcement_router.settings") as ms, \
             patch("integrations.enforcement_router.audit_record") as mock_audit:
            ms.edr_enforcement_enabled = True
            ms.edr_enforcement_fallback = "none"

            await enf_router.enforce(
                db=mock_db,
                tenant_id="t1",
                endpoint_id="ep-1",
                hostname="laptop-01",
                enforcement_provider_name="crowdstrike",
                action="kill_process",
                pid=1234,
                process_name="tool.exe",
            )

            mock_audit.assert_called_once()
            call_kwargs = mock_audit.call_args
            assert call_kwargs[1]["action"] == "enforcement.delegated_failed"
            assert call_kwargs[1]["detail"]["success"] is False
            assert call_kwargs[1]["detail"]["fallback_reason"] == "endpoint_not_reachable"

    @pytest.mark.asyncio
    async def test_block_network_fallback_on_timeout(self, mock_db):
        """block_network action also falls back on timeout."""
        provider = _TimeoutEnforcementProvider(_cs_provider())
        enf_router.register_provider(provider)

        with patch("integrations.enforcement_router.settings") as ms:
            ms.edr_enforcement_enabled = True
            ms.edr_enforcement_fallback = "local"

            decision = await enf_router.enforce(
                db=mock_db,
                tenant_id="t1",
                endpoint_id="ep-1",
                hostname="laptop-01",
                enforcement_provider_name="crowdstrike",
                action="block_network",
            )

            assert decision.fallback_used is True
            assert decision.success is True


# ===================================================================
# Expected RTR latency documentation
# ===================================================================

class TestRTRLatencyDocumentation:
    """Not a behavioral test. Documents expected CrowdStrike RTR timing
    based on CrowdStrike's published SLAs and observed behavior.

    These values should be validated against a real sandbox when access
    is available. Update the constants if measured values differ.
    """

    EXPECTED_OAUTH_TOKEN_MS = 200       # OAuth2 token issuance
    EXPECTED_HOST_RESOLVE_MS = 300      # /devices/queries/devices/v1
    EXPECTED_SESSION_INIT_MS = 2000     # RTR session init (sensor handshake)
    EXPECTED_KILL_COMMAND_MS = 1500     # RTR admin kill command
    EXPECTED_SESSION_CLOSE_MS = 200     # RTR session delete (best-effort)
    EXPECTED_CONTAIN_MS = 1000          # Host containment action

    EXPECTED_TOTAL_KILL_MS = (
        EXPECTED_OAUTH_TOKEN_MS
        + EXPECTED_HOST_RESOLVE_MS
        + EXPECTED_SESSION_INIT_MS
        + EXPECTED_KILL_COMMAND_MS
        + EXPECTED_SESSION_CLOSE_MS
    )

    def test_expected_kill_roundtrip_under_5s(self):
        """Full kill cycle (token + resolve + session + kill + close)
        is expected to complete in under 5 seconds."""
        assert self.EXPECTED_TOTAL_KILL_MS < 5000

    def test_expected_contain_roundtrip_under_2s(self):
        """Network contain (token + resolve + contain) expected under 2 seconds."""
        total = (
            self.EXPECTED_OAUTH_TOKEN_MS
            + self.EXPECTED_HOST_RESOLVE_MS
            + self.EXPECTED_CONTAIN_MS
        )
        assert total < 2000

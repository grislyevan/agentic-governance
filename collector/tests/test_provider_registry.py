"""Tests for provider registry and native provider available()."""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

_COLLECTOR_DIR = str(Path(__file__).resolve().parent.parent)
if _COLLECTOR_DIR not in sys.path:
    sys.path.insert(0, _COLLECTOR_DIR)

from providers.polling import PollingProvider
from providers.registry import get_best_provider


def test_preference_polling_always_returns_polling() -> None:
    provider = get_best_provider(preference="polling")
    assert provider.name == "polling"
    assert isinstance(provider, PollingProvider)


def test_preference_native_raises_when_no_native_available() -> None:
    with patch("providers.registry._try_native", return_value=None):
        with pytest.raises(RuntimeError, match="No native telemetry provider"):
            get_best_provider(preference="native")


def test_preference_auto_falls_back_to_polling_when_native_unavailable() -> None:
    with patch("providers.registry._try_native", return_value=None):
        provider = get_best_provider(preference="auto")
        assert provider.name == "polling"


def test_preference_auto_uses_native_when_available() -> None:
    mock_native = MagicMock()
    mock_native.name = "esf"
    with patch("providers.registry._try_native", return_value=mock_native):
        provider = get_best_provider(preference="auto")
        assert provider.name == "esf"


def test_preference_native_returns_native_when_available() -> None:
    mock_native = MagicMock()
    mock_native.name = "ebpf"
    with patch("providers.registry._try_native", return_value=mock_native):
        provider = get_best_provider(preference="native")
        assert provider.name == "ebpf"


def test_platform_darwin_tries_esf() -> None:
    mock_esf_provider = MagicMock()
    mock_esf_provider.name = "esf"
    with patch("providers.registry.sys.platform", "darwin"):
        with patch("providers.registry._try_esf") as mock_esf:
            mock_esf.return_value = mock_esf_provider
            provider = get_best_provider(preference="auto")
            mock_esf.assert_called_once()
            assert provider.name == "esf"


def test_platform_linux_tries_ebpf() -> None:
    mock_ebpf_provider = MagicMock()
    mock_ebpf_provider.name = "ebpf"
    with patch("providers.registry.sys.platform", "linux"):
        with patch("providers.registry._try_ebpf") as mock_ebpf:
            mock_ebpf.return_value = mock_ebpf_provider
            provider = get_best_provider(preference="auto")
            mock_ebpf.assert_called_once()
            assert provider.name == "ebpf"


def test_platform_win32_tries_etw() -> None:
    mock_etw_provider = MagicMock()
    mock_etw_provider.name = "etw"
    with patch("providers.registry.sys.platform", "win32"):
        with patch("providers.registry._try_etw") as mock_etw:
            mock_etw.return_value = mock_etw_provider
            provider = get_best_provider(preference="auto")
            mock_etw.assert_called_once()
            assert provider.name == "etw"


def test_esf_available_returns_false_on_non_darwin() -> None:
    from providers.esf_provider import ESFProvider

    with patch("providers.esf_provider.sys") as mock_sys:
        mock_sys.platform = "linux"
        provider = ESFProvider()
        assert provider.available() is False
        assert "macOS" in provider.unavailable_reason


def test_esf_available_returns_false_when_helper_missing() -> None:
    from providers.esf_provider import ESFProvider

    with patch("providers.esf_provider.sys") as mock_sys:
        mock_sys.platform = "darwin"
        mock_sys.frozen = False
        with patch("providers.esf_provider._find_esf_helper", return_value=None):
            with patch("providers.esf_provider._macos_version_ok", return_value=True):
                provider = ESFProvider()
                assert provider.available() is False
                assert "helper" in provider.unavailable_reason.lower()


def test_esf_available_returns_false_when_macos_too_old() -> None:
    from providers.esf_provider import ESFProvider

    with patch("providers.esf_provider.sys") as mock_sys:
        mock_sys.platform = "darwin"
        with patch("providers.esf_provider.shutil.which", return_value="/usr/bin/detec-esf-helper"):
            with patch("providers.esf_provider.platform.mac_ver", return_value=("10.14.0", "", "")):
                provider = ESFProvider()
                assert provider.available() is False
                assert "10.15" in provider.unavailable_reason or "required" in provider.unavailable_reason


def test_esf_available_returns_true_when_conditions_met() -> None:
    from providers.esf_provider import ESFProvider

    with patch("providers.esf_provider.sys") as mock_sys:
        mock_sys.platform = "darwin"
        with patch("providers.esf_provider.shutil.which", return_value="/usr/bin/detec-esf-helper"):
            with patch("providers.esf_provider.platform.mac_ver", return_value=("14.0.0", "", "")):
                provider = ESFProvider()
                assert provider.available() is True


def test_ebpf_available_returns_false_on_non_linux() -> None:
    from providers.ebpf_provider import EBPFProvider

    with patch("providers.ebpf_provider.sys") as mock_sys:
        mock_sys.platform = "darwin"
        provider = EBPFProvider()
        assert provider.available() is False
        assert "Linux" in provider.unavailable_reason


def test_ebpf_available_returns_false_when_kernel_too_old() -> None:
    from providers.ebpf_provider import EBPFProvider

    with patch("providers.ebpf_provider.sys") as mock_sys:
        mock_sys.platform = "linux"
        with patch("providers.ebpf_provider.platform.release", return_value="4.14.0-generic"):
            provider = EBPFProvider()
            assert provider.available() is False
            assert "4.15" in provider.unavailable_reason or "kernel" in provider.unavailable_reason


def test_ebpf_available_returns_false_when_not_root_and_no_cap_bpf() -> None:
    from providers.ebpf_provider import EBPFProvider

    with patch("providers.ebpf_provider.sys") as mock_sys:
        mock_sys.platform = "linux"
        with patch("providers.ebpf_provider.platform.release", return_value="6.0.0-generic"):
            with patch("providers.ebpf_provider.os.geteuid", return_value=1000):
                with patch("providers.ebpf_provider._has_capabilities", return_value=False):
                    provider = EBPFProvider()
                    assert provider.available() is False
                    assert "root" in provider.unavailable_reason or "CAP_BPF" in provider.unavailable_reason


def test_ebpf_available_returns_true_when_root() -> None:
    from providers.ebpf_provider import EBPFProvider

    with patch("providers.ebpf_provider.sys") as mock_sys:
        mock_sys.platform = "linux"
        with patch("providers.ebpf_provider.platform.release", return_value="6.0.0-generic"):
            with patch("providers.ebpf_provider.os.geteuid", return_value=0):
                with patch.dict("sys.modules", {"bcc": MagicMock()}):
                    provider = EBPFProvider()
                    assert provider.available() is True


def test_etw_available_returns_false_on_non_win32() -> None:
    from providers.etw_provider import ETWProvider

    with patch("providers.etw_provider.sys") as mock_sys:
        mock_sys.platform = "darwin"
        provider = ETWProvider()
        assert provider.available() is False
        assert "Windows" in provider.unavailable_reason


def test_etw_available_returns_false_when_not_admin() -> None:
    from providers.etw_provider import ETWProvider

    with patch("providers.etw_provider.sys") as mock_sys:
        mock_sys.platform = "win32"
        with patch("providers.etw_provider._is_admin", return_value=False):
            provider = ETWProvider()
            assert provider.available() is False
            assert "admin" in provider.unavailable_reason.lower()


def test_etw_available_returns_true_when_admin() -> None:
    from providers.etw_provider import ETWProvider

    with patch("providers.etw_provider.sys") as mock_sys:
        mock_sys.platform = "win32"
        with patch("providers.etw_provider._is_admin", return_value=True):
            with patch("providers.etw_provider._check_pywintrace", return_value=True):
                provider = ETWProvider()
                assert provider.available() is True

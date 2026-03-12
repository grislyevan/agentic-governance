"""Provider negotiation and registry."""

from __future__ import annotations

import logging
import sys

from .base import TelemetryProvider
from .polling import PollingProvider

logger = logging.getLogger(__name__)


def _try_esf() -> TelemetryProvider | None:
    """Attempt to load the macOS ESF provider."""
    try:
        from .esf_provider import ESFProvider

        provider = ESFProvider()
        if provider.available():
            return provider
        logger.debug("ESF provider not available: %s", provider.unavailable_reason)
    except Exception as exc:
        logger.debug("ESF provider import failed: %s", exc)
    return None


def _try_ebpf() -> TelemetryProvider | None:
    """Attempt to load the Linux eBPF provider."""
    try:
        from .ebpf_provider import EBPFProvider

        provider = EBPFProvider()
        if provider.available():
            return provider
        logger.debug("eBPF provider not available: %s", provider.unavailable_reason)
    except Exception as exc:
        logger.debug("eBPF provider import failed: %s", exc)
    return None


def _try_etw() -> TelemetryProvider | None:
    """Attempt to load the Windows ETW provider."""
    try:
        from .etw_provider import ETWProvider

        provider = ETWProvider()
        if provider.available():
            return provider
        logger.debug("ETW provider not available: %s", provider.unavailable_reason)
    except Exception as exc:
        logger.debug("ETW provider import failed: %s", exc)
    return None


def _try_native() -> TelemetryProvider | None:
    """Try the native provider for the current platform."""
    if sys.platform == "darwin":
        return _try_esf()
    elif sys.platform == "linux":
        return _try_ebpf()
    elif sys.platform == "win32":
        return _try_etw()
    return None


def get_best_provider(preference: str = "auto") -> TelemetryProvider:
    """Return the best available telemetry provider for the given preference.

    Args:
        preference: "auto" (try native, fall back to polling), "native" (require
            native, raise if unavailable), "polling" (polling only).

    Returns:
        A configured TelemetryProvider instance.

    Raises:
        RuntimeError: When preference is "native" and no native provider is available.
    """
    if preference == "polling":
        return PollingProvider()

    native = _try_native()

    if preference == "native":
        if native is None:
            raise RuntimeError(
                f"No native telemetry provider available on {sys.platform}"
            )
        logger.info("Using native telemetry provider: %s", native.name)
        return native

    # preference == "auto": try native first, fall back to polling
    if native is not None:
        logger.info("Using native telemetry provider: %s", native.name)
        return native

    logger.debug("No native provider available; falling back to polling")
    return PollingProvider()

"""Provider selection and multi-provider startup.

Delegates single-provider selection to the registry. Supports starting
multiple providers against the same EventStore for optional multi-provider mode.
"""

from __future__ import annotations

import logging
import sys
from typing import TYPE_CHECKING

from providers.registry import get_best_provider

if TYPE_CHECKING:
    from telemetry.event_store import EventStore
    from telemetry.providers.base_provider import TelemetryProviderBase

logger = logging.getLogger(__name__)


def get_provider(preference: str = "auto") -> TelemetryProviderBase:
    """Return the best available telemetry provider for the given preference.

    Delegates to providers.registry.get_best_provider. preference is
    "auto" (try native, fall back to polling), "native" (require native),
    or "polling".
    """
    return get_best_provider(preference)  # type: ignore[return-value]


def get_providers_for_platform() -> list[TelemetryProviderBase]:
    """Return a list of available native providers for the current OS.

    Each provider's available() is True. Used for optional multi-provider
    mode. On darwin returns at most [ESFProvider]; on linux [EBPFProvider];
    on win32 [ETWProvider].
    """
    providers: list[TelemetryProviderBase] = []
    if sys.platform == "darwin":
        try:
            from providers.esf_provider import ESFProvider

            p = ESFProvider()
            if p.available():
                providers.append(p)  # type: ignore[arg-type]
        except Exception as e:
            logger.debug("ESF provider not loadable: %s", e)
    elif sys.platform == "linux":
        try:
            from providers.ebpf_provider import EBPFProvider

            p = EBPFProvider()
            if p.available():
                providers.append(p)  # type: ignore[arg-type]
        except Exception as e:
            logger.debug("eBPF provider not loadable: %s", e)
    elif sys.platform == "win32":
        try:
            from providers.etw_provider import ETWProvider

            p = ETWProvider()
            if p.available():
                providers.append(p)  # type: ignore[arg-type]
        except Exception as e:
            logger.debug("ETW provider not loadable: %s", e)
    return providers


def start_providers(
    store: EventStore,
    providers: list[TelemetryProviderBase],
) -> None:
    """Start each provider with the same store.

    All providers push into the same EventStore. Caller is responsible for
    calling stop() on each provider when done. Orchestrator may use this
    for multi-provider mode in the future.
    """
    for p in providers:
        try:
            p.start(store)
            logger.debug("Started telemetry provider: %s", p.name)
        except Exception as e:
            logger.warning("Failed to start provider %s: %s", p.name, e)

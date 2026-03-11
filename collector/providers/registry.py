"""Provider negotiation and registry."""

from __future__ import annotations

from .base import TelemetryProvider
from .polling import PollingProvider


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

    if preference == "native":
        # No native providers exist yet
        raise RuntimeError("No native telemetry provider available on this platform")

    # preference == "auto": try native first, fall back to polling
    # No native providers exist yet, so always return polling
    return PollingProvider()

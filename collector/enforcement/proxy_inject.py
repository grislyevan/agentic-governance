"""Environment proxy injection for governed LLM traffic routing.

Forces ``HTTP_PROXY`` / ``HTTPS_PROXY`` environment variables so that
agentic tool traffic passes through an organizational proxy where it
can be inspected, rate-limited, or blocked.

This is the lowest-friction enforcement tactic — tools still work,
but their LLM API traffic is observable and governable.
"""

from __future__ import annotations

import logging
import os
import platform
import subprocess
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class ProxyConfig:
    http_proxy: str = ""
    https_proxy: str = ""
    no_proxy: str = "localhost,127.0.0.1,::1"


def inject_proxy_env(config: ProxyConfig) -> bool:
    """Set proxy environment variables for the current process and children.

    These are inherited by any child processes spawned by the collector,
    and can be picked up by tools that respect standard proxy env vars.
    """
    if config.http_proxy:
        os.environ["HTTP_PROXY"] = config.http_proxy
        os.environ["http_proxy"] = config.http_proxy
    if config.https_proxy:
        os.environ["HTTPS_PROXY"] = config.https_proxy
        os.environ["https_proxy"] = config.https_proxy
    if config.no_proxy:
        os.environ["NO_PROXY"] = config.no_proxy
        os.environ["no_proxy"] = config.no_proxy

    logger.info(
        "Proxy environment injected: HTTP=%s HTTPS=%s",
        config.http_proxy or "(none)",
        config.https_proxy or "(none)",
    )
    return True


def clear_proxy_env() -> None:
    """Remove proxy environment variables."""
    for var in ("HTTP_PROXY", "http_proxy", "HTTPS_PROXY", "https_proxy", "NO_PROXY", "no_proxy"):
        os.environ.pop(var, None)
    logger.info("Proxy environment cleared")


def configure_system_proxy_macos(config: ProxyConfig) -> bool:
    """Set the macOS system HTTP proxy via networksetup.

    WARNING: This is a system-wide change.  It affects ALL applications
    on the active network service (not just the target tool).  Use
    ``inject_proxy_env`` for scoped, process-level proxy injection
    when possible.

    Requires admin privileges.
    """
    if platform.system() != "Darwin":
        return False

    service = _get_active_network_service()
    if not service:
        logger.warning("Could not determine active network service")
        return False

    logger.warning(
        "Setting system-wide proxy on '%s'. This affects ALL "
        "applications using this network service, not just the "
        "target tool. Use inject_proxy_env() for scoped enforcement.",
        service,
    )

    success = True
    if config.https_proxy:
        host, port = _parse_proxy_url(config.https_proxy)
        if host:
            try:
                subprocess.run(
                    ["networksetup", "-setsecurewebproxy", service, host, str(port)],
                    capture_output=True, timeout=10, check=True,
                )
                logger.info("macOS secure web proxy set to %s:%d on %s", host, port, service)
            except (subprocess.CalledProcessError, subprocess.TimeoutExpired, FileNotFoundError) as exc:
                logger.warning("Failed to set macOS secure web proxy: %s", exc)
                success = False

    return success


def _get_active_network_service() -> str | None:
    try:
        result = subprocess.run(
            ["networksetup", "-listallnetworkservices"],
            capture_output=True, text=True, timeout=5,
        )
        if result.returncode == 0:
            for line in result.stdout.splitlines():
                line = line.strip()
                if line and not line.startswith("*") and not line.startswith("An asterisk"):
                    if "Wi-Fi" in line or "Ethernet" in line:
                        return line
    except (subprocess.TimeoutExpired, FileNotFoundError) as exc:
        logger.debug("Could not list network services via networksetup: %s", exc)
    return None


def _parse_proxy_url(url: str) -> tuple[str, int]:
    url = url.replace("http://", "").replace("https://", "")
    if ":" in url:
        parts = url.rsplit(":", 1)
        try:
            return parts[0], int(parts[1].rstrip("/"))
        except ValueError as exc:
            logger.debug("Could not parse proxy URL port from %s: %s", url, exc)
    return url.rstrip("/"), 8080

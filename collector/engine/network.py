"""Network outbound correlation engine.

Correlates running agentic tool PIDs with active outbound network
connections.  When a Class C/D tool has established connections to
destinations not in the allowlist, the risk profile is escalated.
"""

from __future__ import annotations

import ipaddress
import logging
import os
import socket
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

try:
    import psutil
except ImportError:
    psutil = None  # type: ignore[assignment]

logger = logging.getLogger(__name__)

DEFAULT_ALLOWLIST_PATH = Path(__file__).resolve().parent.parent / "config" / "network_allowlist.txt"


@dataclass
class ConnectionInfo:
    pid: int
    local_addr: str
    local_port: int
    remote_addr: str
    remote_port: int
    status: str
    remote_hostname: str | None = None


@dataclass
class NetworkCorrelation:
    """Result of correlating a tool's process(es) with network connections."""

    tool_name: str
    tool_class: str
    total_connections: int = 0
    unknown_connections: list[ConnectionInfo] = field(default_factory=list)
    allowed_connections: list[ConnectionInfo] = field(default_factory=list)
    risk_elevated: bool = False
    risk_reason: str = ""


def _load_allowlist(path: Path | None = None) -> set[str]:
    """Load network allowlist from a text file (one domain/IP per line)."""
    p = path or DEFAULT_ALLOWLIST_PATH
    entries: set[str] = set()
    if not p.exists():
        return entries
    try:
        for line in p.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#"):
                entries.add(line.lower())
    except OSError as exc:
        logger.warning("Cannot read allowlist %s: %s", p, exc)
    return entries


_allowlist_cache: set[str] | None = None


def get_allowlist(path: Path | None = None) -> set[str]:
    """Return cached allowlist, loading once from disk."""
    global _allowlist_cache
    if _allowlist_cache is None:
        _allowlist_cache = _load_allowlist(path)
    return _allowlist_cache


def reload_allowlist(path: Path | None = None) -> None:
    global _allowlist_cache
    _allowlist_cache = _load_allowlist(path)


def _is_private_ip(addr: str) -> bool:
    try:
        return ipaddress.ip_address(addr).is_private
    except ValueError:
        return False


def _resolve_hostname(addr: str) -> str | None:
    """Best-effort reverse DNS lookup, cached in-process."""
    try:
        hostname, _, _ = socket.gethostbyaddr(addr)
        return hostname.lower()
    except (socket.herror, socket.gaierror, OSError):
        return None


def _matches_allowlist(addr: str, hostname: str | None, allowlist: set[str]) -> bool:
    if addr.lower() in allowlist:
        return True
    if hostname and hostname in allowlist:
        return True
    if hostname:
        for entry in allowlist:
            if entry.startswith("*.") and hostname.endswith(entry[1:]):
                return True
    return False


def get_outbound_connections(pids: set[int] | None = None) -> list[ConnectionInfo]:
    """Return established outbound TCP connections, optionally filtered by PIDs."""
    if psutil is None:
        logger.warning("psutil not installed — network correlation unavailable")
        return []

    results: list[ConnectionInfo] = []
    try:
        for conn in psutil.net_connections(kind="tcp"):
            if conn.status != "ESTABLISHED":
                continue
            if conn.raddr is None:
                continue
            if pids is not None and conn.pid not in pids:
                continue
            if _is_private_ip(conn.raddr.ip):
                continue

            results.append(ConnectionInfo(
                pid=conn.pid or 0,
                local_addr=conn.laddr.ip if conn.laddr else "",
                local_port=conn.laddr.port if conn.laddr else 0,
                remote_addr=conn.raddr.ip,
                remote_port=conn.raddr.port,
                status=conn.status,
                remote_hostname=_resolve_hostname(conn.raddr.ip),
            ))
    except (psutil.AccessDenied, psutil.NoSuchProcess, OSError) as exc:
        logger.debug("Error reading connections: %s", exc)

    return results


def correlate_tool_connections(
    tool_name: str,
    tool_class: str,
    pids: set[int],
    allowlist_path: Path | None = None,
) -> NetworkCorrelation:
    """Match a tool's PIDs against outbound connections and the allowlist."""
    allowlist = get_allowlist(allowlist_path)
    connections = get_outbound_connections(pids)
    result = NetworkCorrelation(
        tool_name=tool_name,
        tool_class=tool_class,
        total_connections=len(connections),
    )

    for conn in connections:
        if _matches_allowlist(conn.remote_addr, conn.remote_hostname, allowlist):
            result.allowed_connections.append(conn)
        else:
            result.unknown_connections.append(conn)

    if result.unknown_connections:
        result.risk_elevated = True
        destinations = {
            c.remote_hostname or c.remote_addr for c in result.unknown_connections
        }
        result.risk_reason = (
            f"{tool_name} (Class {tool_class}) has {len(result.unknown_connections)} "
            f"outbound connection(s) to unknown destination(s): "
            f"{', '.join(sorted(destinations))}"
        )

    return result

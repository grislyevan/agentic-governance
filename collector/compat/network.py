"""Cross-platform network connection enumeration backed by psutil."""

from __future__ import annotations

import logging

import psutil

from .types import ConnectionInfo

logger = logging.getLogger(__name__)

_STATUS_MAP: dict[str, str] = {
    psutil.CONN_ESTABLISHED: "ESTABLISHED",
    psutil.CONN_SYN_SENT: "SYN_SENT",
    psutil.CONN_SYN_RECV: "SYN_RECV",
    psutil.CONN_FIN_WAIT1: "FIN_WAIT1",
    psutil.CONN_FIN_WAIT2: "FIN_WAIT2",
    psutil.CONN_TIME_WAIT: "TIME_WAIT",
    psutil.CONN_CLOSE: "CLOSE",
    psutil.CONN_CLOSE_WAIT: "CLOSE_WAIT",
    psutil.CONN_LAST_ACK: "LAST_ACK",
    psutil.CONN_LISTEN: "LISTEN",
    psutil.CONN_CLOSING: "CLOSING",
    psutil.CONN_NONE: "NONE",
}


def get_connections(
    pids: set[int] | None = None,
    port: int | None = None,
) -> list[ConnectionInfo]:
    """Return TCP connections, optionally filtered by PID set and/or port.

    Requires elevated privileges on most platforms for PID mapping.
    Falls back gracefully if access is denied (returns an empty list).
    """
    try:
        raw = psutil.net_connections(kind="tcp")
    except psutil.AccessDenied:
        logger.debug("net_connections: access denied (needs elevation)")
        return []

    results: list[ConnectionInfo] = []
    for conn in raw:
        if pids is not None and conn.pid not in pids:
            continue

        laddr = conn.laddr
        raddr = conn.raddr

        local_port = laddr.port if laddr else 0
        remote_port = raddr.port if raddr else None

        if port is not None and local_port != port and remote_port != port:
            continue

        results.append(ConnectionInfo(
            pid=conn.pid,
            local_addr=laddr.ip if laddr else "",
            local_port=local_port,
            remote_addr=raddr.ip if raddr else None,
            remote_port=remote_port,
            status=_STATUS_MAP.get(conn.status, conn.status),
        ))

    return results


def get_listeners(port: int | None = None) -> list[ConnectionInfo]:
    """Return listening TCP sockets, optionally filtered to a single port."""
    all_conns = get_connections(port=port)
    return [c for c in all_conns if c.status == "LISTEN"]

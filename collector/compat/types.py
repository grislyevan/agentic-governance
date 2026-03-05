"""Shared data types for the platform abstraction layer."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class ProcessInfo:
    """Snapshot of a single OS process."""

    pid: int
    name: str
    cmdline: str
    username: str | None = None
    ppid: int | None = None


@dataclass
class ConnectionInfo:
    """A single TCP/UDP network connection or listener."""

    pid: int | None
    local_addr: str
    local_port: int
    remote_addr: str | None = None
    remote_port: int | None = None
    status: str = ""  # LISTEN, ESTABLISHED, TIME_WAIT, etc.


@dataclass
class ServiceInfo:
    """Status of an OS-managed service/daemon."""

    name: str
    status: str  # running, stopped, not_found
    start_type: str = "unknown"  # auto, manual, disabled, unknown


@dataclass
class SignatureInfo:
    """Result of a code-signature verification."""

    signed: bool
    subject: str | None = None
    issuer: str | None = None


@dataclass
class ToolPaths:
    """Platform-specific filesystem paths for a detected tool."""

    install_dir: Path | None = None
    config_dir: Path | None = None
    data_dir: Path | None = None
    extensions_dir: Path | None = None
    log_dir: Path | None = None

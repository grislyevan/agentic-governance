"""macOS Endpoint Security Framework telemetry provider."""

from __future__ import annotations

import json
import logging
import os
import re
import platform
import shutil
import socket
import subprocess
import sys
import tempfile
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING

from telemetry.capabilities import TelemetryCapabilities

from .base import TelemetryProvider

if TYPE_CHECKING:
    from telemetry.event_store import EventStore

from telemetry.event_store import (
    FileChangeEvent,
    FileReadEvent,
    NetworkConnectEvent,
    ProcessExecEvent,
)

logger = logging.getLogger(__name__)

ESF_SOURCE = "esf"

# Path prefixes to filter out (noisy caches, temp, trash)
_NOISY_PATH_PREFIXES: tuple[str, ...] = (
    "/var/folders/",
    "/tmp/",
    "/private/var/folders/",
    "/Library/Caches/",
    "Caches/",
    ".Trash/",
    "/.Trash/",
    "/var/tmp/",
)

# O_RDONLY = 0, O_WRONLY = 1, O_RDWR = 2 (low bits of fflag)
_FFLAG_READ_ONLY = 0

# Batch file/file_read events before pushing to avoid flooding the store
_ESF_BATCH_SIZE = 20

# es_new_client_result_t numeric codes (macOS Endpoint Security)
ES_NEW_CLIENT_ERROR_CODES = {
    1: "internal error (Endpoint Security subsystem)",
    2: "invalid argument",
    3: "not entitled (missing com.apple.developer.endpoint-security.client entitlement)",
    4: "not permitted (TCC / Full Disk Access or approval required)",
    5: "not privileged (Endpoint Security requires root or SIP exception)",
    6: "too many clients (limit reached)",
}


def _parse_es_new_client_error(stderr_bytes: bytes) -> str | None:
    """Parse esf_helper stderr for 'es_new_client failed: N'; return human-readable message or None."""
    text = stderr_bytes.decode("utf-8", errors="replace")
    m = re.search(r"es_new_client failed:\s*(\d+)", text)
    if not m:
        return None
    code = int(m.group(1))
    if code in ES_NEW_CLIENT_ERROR_CODES:
        return f"macOS Endpoint Security: {ES_NEW_CLIENT_ERROR_CODES[code]}"
    return f"macOS Endpoint Security initialization failed (error code {code})"


def _find_esf_helper() -> str | None:
    """Locate esf_helper binary. Returns path or None."""
    candidates: list[Path] = []

    provider_dir = Path(__file__).resolve().parent
    candidates.append(provider_dir / "esf_helper" / "esf_helper")
    candidates.append(provider_dir / "esf_helper" / "esf_helper.exe")

    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        bundle_resources = Path(sys._MEIPASS) / "Resources"
        candidates.append(bundle_resources / "esf_helper")
    else:
        app_bundle = Path(__file__).resolve()
        for _ in range(6):
            app_bundle = app_bundle.parent
            if app_bundle.name.endswith(".app"):
                resources = app_bundle / "Contents" / "Resources"
                candidates.append(resources / "esf_helper")
                break

    for p in candidates:
        if p.is_file() and os.access(p, os.X_OK):
            return str(p)

    path_result = shutil.which("esf_helper")
    if path_result:
        return path_result

    return None


def _should_filter_path(path: str) -> bool:
    """Return True if path should be filtered (noisy temp/cache)."""
    if not path:
        return True
    normalized = path if path.startswith("/") else "/" + path
    for prefix in _NOISY_PATH_PREFIXES:
        if normalized.startswith(prefix) or path.startswith(prefix):
            return True
    if "/Caches/" in path or "/.Trash" in path:
        return True
    return False


def _macos_version_ok() -> bool:
    """Check macOS version >= 10.15."""
    if sys.platform != "darwin":
        return False
    try:
        ver = platform.mac_ver()[0]
        if not ver:
            return False
        parts = ver.split(".")
        major = int(parts[0]) if parts else 0
        minor = int(parts[1]) if len(parts) > 1 else 0
        return (major > 10) or (major == 10 and minor >= 15)
    except (ValueError, IndexError):
        return False


class ESFProvider(TelemetryProvider):
    """Telemetry provider using macOS Endpoint Security Framework."""

    @property
    def name(self) -> str:
        return "esf"

    @property
    def unavailable_reason(self) -> str:
        if sys.platform != "darwin":
            return f"ESF requires macOS, not {sys.platform}"
        if not _macos_version_ok():
            return "ESF requires macOS 10.15 or later"
        helper = _find_esf_helper()
        if not helper:
            return "esf_helper binary not found (build with: make -C collector/providers/esf_helper)"
        if not os.access(helper, os.X_OK):
            return f"esf_helper not executable: {helper}"
        return ""

    def available(self) -> bool:
        if sys.platform != "darwin":
            return False
        if not _macos_version_ok():
            return False
        helper = _find_esf_helper()
        return helper is not None and os.access(helper, os.X_OK)

    def capabilities(self) -> TelemetryCapabilities:
        return TelemetryCapabilities(
            has_process_exec=True,
            has_file_change=True,
            has_file_read=True,
            has_network_events=True,
            has_process_parent=True,
        )

    def __init__(self) -> None:
        self._store: EventStore | None = None
        self._proc: subprocess.Popen | None = None
        self._sock_path: str | None = None
        self._sock: socket.socket | None = None
        self._reader_thread: threading.Thread | None = None
        self._stop_event = threading.Event()
        self._file_batch: list[FileChangeEvent] = []
        self._read_batch: list[FileReadEvent] = []

    def _flush_file_batch(self) -> None:
        if not self._store:
            return
        for event in self._file_batch:
            self._store.push_file(event)
        self._file_batch.clear()

    def _flush_read_batch(self) -> None:
        if not self._store:
            return
        for event in self._read_batch:
            self._store.push_file_read(event)
        self._read_batch.clear()

    def start(self, store: EventStore) -> None:
        self._store = store
        helper = _find_esf_helper()
        if not helper:
            raise RuntimeError("esf_helper not found")

        fd, self._sock_path = tempfile.mkstemp(suffix=".sock", prefix="detec-esf-")
        os.close(fd)
        try:
            os.unlink(self._sock_path)
        except OSError:
            pass

        self._proc = subprocess.Popen(
            [helper, self._sock_path],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
        )

        for _ in range(50):
            if os.path.exists(self._sock_path):
                break
            self._proc.poll()
            if self._proc.returncode is not None:
                _, err = self._proc.communicate()
                explanation = _parse_es_new_client_error(err) if err else None
                if explanation:
                    raise RuntimeError(explanation)
                raise RuntimeError(
                    f"esf_helper exited {self._proc.returncode}: {err.decode(errors='replace')}"
                )
            threading.Event().wait(0.05)
        else:
            self._proc.terminate()
            raise RuntimeError("esf_helper did not create socket in time")

        self._sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        try:
            self._sock.settimeout(5.0)
            self._sock.connect(self._sock_path)
            self._sock.settimeout(None)
        except OSError as e:
            self._cleanup()
            raise RuntimeError(f"Failed to connect to esf_helper: {e}") from e

        self._stop_event.clear()
        self._reader_thread = threading.Thread(target=self._reader_loop, daemon=True)
        self._reader_thread.start()

    def _reader_loop(self) -> None:
        buf = b""
        while not self._stop_event.is_set() and self._sock and self._store:
            try:
                if self._proc and self._proc.poll() is not None:
                    logger.error(
                        "ESF helper exited unexpectedly (code=%s)",
                        self._proc.returncode,
                    )
                    break
                data = self._sock.recv(65536)
                if not data:
                    break
                buf += data
                while b"\n" in buf:
                    line, buf = buf.split(b"\n", 1)
                    line = line.strip()
                    if not line:
                        continue
                    self._process_line(line.decode("utf-8", errors="replace"))
            except (ConnectionResetError, BrokenPipeError, OSError) as e:
                logger.warning("ESF reader loop: %s", e)
                break
            except Exception:
                logger.debug("ESF reader loop error", exc_info=True)

    def _process_line(self, line: str) -> None:
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            logger.debug("ESF malformed JSON: %r", line[:200])
            return

        if not isinstance(obj, dict):
            return

        t = obj.get("type")
        if not t:
            return

        ts_str = obj.get("timestamp", "")
        try:
            ts = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
            if ts.tzinfo is None:
                ts = ts.replace(tzinfo=timezone.utc)
        except (ValueError, TypeError):
            ts = datetime.now(timezone.utc)

        if t == "exec":
            self._flush_file_batch()
            self._flush_read_batch()
            self._store.push_process(
                ProcessExecEvent(
                    timestamp=ts,
                    pid=int(obj.get("pid", 0)),
                    ppid=int(obj.get("ppid", 0)),
                    name=str(obj.get("name", "")),
                    cmdline=str(obj.get("cmdline", "")),
                    username=str(obj.get("username")) or None,
                    binary_path=str(obj.get("binary_path")) or None,
                    source=ESF_SOURCE,
                )
            )
        elif t == "open":
            path = str(obj.get("path", ""))
            if _should_filter_path(path):
                return
            fflag = obj.get("flags", 0)
            pid_val = int(obj.get("pid", 0)) or None
            process_name = str(obj.get("process_name", "")) or None
            if (fflag & 0x3) == _FFLAG_READ_ONLY:
                self._read_batch.append(
                    FileReadEvent(
                        timestamp=ts,
                        path=path,
                        pid=pid_val,
                        process_name=process_name,
                        source=ESF_SOURCE,
                    )
                )
                if len(self._read_batch) >= _ESF_BATCH_SIZE:
                    self._flush_read_batch()
            else:
                action = "modified" if (fflag & 0x3) else "created"
                self._file_batch.append(
                    FileChangeEvent(
                        timestamp=ts,
                        path=path,
                        action=action,
                        pid=pid_val,
                        process_name=process_name,
                        source=ESF_SOURCE,
                    )
                )
                if len(self._file_batch) >= _ESF_BATCH_SIZE:
                    self._flush_file_batch()
        elif t == "uipc_connect":
            # Unix-domain socket IPC (ES_EVENT_TYPE_NOTIFY_UIPC_CONNECT).
            # Emitted as a NetworkConnectEvent with the socket path as remote_addr
            # and protocol="unix" so consumers can distinguish IPC from TCP/UDP.
            socket_path = str(obj.get("socket_path", ""))
            self._store.push_network(
                NetworkConnectEvent(
                    timestamp=ts,
                    pid=int(obj.get("pid", 0)),
                    process_name=str(obj.get("process_name", "")),
                    remote_addr=socket_path,
                    remote_port=0,
                    local_port=0,
                    protocol="unix",
                    sni=None,
                    source=ESF_SOURCE,
                )
            )

    def stop(self) -> None:
        self._stop_event.set()
        self._cleanup()

    def _cleanup(self) -> None:
        self._flush_file_batch()
        self._flush_read_batch()
        if self._proc:
            try:
                self._proc.terminate()
                self._proc.wait(timeout=3)
            except (subprocess.TimeoutExpired, ProcessLookupError):
                try:
                    self._proc.kill()
                except ProcessLookupError:
                    pass
            self._proc = None

        if self._sock:
            try:
                self._sock.close()
            except OSError:
                pass
            self._sock = None

        if self._sock_path:
            try:
                os.unlink(self._sock_path)
            except OSError:
                pass
            self._sock_path = None

        if self._reader_thread:
            self._reader_thread.join(timeout=2.0)
            self._reader_thread = None

        self._file_batch.clear()
        self._read_batch.clear()
        self._store = None

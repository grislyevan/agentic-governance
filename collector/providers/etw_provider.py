"""Windows ETW telemetry provider."""

from __future__ import annotations

import logging
import sys
import threading
import uuid
from datetime import datetime, timezone
from typing import TYPE_CHECKING

from telemetry.event_store import (
    FileChangeEvent,
    NetworkConnectEvent,
    ProcessExecEvent,
)

from .base import TelemetryProvider

if TYPE_CHECKING:
    from telemetry.event_store import EventStore

logger = logging.getLogger(__name__)

# Provider GUIDs (Microsoft-Windows-Kernel-*)
_GUID_KERNEL_PROCESS = "{22FB2CD6-0E7B-422B-A0C7-2FAD1FD0E716}"
_GUID_KERNEL_NETWORK = "{7DD42A49-5329-4832-8DFD-43D979153A88}"
_GUID_KERNEL_FILE = "{EDD08927-9CC4-4E65-B970-C2560FB5C289}"

_SESSION_NAME = "DetecETW"
_SOURCE = "etw"


def _is_admin() -> bool:
    if sys.platform != "win32":
        return False
    try:
        import ctypes
        return ctypes.windll.shell32.IsUserAnAdmin() != 0
    except (AttributeError, OSError):
        return False


def _check_ctypes_etw() -> bool:
    """Verify ctypes can access ETW APIs (advapi32)."""
    if sys.platform != "win32":
        return False
    try:
        import ctypes
        _ = ctypes.windll.advapi32
        return True
    except (AttributeError, OSError):
        return False


def _check_pywintrace() -> bool:
    """Check if pywintrace is importable."""
    try:
        import etw
        return hasattr(etw, "ETW") and hasattr(etw, "ProviderInfo")
    except ImportError:
        return False


def _parse_event_pywintrace(
    store: EventStore,
    event_tuple: tuple[int, dict],
) -> None:
    """Map pywintrace callback (event_id, out) to EventStore types."""
    event_id, out = event_tuple
    ts = datetime.now(timezone.utc)

    if "ProcessId" in out and "ParentId" in out:
        store.push_process(
            ProcessExecEvent(
                timestamp=ts,
                pid=int(out.get("ProcessId") or 0),
                ppid=int(out.get("ParentId") or 0),
                name=str(out.get("ImageFileName") or "").strip() or "unknown",
                cmdline=str(out.get("CommandLine") or ""),
                username=None,
                binary_path=str(out.get("ImageFileName") or "").strip() or None,
                source=_SOURCE,
            )
        )
        return

    if "daddr" in out or "saddr" in out or "RemoteAddr" in out:
        daddr = out.get("daddr") or out.get("RemoteAddr") or ""
        sport = int(out.get("sport") or out.get("LocalPort") or 0)
        dport = int(out.get("dport") or out.get("RemotePort") or 0)
        pid = int(out.get("PID") or out.get("ProcessId") or 0)
        pname = str(out.get("ProcessName") or "")
        if isinstance(daddr, bytes):
            try:
                daddr = daddr.decode("utf-8", errors="replace")
            except Exception:
                daddr = str(daddr)
        store.push_network(
            NetworkConnectEvent(
                timestamp=ts,
                pid=pid,
                process_name=pname,
                remote_addr=str(daddr),
                remote_port=dport,
                local_port=sport,
                protocol="tcp",
                sni=None,
                source=_SOURCE,
            )
        )
        return

    if "FileName" in out or "FileObject" in out:
        path = str(out.get("FileName") or out.get("FileKey") or "")
        if path:
            action = "created" if event_id == 12 else "modified"
            store.push_file(
                FileChangeEvent(
                    timestamp=ts,
                    path=path,
                    action=action,
                    pid=int(out.get("PID") or out.get("ProcessId") or 0) or None,
                    process_name=str(out.get("ProcessName") or "") or None,
                    source=_SOURCE,
                )
            )


class ETWProvider(TelemetryProvider):
    """Windows ETW telemetry provider."""

    def __init__(self) -> None:
        self._store: EventStore | None = None
        self._unavailable_reason: str = ""
        self._etw: object | None = None
        self._thread: threading.Thread | None = None
        self._stop_event: threading.Event | None = None

    @property
    def name(self) -> str:
        return "etw"

    @property
    def unavailable_reason(self) -> str:
        return self._unavailable_reason

    def available(self) -> bool:
        if sys.platform != "win32":
            self._unavailable_reason = "ETW is Windows only"
            return False
        if not _is_admin():
            self._unavailable_reason = "Administrator privileges required"
            return False
        if _check_pywintrace():
            self._unavailable_reason = ""
            return True
        if _check_ctypes_etw():
            self._unavailable_reason = ""
            return True
        self._unavailable_reason = "pywintrace or ctypes ETW APIs required"
        return False

    def start(self, store: EventStore) -> None:
        self._store = store
        if _check_pywintrace():
            self._start_pywintrace()
        else:
            self._start_ctypes()

    def _start_pywintrace(self) -> None:
        import etw

        def callback(event_tuple: tuple[int, dict]) -> None:
            if self._store is None:
                return
            try:
                _parse_event_pywintrace(self._store, event_tuple)
            except Exception as e:
                logger.debug("ETW callback error: %s", e)

        providers = [
            etw.ProviderInfo("Kernel-Process", etw.GUID(_GUID_KERNEL_PROCESS)),
            etw.ProviderInfo("Kernel-Network", etw.GUID(_GUID_KERNEL_NETWORK)),
            etw.ProviderInfo("Kernel-File", etw.GUID(_GUID_KERNEL_FILE)),
        ]
        session_name = f"{_SESSION_NAME}-{uuid.uuid4().hex[:8]}"
        self._etw = etw.ETW(
            providers=providers,
            event_callback=callback,
            session_name=session_name,
        )
        self._etw.start()

    def _start_ctypes(self) -> None:
        self._stop_event = threading.Event()
        self._thread = threading.Thread(
            target=self._run_ctypes_session,
            daemon=True,
        )
        self._thread.start()

    def _run_ctypes_session(self) -> None:
        if sys.platform != "win32" or self._store is None:
            return
        try:
            from ._etw_ctypes import run_etw_session
            run_etw_session(
                store=self._store,
                stop_event=self._stop_event,
                source=_SOURCE,
            )
        except ImportError as e:
            logger.warning("ETW ctypes backend unavailable: %s", e)
        except Exception as e:
            logger.debug("ETW session error: %s", e)

    def stop(self) -> None:
        if self._etw is not None:
            try:
                self._etw.stop()
            except Exception as e:
                logger.debug("ETW stop error: %s", e)
            self._etw = None
        if self._stop_event is not None:
            self._stop_event.set()
        if self._thread is not None:
            self._thread.join(timeout=5.0)
            self._thread = None
        self._store = None

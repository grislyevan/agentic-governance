"""Windows ETW ctypes backend for DetecETW provider.

Implements ``run_etw_session`` using advapi32 StartTraceW / OpenTraceW /
ProcessTrace / StopTrace / CloseTrace.  This module is Windows-only and
raises ImportError on any other platform.

Only stdlib is used (ctypes, struct, threading, logging, uuid, datetime).
"""

from __future__ import annotations

import sys

if sys.platform != "win32":
    raise ImportError("_etw_ctypes is Windows-only")

import ctypes
import ctypes.wintypes
import logging
import struct
import threading
import uuid
from datetime import datetime, timezone
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from telemetry.event_store import EventStore

__all__ = ["run_etw_session"]

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Windows / ETW constants
# ---------------------------------------------------------------------------

# Event trace flags
EVENT_TRACE_REAL_TIME_MODE = 0x00000100
WNODE_FLAG_TRACED_GUID = 0x00020000
EVENT_TRACE_CONTROL_STOP = 1

# Process in real-time (no log file)
PROCESS_TRACE_MODE_REAL_TIME = 0x00000100
PROCESS_TRACE_MODE_EVENT_RECORD = 0x10000000

# winerror
ERROR_SUCCESS = 0
ERROR_ALREADY_EXISTS = 183

# Kernel logger session name (for kernel providers we need the NT kernel logger
# OR we use a private session with non-kernel providers).  We use a private
# session name and route through EnableTraceEx2.
_KERNEL_LOGGER_NAME = "NT Kernel Logger"

# Opcodes we care about
_OPCODE_PROCESS_START = 1
_OPCODE_NETWORK_CONNECT = 12
_OPCODE_FILE_CREATE = 64

# Provider GUIDs (binary form: little-endian Data1/Data2/Data3, big-endian Data4)
_GUID_KERNEL_PROCESS_STR = "22FB2CD6-0E7B-422B-A0C7-2FAD1FD0E716"
_GUID_KERNEL_NETWORK_STR = "7DD42A49-5329-4832-8DFD-43D979153A88"
_GUID_KERNEL_FILE_STR = "EDD08927-9CC4-4E65-B970-C2560FB5C289"


# ---------------------------------------------------------------------------
# GUID helpers
# ---------------------------------------------------------------------------


class GUID(ctypes.Structure):
    """Windows GUID structure."""

    _fields_ = [
        ("Data1", ctypes.wintypes.DWORD),
        ("Data2", ctypes.wintypes.WORD),
        ("Data3", ctypes.wintypes.WORD),
        ("Data4", ctypes.c_ubyte * 8),
    ]

    @classmethod
    def from_str(cls, guid_str: str) -> "GUID":
        """Parse a ``{XXXXXXXX-XXXX-XXXX-XXXX-XXXXXXXXXXXX}`` string."""
        s = guid_str.strip("{}")
        parts = s.split("-")
        if len(parts) != 5:
            raise ValueError(f"Bad GUID: {guid_str!r}")
        d1 = int(parts[0], 16)
        d2 = int(parts[1], 16)
        d3 = int(parts[2], 16)
        d4_bytes = bytes.fromhex(parts[3] + parts[4])
        g = cls()
        g.Data1 = d1
        g.Data2 = d2
        g.Data3 = d3
        for i, b in enumerate(d4_bytes):
            g.Data4[i] = b
        return g

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, GUID):
            return NotImplemented
        return (
            self.Data1 == other.Data1
            and self.Data2 == other.Data2
            and self.Data3 == other.Data3
            and bytes(self.Data4) == bytes(other.Data4)
        )

    def __repr__(self) -> str:  # pragma: no cover
        d4 = bytes(self.Data4)
        return (
            f"{{{self.Data1:08X}-{self.Data2:04X}-{self.Data3:04X}-"
            f"{d4[:2].hex().upper()}-{d4[2:].hex().upper()}}}"
        )


# Pre-built GUID instances for the three kernel providers.
_GUID_PROCESS = GUID.from_str(_GUID_KERNEL_PROCESS_STR)
_GUID_NETWORK = GUID.from_str(_GUID_KERNEL_NETWORK_STR)
_GUID_FILE = GUID.from_str(_GUID_KERNEL_FILE_STR)


# ---------------------------------------------------------------------------
# ETW structures (ctypes)
# ---------------------------------------------------------------------------


class WNODE_HEADER(ctypes.Structure):
    """WNODE_HEADER — the first field of EVENT_TRACE_PROPERTIES."""

    _fields_ = [
        ("BufferSize", ctypes.wintypes.ULONG),
        ("ProviderId", ctypes.wintypes.ULONG),
        ("HistoricalContext", ctypes.c_uint64),
        ("TimeStamp", ctypes.c_int64),
        ("Guid", GUID),
        ("ClientContext", ctypes.wintypes.ULONG),
        ("Flags", ctypes.wintypes.ULONG),
    ]


# We allocate EVENT_TRACE_PROPERTIES with extra space for the session name
# string that immediately follows the struct in memory.
_SESSION_NAME_MAX = 256  # characters


class EVENT_TRACE_PROPERTIES(ctypes.Structure):
    """EVENT_TRACE_PROPERTIES structure followed by the session name buffer."""

    _fields_ = [
        ("Wnode", WNODE_HEADER),
        ("BufferSize", ctypes.wintypes.ULONG),
        ("MinimumBuffers", ctypes.wintypes.ULONG),
        ("MaximumBuffers", ctypes.wintypes.ULONG),
        ("MaximumFileSize", ctypes.wintypes.ULONG),
        ("LogFileMode", ctypes.wintypes.ULONG),
        ("FlushTimer", ctypes.wintypes.ULONG),
        ("EnableFlags", ctypes.wintypes.ULONG),
        ("AgeLimit", ctypes.c_long),
        ("NumberOfBuffers", ctypes.wintypes.ULONG),
        ("FreeBuffers", ctypes.wintypes.ULONG),
        ("EventsLost", ctypes.wintypes.ULONG),
        ("BuffersWritten", ctypes.wintypes.ULONG),
        ("LogBuffersLost", ctypes.wintypes.ULONG),
        ("RealTimeBuffersLost", ctypes.wintypes.ULONG),
        ("LoggerThreadId", ctypes.wintypes.HANDLE),
        ("LogFileNameOffset", ctypes.wintypes.ULONG),
        ("LoggerNameOffset", ctypes.wintypes.ULONG),
        # Name buffer immediately follows — we append it in the allocating helper.
    ]


def _alloc_properties(session_name: str) -> ctypes.Array:
    """Allocate an EVENT_TRACE_PROPERTIES buffer with the name appended."""
    # The actual buffer passed to ETW APIs must be large enough to hold the
    # struct PLUS the session-name string (UTF-16LE) starting at LoggerNameOffset.
    name_bytes = (session_name + "\0").encode("utf-16-le")
    extra = len(name_bytes)
    buf_size = ctypes.sizeof(EVENT_TRACE_PROPERTIES) + extra

    buf = (ctypes.c_byte * buf_size)()
    props = ctypes.cast(buf, ctypes.POINTER(EVENT_TRACE_PROPERTIES)).contents

    props.Wnode.BufferSize = buf_size
    props.Wnode.Flags = WNODE_FLAG_TRACED_GUID
    props.LogFileMode = EVENT_TRACE_REAL_TIME_MODE
    props.LoggerNameOffset = ctypes.sizeof(EVENT_TRACE_PROPERTIES)

    # Write the session name string into the tail of the buffer.
    name_offset = ctypes.sizeof(EVENT_TRACE_PROPERTIES)
    ctypes.memmove(ctypes.addressof(buf) + name_offset, name_bytes, len(name_bytes))

    return buf


# ---------------------------------------------------------------------------
# EVENT_RECORD structures (simplified)
# ---------------------------------------------------------------------------


class EVENT_DESCRIPTOR(ctypes.Structure):
    _fields_ = [
        ("Id", ctypes.wintypes.USHORT),
        ("Version", ctypes.c_ubyte),
        ("Channel", ctypes.c_ubyte),
        ("Level", ctypes.c_ubyte),
        ("Opcode", ctypes.c_ubyte),
        ("Task", ctypes.wintypes.USHORT),
        ("Keyword", ctypes.c_uint64),
    ]


class EVENT_HEADER(ctypes.Structure):
    _fields_ = [
        ("Size", ctypes.wintypes.USHORT),
        ("HeaderType", ctypes.wintypes.USHORT),
        ("Flags", ctypes.wintypes.USHORT),
        ("EventProperty", ctypes.wintypes.USHORT),
        ("ThreadId", ctypes.wintypes.ULONG),
        ("ProcessId", ctypes.wintypes.ULONG),
        ("TimeStamp", ctypes.c_int64),
        ("ProviderId", GUID),
        ("EventDescriptor", EVENT_DESCRIPTOR),
        ("KernelTime", ctypes.wintypes.ULONG),
        ("UserTime", ctypes.wintypes.ULONG),
        ("ActivityId", GUID),
    ]


class ETW_BUFFER_CONTEXT(ctypes.Structure):
    _fields_ = [
        ("ProcessorNumber", ctypes.c_ubyte),
        ("Alignment", ctypes.c_ubyte),
        ("LoggerId", ctypes.wintypes.USHORT),
    ]


class EVENT_RECORD(ctypes.Structure):
    _fields_ = [
        ("EventHeader", EVENT_HEADER),
        ("BufferContext", ETW_BUFFER_CONTEXT),
        ("ExtendedDataCount", ctypes.wintypes.USHORT),
        ("UserDataLength", ctypes.wintypes.USHORT),
        ("ExtendedData", ctypes.c_void_p),
        ("UserData", ctypes.c_void_p),
        ("UserContext", ctypes.c_void_p),
    ]


# ---------------------------------------------------------------------------
# EVENT_TRACE_LOGFILEW (for OpenTraceW)
# ---------------------------------------------------------------------------

# Forward-declare the callback type.
EVENT_RECORD_CALLBACK = ctypes.WINFUNCTYPE(None, ctypes.POINTER(EVENT_RECORD))


class EVENT_TRACE_LOGFILEW(ctypes.Structure):
    """EVENT_TRACE_LOGFILE structure (simplified — real-time mode fields only)."""

    _fields_ = [
        ("LogFileName", ctypes.c_wchar_p),
        ("LoggerName", ctypes.c_wchar_p),
        ("CurrentTime", ctypes.c_int64),
        ("BuffersRead", ctypes.wintypes.ULONG),
        ("ProcessTraceMode", ctypes.wintypes.ULONG),
        ("CurrentEvent", EVENT_RECORD),
        ("LogfileHeader", ctypes.c_byte * 304),  # TRACE_LOGFILE_HEADER (approx)
        ("BufferCallback", ctypes.c_void_p),
        ("BufferSize", ctypes.wintypes.ULONG),
        ("Filled", ctypes.wintypes.ULONG),
        ("EventsLost", ctypes.wintypes.ULONG),
        ("EventRecordCallback", EVENT_RECORD_CALLBACK),
        ("IsKernelTrace", ctypes.wintypes.ULONG),
        ("Context", ctypes.c_void_p),
    ]


# ---------------------------------------------------------------------------
# advapi32 bindings
# ---------------------------------------------------------------------------

_advapi32 = ctypes.windll.advapi32  # type: ignore[attr-defined]

# TRACEHANDLE is ULONG64 on both 32/64-bit
TRACEHANDLE = ctypes.c_uint64
INVALID_PROCESSTRACE_HANDLE = ctypes.c_uint64(0xFFFFFFFFFFFFFFFF).value

# StartTraceW(pSessionHandle, SessionName, Properties)
_advapi32.StartTraceW.restype = ctypes.wintypes.ULONG
_advapi32.StartTraceW.argtypes = [
    ctypes.POINTER(TRACEHANDLE),
    ctypes.c_wchar_p,
    ctypes.c_void_p,
]

# ControlTraceW(TraceHandle, InstanceName, Properties, ControlCode)
_advapi32.ControlTraceW.restype = ctypes.wintypes.ULONG
_advapi32.ControlTraceW.argtypes = [
    TRACEHANDLE,
    ctypes.c_wchar_p,
    ctypes.c_void_p,
    ctypes.wintypes.ULONG,
]

# EnableTraceEx2(TraceHandle, ProviderId, ControlCode, Level, MatchAnyKeyword,
#                MatchAllKeyword, Timeout, EnableParameters)
_advapi32.EnableTraceEx2.restype = ctypes.wintypes.ULONG
_advapi32.EnableTraceEx2.argtypes = [
    TRACEHANDLE,
    ctypes.POINTER(GUID),
    ctypes.wintypes.ULONG,
    ctypes.c_ubyte,
    ctypes.c_uint64,
    ctypes.c_uint64,
    ctypes.wintypes.ULONG,
    ctypes.c_void_p,
]

# OpenTraceW(Logfile)
_advapi32.OpenTraceW.restype = TRACEHANDLE
_advapi32.OpenTraceW.argtypes = [ctypes.POINTER(EVENT_TRACE_LOGFILEW)]

# ProcessTrace(HandleArray, HandleCount, StartTime, EndTime)
_advapi32.ProcessTrace.restype = ctypes.wintypes.ULONG
_advapi32.ProcessTrace.argtypes = [
    ctypes.POINTER(TRACEHANDLE),
    ctypes.wintypes.ULONG,
    ctypes.c_void_p,
    ctypes.c_void_p,
]

# CloseTrace(TraceHandle)
_advapi32.CloseTrace.restype = ctypes.wintypes.ULONG
_advapi32.CloseTrace.argtypes = [TRACEHANDLE]

# EVENT_ENABLE_PROPERTY values
_EVENT_CONTROL_CODE_ENABLE_PROVIDER = 1
_TRACE_LEVEL_VERBOSE = 5


# ---------------------------------------------------------------------------
# UserData parsers (best-effort, skip on any error)
# ---------------------------------------------------------------------------


def _parse_process_userdata(
    user_data_ptr: int,
    data_len: int,
) -> tuple[str, int]:
    """Extract (process_name, ppid) from a Kernel-Process/Start UserData blob.

    Layout (approximate, documented in ETW provider manifest):
      ULONG  UniqueProcessId
      ULONG  ParentId
      ...variable-length image name (WCHAR) near end...

    Returns (name, ppid) or ("unknown", 0) on parse failure.
    """
    try:
        if user_data_ptr == 0 or data_len < 8:
            return "unknown", 0
        raw = (ctypes.c_byte * data_len).from_address(user_data_ptr)
        blob = bytes(raw)
        ppid = struct.unpack_from("<I", blob, 4)[0]
        # Image name tends to be a null-terminated WCHAR string near the end;
        # try to decode from offset 16 onward.
        name = "unknown"
        if data_len > 16:
            try:
                name_raw = blob[16:]
                name = (
                    name_raw.decode("utf-16-le", errors="ignore")
                    .split("\x00")[0]
                    .strip()
                )
                if not name:
                    name = "unknown"
            except Exception:
                name = "unknown"
        return name, ppid
    except Exception:
        return "unknown", 0


def _parse_network_userdata(
    user_data_ptr: int,
    data_len: int,
) -> tuple[str, int, int]:
    """Extract (remote_addr, remote_port, local_port) from Kernel-Network UserData.

    Approximate layout for TCPv4/connect events:
      ULONG  PID
      ULONG  size
      USHORT sport
      USHORT dport
      ULONG  saddr (IPv4 big-endian)
      ULONG  daddr (IPv4 big-endian)

    Returns ("", 0, 0) on parse failure.
    """
    try:
        if user_data_ptr == 0 or data_len < 20:
            return "", 0, 0
        raw = (ctypes.c_byte * data_len).from_address(user_data_ptr)
        blob = bytes(raw)
        sport = struct.unpack_from(">H", blob, 8)[0]
        dport = struct.unpack_from(">H", blob, 10)[0]
        daddr_int = struct.unpack_from(">I", blob, 16)[0]
        daddr = (
            f"{(daddr_int >> 24) & 0xFF}."
            f"{(daddr_int >> 16) & 0xFF}."
            f"{(daddr_int >> 8) & 0xFF}."
            f"{daddr_int & 0xFF}"
        )
        return daddr, dport, sport
    except Exception:
        return "", 0, 0


def _parse_file_userdata(
    user_data_ptr: int,
    data_len: int,
) -> str:
    """Extract file path from Kernel-File/Create UserData (WCHAR path).

    Returns "" on parse failure.
    """
    try:
        if user_data_ptr == 0 or data_len < 4:
            return ""
        raw = (ctypes.c_byte * data_len).from_address(user_data_ptr)
        blob = bytes(raw)
        # Skip first 4 bytes (IrpPtr / TTID), rest is WCHAR path
        path = blob[4:].decode("utf-16-le", errors="ignore").split("\x00")[0].strip()
        return path
    except Exception:
        return ""


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------


def run_etw_session(
    store: "EventStore",
    stop_event: threading.Event,
    source: str,
) -> None:
    """Consume ETW kernel events via ctypes advapi32 APIs.

    Blocks until stop_event is set.
    Emits ProcessExecEvent, NetworkConnectEvent, FileChangeEvent into store.
    """
    # Import event types here to avoid circular imports at module level.
    try:
        from telemetry.event_store import (
            FileChangeEvent,
            NetworkConnectEvent,
            ProcessExecEvent,
        )
    except ImportError as exc:  # pragma: no cover
        logger.warning("ETW ctypes: cannot import event types: %s", exc)
        return

    session_name = f"DetecETW-{uuid.uuid4().hex[:8]}"
    trace_handle = TRACEHANDLE(0)
    consumer_handle = TRACEHANDLE(INVALID_PROCESSTRACE_HANDLE)

    # --- Build callback -------------------------------------------------------

    def _event_callback(record_ptr: ctypes.POINTER(EVENT_RECORD)) -> None:  # type: ignore[valid-type]
        try:
            if not record_ptr:
                return
            rec = record_ptr.contents
            provider_guid = rec.EventHeader.ProviderId
            opcode = rec.EventHeader.EventDescriptor.Opcode
            pid = int(rec.EventHeader.ProcessId)
            ts = datetime.now(timezone.utc)
            user_data_ptr = rec.UserData or 0
            data_len = int(rec.UserDataLength)

            if provider_guid == _GUID_PROCESS and opcode == _OPCODE_PROCESS_START:
                name, ppid = _parse_process_userdata(user_data_ptr, data_len)
                store.push_process(
                    ProcessExecEvent(
                        timestamp=ts,
                        pid=pid,
                        ppid=ppid,
                        name=name if name else str(pid),
                        cmdline="",
                        username=None,
                        binary_path=None,
                        source=source,
                    )
                )

            elif provider_guid == _GUID_NETWORK and opcode == _OPCODE_NETWORK_CONNECT:
                remote_addr, remote_port, local_port = _parse_network_userdata(
                    user_data_ptr, data_len
                )
                if remote_addr:
                    store.push_network(
                        NetworkConnectEvent(
                            timestamp=ts,
                            pid=pid,
                            process_name=str(pid),
                            remote_addr=remote_addr,
                            remote_port=remote_port,
                            local_port=local_port,
                            protocol="tcp",
                            sni=None,
                            source=source,
                        )
                    )

            elif provider_guid == _GUID_FILE and opcode == _OPCODE_FILE_CREATE:
                path = _parse_file_userdata(user_data_ptr, data_len)
                if path:
                    store.push_file(
                        FileChangeEvent(
                            timestamp=ts,
                            path=path,
                            action="created",
                            pid=pid,
                            process_name=str(pid),
                            source=source,
                        )
                    )

        except Exception as exc:
            logger.debug("ETW event callback error: %s", exc)

    cb_func = EVENT_RECORD_CALLBACK(_event_callback)

    # --- Start trace session --------------------------------------------------

    try:
        props_buf = _alloc_properties(session_name)
        rc = _advapi32.StartTraceW(
            ctypes.byref(trace_handle),
            session_name,
            props_buf,
        )
        if rc == ERROR_ALREADY_EXISTS:
            # Stop the existing session and retry once.
            _advapi32.ControlTraceW(
                TRACEHANDLE(0),
                session_name,
                props_buf,
                EVENT_TRACE_CONTROL_STOP,
            )
            props_buf = _alloc_properties(session_name)
            rc = _advapi32.StartTraceW(
                ctypes.byref(trace_handle),
                session_name,
                props_buf,
            )
        if rc != ERROR_SUCCESS:
            logger.warning(
                "ETW StartTraceW failed (rc=%d); ctypes backend inactive.", rc
            )
            return
    except Exception as exc:
        logger.warning("ETW StartTraceW exception: %s", exc)
        return

    # --- Enable providers -----------------------------------------------------

    try:
        for guid_obj in (_GUID_PROCESS, _GUID_NETWORK, _GUID_FILE):
            _advapi32.EnableTraceEx2(
                trace_handle,
                ctypes.byref(guid_obj),
                _EVENT_CONTROL_CODE_ENABLE_PROVIDER,
                _TRACE_LEVEL_VERBOSE,
                ctypes.c_uint64(0xFFFFFFFFFFFFFFFF),  # match any keyword
                ctypes.c_uint64(0),
                0,
                None,
            )
    except Exception as exc:
        logger.warning("ETW EnableTraceEx2 exception: %s", exc)
        # Non-fatal; we may still receive some events.

    # --- Open consumer --------------------------------------------------------

    try:
        logfile = EVENT_TRACE_LOGFILEW()
        logfile.LoggerName = session_name
        logfile.ProcessTraceMode = (
            PROCESS_TRACE_MODE_REAL_TIME | PROCESS_TRACE_MODE_EVENT_RECORD
        )
        logfile.EventRecordCallback = cb_func

        consumer_handle_val = _advapi32.OpenTraceW(ctypes.byref(logfile))
        if consumer_handle_val == INVALID_PROCESSTRACE_HANDLE:
            logger.warning(
                "ETW OpenTraceW returned invalid handle; ctypes backend inactive."
            )
            _stop_trace(trace_handle, session_name)
            return
        consumer_handle = TRACEHANDLE(consumer_handle_val)
    except Exception as exc:
        logger.warning("ETW OpenTraceW exception: %s", exc)
        _stop_trace(trace_handle, session_name)
        return

    # --- ProcessTrace in background thread ------------------------------------

    process_error: list[int] = []

    def _process_thread() -> None:
        try:
            handle_arr = (TRACEHANDLE * 1)(consumer_handle)
            rc = _advapi32.ProcessTrace(handle_arr, 1, None, None)
            process_error.append(rc)
        except Exception as exc:
            logger.debug("ETW ProcessTrace thread exception: %s", exc)

    pt_thread = threading.Thread(
        target=_process_thread, daemon=True, name="DetecETW-consume"
    )
    pt_thread.start()

    # --- Poll stop_event ------------------------------------------------------

    try:
        while not stop_event.wait(timeout=1.0):
            pass
    finally:
        # Tear down: CloseTrace first (unblocks ProcessTrace), then StopTrace.
        try:
            _advapi32.CloseTrace(consumer_handle)
        except Exception as exc:
            logger.debug("ETW CloseTrace exception: %s", exc)

        pt_thread.join(timeout=5.0)

        _stop_trace(trace_handle, session_name)

    logger.debug("ETW ctypes session stopped.")


# ---------------------------------------------------------------------------
# Internal helper
# ---------------------------------------------------------------------------


def _stop_trace(trace_handle: TRACEHANDLE, session_name: str) -> None:
    """Send STOP control to the named session, ignoring errors."""
    try:
        props_buf = _alloc_properties(session_name)
        _advapi32.ControlTraceW(
            trace_handle,
            session_name,
            props_buf,
            EVENT_TRACE_CONTROL_STOP,
        )
    except Exception as exc:
        logger.debug("ETW ControlTraceW(STOP) exception: %s", exc)

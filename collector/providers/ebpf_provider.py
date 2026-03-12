"""Linux eBPF telemetry provider using BCC."""

from __future__ import annotations

import logging
import os
import platform
import sys
import threading
from datetime import datetime, timezone
from socket import AF_INET, AF_INET6, inet_ntop
from struct import pack
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

_CAP_BPF = 39
_CAP_PERFMON = 38
_MIN_KERNEL_MAJOR = 4
_MIN_KERNEL_MINOR = 15


def _parse_kernel_version() -> tuple[int, int] | None:
    try:
        release = platform.release()
        parts = release.split(".", 2)
        if len(parts) >= 2:
            major = int(parts[0])
            minor = int(parts[1].split("-")[0])
            return (major, minor)
    except (ValueError, IndexError):
        pass
    return None


def _has_capabilities() -> bool:
    if os.geteuid() == 0:
        return True
    try:
        with open("/proc/self/status") as f:
            for line in f:
                if line.startswith("CapEff:"):
                    cap_eff = int(line.split()[1], 16)
                    has_bpf = bool((cap_eff >> _CAP_BPF) & 1)
                    has_perfmon = bool((cap_eff >> _CAP_PERFMON) & 1)
                    return has_bpf and has_perfmon
    except (OSError, ValueError, IndexError):
        pass
    return False


def _kernel_ok() -> bool:
    ver = _parse_kernel_version()
    if ver is None:
        return False
    major, minor = ver
    return (major > _MIN_KERNEL_MAJOR) or (
        major == _MIN_KERNEL_MAJOR and minor >= _MIN_KERNEL_MINOR
    )


class EBPFProvider(TelemetryProvider):
    """Linux eBPF telemetry provider using BCC tracepoints and kprobes."""

    def __init__(self) -> None:
        self._store: EventStore | None = None
        self._bpf: object | None = None
        self._reader_thread: threading.Thread | None = None
        self._stop_event: threading.Event | None = None
        self._unavailable_reason_str = ""

    @property
    def name(self) -> str:
        return "ebpf"

    @property
    def unavailable_reason(self) -> str:
        return self._unavailable_reason_str or "unknown"

    def available(self) -> bool:
        self._unavailable_reason_str = ""
        if sys.platform != "linux":
            self._unavailable_reason_str = "not Linux"
            return False
        if not _kernel_ok():
            self._unavailable_reason_str = "kernel < 4.15"
            return False
        if not _has_capabilities():
            self._unavailable_reason_str = "need root or CAP_BPF+CAP_PERFMON"
            return False
        try:
            from bcc import BPF
        except ImportError as e:
            self._unavailable_reason_str = f"bcc not importable: {e}"
            return False
        return True

    def start(self, store: EventStore) -> None:
        from bcc import BPF

        from .ebpf_programs import EXEC_TRACE_SRC, FILE_TRACE_SRC, NET_TRACE_SRC

        self._store = store
        self._stop_event = threading.Event()

        combined_src = f"""
{EXEC_TRACE_SRC}

{NET_TRACE_SRC}

{FILE_TRACE_SRC}
"""
        try:
            self._bpf = BPF(text=combined_src)
        except Exception as e:
            logger.warning("eBPF load failed: %s", e)
            return

        exec_attached = False
        net_attached = False
        file_attached = False

        try:
            self._bpf.attach_raw_tracepoint(
                tp="sched_process_exec", fn_name="trace_sched_process_exec"
            )
            exec_attached = True
        except Exception as e:
            logger.warning("eBPF exec tracepoint attach failed: %s", e)

        try:
            self._bpf.attach_kprobe(
                event="tcp_v4_connect", fn_name="trace_connect_entry"
            )
            self._bpf.attach_kprobe(
                event="tcp_v6_connect", fn_name="trace_connect_entry"
            )
            self._bpf.attach_kretprobe(
                event="tcp_v4_connect", fn_name="trace_connect_v4_return"
            )
            self._bpf.attach_kretprobe(
                event="tcp_v6_connect", fn_name="trace_connect_v6_return"
            )
            net_attached = True
        except Exception as e:
            logger.warning("eBPF net kprobe attach failed: %s", e)

        try:
            openat_fn = self._bpf.get_syscall_fnname("openat")
            self._bpf.attach_kprobe(
                event=openat_fn, fn_name="trace_sys_enter_openat"
            )
            file_attached = True
        except Exception as e:
            logger.warning("eBPF file kprobe attach failed: %s", e)

        if not (exec_attached or net_attached or file_attached):
            logger.warning("eBPF: no programs attached")
            return

        def _on_exec(cpu: int, data: bytes, size: int) -> None:
            if self._store is None:
                return
            try:
                from ctypes import Structure, c_char, c_uint32

                class ExecEvent(Structure):
                    _fields_ = [
                        ("pid", c_uint32),
                        ("ppid", c_uint32),
                        ("comm", c_char * 16),
                        ("filename", c_char * 256),
                    ]

                ev = ExecEvent.from_buffer_copy(data)
                comm = ev.comm[:].decode("utf-8", errors="replace").strip("\x00")
                filename = (
                    ev.filename[:].decode("utf-8", errors="replace").strip("\x00")
                )
                self._store.push_process(
                    ProcessExecEvent(
                        timestamp=datetime.now(timezone.utc),
                        pid=ev.pid,
                        ppid=ev.ppid,
                        name=comm,
                        cmdline=filename,
                        username=None,
                        binary_path=filename or None,
                        source="ebpf",
                    )
                )
            except Exception as e:
                logger.debug("eBPF exec event parse error: %s", e)

        def _on_ipv4(cpu: int, data: bytes, size: int) -> None:
            if self._store is None:
                return
            try:
                from ctypes import Structure, c_char, c_uint16, c_uint32

                class IPv4Event(Structure):
                    _fields_ = [
                        ("pid", c_uint32),
                        ("saddr", c_uint32),
                        ("daddr", c_uint32),
                        ("lport", c_uint16),
                        ("dport", c_uint16),
                        ("task", c_char * 16),
                    ]

                ev = IPv4Event.from_buffer_copy(data)
                task = ev.task[:].decode("utf-8", errors="replace").strip("\x00")
                remote = inet_ntop(AF_INET, pack("I", ev.daddr))
                self._store.push_network(
                    NetworkConnectEvent(
                        timestamp=datetime.now(timezone.utc),
                        pid=ev.pid,
                        process_name=task,
                        remote_addr=remote,
                        remote_port=ev.dport,
                        local_port=ev.lport,
                        protocol="tcp",
                        sni=None,
                        source="ebpf",
                    )
                )
            except Exception as e:
                logger.debug("eBPF ipv4 event parse error: %s", e)

        def _on_ipv6(cpu: int, data: bytes, size: int) -> None:
            if self._store is None:
                return
            try:
                from ctypes import Structure, c_char, c_uint8, c_uint16, c_uint32

                class IPv6Event(Structure):
                    _fields_ = [
                        ("pid", c_uint32),
                        ("saddr", c_uint8 * 16),
                        ("daddr", c_uint8 * 16),
                        ("lport", c_uint16),
                        ("dport", c_uint16),
                        ("task", c_char * 16),
                    ]

                ev = IPv6Event.from_buffer_copy(data)
                task = ev.task[:].decode("utf-8", errors="replace").strip("\x00")
                remote = inet_ntop(AF_INET6, bytes(ev.daddr))
                self._store.push_network(
                    NetworkConnectEvent(
                        timestamp=datetime.now(timezone.utc),
                        pid=ev.pid,
                        process_name=task,
                        remote_addr=remote,
                        remote_port=ev.dport,
                        local_port=ev.lport,
                        protocol="tcp",
                        sni=None,
                        source="ebpf",
                    )
                )
            except Exception as e:
                logger.debug("eBPF ipv6 event parse error: %s", e)

        def _on_file(cpu: int, data: bytes, size: int) -> None:
            if self._store is None:
                return
            try:
                from ctypes import Structure, c_char, c_int, c_uint32

                class FileEvent(Structure):
                    _fields_ = [
                        ("pid", c_uint32),
                        ("flags", c_int),
                        ("comm", c_char * 16),
                        ("filename", c_char * 255),
                    ]

                ev = FileEvent.from_buffer_copy(data)
                path = (
                    ev.filename[:]
                    .decode("utf-8", errors="replace")
                    .strip("\x00")
                )
                O_CREAT = 0x40
                O_WRONLY = 0x1
                O_RDWR = 0x2
                if ev.flags & O_CREAT:
                    action = "created"
                elif ev.flags & (O_WRONLY | O_RDWR):
                    action = "modified"
                else:
                    action = "modified"
                comm = ev.comm[:].decode("utf-8", errors="replace").strip("\x00")
                self._store.push_file(
                    FileChangeEvent(
                        timestamp=datetime.now(timezone.utc),
                        path=path,
                        action=action,
                        pid=ev.pid,
                        process_name=comm,
                        source="ebpf",
                    )
                )
            except Exception as e:
                logger.debug("eBPF file event parse error: %s", e)

        def _reader_loop() -> None:
            while not (self._stop_event and self._stop_event.is_set()):
                try:
                    self._bpf.perf_buffer_poll(timeout_ms=100)
                except Exception as e:
                    if self._stop_event and self._stop_event.is_set():
                        break
                    logger.debug("eBPF poll error: %s", e)

        if exec_attached:
            self._bpf["exec_events"].open_perf_buffer(_on_exec)
        if net_attached:
            self._bpf["ipv4_events"].open_perf_buffer(_on_ipv4)
            self._bpf["ipv6_events"].open_perf_buffer(_on_ipv6)
        if file_attached:
            self._bpf["file_events"].open_perf_buffer(_on_file)

        self._reader_thread = threading.Thread(target=_reader_loop, daemon=True)
        self._reader_thread.start()

    def stop(self) -> None:
        if self._stop_event:
            self._stop_event.set()
        if self._reader_thread:
            self._reader_thread.join(timeout=2.0)
            self._reader_thread = None
        self._bpf = None
        self._store = None
        self._stop_event = None

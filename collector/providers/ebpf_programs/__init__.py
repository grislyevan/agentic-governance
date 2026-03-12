"""Load BPF program C sources as strings for BCC."""

from __future__ import annotations

from pathlib import Path

_EXEC_TRACE = Path(__file__).parent / "exec_trace.c"
_NET_TRACE = Path(__file__).parent / "net_trace.c"
_FILE_TRACE = Path(__file__).parent / "file_trace.c"

EXEC_TRACE_SRC = _EXEC_TRACE.read_text()
NET_TRACE_SRC = _NET_TRACE.read_text()
FILE_TRACE_SRC = _FILE_TRACE.read_text()

__all__ = ["EXEC_TRACE_SRC", "NET_TRACE_SRC", "FILE_TRACE_SRC"]

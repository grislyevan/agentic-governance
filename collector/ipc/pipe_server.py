r"""Named pipe server for the DetecAgent Windows Service.

Listens on \\.\pipe\DetecAgent, accepts tray app connections,
handles commands (status, scan_now), and broadcasts detection events.

On non-Windows platforms, this module is a no-op stub.
"""

import json
import logging
import sys
import threading
from typing import Callable, Optional

from collector.ipc.protocol import (
    CMD_STATUS,
    CMD_SCAN_NOW,
    EVT_STATUS_UPDATE,
    make_event,
    parse_message,
    MessageError,
    PIPE_NAME,
)

logger = logging.getLogger(__name__)

IS_WINDOWS = sys.platform == "win32"


class PipeServer:
    def __init__(
        self,
        status_provider: Callable[[], dict],
        scan_callback: Optional[Callable[[], None]] = None,
    ):
        self._status_provider = status_provider
        self._scan_callback = scan_callback
        self._clients: list = []
        self._lock = threading.Lock()
        self._running = False
        self._thread: Optional[threading.Thread] = None

    def start(self):
        if not IS_WINDOWS:
            logger.info("Named pipe server skipped (not Windows)")
            return
        self._running = True
        self._thread = threading.Thread(target=self._listen_loop, daemon=True)
        self._thread.start()
        logger.info("Named pipe server started on %s", PIPE_NAME)

    def stop(self):
        self._running = False
        with self._lock:
            for client in self._clients:
                try:
                    client.close()
                except Exception:
                    pass
            self._clients.clear()
        logger.info("Named pipe server stopped")

    def broadcast(self, message: str):
        with self._lock:
            alive = []
            for client in self._clients:
                if getattr(client, "closed", False):
                    continue
                try:
                    client.write_line(message)
                    alive.append(client)
                except Exception:
                    logger.debug("Dropping disconnected pipe client")
            self._clients = alive

    def _handle_message(self, client, raw: str):
        try:
            msg = parse_message(raw)
        except MessageError:
            logger.debug("Ignoring invalid pipe message: %s", raw[:100])
            return

        cmd = msg.get("cmd")
        if cmd == CMD_STATUS:
            status = self._status_provider()
            client.write_line(make_event(EVT_STATUS_UPDATE, status))
        elif cmd == CMD_SCAN_NOW:
            if self._scan_callback:
                threading.Thread(target=self._scan_callback, daemon=True).start()

    def _listen_loop(self):
        if not IS_WINDOWS:
            return

        import pywintypes
        import win32file
        import win32pipe

        while self._running:
            try:
                pipe_handle = win32pipe.CreateNamedPipe(
                    PIPE_NAME,
                    win32pipe.PIPE_ACCESS_DUPLEX,
                    (
                        win32pipe.PIPE_TYPE_MESSAGE
                        | win32pipe.PIPE_READMODE_MESSAGE
                        | win32pipe.PIPE_WAIT
                    ),
                    win32pipe.PIPE_UNLIMITED_INSTANCES,
                    4096,
                    4096,
                    0,
                    None,
                )
                win32pipe.ConnectNamedPipe(pipe_handle, None)
                client = Win32PipeClient(pipe_handle)
                with self._lock:
                    self._clients.append(client)
                threading.Thread(
                    target=self._client_loop, args=(client,), daemon=True
                ).start()
            except pywintypes.error as exc:
                if self._running:
                    logger.error("Pipe listen error: %s", exc)
                break

    def _client_loop(self, client):
        try:
            while self._running and not client.closed:
                line = client.read_line()
                if line is None:
                    break
                self._handle_message(client, line)
        except Exception:
            pass
        finally:
            client.close()
            with self._lock:
                if client in self._clients:
                    self._clients.remove(client)


class Win32PipeClient:
    """Wraps a win32 pipe handle with line-oriented read/write."""

    def __init__(self, handle):
        self._handle = handle
        self.closed = False

    def read_line(self) -> Optional[str]:
        import pywintypes
        import win32file

        try:
            hr, data = win32file.ReadFile(self._handle, 4096)
            return data.decode("utf-8").strip()
        except pywintypes.error:
            self.closed = True
            return None

    def write_line(self, line: str):
        import win32file

        win32file.WriteFile(self._handle, (line + "\n").encode("utf-8"))

    def close(self):
        if not self.closed:
            self.closed = True
            try:
                import win32file
                win32file.CloseHandle(self._handle)
            except Exception:
                pass

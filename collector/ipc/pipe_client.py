r"""Named pipe client for the DetecAgent tray application.

Connects to \\.\pipe\DetecAgent, sends commands, and receives events.
On non-Windows platforms, this module is a no-op stub.
"""

import logging
import sys
import threading
from typing import Callable, Optional

from collector.ipc.protocol import (
    make_command,
    parse_message,
    MessageError,
    PIPE_NAME,
)

logger = logging.getLogger(__name__)

IS_WINDOWS = sys.platform == "win32"


class PipeClient:
    def __init__(self):
        self._handle = None
        self._connected = False
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self.on_event: Optional[Callable[[dict], None]] = None

    @property
    def connected(self) -> bool:
        return self._connected

    def connect(self, retry_interval: float = 5.0):
        if not IS_WINDOWS:
            logger.info("Pipe client skipped (not Windows)")
            return
        self._running = True
        self._thread = threading.Thread(
            target=self._connect_loop, args=(retry_interval,), daemon=True
        )
        self._thread.start()

    def disconnect(self):
        self._running = False
        self._connected = False
        if self._handle:
            try:
                import win32file
                win32file.CloseHandle(self._handle)
            except Exception:
                pass
            self._handle = None

    def send_command(self, cmd: str):
        if not self._connected or not self._handle:
            logger.warning("Cannot send command — not connected to service")
            return
        try:
            msg = make_command(cmd)
            if IS_WINDOWS:
                import win32file
                win32file.WriteFile(self._handle, (msg + "\n").encode("utf-8"))
            else:
                self._handle.write((msg + "\n").encode("utf-8"))
        except Exception as exc:
            logger.error("Failed to send command: %s", exc)
            self._connected = False

    def _dispatch(self, raw: str):
        try:
            msg = parse_message(raw)
        except MessageError:
            return
        if self.on_event:
            self.on_event(msg)

    def _connect_loop(self, retry_interval: float):
        import time

        while self._running:
            try:
                self._try_connect()
                self._read_loop()
            except Exception as exc:
                logger.debug("Pipe connection lost: %s", exc)
                self._connected = False
            if self._running:
                time.sleep(retry_interval)

    def _try_connect(self):
        import pywintypes
        import win32file

        self._handle = win32file.CreateFile(
            PIPE_NAME,
            win32file.GENERIC_READ | win32file.GENERIC_WRITE,
            0,
            None,
            win32file.OPEN_EXISTING,
            0,
            None,
        )
        self._connected = True
        logger.info("Connected to service pipe")

    def _read_loop(self):
        import pywintypes
        import win32file

        while self._running and self._connected:
            try:
                hr, data = win32file.ReadFile(self._handle, 4096)
                line = data.decode("utf-8").strip()
                if line:
                    self._dispatch(line)
            except pywintypes.error:
                self._connected = False
                break

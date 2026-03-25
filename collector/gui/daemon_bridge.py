"""Bridge between the tray GUI and the DetecAgent Windows Service.

Communicates with the service over a named pipe. Does not run its own
scan loop — all scanning happens in the service.
"""

import logging
import threading
from typing import Callable, Optional

from collector.ipc.pipe_client import PipeClient
from collector.ipc.protocol import CMD_STATUS, CMD_SCAN_NOW

logger = logging.getLogger(__name__)


class DaemonBridge:
    def __init__(self, on_status: Optional[Callable[[dict], None]] = None):
        self._pipe = PipeClient()
        self._on_status = on_status
        self._status = {
            "connected": False,
            "last_scan": None,
            "events_sent": 0,
            "version": "unknown",
        }
        self._detection_callbacks: list[Callable[[dict], None]] = []
        self._lock = threading.Lock()

    @property
    def status(self) -> dict:
        with self._lock:
            return dict(self._status)

    @property
    def events_sent(self) -> int:
        return self._status.get("events_sent", 0)

    def on_detection(self, callback: Callable[[dict], None]):
        self._detection_callbacks.append(callback)

    def start(self):
        self._pipe.on_event = self._handle_event
        self._pipe.connect(retry_interval=5.0)
        threading.Thread(target=self._request_initial_status, daemon=True).start()

    def stop(self):
        self._pipe.disconnect()

    def request_scan(self):
        self._pipe.send_command(CMD_SCAN_NOW)

    def _request_initial_status(self):
        import time
        for _ in range(10):
            if self._pipe.connected:
                self._pipe.send_command(CMD_STATUS)
                return
            time.sleep(1)

    def _handle_event(self, msg: dict):
        evt = msg.get("evt")

        if evt == "status_update":
            with self._lock:
                self._status.update(msg.get("data", {}))
            if self._on_status:
                self._on_status(self._status)

        elif evt in ("detection", "approval"):
            for cb in self._detection_callbacks:
                try:
                    cb(msg.get("data", {}))
                except Exception:
                    logger.exception("Detection callback error")

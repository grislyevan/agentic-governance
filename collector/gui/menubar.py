"""macOS menu bar application for the Detec endpoint agent.

Provides a system tray icon with status information and a dropdown menu.
Integrates the collector daemon (background scanning) and a native
status window showing branding and connection state.

Entry point: ``detec-agent-gui`` (registered in pyproject.toml).
"""

from __future__ import annotations

import logging
import sys
from datetime import datetime, timezone
from pathlib import Path

_COLLECTOR_DIR = str(Path(__file__).resolve().parent.parent)
if _COLLECTOR_DIR not in sys.path:
    sys.path.insert(0, _COLLECTOR_DIR)

import rumps

from collector.gui.assets import get_menubar_icon_path
from collector.gui.daemon_bridge import (
    DaemonBridge,
    STATUS_CONNECTED,
    STATUS_DISCONNECTED,
    STATUS_SCANNING,
    STATUS_ERROR,
    STATUS_STOPPED,
)
from collector.gui.statuswindow import DetecStatusWindow

logger = logging.getLogger(__name__)

_STATUS_DISPLAY = {
    STATUS_CONNECTED: "Connected",
    STATUS_DISCONNECTED: "Disconnected",
    STATUS_SCANNING: "Scanning...",
    STATUS_ERROR: "Error",
    STATUS_STOPPED: "Stopped",
}

_POLL_INTERVAL = 5  # seconds between UI status refreshes


class DetecAgentApp(rumps.App):
    """macOS status bar application for the Detec endpoint agent."""

    def __init__(self) -> None:
        icon_path = str(get_menubar_icon_path())

        super().__init__(
            name="Detec Agent",
            icon=icon_path,
            template=True,
            quit_button=None,
        )

        self._bridge = DaemonBridge()
        self._status_window = DetecStatusWindow()

        self._status_item = rumps.MenuItem("Status: Disconnected")
        self._status_item.set_callback(None)

        self._last_scan_item = rumps.MenuItem("Last Scan: Never")
        self._last_scan_item.set_callback(None)

        self._events_item = rumps.MenuItem("Events Sent: 0")
        self._events_item.set_callback(None)

        self.menu = [
            self._status_item,
            self._last_scan_item,
            self._events_item,
            rumps.separator,
            rumps.MenuItem("Show Status Window", callback=self._on_show_status),
            rumps.MenuItem("Run Scan Now", callback=self._on_run_scan),
            rumps.separator,
            rumps.MenuItem("Quit Detec Agent", callback=self._on_quit),
        ]

        self._poll_timer = rumps.Timer(self._poll_status, _POLL_INTERVAL)
        self._startup_timer = rumps.Timer(self._on_first_tick, 1)
        self._startup_timer.start()

    def _start_daemon(self) -> None:
        """Start the background scan daemon with current configuration."""
        self._bridge.start()

    def _on_first_tick(self, _timer: rumps.Timer) -> None:
        """Fires once shortly after the run loop begins to perform setup."""
        _timer.stop()
        self._start_daemon()
        self._status_window.show()
        self._poll_timer.start()

    def _poll_status(self, _timer: rumps.Timer | None = None) -> None:
        """Periodic callback to sync bridge state into menu items."""
        status = self._bridge.status
        display = _STATUS_DISPLAY.get(status, status.title())
        self._status_item.title = f"Status: {display}"

        last_scan = self._bridge.last_scan_time
        if last_scan:
            ts = last_scan.astimezone().strftime("%H:%M:%S")
            self._last_scan_item.title = f"Last Scan: {ts}"
        else:
            self._last_scan_item.title = "Last Scan: Never"

        self._events_item.title = f"Events Sent: {self._bridge.events_sent}"

        self._status_window.update_status(status)

    def _on_show_status(self, _sender: rumps.MenuItem) -> None:
        self._status_window.show()

    def _on_run_scan(self, _sender: rumps.MenuItem) -> None:
        if self._bridge.is_running:
            self._bridge.request_scan()
            rumps.notification(
                title="Detec Agent",
                subtitle="",
                message="Scan requested. Results will appear shortly.",
            )
        else:
            rumps.notification(
                title="Detec Agent",
                subtitle="",
                message="Agent is not running. Check your API configuration.",
            )

    def _on_quit(self, _sender: rumps.MenuItem) -> None:
        self._poll_timer.stop()
        self._bridge.stop()
        self._status_window.hide()
        rumps.quit_application()


def main() -> None:
    """Entry point for the Detec Agent GUI application."""
    log_dir = Path.home() / "Library" / "Logs" / "DetecAgent"
    log_dir.mkdir(parents=True, exist_ok=True)

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler(log_dir / "agent.log"),
        ],
    )

    app = DetecAgentApp()
    app.run()


if __name__ == "__main__":
    main()

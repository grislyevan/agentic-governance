"""Windows system tray application for the Detec endpoint agent.

Provides a notification-area icon with a context menu and a tkinter
status window. Integrates the collector daemon (background scanning)
and mirrors the macOS menu bar app (menubar.py) in functionality.

Threading model:
  - Main thread: tkinter event loop (required by Tk on Windows)
  - Thread 1: pystray tray icon loop
  - Thread 2+: DaemonBridge background scanning

Entry point: ``detec-agent-gui`` on Windows (registered in pyproject.toml).
"""

from __future__ import annotations

import logging
import os
import sys
import threading
from pathlib import Path

from collector.gui.daemon_bridge import (
    DaemonBridge,
    STATUS_CONNECTED,
    STATUS_DISCONNECTED,
    STATUS_SCANNING,
    STATUS_ERROR,
    STATUS_STOPPED,
)

logger = logging.getLogger(__name__)

_STATUS_DISPLAY = {
    STATUS_CONNECTED: "Connected",
    STATUS_DISCONNECTED: "Disconnected",
    STATUS_SCANNING: "Scanning...",
    STATUS_ERROR: "Error",
    STATUS_STOPPED: "Stopped",
}

_POLL_MS = 5_000


def _find_icon_path() -> str | None:
    """Locate the Icon.ico file for the tray icon."""
    bundle_dir = getattr(sys, "_MEIPASS", None)
    if bundle_dir:
        candidate = os.path.join(bundle_dir, "branding", "Icon.ico")
        if os.path.exists(candidate):
            return candidate

    repo_root = Path(__file__).resolve().parent.parent.parent
    candidate = repo_root / "branding" / "Icon.ico"
    if candidate.exists():
        return str(candidate)

    return None


def _load_icon():
    """Load the tray icon as a PIL Image."""
    from PIL import Image

    icon_path = _find_icon_path()
    if icon_path:
        return Image.open(icon_path)

    return Image.new("RGBA", (64, 64), (20, 184, 166, 255))


class DetecTrayApp:
    """Windows notification-area application for the Detec endpoint agent.

    Call ``run()`` from the main thread. It starts the tray icon in a
    background thread, the daemon bridge in another, and runs the tkinter
    event loop on the main thread.
    """

    def __init__(self) -> None:
        self._bridge = DaemonBridge()
        self._tray = None
        self._root = None
        self._status_window = None

    def run(self) -> None:
        """Start the tray app (blocks until quit)."""
        import tkinter as tk

        self._root = tk.Tk()
        self._root.withdraw()

        from collector.gui.statuswindow_tk import DetecStatusWindowTk
        self._status_window = DetecStatusWindowTk(master=self._root)

        self._bridge.start()

        tray_thread = threading.Thread(target=self._run_tray, daemon=True, name="tray")
        tray_thread.start()

        self._root.after(500, self._show_status_window)
        self._root.after(_POLL_MS, self._poll_status)
        self._root.mainloop()

    def _run_tray(self) -> None:
        """Run the pystray icon loop (background thread)."""
        import pystray

        icon_image = _load_icon()
        menu = pystray.Menu(
            pystray.MenuItem("Show Status Window", self._on_show_status, default=True),
            pystray.MenuItem(
                lambda _: f"Status: {_STATUS_DISPLAY.get(self._bridge.status, 'Unknown')}",
                None,
                enabled=False,
            ),
            pystray.MenuItem(
                lambda _: f"Events Sent: {self._bridge.events_sent}",
                None,
                enabled=False,
            ),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Run Scan Now", self._on_run_scan),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Quit Detec Agent", self._on_quit),
        )

        self._tray = pystray.Icon(
            name="Detec Agent",
            icon=icon_image,
            title="Detec Agent",
            menu=menu,
        )
        self._tray.run()

    def _poll_status(self) -> None:
        """Periodic callback to sync bridge state into the UI."""
        if self._root is None:
            return

        status = self._bridge.status
        display = _STATUS_DISPLAY.get(status, status.title())

        if self._tray:
            self._tray.title = f"Detec Agent - {display}"

        if self._status_window:
            self._status_window.update_status(status)

        self._root.after(_POLL_MS, self._poll_status)

    def _show_status_window(self) -> None:
        if self._status_window:
            self._status_window.show()

    def _on_show_status(self, icon=None, item=None) -> None:
        if self._root:
            self._root.after(0, self._show_status_window)

    def _on_run_scan(self, icon=None, item=None) -> None:
        if self._bridge.is_running:
            self._bridge.request_scan()

    def _on_quit(self, icon=None, item=None) -> None:
        self._bridge.stop()
        if self._tray:
            self._tray.stop()
        if self._root:
            self._root.after(0, self._root.quit)


def main() -> None:
    """Entry point for the Detec Agent GUI on Windows."""
    log_dir = Path(os.environ.get("PROGRAMDATA", r"C:\ProgramData")) / "Detec" / "Agent"
    log_dir.mkdir(parents=True, exist_ok=True)

    handlers: list[logging.Handler] = [logging.StreamHandler()]
    try:
        handlers.append(logging.FileHandler(log_dir / "agent-gui.log"))
    except PermissionError:
        pass

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        handlers=handlers,
    )

    app = DetecTrayApp()
    app.run()


if __name__ == "__main__":
    main()

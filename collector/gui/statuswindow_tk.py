"""Cross-platform (tkinter) status window for the Detec Agent.

Used on Windows where PyObjC is not available. Displays the agent's
connection status, branding, and version information in a Toplevel
window that matches the macOS reference design: light blue-gray
background, centered Detec logo with wordmark, status text, and
footer with year and version.
"""

from __future__ import annotations

import datetime
import logging
import os
import sys
import tkinter as tk
from pathlib import Path

logger = logging.getLogger(__name__)

_VERSION = "0.3"
_BUILD = "0.3.0"
_WIN_WIDTH = 720
_WIN_HEIGHT = 440
_BG_HEX = "#CBD5E1"

_STATUS_LABELS = {
    "connected": "Agent Status... Connected",
    "disconnected": "Agent Status... Disconnected",
    "scanning": "Agent Status... Scanning",
    "error": "Agent Status... Error",
    "stopped": "Agent Status... Stopped",
}

_WORDMARK_COLOR = "#2D2B7A"
_FOOTER_COLOR = "#737380"
_STATUS_COLOR = "#5A5A66"


def _find_logo_path() -> str | None:
    """Locate the logo PNG for the status window."""
    bundle_dir = getattr(sys, "_MEIPASS", None)
    if bundle_dir:
        candidate = os.path.join(bundle_dir, "branding", "Icon.png")
        if os.path.exists(candidate):
            return candidate

    repo_root = Path(__file__).resolve().parent.parent.parent
    candidate = repo_root / "branding" / "Icon.png"
    if candidate.exists():
        return str(candidate)

    return None


def _find_ico_path() -> str | None:
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


class DetecStatusWindowTk:
    """Manages the Detec Agent status window using tkinter.

    Create with an existing Tk root so it shares the main event loop.
    Thread-safe: ``update_status()`` dispatches via ``root.after()``.
    """

    def __init__(self, master: tk.Tk | None = None) -> None:
        self._master = master
        self._window: tk.Toplevel | None = None
        self._status_var: tk.StringVar | None = None
        self._logo_image = None
        self._built = False

    def _build(self) -> None:
        if self._built:
            return
        if self._master is None:
            raise RuntimeError("DetecStatusWindowTk requires a Tk master")

        self._status_var = tk.StringVar(
            master=self._master, value="Agent Status... Disconnected"
        )

        win = tk.Toplevel(self._master)
        win.title("Detec - Agent")
        win.geometry(f"{_WIN_WIDTH}x{_WIN_HEIGHT}")
        win.resizable(False, False)
        win.configure(bg=_BG_HEX)
        win.protocol("WM_DELETE_WINDOW", self.hide)
        self._window = win

        ico_path = _find_ico_path()
        if ico_path:
            try:
                win.iconbitmap(ico_path)
            except tk.TclError:
                pass

        canvas = tk.Canvas(
            win,
            width=_WIN_WIDTH,
            height=_WIN_HEIGHT,
            bg=_BG_HEX,
            highlightthickness=0,
        )
        canvas.pack(fill="both", expand=True)

        logo_path = _find_logo_path()
        if logo_path:
            try:
                from PIL import Image, ImageTk

                img = Image.open(logo_path).convert("RGBA")
                logo_size = 110
                img = img.resize((logo_size, logo_size), Image.LANCZOS)
                self._logo_image = ImageTk.PhotoImage(img)
                logo_x = (_WIN_WIDTH // 2) - (logo_size // 2) - 60
                logo_y = (_WIN_HEIGHT // 2) - 20
                canvas.create_image(
                    logo_x, logo_y, image=self._logo_image, anchor="center"
                )
            except ImportError:
                logger.debug("PIL not available, skipping logo")

        wordmark_x = (_WIN_WIDTH // 2) + 55
        wordmark_y = (_WIN_HEIGHT // 2) - 20
        try:
            font_family = "Segoe UI"
            canvas.create_text(0, 0, text=".", font=(font_family, 10))
        except tk.TclError:
            font_family = "Helvetica"
        canvas.delete("all")

        if self._logo_image:
            logo_x = (_WIN_WIDTH // 2) - (110 // 2) - 60
            logo_y = (_WIN_HEIGHT // 2) - 20
            canvas.create_image(
                logo_x, logo_y, image=self._logo_image, anchor="center"
            )

        canvas.create_text(
            wordmark_x,
            wordmark_y,
            text="Detec",
            font=(font_family, 42, "bold"),
            fill=_WORDMARK_COLOR,
            anchor="w",
        )

        status_y = (_WIN_HEIGHT // 2) + 40
        canvas.create_window(
            _WIN_WIDTH // 2,
            status_y,
            window=tk.Label(
                canvas,
                textvariable=self._status_var,
                font=(font_family, 13),
                fg=_STATUS_COLOR,
                bg=_BG_HEX,
            ),
            anchor="center",
        )

        year_text = str(datetime.date.today().year)
        canvas.create_text(
            16,
            _WIN_HEIGHT - 18,
            text=year_text,
            font=(font_family, 10),
            fill=_FOOTER_COLOR,
            anchor="w",
        )

        version_text = f"Version {_VERSION} - Build no. {_BUILD}"
        canvas.create_text(
            _WIN_WIDTH - 16,
            _WIN_HEIGHT - 18,
            text=version_text,
            font=(font_family, 10),
            fill=_FOOTER_COLOR,
            anchor="e",
        )

        self._center_window()
        self._built = True

    def _center_window(self) -> None:
        if not self._window:
            return
        self._window.update_idletasks()
        x = (self._window.winfo_screenwidth() // 2) - (_WIN_WIDTH // 2)
        y = (self._window.winfo_screenheight() // 2) - (_WIN_HEIGHT // 2)
        self._window.geometry(f"{_WIN_WIDTH}x{_WIN_HEIGHT}+{x}+{y}")

    def show(self) -> None:
        """Show the status window, creating it if necessary."""
        if not self._built:
            self._build()
        if self._window:
            self._window.deiconify()
            self._window.lift()
            try:
                self._window.focus_force()
            except tk.TclError:
                pass

    def hide(self) -> None:
        """Hide the window (minimize to tray, don't destroy)."""
        if self._window:
            self._window.withdraw()

    def destroy(self) -> None:
        """Permanently close the window."""
        if self._window:
            try:
                self._window.destroy()
            except tk.TclError:
                pass
            self._window = None
            self._built = False

    def update_status(self, status: str) -> None:
        """Update the status label. Safe to call from any thread."""
        text = _STATUS_LABELS.get(status, f"Agent Status... {status.title()}")
        if self._status_var and self._master:
            try:
                self._master.after(0, lambda: self._status_var.set(text))
            except (tk.TclError, RuntimeError):
                pass

    @property
    def is_visible(self) -> bool:
        if self._window:
            try:
                return self._window.state() == "normal"
            except tk.TclError:
                return False
        return False

"""Native macOS status window for the Detec Agent.

Uses PyObjC to create an NSWindow that displays the agent's connection
status, branding, and version information. The window matches the
reference design: light blue-gray background, centered Detec logo with
wordmark, status text, and footer with year and version.
"""

from __future__ import annotations

import datetime
import logging
import os
import sys

try:
    import warnings
    warnings.filterwarnings("ignore", category=DeprecationWarning, module="objc")
    warnings.filterwarnings("ignore", message="PyObjCPointer created")

    import objc
    from AppKit import (
        NSWindow,
        NSView,
        NSTextField,
        NSImageView,
        NSImage,
        NSColor,
        NSFont,
        NSMakeRect,
        NSWindowStyleMaskTitled,
        NSWindowStyleMaskClosable,
        NSBackingStoreBuffered,
        NSTextAlignmentCenter,
        NSTextAlignmentLeft,
        NSTextAlignmentRight,
        NSImageScaleProportionallyUpOrDown,
        NSApplication,
        NSApp,
        NSWindowCollectionBehaviorCanJoinAllSpaces,
    )
    from Foundation import NSObject, NSBundle

    _OBJC_AVAILABLE = True
except ImportError:
    _OBJC_AVAILABLE = False

try:
    from collector._version import __version__ as _VERSION, __build__ as _BUILD
except ImportError:
    from _version import __version__ as _VERSION, __build__ as _BUILD
from collector.gui.assets import create_aperture_image, WORDMARK_COLOR

logger = logging.getLogger(__name__)
_WIN_WIDTH = 720
_WIN_HEIGHT = 440

# Background: light blue-gray similar to Tailwind slate-200/300
_BG_R, _BG_G, _BG_B = 0xCB / 255, 0xD5 / 255, 0xE1 / 255

_STATUS_LABELS = {
    "connected": "Agent Status... Connected",
    "disconnected": "Agent Status... Disconnected",
    "scanning": "Agent Status... Scanning",
    "error": "Agent Status... Error",
    "stopped": "Agent Status... Stopped",
}


class DetecStatusWindow:
    """Manages the Detec Agent status window.

    Create on the main thread (AppKit requirement). Call ``show()`` and
    ``hide()`` to control visibility. Call ``update_status()`` from any
    thread; it dispatches to the main thread automatically.
    """

    def __init__(self) -> None:
        if not _OBJC_AVAILABLE:
            raise RuntimeError("PyObjC is required for the status window")

        self._window: NSWindow | None = None
        self._status_label: NSTextField | None = None
        self._built = False

    def _build(self) -> None:
        if self._built:
            return

        style = NSWindowStyleMaskTitled | NSWindowStyleMaskClosable
        self._window = NSWindow.alloc().initWithContentRect_styleMask_backing_defer_(
            NSMakeRect(0, 0, _WIN_WIDTH, _WIN_HEIGHT),
            style,
            NSBackingStoreBuffered,
            False,
        )
        self._window.setTitle_("Detec - Agent")
        self._window.setIsVisible_(False)
        self._window.setReleasedWhenClosed_(False)
        self._window.center()

        content = self._window.contentView()

        bg_color = NSColor.colorWithCalibratedRed_green_blue_alpha_(
            _BG_R, _BG_G, _BG_B, 1.0
        )
        self._window.setBackgroundColor_(bg_color)

        # --- App icon (Icon.icns from bundle or branding directory) ---
        logo_size = 110
        logo_image = None
        icns_candidates = []
        bundle = NSBundle.mainBundle()
        if bundle and bundle.resourcePath():
            icns_candidates.append(os.path.join(bundle.resourcePath(), "Icon.icns"))
        bundle_dir = getattr(sys, "_MEIPASS", None)
        if bundle_dir:
            icns_candidates.append(os.path.join(bundle_dir, "branding", "Icon.icns"))
        repo_root = os.path.join(os.path.dirname(__file__), "..", "..")
        icns_candidates.append(os.path.join(repo_root, "branding", "Icon.icns"))
        for icns_path in icns_candidates:
            if os.path.exists(icns_path):
                logo_image = NSImage.alloc().initWithContentsOfFile_(icns_path)
                break
        if logo_image is None:
            logo_image = create_aperture_image(logo_size)
        logo_view = NSImageView.alloc().initWithFrame_(
            NSMakeRect(
                (_WIN_WIDTH / 2) - logo_size - 10,
                (_WIN_HEIGHT / 2) - (logo_size / 2) + 20,
                logo_size,
                logo_size,
            )
        )
        logo_view.setImage_(logo_image)
        logo_view.setImageScaling_(NSImageScaleProportionallyUpOrDown)
        content.addSubview_(logo_view)

        # --- Wordmark "Detec" ---
        wordmark = NSTextField.labelWithString_("Detec")
        wordmark.setFont_(NSFont.fontWithName_size_("Helvetica Neue Bold", 60))
        wordmark.setTextColor_(
            NSColor.colorWithCalibratedRed_green_blue_alpha_(
                WORDMARK_COLOR[0], WORDMARK_COLOR[1], WORDMARK_COLOR[2], 1.0
            )
        )
        wordmark.setBackgroundColor_(NSColor.clearColor())
        wordmark.setBezeled_(False)
        wordmark.setEditable_(False)
        wordmark.setSelectable_(False)
        wordmark.sizeToFit()
        wm_frame = wordmark.frame()
        wordmark.setFrame_(
            NSMakeRect(
                (_WIN_WIDTH / 2) + 10,
                (_WIN_HEIGHT / 2) - (wm_frame.size.height / 2) + 20,
                wm_frame.size.width,
                wm_frame.size.height,
            )
        )
        content.addSubview_(wordmark)

        # --- Status label ---
        self._status_label = NSTextField.labelWithString_(
            "Agent Status... Disconnected"
        )
        self._status_label.setFont_(
            NSFont.fontWithName_size_("Helvetica Neue", 16)
        )
        self._status_label.setTextColor_(
            NSColor.colorWithCalibratedRed_green_blue_alpha_(
                0.35, 0.35, 0.40, 1.0
            )
        )
        self._status_label.setBackgroundColor_(NSColor.clearColor())
        self._status_label.setBezeled_(False)
        self._status_label.setEditable_(False)
        self._status_label.setSelectable_(False)
        self._status_label.setAlignment_(NSTextAlignmentCenter)
        self._status_label.setFrame_(
            NSMakeRect(0, (_WIN_HEIGHT / 2) - 50, _WIN_WIDTH, 24)
        )
        content.addSubview_(self._status_label)

        # --- Footer: year (left) ---
        year_label = NSTextField.labelWithString_(
            str(datetime.date.today().year)
        )
        year_label.setFont_(NSFont.fontWithName_size_("Helvetica Neue", 12))
        year_label.setTextColor_(
            NSColor.colorWithCalibratedRed_green_blue_alpha_(
                0.45, 0.45, 0.50, 1.0
            )
        )
        year_label.setBackgroundColor_(NSColor.clearColor())
        year_label.setBezeled_(False)
        year_label.setEditable_(False)
        year_label.setSelectable_(False)
        year_label.setAlignment_(NSTextAlignmentLeft)
        year_label.setFrame_(NSMakeRect(16, 12, 100, 18))
        content.addSubview_(year_label)

        # --- Footer: version (right) ---
        version_text = f"Version {_VERSION} - Build no. {_BUILD}"
        version_label = NSTextField.labelWithString_(version_text)
        version_label.setFont_(NSFont.fontWithName_size_("Helvetica Neue", 12))
        version_label.setTextColor_(
            NSColor.colorWithCalibratedRed_green_blue_alpha_(
                0.45, 0.45, 0.50, 1.0
            )
        )
        version_label.setBackgroundColor_(NSColor.clearColor())
        version_label.setBezeled_(False)
        version_label.setEditable_(False)
        version_label.setSelectable_(False)
        version_label.setAlignment_(NSTextAlignmentRight)
        version_label.setFrame_(NSMakeRect(_WIN_WIDTH - 250, 12, 234, 18))
        content.addSubview_(version_label)

        self._built = True

    def show(self) -> None:
        """Show the status window, creating it if necessary."""
        self._build()
        if self._window:
            self._window.center()
            self._window.makeKeyAndOrderFront_(None)
            NSApp.activateIgnoringOtherApps_(True)

    def hide(self) -> None:
        if self._window:
            self._window.orderOut_(None)

    def update_status(self, status: str) -> None:
        """Update the status label. Safe to call from any thread."""
        text = _STATUS_LABELS.get(status, f"Agent Status... {status.title()}")
        if self._status_label:
            self._status_label.performSelectorOnMainThread_withObject_waitUntilDone_(
                "setStringValue:", text, False
            )

    @property
    def is_visible(self) -> bool:
        if self._window:
            return bool(self._window.isVisible())
        return False

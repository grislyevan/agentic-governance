"""Embedded logo assets and drawing utilities for the Detec Agent GUI.

Renders the Detec aperture mark as NSImage instances at any size, using
NSBezierPath with path coordinates derived from the brand mark.
The master icon source is branding/Icon.icns; this programmatic renderer
exists for macOS menu bar template images (which require monochrome
rendering) and the status window logo. No external image files are
needed at runtime.
"""

from __future__ import annotations

import math
import re
import sys
import tempfile
from pathlib import Path

try:
    import AppKit
    from AppKit import (
        NSImage,
        NSBezierPath,
        NSColor,
        NSAffineTransform,
        NSGraphicsContext,
        NSCompositingOperationSourceOver,
    )
    from Foundation import NSMakeSize, NSMakeRect, NSMakePoint

    _OBJC_AVAILABLE = True
except ImportError:
    _OBJC_AVAILABLE = False


TEAL = (0x14 / 255, 0xB8 / 255, 0xA6 / 255)
AMBER = (0xF5 / 255, 0x9E / 255, 0x0B / 255)
INDIGO = (0x63 / 255, 0x66 / 255, 0xF1 / 255)
WORDMARK_COLOR = (0x2D / 255, 0x2B / 255, 0x7A / 255)
LIGHT_SLATE = (0xF1 / 255, 0xF5 / 255, 0xF9 / 255)

# SVG viewBox is 0 0 100 100.  Clip circle: cx=50 cy=50 r=44.
_CLIP_CX, _CLIP_CY, _CLIP_R = 50.0, 50.0, 44.0

_APERTURE_PATHS: list[tuple[str, tuple[float, float, float], float]] = [
    # Teal blade (front)
    (
        "M18 14 C28 6 46 4 56 10 C62 14 58 22 50 28 "
        "C42 34 36 42 38 48 L46 50 C44 44 44 36 50 30 "
        "C56 24 50 16 40 14 C34 13 26 16 18 14 Z",
        TEAL,
        1.0,
    ),
    # Teal blade (back)
    (
        "M10 28 C6 40 8 18 18 14 C26 16 34 13 40 14 "
        "C50 16 56 24 50 30 C44 36 44 44 46 50 L38 48 "
        "C36 42 30 36 22 34 C14 32 10 32 10 28 Z",
        TEAL,
        0.85,
    ),
    # Amber blade (front)
    (
        "M80 18 C90 28 94 46 88 58 C84 66 76 62 70 54 "
        "C64 46 56 42 52 44 L50 46 C54 44 62 44 68 50 "
        "C74 56 78 52 80 44 C82 36 80 28 80 18 Z",
        AMBER,
        1.0,
    ),
    # Amber blade (back)
    (
        "M68 8 C78 10 88 16 80 18 C80 28 82 36 80 44 "
        "C78 52 74 56 68 50 C62 44 54 44 50 46 L52 44 "
        "C56 42 62 38 66 30 C70 22 70 14 68 8 Z",
        AMBER,
        0.85,
    ),
    # Indigo blade (front)
    (
        "M30 90 C18 82 10 66 14 54 C16 46 26 48 34 52 "
        "C42 56 48 50 48 46 L50 48 C48 52 42 56 36 54 "
        "C28 52 24 56 26 64 C28 72 32 82 30 90 Z",
        INDIGO,
        1.0,
    ),
    # Indigo blade (back)
    (
        "M50 94 C38 94 24 90 30 90 C32 82 28 72 26 64 "
        "C24 56 28 52 36 54 C42 56 48 52 50 48 L48 46 "
        "C48 50 52 58 44 64 C38 70 42 82 50 94 Z",
        INDIGO,
        0.85,
    ),
]

# Central focal dots
_CENTER_DOT_OUTER = (_CLIP_CX, _CLIP_CY, 4.5, INDIGO, 1.0)
_CENTER_DOT_INNER = (_CLIP_CX, _CLIP_CY, 2.5, LIGHT_SLATE, 0.85)


def _parse_svg_d(d: str) -> list[tuple]:
    """Parse a simplified SVG path 'd' attribute into drawing commands.

    Handles M, C, L, Z commands with absolute coordinates.
    """
    commands: list[tuple] = []
    segments = re.findall(r"[MCLZ][^MCLZ]*", d, re.IGNORECASE)
    for seg in segments:
        cmd = seg[0].upper()
        nums = [float(x) for x in re.findall(r"-?[\d.]+", seg[1:])]
        if cmd == "M":
            commands.append(("M", nums[0], nums[1]))
        elif cmd == "L":
            commands.append(("L", nums[0], nums[1]))
        elif cmd == "C":
            for i in range(0, len(nums), 6):
                commands.append(("C", *nums[i : i + 6]))
        elif cmd == "Z":
            commands.append(("Z",))
    return commands


def _draw_svg_path(path_d: str, scale: float) -> None:
    """Draw an SVG path using NSBezierPath (assumes y-flipped graphics context)."""
    bp = NSBezierPath.bezierPath()
    for cmd in _parse_svg_d(path_d):
        if cmd[0] == "M":
            bp.moveToPoint_(NSMakePoint(cmd[1] * scale, cmd[2] * scale))
        elif cmd[0] == "L":
            bp.lineToPoint_(NSMakePoint(cmd[1] * scale, cmd[2] * scale))
        elif cmd[0] == "C":
            bp.curveToPoint_controlPoint1_controlPoint2_(
                NSMakePoint(cmd[5] * scale, cmd[6] * scale),
                NSMakePoint(cmd[1] * scale, cmd[2] * scale),
                NSMakePoint(cmd[3] * scale, cmd[4] * scale),
            )
        elif cmd[0] == "Z":
            bp.closePath()
    bp.fill()


def create_aperture_image(size: int, template: bool = False) -> "NSImage":
    """Create an NSImage of the Detec aperture mark.

    Args:
        size: Width and height in points.
        template: If True, render monochrome black for use as a macOS
                  template image (menu bar icon). The OS applies appropriate
                  coloring for light/dark mode automatically.
    """
    if not _OBJC_AVAILABLE:
        raise RuntimeError("PyObjC is required for GUI assets")

    scale = size / 100.0
    image = NSImage.alloc().initWithSize_(NSMakeSize(size, size))
    image.lockFocus()

    ctx = NSGraphicsContext.currentContext()
    ctx.saveGraphicsState()

    # Flip coordinate system so y-down matches SVG convention
    flip = NSAffineTransform.transform()
    flip.translateXBy_yBy_(0, size)
    flip.scaleXBy_yBy_(1, -1)
    flip.concat()

    # Clip to the aperture circle
    clip_path = NSBezierPath.bezierPath()
    clip_path.appendBezierPathWithOvalInRect_(
        NSMakeRect(
            (_CLIP_CX - _CLIP_R) * scale,
            (_CLIP_CY - _CLIP_R) * scale,
            _CLIP_R * 2 * scale,
            _CLIP_R * 2 * scale,
        )
    )
    clip_path.addClip()

    # Draw blade paths
    for path_d, rgb, opacity in _APERTURE_PATHS:
        if template:
            NSColor.colorWithCalibratedRed_green_blue_alpha_(0, 0, 0, opacity).set()
        else:
            NSColor.colorWithCalibratedRed_green_blue_alpha_(
                rgb[0], rgb[1], rgb[2], opacity
            ).set()
        _draw_svg_path(path_d, scale)

    ctx.restoreGraphicsState()

    # Central dots (outside clip region)
    for cx, cy, r, rgb, opacity in [_CENTER_DOT_OUTER, _CENTER_DOT_INNER]:
        if template:
            NSColor.colorWithCalibratedRed_green_blue_alpha_(0, 0, 0, opacity).set()
        else:
            NSColor.colorWithCalibratedRed_green_blue_alpha_(
                rgb[0], rgb[1], rgb[2], opacity
            ).set()
        # Re-apply the flip transform for these circles
        ctx.saveGraphicsState()
        flip2 = NSAffineTransform.transform()
        flip2.translateXBy_yBy_(0, size)
        flip2.scaleXBy_yBy_(1, -1)
        flip2.concat()
        dot = NSBezierPath.bezierPath()
        dot.appendBezierPathWithOvalInRect_(
            NSMakeRect(
                (cx - r) * scale,
                (cy - r) * scale,
                r * 2 * scale,
                r * 2 * scale,
            )
        )
        dot.fill()
        ctx.restoreGraphicsState()

    image.unlockFocus()

    if template:
        image.setTemplate_(True)

    return image


def save_icon_to_path(size: int, template: bool = False, path: Path | None = None) -> Path:
    """Render the aperture mark and save as PNG. Returns the file path."""
    if path is None:
        icon_dir = Path.home() / ".agentic-gov" / "icons"
        icon_dir.mkdir(parents=True, exist_ok=True)
        suffix = "template" if template else "color"
        path = icon_dir / f"aperture-{size}-{suffix}.png"
    else:
        path.parent.mkdir(parents=True, exist_ok=True)

    image = create_aperture_image(size, template=template)
    tiff_data = image.TIFFRepresentation()

    bitmap = AppKit.NSBitmapImageRep.imageRepWithData_(tiff_data)
    png_data = bitmap.representationUsingType_properties_(
        AppKit.NSBitmapImageFileTypePNG, {}
    )
    png_data.writeToFile_atomically_(str(path), True)
    return path


def get_menubar_icon_path() -> Path:
    """Return path to a 22x22 template PNG for the menu bar.

    Checks three locations in order:
    1. PyInstaller bundle (icons/ directory inside _MEIPASS)
    2. Previously generated cache (~/.agentic-gov/icons/)
    3. Generates fresh icons to the cache as a last resort
    """
    bundle_dir = getattr(sys, "_MEIPASS", None)
    if bundle_dir:
        bundled = Path(bundle_dir) / "icons" / "menubar-template.png"
        if bundled.exists():
            return bundled

    icon_dir = Path.home() / ".agentic-gov" / "icons"
    icon_path = icon_dir / "menubar-template.png"
    if icon_path.exists():
        return icon_path

    save_icon_to_path(22, template=True, path=icon_path)

    retina_path = icon_dir / "menubar-template@2x.png"
    save_icon_to_path(44, template=True, path=retina_path)

    return icon_path

#!/usr/bin/env python3
"""Generate macOS icon assets for the Detec Agent app bundle.

Uses branding/Icon.icns as the master icon source. Generates:
  - DetecAgent.icns (copied from branding master)
  - AppIcon.iconset/ (extracted from .icns for reference)
  - menubar-template.png (22x22 monochrome template image)
  - menubar-template@2x.png (44x44 retina)

Menubar templates are rendered programmatically via collector.gui.assets
because they need monochrome treatment that isn't in the color .icns.

Usage:
    python packaging/macos/generate-icons.py

The script must be run on macOS (uses iconutil and PyObjC for menubar icons).
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "collector"))

OUTPUT_DIR = Path(__file__).resolve().parent / "icons"
MASTER_ICNS = PROJECT_ROOT / "branding" / "Icon.icns"


def _save_nsimage_as_png(image, path: Path, pixel_size: int) -> None:
    """Save an NSImage as a PNG file at exact pixel dimensions."""
    import AppKit

    tiff_data = image.TIFFRepresentation()
    bitmap = AppKit.NSBitmapImageRep.imageRepWithData_(tiff_data)

    new_rep = AppKit.NSBitmapImageRep.alloc().initWithBitmapDataPlanes_pixelsWide_pixelsHigh_bitsPerSample_samplesPerPixel_hasAlpha_isPlanar_colorSpaceName_bytesPerRow_bitsPerPixel_(
        None, pixel_size, pixel_size, 8, 4, True, False,
        AppKit.NSCalibratedRGBColorSpace, 0, 0,
    )
    new_rep.setSize_(AppKit.NSMakeSize(pixel_size, pixel_size))

    AppKit.NSGraphicsContext.saveGraphicsState()
    ctx = AppKit.NSGraphicsContext.graphicsContextWithBitmapImageRep_(new_rep)
    AppKit.NSGraphicsContext.setCurrentContext_(ctx)
    image.drawInRect_fromRect_operation_fraction_(
        AppKit.NSMakeRect(0, 0, pixel_size, pixel_size),
        AppKit.NSZeroRect,
        AppKit.NSCompositingOperationSourceOver,
        1.0,
    )
    AppKit.NSGraphicsContext.restoreGraphicsState()

    png_data = new_rep.representationUsingType_properties_(
        AppKit.NSBitmapImageFileTypePNG, {},
    )
    png_data.writeToFile_atomically_(str(path), True)


def copy_master_icns() -> Path:
    """Copy the branding master .icns into the build output directory."""
    if not MASTER_ICNS.exists():
        print(f"  ERROR: Master .icns not found at {MASTER_ICNS}")
        sys.exit(1)

    icns_path = OUTPUT_DIR / "DetecAgent.icns"
    shutil.copy2(MASTER_ICNS, icns_path)
    print(f"  Copied {MASTER_ICNS.name} -> {icns_path.name}")
    return icns_path


def extract_iconset(icns_path: Path) -> Path:
    """Extract .icns to .iconset for reference and verification."""
    iconset_dir = OUTPUT_DIR / "AppIcon.iconset"
    if iconset_dir.exists():
        shutil.rmtree(iconset_dir)

    subprocess.run(
        ["iconutil", "--convert", "iconset", "--output", str(iconset_dir), str(icns_path)],
        check=True,
    )

    for f in sorted(iconset_dir.iterdir()):
        print(f"  {f.name}")

    return iconset_dir


def generate_menubar_icons() -> None:
    """Generate menu bar template images (monochrome, 22x22 and 44x44).

    These are rendered programmatically because macOS template images
    need to be monochrome black — the OS applies light/dark mode coloring.
    """
    from collector.gui.assets import create_aperture_image

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    for size, suffix in [(22, ""), (44, "@2x")]:
        image = create_aperture_image(size, template=True)
        filename = f"menubar-template{suffix}.png"
        out_path = OUTPUT_DIR / filename
        _save_nsimage_as_png(image, out_path, size)
        print(f"  {filename} ({size}x{size}px)")


def main() -> None:
    print("Generating Detec Agent icon assets...")
    print(f"Master source: {MASTER_ICNS}")
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    print("\n[1/3] App icon (.icns):")
    icns_path = copy_master_icns()

    print("\n[2/3] Extract .iconset (for reference):")
    extract_iconset(icns_path)

    print("\n[3/3] Menu bar template icons:")
    generate_menubar_icons()

    print(f"\nAll icons generated in {OUTPUT_DIR}/")
    print(f"  .icns: {icns_path}")


if __name__ == "__main__":
    main()

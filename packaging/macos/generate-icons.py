#!/usr/bin/env python3
"""Generate macOS icon assets from the Detec aperture SVG.

Produces:
  - AppIcon.iconset/ with all required sizes for iconutil
  - DetecAgent.icns (via iconutil)
  - menubar-template.png (22x22 monochrome template image)
  - menubar-template@2x.png (44x44 retina)

Requirements: Pillow, cairosvg (or just Pillow with the SVG rendered via
the collector.gui.assets module which uses PyObjC).

Usage:
    python packaging/macos/generate-icons.py

The script must be run on macOS (uses iconutil and PyObjC).
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "collector"))

OUTPUT_DIR = Path(__file__).resolve().parent / "icons"

ICONSET_SIZES = [
    (16, 1),
    (16, 2),
    (32, 1),
    (32, 2),
    (128, 1),
    (128, 2),
    (256, 1),
    (256, 2),
    (512, 1),
    (512, 2),
]


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


def generate_iconset() -> Path:
    """Generate the .iconset directory with all required PNG sizes."""
    from collector.gui.assets import create_aperture_image

    iconset_dir = OUTPUT_DIR / "AppIcon.iconset"
    iconset_dir.mkdir(parents=True, exist_ok=True)

    for base_size, scale in ICONSET_SIZES:
        pixel_size = base_size * scale
        image = create_aperture_image(pixel_size)

        if scale == 1:
            filename = f"icon_{base_size}x{base_size}.png"
        else:
            filename = f"icon_{base_size}x{base_size}@{scale}x.png"

        out_path = iconset_dir / filename
        _save_nsimage_as_png(image, out_path, pixel_size)
        print(f"  {filename} ({pixel_size}x{pixel_size}px)")

    return iconset_dir


def generate_icns(iconset_dir: Path) -> Path:
    """Convert .iconset to .icns using macOS iconutil."""
    icns_path = OUTPUT_DIR / "DetecAgent.icns"
    subprocess.run(
        ["iconutil", "--convert", "icns", "--output", str(icns_path), str(iconset_dir)],
        check=True,
    )
    print(f"  {icns_path.name}")
    return icns_path


def generate_menubar_icons() -> None:
    """Generate menu bar template images (monochrome, 22x22 and 44x44)."""
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
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    print("\n[1/3] App icon (.iconset):")
    iconset_dir = generate_iconset()

    print("\n[2/3] App icon (.icns):")
    icns_path = generate_icns(iconset_dir)

    print("\n[3/3] Menu bar template icons:")
    generate_menubar_icons()

    print(f"\nAll icons generated in {OUTPUT_DIR}/")
    print(f"  .icns: {icns_path}")


if __name__ == "__main__":
    main()

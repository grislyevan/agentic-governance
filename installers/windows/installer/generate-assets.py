"""Generate Inno Setup branding assets from the Detec master icon.

Produces two BMP files required by the installer wizard:
  - wizard-image.bmp     (164x314)  sidebar on Welcome/Finish pages
  - wizard-small-image.bmp (55x55) header icon on interior pages

Requires: pip install Pillow

Usage:
    python generate-assets.py
"""

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[3]
ICON_SRC = ROOT / "branding" / "Icon.png"
OUT_DIR = Path(__file__).resolve().parent
FONTS_DIR = ROOT / "branding" / "fonts"

SLATE_900 = (15, 23, 42)
SLATE_100 = (241, 245, 249)
SLATE_400 = (148, 163, 184)
PRIMARY_500 = (99, 102, 241)

TAGLINE = "Endpoint governance\nfor agentic AI"


def _load_font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    """Try bundled font first, then system fonts, then Pillow default."""
    candidates = [
        FONTS_DIR / "Inter.ttf",
        FONTS_DIR / "inter.ttf",
        "arial.ttf",
        "segoeui.ttf",
        "/System/Library/Fonts/Helvetica.ttc",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    ]
    for path in candidates:
        try:
            return ImageFont.truetype(str(path), size)
        except OSError:
            continue
    return ImageFont.load_default(size=size)


def generate_wizard_image() -> None:
    """164x314 sidebar image: dark background with centered aperture mark."""
    width, height = 164, 314
    canvas = Image.new("RGB", (width, height), SLATE_900)

    mark = Image.open(ICON_SRC).convert("RGBA")
    mark_size = 100
    mark = mark.resize((mark_size, mark_size), Image.LANCZOS)
    x = (width - mark_size) // 2
    y = 72
    canvas.paste(mark, (x, y), mark)

    draw = ImageDraw.Draw(canvas)
    line_y = y + mark_size + 24
    draw.line([(32, line_y), (width - 32, line_y)], fill=PRIMARY_500, width=2)

    # Brand name
    text_y = line_y + 16
    name_font = _load_font(20)
    bbox = draw.textbbox((0, 0), "Detec", font=name_font)
    text_w = bbox[2] - bbox[0]
    draw.text(((width - text_w) // 2, text_y), "Detec", fill=SLATE_100, font=name_font)

    # Descriptor tagline in a smaller, muted weight
    tagline_font = _load_font(10)
    tagline_y = text_y + (bbox[3] - bbox[1]) + 10
    draw.multiline_text(
        (width // 2, tagline_y),
        TAGLINE,
        fill=SLATE_400,
        font=tagline_font,
        anchor="ma",
        align="center",
        spacing=3,
    )

    canvas.save(OUT_DIR / "wizard-image.bmp", "BMP")
    print(f"  wizard-image.bmp ({width}x{height})")


def generate_wizard_small_image() -> None:
    """55x55 header icon: dark background with small aperture mark."""
    width, height = 55, 55
    canvas = Image.new("RGB", (width, height), SLATE_900)

    mark = Image.open(ICON_SRC).convert("RGBA")
    mark_size = 40
    mark = mark.resize((mark_size, mark_size), Image.LANCZOS)
    x = (width - mark_size) // 2
    y = (height - mark_size) // 2
    canvas.paste(mark, (x, y), mark)

    canvas.save(OUT_DIR / "wizard-small-image.bmp", "BMP")
    print(f"  wizard-small-image.bmp ({width}x{height})")


if __name__ == "__main__":
    if not ICON_SRC.exists():
        raise FileNotFoundError(f"Master icon not found: {ICON_SRC}")
    if not FONTS_DIR.exists():
        print(f"  Note: {FONTS_DIR} not found; will use system fonts.")
    print("Generating installer assets...")
    generate_wizard_image()
    generate_wizard_small_image()
    print("Done.")

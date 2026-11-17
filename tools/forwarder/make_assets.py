#!/usr/bin/env python3
"""Draw the forwarder's HOME Menu icon and banner (no game art).

    python tools/forwarder/make_assets.py

Writes icon.png (48x48) and banner.png (256x128) beside this script. Both are
original graphics: a dark field, the word SINJOH, and the platinum-red accent
the game's wide bands use. Run again after changing the design; the checked-in
PNGs are the build inputs.
"""
from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

HERE = Path(__file__).resolve().parent
BOLD = Path(r"C:\Windows\Fonts\segoeuib.ttf")
REGULAR = Path(r"C:\Windows\Fonts\segoeui.ttf")

INK = (12, 14, 20, 255)
INK_TOP = (24, 28, 38, 255)
PAPER = (226, 229, 236, 255)
STEEL = (138, 146, 162, 255)
RED = (168, 34, 46, 255)


def font(path: Path, size: int) -> ImageFont.FreeTypeFont:
    try:
        return ImageFont.truetype(str(path), size)
    except OSError:
        return ImageFont.load_default(size)


def gradient(size: tuple[int, int]) -> Image.Image:
    image = Image.new("RGBA", size)
    draw = ImageDraw.Draw(image)
    for y in range(size[1]):
        t = y / max(size[1] - 1, 1)
        colour = tuple(round(INK_TOP[i] + (INK[i] - INK_TOP[i]) * t) for i in range(3))
        draw.line((0, y, size[0], y), fill=colour + (255,))
    return image


def icon() -> Image.Image:
    image = gradient((48, 48))
    draw = ImageDraw.Draw(image)
    draw.rectangle((0, 0, 47, 2), fill=RED)
    draw.arc((6, 8, 42, 44), start=-60, end=235, fill=RED, width=2)
    draw.text((24, 23), "S", font=font(BOLD, 30), fill=PAPER, anchor="mm")
    return image


def banner() -> Image.Image:
    image = gradient((256, 128))
    draw = ImageDraw.Draw(image)
    draw.rectangle((0, 0, 5, 127), fill=RED)
    draw.ellipse((176, 8, 296, 128), outline=(46, 51, 64, 255), width=3)
    draw.ellipse((196, 28, 276, 108), outline=(63, 69, 84, 255), width=1)
    draw.text((22, 20), "SINJOH", font=font(BOLD, 44), fill=PAPER)
    draw.text((24, 76), "POKEMON PLATINUM", font=font(REGULAR, 13), fill=STEEL)
    draw.text((24, 96), "ORIGINAL 3DS", font=font(REGULAR, 10), fill=(94, 101, 116, 255))
    return image


def main() -> int:
    icon().save(HERE / "icon.png")
    banner().save(HERE / "banner.png")
    print(f"wrote {HERE / 'icon.png'}")
    print(f"wrote {HERE / 'banner.png'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

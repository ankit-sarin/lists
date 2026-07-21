"""Reproducible PWA icon generator for Lists.

Brand (digitalsurgeon-brand, authoritative for color/type):
  Field  = Forest Teal  #0A5E56
  Glyph  = Mist White    #EEF5F4
  No gradients. Glyph is a simple checklist mark (three rows: checkbox + line),
  which reads as a "list" app icon without a font dependency.

Outputs (static/icons/):
  icon-192.png            192x192  purpose "any"      (rounded field, transparent corners)
  icon-512.png            512x512  purpose "any"      (rounded field, transparent corners)
  icon-512-maskable.png   512x512  purpose "maskable" (full-bleed field, glyph in ~80% safe zone)
  apple-touch-icon.png    180x180  iOS home screen    (full-bleed field, iOS rounds it)

Run:  python static/make_icons.py
"""
import os
from PIL import Image, ImageDraw

TEAL = (10, 94, 86, 255)     # #0A5E56 Forest Teal
MIST = (238, 245, 244, 255)  # #EEF5F4 Mist White

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "icons")


def _draw_glyph(draw: ImageDraw.ImageDraw, size: int, safe: float):
    """Draw a centered checklist glyph occupying `safe` fraction of the canvas."""
    box = size * safe
    x0 = (size - box) / 2
    y0 = (size - box) / 2
    rows = 3
    gap = box * 0.14
    row_h = (box - gap * (rows - 1)) / rows
    cb = row_h * 0.82                       # checkbox side
    stroke = max(2, int(size * 0.016))      # line weight
    line_x = x0 + cb + box * 0.10           # where the "text" line starts
    line_w = x0 + box - line_x              # its length
    line_h = max(2, int(row_h * 0.34))

    for i in range(rows):
        ry = y0 + i * (row_h + gap)
        # checkbox outline (rounded square)
        draw.rounded_rectangle(
            [x0, ry, x0 + cb, ry + cb],
            radius=cb * 0.22, outline=MIST, width=stroke,
        )
        # checkmark inside the first two rows
        if i < 2:
            p1 = (x0 + cb * 0.22, ry + cb * 0.52)
            p2 = (x0 + cb * 0.44, ry + cb * 0.74)
            p3 = (x0 + cb * 0.80, ry + cb * 0.28)
            draw.line([p1, p2, p3], fill=MIST, width=stroke, joint="curve")
        # the "item text" line, vertically centered on the row
        ly = ry + (cb - line_h) / 2
        draw.rounded_rectangle(
            [line_x, ly, line_x + line_w, ly + line_h],
            radius=line_h / 2, fill=MIST,
        )


def make(size: int, path: str, maskable: bool = False, apple: bool = False):
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    if maskable or apple:
        # full-bleed teal field (platform applies its own mask/rounding)
        draw.rectangle([0, 0, size, size], fill=TEAL)
    else:
        # rounded teal field with transparent corners
        draw.rounded_rectangle([0, 0, size - 1, size - 1], radius=int(size * 0.22), fill=TEAL)
    # glyph safe fraction: keep well within the 80% maskable safe zone
    safe = 0.50 if maskable else (0.60 if apple else 0.56)
    _draw_glyph(draw, size, safe)
    img.save(path, "PNG")
    print("wrote", os.path.relpath(path, HERE), f"({size}x{size})")


if __name__ == "__main__":
    os.makedirs(OUT, exist_ok=True)
    make(192, os.path.join(OUT, "icon-192.png"))
    make(512, os.path.join(OUT, "icon-512.png"))
    make(512, os.path.join(OUT, "icon-512-maskable.png"), maskable=True)
    make(180, os.path.join(OUT, "apple-touch-icon.png"), apple=True)

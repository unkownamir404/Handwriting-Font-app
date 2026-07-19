"""
Generates the printable worksheet (template.png) the user writes their
handwriting into, plus template_layout.json which records, in the
template's own pixel coordinate space:
  - the 4 corner marker boxes (used later to perspective-correct a photo/scan)
  - the writing-box rectangle for every character

Run:  python template_generator.py
Output goes to output/template.png and output/template_layout.json
"""
import json
import os
from PIL import Image, ImageDraw, ImageFont

# ---- characters the user will hand-write, one per box ----
CHARACTERS = list("abcdefghijklmnopqrstuvwxyz") + list("ABCDEFGHIJKLMNOPQRSTUVWXYZ")

# ---- page / grid geometry (pixels, ~200 DPI on US Letter) ----
PAGE_W, PAGE_H = 1700, 2200
MARGIN = 60
MARKER_SIZE = 50          # solid black square corner markers
COLS, ROWS = 8, 7         # 56 boxes, enough for 52 characters
CELL_W = (PAGE_W - 2 * MARGIN) // COLS
CELL_H = (PAGE_H - 2 * MARGIN - 120) // ROWS  # leave header room
GRID_TOP = MARGIN + 120

OUT_DIR = os.path.join(os.path.dirname(__file__), "output")
os.makedirs(OUT_DIR, exist_ok=True)


def _font(size):
    try:
        return ImageFont.truetype(
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", size
        )
    except Exception:
        return ImageFont.load_default()


def generate():
    img = Image.new("RGB", (PAGE_W, PAGE_H), "white")
    draw = ImageDraw.Draw(img)

    # --- corner markers (solid black squares, used for perspective correction) ---
    marker_positions = {
        "top_left": (MARGIN, MARGIN),
        "top_right": (PAGE_W - MARGIN - MARKER_SIZE, MARGIN),
        "bottom_left": (MARGIN, PAGE_H - MARGIN - MARKER_SIZE),
        "bottom_right": (PAGE_W - MARGIN - MARKER_SIZE, PAGE_H - MARGIN - MARKER_SIZE),
    }
    for (x, y) in marker_positions.values():
        draw.rectangle([x, y, x + MARKER_SIZE, y + MARKER_SIZE], fill="black")

    # --- title ---
    draw.text((MARGIN, MARGIN + 10), "      Handwriting Font Worksheet", font=_font(36), fill="black")
    draw.text(
        (MARGIN, MARGIN + 55),
        "Write ONE character per box, in your natural cursive. Keep the pen strokes inside the box.",
        font=_font(20),
        fill="gray",
    )

    # --- character boxes ---
    label_font = _font(16)
    cell_boxes = {}
    for i, ch in enumerate(CHARACTERS):
        col = i % COLS
        row = i // COLS
        x1 = MARGIN + col * CELL_W
        y1 = GRID_TOP + row * CELL_H
        x2 = x1 + CELL_W - 10
        y2 = y1 + CELL_H - 10

        draw.rectangle([x1, y1, x2, y2], outline=(180, 180, 180), width=2)
        label = ch if ch.islower() else ch + " (cap)"
        draw.text((x1 + 4, y1 + 2), label, font=label_font, fill=(160, 160, 160))
        # writable area excludes the label strip at the top of the box
        cell_boxes[ch] = [x1 + 6, y1 + 22, x2 - 6, y2 - 6]

    img_path = os.path.join(OUT_DIR, "template.png")
    img.save(img_path)

    layout = {
        "page_size": [PAGE_W, PAGE_H],
        "markers": {k: [v[0], v[1], v[0] + MARKER_SIZE, v[1] + MARKER_SIZE] for k, v in marker_positions.items()},
        "cells": cell_boxes,
    }
    layout_path = os.path.join(OUT_DIR, "template_layout.json")
    with open(layout_path, "w") as f:
        json.dump(layout, f, indent=2)

    print(f"Wrote {img_path}")
    print(f"Wrote {layout_path}")
    return img_path, layout_path


if __name__ == "__main__":
    generate()

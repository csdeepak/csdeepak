#!/usr/bin/env python3
"""
generate_portrait.py — turn a real headshot into a premium cyan portrait SVG.

Derived from the actual photo, so the likeness (hair, glasses, beard, smile,
proportions) is preserved rather than invented. Two layers combine into a
"technical illustration" rather than an AI painting:

  1. HALFTONE FILL  — dot size/opacity encode *brightness*, so the lit face
                      glows on black (hologram feel), background removed.
  2. WIREFRAME EDGES — Sobel-style edges keep hairstyle, glasses frame, jaw
                      and lapels as cyan line-art even in dark regions.

Outputs:
  assets/portrait.svg            (deliverable vector, hand-editable)
  scripts/_portrait_preview.png  (raster QA preview)

Usage:  python scripts/generate_portrait.py
"""
from __future__ import annotations
import os
from collections import deque
import numpy as np
from PIL import Image, ImageOps, ImageDraw, ImageFilter

# ── config ────────────────────────────────────────────────────────────────
SRC       = "photo"
OUT_SVG   = "assets/portrait.svg"
OUT_PREV  = "scripts/_portrait_preview.png"

CROP      = (150, 55, 1105, 1010)   # (l,t,r,b) head + shoulders
COLS      = 140                     # dot columns (grid resolution)
BG_LIGHT  = 200                     # >= this & border-connected  => background
FILL_LIFT = 0.10                    # brightness floor before a fill-dot appears
FILL_GAM  = 0.75                    # <1 lifts mid-tones (keeps skin present)
EDGE_K    = 1.9                     # edge gain (wireframe accents)
EDGE_MIN  = 0.16                    # edge below this ignored
MESH_MIN  = 0.16                    # min dot radius for subject mesh (pixel-mesh floor)
DOT_MAX   = 0.60                    # max dot radius as fraction of spacing
BG        = "#090909"

# ── load ────────────────────────────────────────────────────────────────────
def load():
    fname = next(f for f in os.listdir(SRC)
                 if f.lower().endswith((".jpg", ".jpeg", ".png")))
    img = Image.open(os.path.join(SRC, fname)).convert("RGB").crop(CROP)
    g = ImageOps.autocontrast(ImageOps.grayscale(img), cutoff=1)
    return g

# ── subject mask: flood light background inward from the border ──────────────
def subject_mask(g, cols, rows):
    m = 200
    small = g.resize((m, m), Image.BILINEAR)
    arr = np.asarray(small)
    light = arr >= BG_LIGHT
    bg = np.zeros_like(light, bool)
    dq = deque()
    for i in range(m):
        for (y, x) in ((0, i), (m - 1, i), (i, 0), (i, m - 1)):
            if light[y, x] and not bg[y, x]:
                bg[y, x] = True
                dq.append((y, x))
    while dq:
        y, x = dq.popleft()
        for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            ny, nx = y + dy, x + dx
            if 0 <= ny < m and 0 <= nx < m and light[ny, nx] and not bg[ny, nx]:
                bg[ny, nx] = True
                dq.append((ny, nx))
    subj = (~bg).astype(np.uint8) * 255
    subj_img = Image.fromarray(subj).filter(ImageFilter.MaxFilter(3))
    return np.asarray(subj_img.resize((cols, rows), Image.BILINEAR)) > 120

# ── build dots ───────────────────────────────────────────────────────────────
def build():
    g = load()
    w, h = g.size
    spacing = w / COLS
    rows = int(h / spacing)

    subj = subject_mask(g, COLS, rows)

    bright = np.asarray(g.filter(ImageFilter.GaussianBlur(0.6))
                        .resize((COLS, rows), Image.BILINEAR)) / 255.0
    edges = np.asarray(g.filter(ImageFilter.GaussianBlur(0.8))
                        .filter(ImageFilter.FIND_EDGES)
                        .resize((COLS, rows), Image.BILINEAR)) / 255.0
    if edges.max() > 0:
        edges = edges / edges.max()

    dots = []
    for j in range(rows):
        stagger = (spacing / 2) if (j % 2) else 0.0
        for i in range(COLS):
            if not subj[j, i]:
                continue
            b = bright[j, i]
            fill = max(0.0, (b - FILL_LIFT) / (1 - FILL_LIFT)) ** FILL_GAM
            e = max(0.0, (edges[j, i] - EDGE_MIN)) * EDGE_K
            inten = min(1.0, max(fill, e * 0.7))
            # every subject cell draws a dot: faint pixel-mesh in shadow masses
            # (hair / suit), bright halftone where the face is lit, edge accents.
            r = (MESH_MIN + (1 - MESH_MIN) * inten) * DOT_MAX * spacing
            cx = i * spacing + stagger + spacing / 2
            cy = j * spacing + spacing / 2
            op = 0.13 + 0.62 * inten
            dots.append((cx, cy, r, op))
    return dots, COLS * spacing, rows * spacing

# ── raster preview ────────────────────────────────────────────────────────────
def write_preview(dots, W, H):
    s = 3
    im = Image.new("RGB", (int(W * s), int(H * s)), (9, 9, 9))
    dr = ImageDraw.Draw(im, "RGBA")
    for cx, cy, r, op in dots:
        x, y, rr = cx * s, cy * s, r * s
        dr.ellipse([x - rr, y - rr, x + rr, y + rr], fill=(66, 245, 255, int(op * 255)))
    im.save(OUT_PREV)

# ── SVG emit ─────────────────────────────────────────────────────────────────
def write_svg(dots, W, H):
    W, H = round(W, 1), round(H, 1)
    body = "".join(
        f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="{r:.2f}" opacity="{op:.2f}"/>'
        for cx, cy, r, op in dots)
    svg = f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" role="img" aria-label="C S Deepak — halftone portrait">
  <title>C S Deepak</title>
  <desc>Cyan halftone + wireframe portrait derived from a photograph. Editable vector.</desc>
  <defs>
    <radialGradient id="pv" cx="0.5" cy="0.4" r="0.78">
      <stop offset="0.55" stop-color="#090909" stop-opacity="0"/>
      <stop offset="1" stop-color="#090909" stop-opacity="0.6"/>
    </radialGradient>
    <clipPath id="pcrop"><rect width="{W}" height="{H}"/></clipPath>
  </defs>
  <g clip-path="url(#pcrop)">
    <rect width="{W}" height="{H}" fill="{BG}"/>
    <!-- portrait: tone = dot radius + opacity -->
    <g fill="#42F5FF">{body}</g>
    <rect width="{W}" height="{H}" fill="url(#pv)"/>
    <!-- slow scan line -->
    <rect x="0" width="{W}" height="2" fill="#42F5FF" opacity="0.10">
      <animate attributeName="y" values="-4;{H};-4" dur="6.5s" repeatCount="indefinite"/>
    </rect>
    <!-- corner ticks -->
    <g stroke="#42F5FF" stroke-width="1.4" fill="none" opacity="0.65">
      <path d="M10 24 V10 H24"/><path d="M{W-10:.1f} 24 V10 H{W-24:.1f}"/>
      <path d="M10 {H-24:.1f} V{H-10:.1f} H24"/><path d="M{W-10:.1f} {H-24:.1f} V{H-10:.1f} H{W-24:.1f}"/>
    </g>
  </g>
</svg>'''
    with open(OUT_SVG, "w", encoding="utf-8") as f:
        f.write(svg)
    return len(svg)

def main():
    dots, W, H = build()
    write_preview(dots, W, H)
    size = write_svg(dots, W, H)
    print(f"dots={len(dots)}  svg={size/1024:.1f}KB  -> {OUT_SVG}")

if __name__ == "__main__":
    main()

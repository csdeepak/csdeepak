#!/usr/bin/env python3
"""
generate_portrait.py — premium cyan vector portrait from a real headshot.

Not pure halftone. Layered like a research illustration, derived from the
actual photo so the likeness is preserved (hair, glasses, beard, smile,
proportions):

  L1  SILHOUETTE   soft blurred cyan form  → a large, grounded shape
  L2  SHADING      uniform vector mesh, opacity = brightness (adaptive)
  L3  HALFTONE     selective dot swell in mid-tones only (texture)
  L4  EDGES        crisp cyan accents on hair / glasses / jaw / lapel

Background is removed (border flood-fill), so the subject sits on pure black.

Outputs:
  assets/portrait.svg            (deliverable vector)
  scripts/_portrait_preview.png  (QA raster)

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

CROP      = (170, 60, 1090, 1015)   # (l,t,r,b) head + shoulders, tightened
COLS      = 152                     # mesh columns
BG_LIGHT  = 198                     # >= this & border-connected => background
GAMMA     = 0.80                    # lift mid-tones (keeps face present)
EDGE_K    = 2.1
CYAN      = (66, 245, 255)          # #42F5FF
ACCENT    = "#42F5FF"

# ── load ────────────────────────────────────────────────────────────────────
def load():
    fname = next(f for f in os.listdir(SRC)
                 if f.lower().endswith((".jpg", ".jpeg", ".png")))
    img = Image.open(os.path.join(SRC, fname)).convert("RGB").crop(CROP)
    return ImageOps.autocontrast(ImageOps.grayscale(img), cutoff=1)

# ── subject mask: flood the light background inward from the border ──────────
def subject_mask(g, cols, rows):
    m = 220
    arr = np.asarray(g.resize((m, m), Image.BILINEAR))
    light = arr >= BG_LIGHT
    bg = np.zeros_like(light, bool)
    dq = deque()
    for i in range(m):
        for y, x in ((0, i), (m - 1, i), (i, 0), (i, m - 1)):
            if light[y, x] and not bg[y, x]:
                bg[y, x] = True; dq.append((y, x))
    while dq:
        y, x = dq.popleft()
        for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            ny, nx = y + dy, x + dx
            if 0 <= ny < m and 0 <= nx < m and light[ny, nx] and not bg[ny, nx]:
                bg[ny, nx] = True; dq.append((ny, nx))
    subj = Image.fromarray((~bg).astype(np.uint8) * 255)
    subj = subj.filter(ImageFilter.MaxFilter(5)).filter(ImageFilter.MinFilter(3))
    return np.asarray(subj.resize((cols, rows), Image.BILINEAR)) > 120

# ── build layers ──────────────────────────────────────────────────────────────
def build():
    g = load()
    w, h = g.size
    spacing = w / COLS
    rows = int(h / spacing)

    subj = subject_mask(g, COLS, rows)
    bright = (np.asarray(g.filter(ImageFilter.GaussianBlur(0.7))
              .resize((COLS, rows), Image.BILINEAR)) / 255.0) ** GAMMA
    edges = np.asarray(g.filter(ImageFilter.GaussianBlur(0.8))
                       .filter(ImageFilter.FIND_EDGES)
                       .filter(ImageFilter.MaxFilter(3))
                       .resize((COLS, rows), Image.BILINEAR)) / 255.0
    if edges.max() > 0:
        edges /= edges.max()

    # L1 silhouette spans (per row runs of subject)
    spans = []
    for j in range(rows):
        i = 0
        while i < COLS:
            if subj[j, i]:
                s = i
                while i < COLS and subj[j, i]:
                    i += 1
                spans.append((s * spacing, j * spacing, (i - s) * spacing, spacing))
            else:
                i += 1

    # L2/L3/L4 dots
    mesh, halftone, edge = [], [], []
    for j in range(rows):
        stg = (spacing / 2) if (j % 2) else 0.0
        for i in range(COLS):
            if not subj[j, i]:
                continue
            b, e = bright[j, i], edges[j, i]
            cx = i * spacing + stg + spacing / 2
            cy = j * spacing + spacing / 2
            # edge accent
            if e > 0.34:
                edge.append((cx, cy, 0.40 * spacing, min(1.0, e * EDGE_K)))
            # shading mesh (skip near-black interior; silhouette carries it)
            if b > 0.16 or e > 0.34:
                op = 0.12 + 0.80 * b
                mesh.append((cx, cy, 0.30 * spacing, op))
                # selective halftone swell in mid-tones
                if 0.34 < b < 0.82:
                    halftone.append((cx, cy, (0.34 + 0.34 * b) * spacing, 0.18 + 0.22 * b))
    return dict(spans=spans, mesh=mesh, halftone=halftone, edge=edge,
                W=COLS * spacing, H=rows * spacing, sp=spacing)

# ── raster preview ────────────────────────────────────────────────────────────
def write_preview(d):
    s = 3
    im = Image.new("RGB", (int(d["W"] * s), int(d["H"] * s)), (9, 9, 9))
    dr = ImageDraw.Draw(im, "RGBA")
    for x, y, ww, hh in d["spans"]:
        dr.rectangle([x*s, y*s, (x+ww)*s, (y+hh)*s], fill=(*CYAN, 22))
    for grp, base in ((d["mesh"], 1), (d["halftone"], 1), (d["edge"], 1)):
        for cx, cy, r, op in grp:
            dr.ellipse([(cx-r)*s, (cy-r)*s, (cx+r)*s, (cy+r)*s],
                       fill=(*CYAN, int(min(1, op) * 255)))
    im.save(OUT_PREV)

# ── SVG emit (opacity-bucketed groups → smaller file) ─────────────────────────
def bucket(dots):
    groups = {}
    for cx, cy, r, op in dots:
        key = max(1, min(10, round(op * 10)))
        groups.setdefault(key, []).append(f'<circle cx="{cx:.0f}" cy="{cy:.0f}" r="{r:.1f}"/>')
    out = []
    for key in sorted(groups):
        out.append(f'<g opacity="{key/10:.1f}">{"".join(groups[key])}</g>')
    return "".join(out)

def write_svg(d):
    W, H = round(d["W"], 1), round(d["H"], 1)
    spans = "".join(
        f'<rect x="{x:.0f}" y="{y:.0f}" width="{w:.1f}" height="{h:.1f}"/>'
        for x, y, w, h in d["spans"])
    svg = f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" role="img" aria-label="C S Deepak — portrait">
  <title>C S Deepak</title>
  <desc>Cyan vector portrait derived from a photograph — silhouette, adaptive shading, selective halftone, edge accents.</desc>
  <defs>
    <linearGradient id="pSil" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0" stop-color="#42F5FF" stop-opacity="0.20"/>
      <stop offset="1" stop-color="#42F5FF" stop-opacity="0.05"/>
    </linearGradient>
    <radialGradient id="pGlow" cx="0.5" cy="0.42" r="0.62">
      <stop offset="0" stop-color="#42F5FF" stop-opacity="0.14"/>
      <stop offset="1" stop-color="#42F5FF" stop-opacity="0"/>
    </radialGradient>
    <radialGradient id="pVig" cx="0.5" cy="0.42" r="0.78">
      <stop offset="0.6" stop-color="#090909" stop-opacity="0"/>
      <stop offset="1" stop-color="#090909" stop-opacity="0.55"/>
    </radialGradient>
    <filter id="pBlur" x="-6%" y="-6%" width="112%" height="112%"><feGaussianBlur stdDeviation="{d["sp"]*0.9:.1f}"/></filter>
    <clipPath id="pClip"><rect width="{W}" height="{H}"/></clipPath>
  </defs>
  <g clip-path="url(#pClip)">
    <rect width="{W}" height="{H}" fill="#090909"/>
    <rect width="{W}" height="{H}" fill="url(#pGlow)"/>
    <!-- L1 silhouette -->
    <g fill="url(#pSil)" filter="url(#pBlur)">{spans}</g>
    <!-- L2 adaptive shading mesh -->
    <g fill="{ACCENT}">{bucket(d["mesh"])}</g>
    <!-- L3 selective halftone -->
    <g fill="{ACCENT}">{bucket(d["halftone"])}</g>
    <!-- L4 edge accents -->
    <g fill="{ACCENT}">{bucket(d["edge"])}</g>
    <rect width="{W}" height="{H}" fill="url(#pVig)"/>
    <!-- slow scan line -->
    <rect x="0" width="{W}" height="2" fill="{ACCENT}" opacity="0.09">
      <animate attributeName="y" values="-4;{H};-4" dur="7s" repeatCount="indefinite"/>
    </rect>
    <!-- corner ticks -->
    <g stroke="{ACCENT}" stroke-width="1.4" fill="none" opacity="0.6">
      <path d="M10 24 V10 H24"/><path d="M{W-10:.0f} 24 V10 H{W-24:.0f}"/>
      <path d="M10 {H-24:.0f} V{H-10:.0f} H24"/><path d="M{W-10:.0f} {H-24:.0f} V{H-10:.0f} H{W-24:.0f}"/>
    </g>
  </g>
</svg>'''
    with open(OUT_SVG, "w", encoding="utf-8") as f:
        f.write(svg)
    return len(svg)

def main():
    d = build()
    write_preview(d)
    size = write_svg(d)
    n = len(d["mesh"]) + len(d["halftone"]) + len(d["edge"])
    print(f"spans={len(d['spans'])} dots={n} svg={size/1024:.0f}KB -> {OUT_SVG}")

if __name__ == "__main__":
    main()

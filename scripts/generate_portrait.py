#!/usr/bin/env python3
"""
generate_portrait.py — vector-contour portrait renderer (research-illustration grade).

Ground-up redesign. NOT a dot/halftone filter. The face is reconstructed as
smooth, editable vector regions so it reads as a premium illustration and stays
immediately recognizable as the source photograph.

Pipeline (deterministic, no randomness):
  1. background removal        border flood-fill -> subject mask
  2. face segmentation         subject-only percentile contrast normalization
  3. large silhouette          dark-teal body fill on subject bbox (~80% canvas)
  4. adaptive cyan shading     luminance level-sets, traced to smooth polygons,
                               stacked as translucent cyan layers (gradient tone)
  5. edge enhancement          Sobel linework, traced + filled crisp
  6. gradient mesh             SVG gradients on silhouette + face glow
  7. selective halftone        fine dots in one mid-tone band only (texture)
  8. fine detail restoration   darkest features carved back to black
  9. SVG optimization          integer coords, evenodd fills, grouped opacity

Core engine: marching-squares contour extraction on binary level masks, chained
into closed loops and Chaikin-smoothed into clean curves.

Outputs:
  assets/portrait.svg            (deliverable vector, < 500 KB)
  scripts/_portrait_preview.png  (QA raster)

Usage:  python scripts/generate_portrait.py
"""
from __future__ import annotations
import os
from collections import deque, defaultdict
import numpy as np
from PIL import Image, ImageOps, ImageFilter

# ── configuration ───────────────────────────────────────────────────────────
SRC        = "photo"
OUT_SVG    = "assets/portrait.svg"
OUT_PREV   = "scripts/_portrait_preview.png"

CROP       = (170, 60, 1090, 1015)     # head + shoulders
GRID_W     = 200                        # working resolution (columns)
CELL_PX    = 5.0                        # grid cell -> canvas px
MARGIN     = 0.11                       # canvas padding around subject (=> ~80% fill)

LEVELS     = 8                          # luminance shading layers
LAYER_OP   = 0.15                       # per-layer cyan opacity (stacks to tone)
LO, HI     = 0.14, 0.90                 # brightness band covered by the levels
EDGE_T     = 0.22                       # Sobel edge threshold (frac of max)
DARK_T     = 0.085                      # below this brightness = carved feature
CHAIKIN    = 2                          # contour smoothing iterations
RDP_EPS    = 0.85                       # polyline simplification (grid units)
MIN_DIM    = 2.3                        # drop loops smaller than this (grid units)

ACCENT     = "#42F5FF"
BG         = "#090909"


# ── image preparation ─────────────────────────────────────────────────────────
def load_rgb():
    fname = next(f for f in os.listdir(SRC)
                 if f.lower().endswith((".jpg", ".jpeg", ".png")))
    return Image.open(os.path.join(SRC, fname)).convert("RGB").crop(CROP)


def subject_mask(gray, w, h):
    """Flood the light background inward from the border; everything else = subject."""
    m = 240
    arr = np.asarray(gray.resize((m, m), Image.BILINEAR))
    light = arr >= 196
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
    return np.asarray(subj.resize((w, h), Image.NEAREST)) > 127


def normalized_luma(gray, mask):
    """Subject-only percentile contrast stretch + mild S-curve -> high-contrast face."""
    arr = np.asarray(gray).astype(np.float32)
    vals = arr[mask]
    lo, hi = np.percentile(vals, 3), np.percentile(vals, 97)
    out = np.clip((arr - lo) / max(1.0, hi - lo), 0, 1)
    out = out * out * (3 - 2 * out)               # smoothstep S-curve -> contrast
    out[~mask] = 0.0
    return out


def sobel(field):
    kx = np.array([[-1, 0, 1], [-2, 0, 2], [-1, 0, 1]], np.float32)
    ky = kx.T
    def conv(a, k):
        p = np.pad(a, 1, mode="edge")
        return sum(k[u, v] * p[u:u + a.shape[0], v:v + a.shape[1]]
                   for u in range(3) for v in range(3))
    g = np.hypot(conv(field, kx), conv(field, ky))
    return g / (g.max() + 1e-6)


# ── marching squares: binary field -> smooth closed polygons ──────────────────
def contours(binary):
    """binary: 2-D bool. Returns list of closed loops (each: list of (x, y) grid coords)."""
    f = np.pad(binary.astype(np.int8), 1)          # zero border so all loops close
    a = f > 0
    tl, tr = a[:-1, :-1], a[:-1, 1:]
    br, bl = a[1:, 1:], a[1:, :-1]
    active = (tl | tr | br | bl) & ~(tl & tr & br & bl)
    ii, jj = np.nonzero(active)

    # half-integer edge midpoints (padded grid coords; unpad by -1 later)
    segs = []
    ff = f.astype(np.float32)
    for i, j in zip(ii.tolist(), jj.tolist()):
        a_tl, a_tr, a_br, a_bl = a[i, j], a[i, j + 1], a[i + 1, j + 1], a[i + 1, j]
        pts = {}
        if a_tl != a_tr: pts["T"] = (j + 0.5, i)
        if a_tr != a_br: pts["R"] = (j + 1.0, i + 0.5)
        if a_br != a_bl: pts["B"] = (j + 0.5, i + 1)
        if a_bl != a_tl: pts["L"] = (j, i + 0.5)
        keys = list(pts)
        if len(keys) == 2:
            segs.append((pts[keys[0]], pts[keys[1]]))
        elif len(keys) == 4:                        # saddle – resolve by cell mean
            center = (ff[i, j] + ff[i, j + 1] + ff[i + 1, j + 1] + ff[i + 1, j]) / 4
            if center > 0.5:
                segs.append((pts["T"], pts["R"])); segs.append((pts["B"], pts["L"]))
            else:
                segs.append((pts["T"], pts["L"])); segs.append((pts["B"], pts["R"]))

    # chain segments into loops by exact endpoint matching
    key = lambda p: (round(p[0] * 2), round(p[1] * 2))
    adj = defaultdict(list)
    for s_idx, (p, q) in enumerate(segs):
        adj[key(p)].append((key(q), s_idx))
        adj[key(q)].append((key(p), s_idx))
    coord = {}
    for p, q in segs:
        coord[key(p)] = p; coord[key(q)] = q
    used = [False] * len(segs)
    loops = []
    for start_idx in range(len(segs)):
        if used[start_idx]:
            continue
        p0, q0 = segs[start_idx]
        used[start_idx] = True
        loop = [key(p0), key(q0)]
        cur = key(q0)
        while cur != loop[0]:
            nxt = None
            for nb, si in adj[cur]:
                if not used[si]:
                    used[si] = True; nxt = nb; break
            if nxt is None:
                break
            loop.append(nxt); cur = nxt
        if len(loop) >= 4:
            pts = [(coord[k][0] - 1, coord[k][1] - 1) for k in loop]  # unpad
            xs = [p[0] for p in pts]; ys = [p[1] for p in pts]
            if max(xs) - min(xs) >= MIN_DIM or max(ys) - min(ys) >= MIN_DIM:
                # rotate to a deterministic start (min x+y) to steady the RDP seam
                k0 = min(range(len(pts)), key=lambda i: pts[i][0] + pts[i][1])
                loops.append(pts[k0:] + pts[:k0])
    return loops


def _perp(p, a, b):
    if a == b:
        return ((p[0] - a[0]) ** 2 + (p[1] - a[1]) ** 2) ** 0.5
    dx, dy = b[0] - a[0], b[1] - a[1]
    return abs(dx * (a[1] - p[1]) - dy * (a[0] - p[0])) / (dx * dx + dy * dy) ** 0.5


def rdp(points, eps=RDP_EPS):
    """Iterative Ramer–Douglas–Peucker; collapses staircase runs to key vertices."""
    n = len(points)
    if n < 3:
        return points
    keep = [False] * n
    keep[0] = keep[n - 1] = True
    stack = [(0, n - 1)]
    while stack:
        a, b = stack.pop()
        dmax, idx = 0.0, -1
        for i in range(a + 1, b):
            dd = _perp(points[i], points[a], points[b])
            if dd > dmax:
                dmax, idx = dd, i
        if idx != -1 and dmax > eps:
            keep[idx] = True
            stack.append((a, idx)); stack.append((idx, b))
    return [points[i] for i in range(n) if keep[i]]


def chaikin(loop, iters=CHAIKIN):
    pts = loop
    for _ in range(iters):
        out = []
        n = len(pts)
        for i in range(n):
            p, q = pts[i], pts[(i + 1) % n]
            out.append((0.75 * p[0] + 0.25 * q[0], 0.75 * p[1] + 0.25 * q[1]))
            out.append((0.25 * p[0] + 0.75 * q[0], 0.25 * p[1] + 0.75 * q[1]))
        pts = out
    return pts


def path_d(loops, sx, sy, ox, oy):
    """Loops -> single path 'd' with integer canvas coords."""
    parts = []
    for loop in loops:
        simplified = rdp(loop)
        if len(simplified) < 3:
            continue
        sm = chaikin(simplified)
        prev = None
        d = []
        for x, y in sm:
            cx, cy = round(x * sx - ox), round(y * sy - oy)
            if (cx, cy) == prev:
                continue
            d.append(f"{cx} {cy}")
            prev = (cx, cy)
        if len(d) >= 3:
            parts.append("M" + "L".join(d) + "Z")
    return "".join(parts)


# ── build ─────────────────────────────────────────────────────────────────────
def build():
    rgb = load_rgb()
    gray = ImageOps.grayscale(rgb)
    W = GRID_W
    H = round(W * rgb.height / rgb.width)

    mask = subject_mask(gray, W, H)
    luma_full = normalized_luma(gray.resize((W, H), Image.BILINEAR),
                                mask)                       # already grid-sized
    edge = sobel(luma_full) * mask

    # canvas + viewBox (subject bbox + margin => ~80% fill)
    ys, xs = np.nonzero(mask)
    bx0, bx1, by0, by1 = xs.min(), xs.max(), ys.min(), ys.max()
    sx = sy = CELL_PX
    pad = MARGIN * max(bx1 - bx0, by1 - by0)
    vx = (bx0 - pad) * sx
    vy = (by0 - pad) * sy
    vw = (bx1 - bx0 + 2 * pad) * sx
    vh = (by1 - by0 + 2 * pad) * sy
    P = lambda loops: path_d(loops, sx, sy, vx, vy)

    # silhouette
    sil = P(contours(mask))

    # shading level-sets (low->high threshold)
    layers = [P(contours((luma_full >= t) & mask))
              for t in np.linspace(LO, HI, LEVELS)]

    # edge linework
    edges = P(contours(edge >= (EDGE_T)))

    # darkest features carved back
    dark = P(contours((luma_full < DARK_T) & mask))

    # selective halftone: fine dots in one mid band only
    band = (luma_full > 0.44) & (luma_full < 0.62) & mask
    dots = []
    for j in range(0, H, 2):
        for i in range(0, W, 2):
            if band[j, i]:
                cx = round((i + 0.5) * sx - vx)
                cy = round((j + 0.5) * sy - vy)
                dots.append(f'<circle cx="{cx}" cy="{cy}" r="2"/>')
    halftone = "".join(dots)

    return dict(W=W, H=H, mask=mask, luma=luma_full, edge=edge,
                sx=sx, sy=sy, vx=vx, vy=vy, vw=vw, vh=vh,
                sil=sil, layers=layers, edges=edges, dark=dark, halftone=halftone)


# ── QA preview ─────────────────────────────────────────────────────────────────
def write_preview(d):
    """Cyan-tinted luma raster — a faithful reference for the traced result."""
    lum = (np.clip(d["luma"], 0, 1) * 255).astype(np.uint8)
    face = Image.fromarray(lum).resize((d["W"] * 4, d["H"] * 4), Image.BILINEAR)
    Image.merge("RGB", [face.point(lambda v: int(v * 0.26)), face, face]).save(OUT_PREV)


# ── SVG ─────────────────────────────────────────────────────────────────────────
def write_svg(d):
    vb = f'{d["vx"]:.0f} {d["vy"]:.0f} {d["vw"]:.0f} {d["vh"]:.0f}'
    shading = "".join(
        f'<path d="{p}"/>' for p in d["layers"] if p)
    svg = f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="{vb}" role="img" aria-label="C S Deepak — portrait">
  <title>C S Deepak</title>
  <desc>Cyan vector portrait traced from a photograph (level-set contours + edge linework).</desc>
  <defs>
    <linearGradient id="pBody" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0" stop-color="#0f363c"/>
      <stop offset="1" stop-color="#0a1518"/>
    </linearGradient>
    <radialGradient id="pFace" cx="0.5" cy="0.4" r="0.55">
      <stop offset="0" stop-color="#42F5FF" stop-opacity="0.10"/>
      <stop offset="1" stop-color="#42F5FF" stop-opacity="0"/>
    </radialGradient>
    <clipPath id="pClip"><path d="{d["sil"]}"/></clipPath>
  </defs>

  <rect x="{d["vx"]:.0f}" y="{d["vy"]:.0f}" width="{d["vw"]:.0f}" height="{d["vh"]:.0f}" fill="{BG}"/>

  <!-- L3 large silhouette (gradient body) -->
  <path d="{d["sil"]}" fill="url(#pBody)"/>
  <rect x="{d["vx"]:.0f}" y="{d["vy"]:.0f}" width="{d["vw"]:.0f}" height="{d["vh"]:.0f}" fill="url(#pFace)" clip-path="url(#pClip)"/>

  <!-- L4 adaptive cyan shading (stacked level-sets) -->
  <g fill="{ACCENT}" fill-opacity="{LAYER_OP}" fill-rule="evenodd">{shading}</g>

  <!-- L7 selective halftone (mid-tone texture) -->
  <g fill="{ACCENT}" opacity="0.22">{d["halftone"]}</g>

  <!-- L8 fine detail: carved features -->
  <path d="{d["dark"]}" fill="{BG}" fill-opacity="0.85" fill-rule="evenodd"/>

  <!-- L5 edge linework -->
  <path d="{d["edges"]}" fill="{ACCENT}" fill-opacity="0.9" fill-rule="evenodd"/>

  <!-- corner ticks -->
  <g stroke="{ACCENT}" stroke-width="1.6" fill="none" opacity="0.6">
    <path d="M{d["vx"]+10:.0f} {d["vy"]+24:.0f} V{d["vy"]+10:.0f} H{d["vx"]+24:.0f}"/>
    <path d="M{d["vx"]+d["vw"]-10:.0f} {d["vy"]+24:.0f} V{d["vy"]+10:.0f} H{d["vx"]+d["vw"]-24:.0f}"/>
    <path d="M{d["vx"]+10:.0f} {d["vy"]+d["vh"]-24:.0f} V{d["vy"]+d["vh"]-10:.0f} H{d["vx"]+24:.0f}"/>
    <path d="M{d["vx"]+d["vw"]-10:.0f} {d["vy"]+d["vh"]-24:.0f} V{d["vy"]+d["vh"]-10:.0f} H{d["vx"]+d["vw"]-24:.0f}"/>
  </g>
</svg>'''
    with open(OUT_SVG, "w", encoding="utf-8") as f:
        f.write(svg)
    return len(svg)


def main():
    d = build()
    write_preview(d)
    size = write_svg(d)
    print(f"levels={LEVELS} svg={size/1024:.0f}KB canvas={d['vw']:.0f}x{d['vh']:.0f} -> {OUT_SVG}")


if __name__ == "__main__":
    main()

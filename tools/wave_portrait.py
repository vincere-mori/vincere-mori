#!/usr/bin/env python3
"""Turn a photo into a scanline wave portrait and bake the drawing animation into the SVG.

Each output row is one continuous line whose vertical wobble grows with the
brightness of the source underneath it. Rows are revealed top to bottom with
stroke-dashoffset, so the face draws itself line by line.

Source image for assets/david.svg: plaster cast of the head of David, KAS2232,
Statens Museum for Kunst, public domain.

Usage:
  python tools/wave_portrait.py photo.jpg --crop 262,0,1822,1560 \n      --width 640 --height 640 --rows 96 --gamma 0.9 --contrast 1.4 \n      --out assets/david.svg
"""

import argparse
import math

from PIL import Image, ImageDraw, ImageFilter, ImageOps

W = 640
H = 600
ROWS = 74
GROUPS = 28
DX = 4.0
MAX_AMP = 3.4
FREQ = 0.62
FLOOR = 0.10
DURATION = 13.0


def prepare(path, crop, gamma, contrast, bg):
    """Return (inside, tone): where the subject is, and how deep its shading is.

    The cast is bright on a dark ground, so brightness alone says almost nothing
    about the face. Silhouette comes from a threshold; the wobble is driven by
    shadow depth inside that silhouette, which is what actually draws features.
    """
    im = Image.open(path).convert("RGB")
    if crop:
        im = im.crop(crop)
    im = ImageOps.grayscale(im).resize((W, H), Image.LANCZOS)
    blur = im.filter(ImageFilter.GaussianBlur(radius=H / 14.0))
    px, bx = im.load(), blur.load()

    raw = [[px[x, y] / 255.0 for x in range(W)] for y in range(H)]
    low = [[bx[x, y] / 255.0 for x in range(W)] for y in range(H)]
    inside = [[raw[y][x] > bg for x in range(W)] for y in range(H)]

    vals = [raw[y][x] for y in range(H) for x in range(W) if inside[y][x]]
    if not vals:
        raise SystemExit("silhouette is empty, lower --bg")
    lo, hi = min(vals), max(vals)
    span = max(1e-6, hi - lo)

    # local detail carries the features; the global gradient only says where the
    # light came from, so it is kept at a fraction of the weight
    tone = [[0.0] * W for _ in range(H)]
    for y in range(H):
        for x in range(W):
            if not inside[y][x]:
                continue
            detail = max(0.0, low[y][x] - raw[y][x]) * 6.0
            shade = 1.0 - (raw[y][x] - lo) / span
            t = pow(min(1.0, detail + 0.3 * shade), gamma)
            tone[y][x] = min(1.0, t * contrast)
    return inside, tone


def sample(inside, tone, x, y):
    xi = min(W - 1, max(0, int(x)))
    hits = 0
    total = 0.0
    for dy in (-2, 0, 2):
        yy = min(H - 1, max(0, int(y + dy)))
        if inside[yy][xi]:
            hits += 1
            total += tone[yy][xi]
    return hits >= 2, (total / hits if hits else 0.0)


def build_rows(inside, tone):
    """One row -> list of subpaths, each a list of (x, y) points."""
    row_h = H / ROWS
    rows = []
    for r in range(ROWS):
        base = (r + 0.5) * row_h
        phase = r * 1.7
        subpaths = []
        current = []
        x = 0.0
        while x <= W:
            on, v = sample(inside, tone, x, base)
            phase += FREQ * (0.55 + 1.7 * v)
            if not on:
                if len(current) > 3:
                    subpaths.append(current)
                current = []
            else:
                amp = MAX_AMP * max(0.0, v - FLOOR) / (1 - FLOOR)
                current.append((x, base + amp * math.sin(phase)))
            x += DX
        if len(current) > 3:
            subpaths.append(current)
        rows.append(subpaths)
    return rows


def path_data(points):
    x0, y0 = points[0]
    out = ["M%.0f %.1f" % (x0, y0)]
    prev = y0
    for _, y in points[1:]:
        out.append("l%.0f %.1f" % (DX, y - prev))
        prev = y
    return "".join(out)


def css():
    step = 62.0 / GROUPS
    parts = [
        "path{fill:none;stroke:#e8e4dc;stroke-width:1.15;stroke-linecap:round;"
        "vector-effect:non-scaling-stroke;stroke-dasharray:1;stroke-dashoffset:1;"
        "animation-duration:%.1fs;animation-iteration-count:infinite;"
        "animation-timing-function:cubic-bezier(.35,0,.25,1)}" % DURATION
    ]
    for g in range(GROUPS):
        a = 3.0 + g * step
        b = a + 7.0
        parts.append(
            "@keyframes w%d{0%%,%.2f%%{stroke-dashoffset:1;opacity:1}"
            "%.2f%%,91%%{stroke-dashoffset:0;opacity:1}"
            "100%%{stroke-dashoffset:0;opacity:0}}" % (g, a, b)
        )
        parts.append(".g%d{animation-name:w%d}" % (g, g))
    return "".join(parts)


def to_svg(rows):
    out = [
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 %d %d" width="%d" height="%d" '
        'role="img" aria-label="Head of David, drawn line by line">' % (W, H, W, H),
        "<defs><style><![CDATA[%s]]></style></defs>" % css(),
        '<rect width="%d" height="%d" fill="#0b0b12"/>' % (W, H),
    ]
    for r, subpaths in enumerate(rows):
        g = min(GROUPS - 1, int(r * GROUPS / ROWS))
        for pts in subpaths:
            out.append('<path class="g%d" pathLength="1" d="%s"/>' % (g, path_data(pts)))
    out.append("</svg>")
    return "".join(out)


def preview(rows, path):
    img = Image.new("RGB", (W, H), (11, 11, 18))
    d = ImageDraw.Draw(img)
    for subpaths in rows:
        for pts in subpaths:
            d.line([(x, y) for x, y in pts], fill=(232, 228, 220), width=1)
    img.save(path)


def main():
    global W, H, ROWS
    ap = argparse.ArgumentParser()
    ap.add_argument("src")
    ap.add_argument("--out", default="portrait.svg")
    ap.add_argument("--preview", default="preview.png")
    ap.add_argument("--crop", default="", help="left,top,right,bottom")
    ap.add_argument("--gamma", type=float, default=1.35)
    ap.add_argument("--contrast", type=float, default=1.25)
    ap.add_argument("--bg", type=float, default=0.22, help="silhouette threshold")
    ap.add_argument("--width", type=int, default=W)
    ap.add_argument("--height", type=int, default=H)
    ap.add_argument("--rows", type=int, default=ROWS)
    args = ap.parse_args()
    W, H, ROWS = args.width, args.height, args.rows
    crop = tuple(int(v) for v in args.crop.split(",")) if args.crop else None
    inside, tone = prepare(args.src, crop, args.gamma, args.contrast, args.bg)
    rows = build_rows(inside, tone)
    svg = to_svg(rows)
    with open(args.out, "w", encoding="utf-8", newline="\n") as f:
        f.write(svg)
    preview(rows, args.preview)

    strokes = sum(len(s) for s in rows)
    print("%s  %.0f KB  %d rows  %d subpaths" % (args.out, len(svg) / 1024, len(rows), strokes))


if __name__ == "__main__":
    main()

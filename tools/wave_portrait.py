#!/usr/bin/env python3
"""Turn a picture into an engraved ring portrait and bake the drawing animation into the SVG.

Each ring is a ribbon whose thickness follows the brightness underneath it, so
the image reads like a line engraving. Rings are revealed from the centre
outwards through a mask of stroked circles (stroke-dashoffset).

Source image for assets/mandylion.svg: The Saviour Not Made by Hands, Novgorod,
12th century, Tretyakov Gallery, public domain (Wikimedia Commons,
"Christos Acheiropoietos.jpg").

Usage:
  python tools/wave_portrait.py mandylion.jpg --crop 69,103,1237,1271 --out assets/mandylion.svg
"""

import argparse
import math

from PIL import Image, ImageFilter, ImageOps

N = 640
RINGS = 50
GROUPS = 25
DURATION = 9.0
INK = "#e8e4dc"
BG = "#0b0b12"


def prepare(path, crop, gamma):
    im = Image.open(path).convert("RGB")
    if crop:
        im = im.crop(crop)
    im = ImageOps.grayscale(im).resize((N, N), Image.LANCZOS)
    im = ImageOps.autocontrast(im, cutoff=1)
    im = im.filter(ImageFilter.UnsharpMask(radius=8, percent=90, threshold=2))
    im = im.filter(ImageFilter.GaussianBlur(1.4))
    px = im.load()
    return lambda x, y: pow(px[min(N - 1, max(0, int(x))), min(N - 1, max(0, int(y)))] / 255.0, gamma)


def simplify(pts, eps=0.25):
    if len(pts) < 3:
        return pts
    (ax, ay), (bx, by) = pts[0], pts[-1]
    dx, dy = bx - ax, by - ay
    norm = math.hypot(dx, dy)
    if norm < 1e-3:
        # closed ring, split it so the chord isn't degenerate
        h = len(pts) // 2
        return simplify(pts[: h + 1], eps)[:-1] + simplify(pts[h:], eps)
    dist = [abs(dx * (y - ay) - dy * (x - ax)) / norm for x, y in pts]
    i = max(range(len(pts)), key=dist.__getitem__)
    if dist[i] > eps:
        return simplify(pts[: i + 1], eps)[:-1] + simplify(pts[i:], eps)
    return [pts[0], pts[-1]]


def num(v):
    s = ("%.1f" % v).rstrip("0").rstrip(".")
    return "0" if s in ("-0", "") else s


def path_data(pts):
    out = "M%s %s" % (num(pts[0][0]), num(pts[0][1]))
    px, py = pts[0]
    for x, y in pts[1:]:
        dx, dy = num(x - px), num(y - py)
        out += "l" + dx + ("" if dy.startswith("-") else " ") + dy
        px, py = px + float(dx), py + float(dy)
    return out + "z"


def build(tone):
    c = N / 2
    gap = (N / 2 - 3) / RINGS
    ribbons, mask = [], []
    for k in range(1, RINGS + 1):
        r = k * gap - gap / 2
        n = max(24, int(2 * math.pi * r / 4.5))
        outer, inner = [], []
        for i in range(n + 1):
            a = 2 * math.pi * i / n - math.pi / 2
            x, y = c + r * math.cos(a), c + r * math.sin(a)
            w = max(0.35, gap * 0.94 * tone(x, y)) / 2
            outer.append((x + w * math.cos(a), y + w * math.sin(a)))
            inner.append((x - w * math.cos(a), y - w * math.sin(a)))
        ribbons.append(path_data(simplify(outer)) + path_data(simplify(inner[::-1])))
        g = min(GROUPS - 1, (k - 1) * GROUPS // RINGS)
        mask.append(
            '<circle class="m g%d" pathLength="1" stroke-width="%s" cx="%d" cy="%d" r="%s" transform="rotate(-90 %d %d)"/>'
            % (g, num(gap + 1), c, c, num(r), c, c)
        )
    return ribbons, mask


def css():
    # draw takes the first ~38% of the cycle, then hold and fade
    parts = [
        ".m{fill:none;stroke:#fff;stroke-dasharray:1;stroke-dashoffset:1;"
        "animation:%.0fs cubic-bezier(.4,0,.2,1) infinite}" % DURATION
    ]
    for g in range(GROUPS):
        a = 1 + g * 30.0 / GROUPS
        parts.append(
            "@keyframes w%d{0%%,%.1f%%{stroke-dashoffset:1;opacity:1}%.1f%%,92%%{stroke-dashoffset:0;opacity:1}"
            "100%%{stroke-dashoffset:0;opacity:0}}.g%d{animation-name:w%d}" % (g, a, a + 7, g, g)
        )
    return "".join(parts)


def to_svg(ribbons, mask, label):
    return (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 %d %d" width="%d" height="%d" role="img" aria-label="%s">'
        "<defs><style><![CDATA[%s]]></style>"
        '<mask id="r" maskUnits="userSpaceOnUse" x="0" y="0" width="%d" height="%d">%s</mask></defs>'
        '<rect width="%d" height="%d" fill="%s"/>'
        '<g mask="url(#r)" fill="%s" fill-rule="evenodd"><path d="%s"/></g></svg>'
        % (N, N, N, N, label, css(), N, N, "".join(mask), N, N, BG, INK, "".join(ribbons))
    )


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("src")
    ap.add_argument("--out", default="portrait.svg")
    ap.add_argument("--crop", default="", help="left,top,right,bottom")
    ap.add_argument("--gamma", type=float, default=1.5)
    ap.add_argument("--label", default="The Saviour Not Made by Hands, drawn ring by ring")
    args = ap.parse_args()
    crop = tuple(int(v) for v in args.crop.split(",")) if args.crop else None
    ribbons, mask = build(prepare(args.src, crop, args.gamma))
    svg = to_svg(ribbons, mask, args.label)
    with open(args.out, "w", encoding="utf-8", newline="\n") as f:
        f.write(svg)
    print("%s  %.0f KB" % (args.out, len(svg) / 1024))


if __name__ == "__main__":
    main()

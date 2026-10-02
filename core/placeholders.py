"""Cover placeholders (design 13.2.5): the picture an article or a tournament
shows when nobody uploaded a cover.

Abstract scenes drawn here as SVG. ``manage.py render_placeholders`` writes
them to ``static/img/placeholders/`` and the files are committed; a test
redraws every one and compares, so the files cannot drift from this code.
Each object always gets the same picture (``pick``), so the card on a list,
the detail page and the prerendered copy agree.

The pictures carry no text, no script and no outside reference (same rules as
the emblem, 13.2.8). There is no grain: an SVG filter would be recomputed for
every card on a phone.
"""

from __future__ import annotations

import math
import random
from itertools import pairwise

WIDTH, HEIGHT = 1600, 900
DIRECTORY = "img/placeholders"

# Picked per object type, so an article and a tournament with the same id do
# not share a picture on the homepage.
KIND_OFFSETS = {"content.articlepage": 0, "tournaments.tournament": 13}


# --- drawing helpers ----------------------------------------------------------


def _n(value: float) -> str:
    text = f"{value:.1f}".rstrip("0").rstrip(".")
    return "0" if text in ("-0", "") else text


def _rgb(color: str) -> tuple[int, int, int]:
    color = color.lstrip("#")
    return tuple(int(color[i : i + 2], 16) for i in (0, 2, 4))


def _hex(rgb) -> str:
    return "#" + "".join(f"{max(0, min(255, round(c))):02x}" for c in rgb)


def _mix(a: str, b: str, t: float) -> str:
    ra, rb = _rgb(a), _rgb(b)
    return _hex(x + (y - x) * t for x, y in zip(ra, rb, strict=True))


def _points(points) -> str:
    return " ".join(f"{_n(x)},{_n(y)}" for x, y in points)


class _Svg:
    def __init__(self):
        self.defs: list[str] = []
        self.body: list[str] = []
        self._count = 0

    def _id(self, prefix: str) -> str:
        self._count += 1
        return f"{prefix}{self._count}"

    def linear(self, stops, x1=0, y1=0, x2=0, y2=1) -> str:
        """``stops``: (offset, colour, opacity). Returns ``url(#id)``."""
        gid = self._id("l")
        parts = "".join(
            f'<stop offset="{_n(o)}" stop-color="{c}"'
            + (f' stop-opacity="{_n(a)}"' if a != 1 else "")
            + "/>"
            for o, c, a in stops
        )
        self.defs.append(
            f'<linearGradient id="{gid}" x1="{_n(x1)}" y1="{_n(y1)}" '
            f'x2="{_n(x2)}" y2="{_n(y2)}">{parts}</linearGradient>'
        )
        return f"url(#{gid})"

    def glow(self, cx, cy, r, color, strength=0.85):
        """A soft light: a circle whose radial gradient fades to nothing."""
        gid = self._id("g")
        stops = "".join(
            f'<stop offset="{o}" stop-color="{color}" '
            f'stop-opacity="{round(strength * a, 3)}"/>'
            for o, a in ((0, 1), (0.25, 0.62), (0.5, 0.28), (0.75, 0.08), (1, 0))
        )
        self.defs.append(f'<radialGradient id="{gid}">{stops}</radialGradient>')
        self.add(
            f'<circle cx="{_n(cx)}" cy="{_n(cy)}" r="{_n(r)}" fill="url(#{gid})"/>'
        )

    def sky(self, top, bottom):
        self.add(
            f'<rect width="{WIDTH}" height="{HEIGHT}" '
            f'fill="{self.linear([(0, top, 1), (1, bottom, 1)])}"/>'
        )

    def polygon(self, points, fill, opacity=1.0):
        extra = f' fill-opacity="{round(opacity, 3)}"' if opacity != 1 else ""
        self.add(f'<polygon points="{_points(points)}" fill="{fill}"{extra}/>')

    def path(self, d, fill, opacity=1.0):
        extra = f' fill-opacity="{round(opacity, 3)}"' if opacity != 1 else ""
        self.add(f'<path d="{d}" fill="{fill}"{extra}/>')

    def add(self, element: str):
        self.body.append(element)

    def render(self) -> str:
        return (
            '<svg xmlns="http://www.w3.org/2000/svg" '
            f'viewBox="0 0 {WIDTH} {HEIGHT}" width="{WIDTH}" height="{HEIGHT}" '
            'preserveAspectRatio="xMidYMid slice">'
            f"<defs>{''.join(self.defs)}</defs>{''.join(self.body)}</svg>\n"
        )


def _ridge(rng, base, rough, levels=8):
    """Midpoint displacement: one jagged line from the left edge to the right."""
    heights = [base + rng.uniform(-rough, rough), base + rng.uniform(-rough, rough)]
    amp = rough
    for _ in range(levels):
        nxt = []
        for a, b in pairwise(heights):
            nxt += [a, (a + b) / 2 + rng.uniform(-amp, amp)]
        nxt.append(heights[-1])
        heights = nxt
        amp *= 0.55
    step = WIDTH / (len(heights) - 1)
    return [(i * step, y) for i, y in enumerate(heights)]


def _smooth(points) -> str:
    """A Catmull-Rom curve through ``points`` as cubic Bézier path data."""
    d = f"M{_n(points[0][0])},{_n(points[0][1])}"
    for i in range(len(points) - 1):
        p0 = points[max(i - 1, 0)]
        p1, p2 = points[i], points[i + 1]
        p3 = points[min(i + 2, len(points) - 1)]
        c1 = (p1[0] + (p2[0] - p0[0]) / 6, p1[1] + (p2[1] - p0[1]) / 6)
        c2 = (p2[0] - (p3[0] - p1[0]) / 6, p2[1] - (p3[1] - p1[1]) / 6)
        d += f"C{_n(c1[0])},{_n(c1[1])} {_n(c2[0])},{_n(c2[1])} {_n(p2[0])},{_n(p2[1])}"
    return d


def _stars(svg, rng, count, bottom, color="#ffffff"):
    for _ in range(count):
        x, y = rng.uniform(0, WIDTH), rng.uniform(0, bottom) ** 1.15 / bottom**0.15
        r = rng.choice((1.2, 1.5, 1.8, 2.4))
        svg.add(
            f'<circle cx="{_n(x)}" cy="{_n(y)}" r="{r}" fill="{color}" '
            f'fill-opacity="{round(rng.uniform(0.35, 0.95), 2)}"/>'
        )


# --- the scenes ---------------------------------------------------------------


def landscape(rng, p):
    """Layered mountains under a low sun (the first style the user liked)."""
    svg = _Svg()
    svg.sky(p["top"], p["bottom"])
    svg.glow(
        WIDTH * rng.uniform(0.25, 0.75),
        HEIGHT * rng.uniform(0.3, 0.45),
        HEIGHT * 0.5,
        p["sun"],
    )
    layers = p.get("layers", 5)
    for i in range(layers):
        t = (i + 1) / layers
        line = _ridge(rng, HEIGHT * (0.45 + 0.11 * i), HEIGHT * (0.16 - 0.02 * i))
        svg.polygon(
            line + [(WIDTH, HEIGHT), (0, HEIGHT)], _mix(p["bottom"], p["near"], t**0.8)
        )
    return svg


def skyline(rng, p):
    """A city at night: three rows of towers, some windows lit."""
    svg = _Svg()
    svg.sky(p["top"], p["bottom"])
    svg.glow(
        WIDTH * rng.uniform(0.35, 0.65), HEIGHT * 0.78, HEIGHT * 0.7, p["glow"], 0.7
    )
    windows: dict[str, list[str]] = {c: [] for c in p["windows"]}
    win = 6
    for layer in range(3):
        shade = _mix(p["bottom"], "#080a12", 0.55 + 0.2 * layer)
        towers = []
        x = -rng.randint(0, 50)
        while x < WIDTH:
            bw = rng.randint(int(WIDTH * 0.03), int(WIDTH * 0.08))
            low, high = 0.18 + 0.05 * (2 - layer), 0.42 + 0.12 * (2 - layer)
            top = HEIGHT - rng.randint(int(HEIGHT * low), int(HEIGHT * high))
            towers.append(f"M{x},{top}h{bw}V{HEIGHT}h{-bw}z")
            if layer == 2 or rng.random() < 0.5:
                for wy in range(top + win * 3, HEIGHT - win * 2, win * 3):
                    for wx in range(x + win * 2, x + bw - win * 2, win * 3):
                        if rng.random() < 0.2:
                            color = rng.choice(p["windows"])
                            windows[color].append(f"M{wx},{wy}h{win}v{win}h{-win}z")
            x += bw + rng.randint(0, int(WIDTH * 0.01))
        svg.path("".join(towers), shade)
    for color, rects in windows.items():
        if rects:
            svg.path("".join(rects), color)
    return svg


def geometric(rng, p):
    """Large see-through triangles and circles."""
    svg = _Svg()
    svg.sky(p["top"], p["bottom"])
    for _ in range(14):
        color = rng.choice(p["shapes"])
        opacity = rng.randint(40, 120) / 255
        cx, cy = rng.uniform(-0.1, 1.1) * WIDTH, rng.uniform(-0.1, 1.1) * HEIGHT
        size = rng.uniform(0.15, 0.55) * HEIGHT
        if rng.random() < 0.5:
            angle = rng.uniform(0, math.tau)
            svg.polygon(
                [
                    (
                        cx + size * math.cos(angle + k * math.tau / 3),
                        cy + size * math.sin(angle + k * math.tau / 3),
                    )
                    for k in range(3)
                ],
                color,
                opacity,
            )
        else:
            svg.add(
                f'<circle cx="{_n(cx)}" cy="{_n(cy)}" r="{_n(size)}" fill="{color}" '
                f'fill-opacity="{round(opacity, 3)}"/>'
            )
    return svg


def waves(rng, p):
    """The sea at sunset: bands of swell and the sun's path on the water."""
    svg = _Svg()
    horizon = HEIGHT * rng.uniform(0.5, 0.58)
    svg.sky(p["top"], p["bottom"])
    sun_x = WIDTH * rng.uniform(0.3, 0.7)
    svg.glow(sun_x, horizon - HEIGHT * 0.06, HEIGHT * 0.42, p["sun"])
    svg.add(
        f'<circle cx="{_n(sun_x)}" cy="{_n(horizon - HEIGHT * 0.05)}" '
        f'r="{_n(HEIGHT * 0.06)}" fill="{p["sun"]}" fill-opacity="0.9"/>'
    )
    bands = 9
    for i in range(bands):
        t = i / (bands - 1)
        y0 = horizon + (HEIGHT - horizon) * (t**1.6) * 0.95
        amp = 3 + 22 * t
        freq = rng.uniform(1.5, 3.5) / WIDTH * math.tau
        phase = rng.uniform(0, math.tau)
        pts = [
            (
                x,
                y0
                + amp * math.sin(x * freq + phase)
                + amp * 0.4 * math.sin(x * freq * 2.7),
            )
            for x in range(0, WIDTH + 1, 40)
        ]
        svg.polygon(pts + [(WIDTH, HEIGHT), (0, HEIGHT)], _mix(p["far"], p["near"], t))
    for _ in range(26):
        y = rng.uniform(horizon + 8, HEIGHT * 0.95)
        spread = (y - horizon) / (HEIGHT - horizon)
        w = rng.uniform(30, 140) * (0.4 + spread)
        x = sun_x + rng.gauss(0, 30 + 120 * spread) - w / 2
        opacity = round(0.55 - 0.35 * spread, 2)
        svg.add(
            f'<rect x="{_n(x)}" y="{_n(y)}" width="{_n(w)}" '
            f'height="{_n(2 + 3 * spread)}" rx="2" fill="{p["sun"]}" '
            f'fill-opacity="{opacity}"/>'
        )
    return svg


def dunes(rng, p):
    """Smooth sand dunes, each with a lit face and a shadowed one."""
    svg = _Svg()
    svg.sky(p["top"], p["bottom"])
    svg.glow(
        WIDTH * rng.uniform(0.2, 0.8),
        HEIGHT * rng.uniform(0.2, 0.35),
        HEIGHT * 0.45,
        p["sun"],
    )
    layers = 5
    for i in range(layers):
        t = (i + 1) / layers
        base = HEIGHT * (0.5 + 0.1 * i)
        count = rng.randint(4, 6)
        pts = [
            (
                WIDTH * k / count + rng.uniform(-60, 60) * (0 < k < count),
                base + rng.uniform(-HEIGHT * 0.09, HEIGHT * 0.06),
            )
            for k in range(count + 1)
        ]
        pts[0] = (-20, pts[0][1])
        pts[-1] = (WIDTH + 20, pts[-1][1])
        lit = _mix(p["sand"], p["near"], t * 0.85)
        shade = _mix(lit, p["shadow"], 0.35)
        fill = svg.linear([(0, lit, 1), (1, shade, 1)], x1=0, y1=0, x2=1, y2=0.3)
        svg.path(_smooth(pts) + f"L{WIDTH + 20},{HEIGHT}L-20,{HEIGHT}z", fill)
    return svg


def aurora(rng, p):
    """Northern lights over a dark ridge, with stars."""
    svg = _Svg()
    svg.sky(p["top"], p["bottom"])
    _stars(svg, rng, 90, HEIGHT * 0.6)
    for color in p["lights"]:
        base = HEIGHT * rng.uniform(0.28, 0.45)
        height = HEIGHT * rng.uniform(0.18, 0.3)
        freq = rng.uniform(0.8, 1.6) / WIDTH * math.tau
        phase = rng.uniform(0, math.tau)
        lower = [
            (
                x,
                base
                + 60 * math.sin(x * freq + phase)
                + 25 * math.sin(x * freq * 2.3 + phase),
            )
            for x in range(-40, WIDTH + 41, 40)
        ]
        upper = [
            (x, y - height - 30 * math.sin(x * freq * 1.7)) for x, y in reversed(lower)
        ]
        fill = svg.linear([(0, color, 0), (0.7, color, 0.35), (1, color, 0.75)])
        svg.polygon(lower + upper, fill)
    for i, shade in enumerate((p["far"], p["near"])):
        line = _ridge(rng, HEIGHT * (0.68 + 0.12 * i), HEIGHT * (0.12 - 0.04 * i))
        svg.polygon(line + [(WIDTH, HEIGHT), (0, HEIGHT)], shade)
    return svg


def arena(rng, p):
    """An esports stage: spotlight beams from the roof over a crowd."""
    svg = _Svg()
    svg.sky(p["top"], p["bottom"])
    stage_y = HEIGHT * 0.72
    svg.glow(WIDTH / 2, stage_y, HEIGHT * 0.65, p["stage"], 0.75)
    beams = rng.randint(5, 7)
    for k in range(beams):
        src = WIDTH * (k + 0.5) / beams + rng.uniform(-60, 60)
        hit = WIDTH / 2 + (src - WIDTH / 2) * rng.uniform(-0.2, 0.5)
        spread = rng.uniform(60, 130)
        color = rng.choice(p["beams"])
        fill = svg.linear([(0, color, 0.55), (1, color, 0)])
        svg.polygon(
            [
                (src - 8, -10),
                (src + 8, -10),
                (hit + spread, stage_y),
                (hit - spread, stage_y),
            ],
            fill,
        )
    svg.add(
        f'<rect x="{_n(WIDTH * 0.22)}" y="{_n(stage_y - 6)}" '
        f'width="{_n(WIDTH * 0.56)}" height="6" fill="{p["stage"]}" '
        'fill-opacity="0.85"/>'
    )
    for row in range(3):
        y_base = HEIGHT * (0.8 + 0.07 * row)
        r = 24 + 9 * row
        heads = []
        x = -rng.uniform(0, r)
        while x < WIDTH + r:
            y = y_base + rng.uniform(-6, 6)
            heads.append(
                f"M{_n(x - r)},{_n(y)}a{r},{r} 0 0 1 {2 * r},0z"
                f"M{_n(x - r * 1.6)},{_n(y + r * 1.1)}"
                f"q{_n(r * 1.6)},{_n(-r * 1.9)} {_n(r * 3.2)},0z"
            )
            x += r * rng.uniform(1.9, 2.6)
        shade = _mix(p["crowd"], "#000000", 0.25 * row)
        svg.path("".join(heads), shade)
        svg.add(
            f'<rect y="{_n(y_base + r)}" width="{WIDTH}" '
            f'height="{_n(HEIGHT - y_base)}" fill="{shade}"/>'
        )
    return svg


def planet(rng, p):
    """A ringed planet half out of frame, a moon and stars."""
    svg = _Svg()
    svg.sky(p["top"], p["bottom"])
    _stars(svg, rng, 120, HEIGHT)
    cx = WIDTH * rng.choice((0.22, 0.3, 0.7, 0.78))
    cy = HEIGHT * rng.uniform(0.55, 0.75)
    r = HEIGHT * rng.uniform(0.38, 0.5)
    svg.glow(cx, cy, r * 1.6, p["glow"], 0.45)
    tilt = rng.uniform(-18, -8) if cx < WIDTH / 2 else rng.uniform(8, 18)
    ring = (
        f'<ellipse cx="{_n(cx)}" cy="{_n(cy)}" rx="{_n(r * 1.75)}" ry="{_n(r * 0.36)}" '
        f'fill="none" stroke="{p["ring"]}" stroke-width="{_n(r * 0.07)}" '
        f'stroke-opacity="0.7" transform="rotate({_n(tilt)} {_n(cx)} {_n(cy)})"/>'
    )
    svg.add(ring)
    lit_x = 0.3 if cx > WIDTH / 2 else 0.7
    body = svg.linear(
        [(0, p["light"], 1), (0.55, p["body"], 1), (1, p["dark"], 1)],
        x1=lit_x,
        y1=0.15,
        x2=1 - lit_x,
        y2=0.85,
    )
    svg.add(f'<circle cx="{_n(cx)}" cy="{_n(cy)}" r="{_n(r)}" fill="{body}"/>')
    for k in range(4):
        band_y = cy - r * 0.6 + k * r * 0.35 + rng.uniform(-10, 10)
        half = math.sqrt(max(r * r - (band_y - cy) ** 2, 0))
        svg.add(
            f'<rect x="{_n(cx - half)}" y="{_n(band_y)}" width="{_n(2 * half)}" '
            f'height="{_n(r * 0.06)}" fill="{p["dark"]}" fill-opacity="0.18"/>'
        )
    # The near half of the ring passes in front of the planet.
    svg.add(
        f'<path d="M{_n(cx - r * 1.75)},{_n(cy)}A{_n(r * 1.75)},{_n(r * 0.36)} 0 0 0 '
        f'{_n(cx + r * 1.75)},{_n(cy)}" fill="none" stroke="{p["ring"]}" '
        f'stroke-width="{_n(r * 0.07)}" stroke-opacity="0.85" '
        f'transform="rotate({_n(tilt)} {_n(cx)} {_n(cy)})"/>'
    )
    mx = WIDTH - cx + rng.uniform(-120, 120)
    my = HEIGHT * rng.uniform(0.18, 0.32)
    mr = r * 0.12
    svg.add(
        f'<circle cx="{_n(mx)}" cy="{_n(my)}" r="{_n(mr)}" fill="{p["light"]}" '
        'fill-opacity="0.85"/>'
    )
    return svg


def forest(rng, p):
    """Pine woods fading into morning mist."""
    svg = _Svg()
    svg.sky(p["top"], p["bottom"])
    svg.glow(
        WIDTH * rng.uniform(0.3, 0.7),
        HEIGHT * rng.uniform(0.25, 0.4),
        HEIGHT * 0.5,
        p["sun"],
    )
    layers = 4
    for i in range(layers):
        t = (i + 1) / layers
        ground = _ridge(rng, HEIGHT * (0.58 + 0.1 * i), HEIGHT * 0.05, levels=5)
        trees = []
        size = 40 + 30 * i
        x = -rng.uniform(0, size)
        while x < WIDTH + size:
            at = min(max(int(x / WIDTH * (len(ground) - 1)), 0), len(ground) - 1)
            gy = ground[at][1] + rng.uniform(0, size * 0.3)
            h = size * rng.uniform(2.4, 4.2)
            w = h * rng.uniform(0.36, 0.46)
            # A pine is three stacked tiers, wider towards the ground.
            for k in range(3):
                apex = gy - h + k * h * 0.24
                base = apex + h * 0.46
                half = w / 2 * (0.55 + 0.22 * k)
                trees.append(
                    f"M{_n(x)},{_n(apex)}L{_n(x + half)},{_n(base)}"
                    f"L{_n(x - half)},{_n(base)}z"
                )
            x += w * rng.uniform(0.5, 1.1)
        color = _mix(p["mist"], p["near"], t**0.9)
        svg.path("".join(trees), color)
        svg.polygon(ground + [(WIDTH, HEIGHT), (0, HEIGHT)], color)
    return svg


# --- the catalogue ------------------------------------------------------------

STYLES = {
    "landscape": (
        landscape,
        [
            {
                "top": "#2b1a3d",
                "bottom": "#f08a4b",
                "sun": "#ffd27a",
                "near": "#1a0f1f",
            },
            {
                "top": "#1e3a5f",
                "bottom": "#f6b6a8",
                "sun": "#fff1c9",
                "near": "#13233a",
            },
            {
                "top": "#4f8fc0",
                "bottom": "#cfe8d5",
                "sun": "#fffbe0",
                "near": "#1f3d2b",
            },
            {
                "top": "#0f1e3a",
                "bottom": "#9fb8d9",
                "sun": "#e8f1ff",
                "near": "#0b1424",
                "layers": 6,
            },
        ],
    ),
    "skyline": (
        skyline,
        [
            {
                "top": "#0b1020",
                "bottom": "#1d2a4a",
                "glow": "#f99e1a",
                "windows": ["#ffd28a", "#f99e1a", "#9ad1ff", "#ffffff"],
            },
            {
                "top": "#140c2a",
                "bottom": "#3b1f5c",
                "glow": "#c084fc",
                "windows": ["#f0abfc", "#fde68a", "#ffffff"],
            },
            {
                "top": "#06131f",
                "bottom": "#0e3b5c",
                "glow": "#38bdf8",
                "windows": ["#7dd3fc", "#e0f2fe", "#fde68a"],
            },
            {
                "top": "#1a0b14",
                "bottom": "#4a1d2f",
                "glow": "#fb923c",
                "windows": ["#fed7aa", "#fb923c", "#ffffff"],
            },
        ],
    ),
    "geometric": (
        geometric,
        [
            {
                "top": "#1f2937",
                "bottom": "#374151",
                "shapes": ["#60a5fa", "#93c5fd", "#f99e1a"],
            },
            {
                "top": "#0f3d3a",
                "bottom": "#14532d",
                "shapes": ["#fde047", "#5eead4", "#ffffff"],
            },
            {
                "top": "#1c1917",
                "bottom": "#44403c",
                "shapes": ["#f99e1a", "#218ffe", "#fafaf9"],
            },
            {
                "top": "#2a1430",
                "bottom": "#4c1d3d",
                "shapes": ["#f472b6", "#fbbf24", "#a5b4fc"],
            },
        ],
    ),
    "waves": (
        waves,
        [
            {
                "top": "#2a1b4a",
                "bottom": "#f4a26b",
                "sun": "#ffe1a1",
                "far": "#c97a6b",
                "near": "#1b1838",
            },
            {
                "top": "#123a5a",
                "bottom": "#a9d6e5",
                "sun": "#fffbe6",
                "far": "#6aa3bf",
                "near": "#0b2236",
            },
            {
                "top": "#3b1d3a",
                "bottom": "#ef8f8f",
                "sun": "#ffd6c2",
                "far": "#b0607a",
                "near": "#24122a",
            },
            {
                "top": "#0d1b2a",
                "bottom": "#41658a",
                "sun": "#dfe9f5",
                "far": "#36557a",
                "near": "#070f19",
            },
        ],
    ),
    "dunes": (
        dunes,
        [
            {
                "top": "#f3b562",
                "bottom": "#fde4b4",
                "sun": "#fff6dc",
                "sand": "#e9a35f",
                "shadow": "#8a4b2a",
                "near": "#7a3a1f",
            },
            {
                "top": "#4b2c5e",
                "bottom": "#f2a37a",
                "sun": "#ffd9a8",
                "sand": "#d98a63",
                "shadow": "#5b2a3e",
                "near": "#3a1a2c",
            },
            {
                "top": "#7fb2d9",
                "bottom": "#f5dcc0",
                "sun": "#ffffff",
                "sand": "#e7bf8e",
                "shadow": "#9a6a45",
                "near": "#6e4528",
            },
            {
                "top": "#1b2140",
                "bottom": "#6b5a8e",
                "sun": "#e6dcff",
                "sand": "#8c7aa8",
                "shadow": "#2d2547",
                "near": "#1c1730",
            },
        ],
    ),
    "aurora": (
        aurora,
        [
            {
                "top": "#050b18",
                "bottom": "#0f2b3a",
                "lights": ["#34d399", "#22d3ee"],
                "far": "#0b1a24",
                "near": "#04090f",
            },
            {
                "top": "#0a0718",
                "bottom": "#24123d",
                "lights": ["#a78bfa", "#f472b6"],
                "far": "#150d26",
                "near": "#070512",
            },
            {
                "top": "#03111a",
                "bottom": "#103a3a",
                "lights": ["#86efac", "#fde68a"],
                "far": "#0a2424",
                "near": "#03100f",
            },
            {
                "top": "#080b1f",
                "bottom": "#1b2a52",
                "lights": ["#60a5fa", "#34d399"],
                "far": "#0e1733",
                "near": "#05081a",
            },
        ],
    ),
    "arena": (
        arena,
        [
            {
                "top": "#07080f",
                "bottom": "#1c1530",
                "stage": "#f99e1a",
                "beams": ["#ffd28a", "#9ad1ff"],
                "crowd": "#0d0b16",
            },
            {
                "top": "#05080f",
                "bottom": "#0f2236",
                "stage": "#38bdf8",
                "beams": ["#7dd3fc", "#ffffff"],
                "crowd": "#060c14",
            },
            {
                "top": "#0c0610",
                "bottom": "#2c0f22",
                "stage": "#f43f5e",
                "beams": ["#fda4af", "#fde68a"],
                "crowd": "#12070e",
            },
            {
                "top": "#080a0c",
                "bottom": "#1a2320",
                "stage": "#a3e635",
                "beams": ["#d9f99d", "#ffffff"],
                "crowd": "#0a0e0c",
            },
        ],
    ),
    "planet": (
        planet,
        [
            {
                "top": "#04050d",
                "bottom": "#151b3a",
                "glow": "#6d8cff",
                "light": "#f5d0a9",
                "body": "#c27a4a",
                "dark": "#2a1408",
                "ring": "#f3e3c3",
            },
            {
                "top": "#060310",
                "bottom": "#24103a",
                "glow": "#c084fc",
                "light": "#c4b5fd",
                "body": "#6d4bb5",
                "dark": "#1a0e33",
                "ring": "#e9d5ff",
            },
            {
                "top": "#02080c",
                "bottom": "#0b2a33",
                "glow": "#2dd4bf",
                "light": "#a7f3d0",
                "body": "#2f8a7a",
                "dark": "#06201c",
                "ring": "#d1fae5",
            },
            {
                "top": "#0a0505",
                "bottom": "#2b1210",
                "glow": "#fb923c",
                "light": "#fed7aa",
                "body": "#c2410c",
                "dark": "#2a0d04",
                "ring": "#ffedd5",
            },
        ],
    ),
    "forest": (
        forest,
        [
            {
                "top": "#9cc3d5",
                "bottom": "#e8efe4",
                "sun": "#fffbea",
                "mist": "#cfdccf",
                "near": "#1d3326",
            },
            {
                "top": "#3d4f7a",
                "bottom": "#f0b49e",
                "sun": "#ffe3c7",
                "mist": "#c99a94",
                "near": "#1c1f33",
            },
            {
                "top": "#1d2b2a",
                "bottom": "#6f8f7f",
                "sun": "#e3f1e6",
                "mist": "#5d7d6e",
                "near": "#0b1512",
            },
            {
                "top": "#f2c6a0",
                "bottom": "#f7e9d7",
                "sun": "#ffffff",
                "mist": "#e3c3a8",
                "near": "#4a2a1d",
            },
        ],
    ),
}

STYLE_LABELS = {
    "landscape": "山峦",
    "skyline": "夜景",
    "geometric": "几何",
    "waves": "海面",
    "dunes": "沙丘",
    "aurora": "极光",
    "arena": "舞台",
    "planet": "星球",
    "forest": "松林",
}

# Styles interleave, so neighbouring ids never share a scene.
CATALOGUE = [(style, variant) for variant in range(4) for style in STYLES]


def render(index: int) -> str:
    style, variant = CATALOGUE[index]
    draw, palettes = STYLES[style]
    seed = 1000 * (list(STYLES).index(style) + 1) + variant
    return draw(random.Random(seed), palettes[variant]).render()


def filename(index: int) -> str:
    return f"cover-{index + 1:02d}.svg"


def pick(obj) -> int:
    """The same picture for the same object, every time (13.2.5)."""
    offset = KIND_OFFSETS.get(obj._meta.label_lower, 0)
    return ((obj.pk or 0) + offset) % len(CATALOGUE)


def static_path(obj) -> str:
    return f"{DIRECTORY}/{filename(pick(obj))}"


def catalogue() -> list[tuple[str, str]]:
    """(static path, style label) for every picture, for the style guide."""
    return [
        (f"{DIRECTORY}/{filename(i)}", STYLE_LABELS[style])
        for i, (style, _variant) in enumerate(CATALOGUE)
    ]

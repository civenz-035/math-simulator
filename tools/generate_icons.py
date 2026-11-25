#!/usr/bin/env python3
"""Generate Dice Lab PWA icons with the Python standard library only.

No Pillow, no ImageMagick, no network. Run from the repo root:

    python3 tools/generate_icons.py

Outputs (web/icons/):
    icon-192.png
    icon-512.png
    icon-maskable-512.png
    apple-touch-icon.png
"""

from __future__ import annotations

import math
import os
import struct
import zlib

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT_DIR = os.path.join(ROOT, "web", "icons")

SCALE = 2  # supersampling factor (2x is plenty for rounded shapes)

ACCENT_A = (0x6B, 0x8C, 0xFF)
ACCENT_B = (0xA7, 0x8B, 0xFA)
DIE_TOP = (250, 251, 255)
DIE_BOTTOM = (224, 230, 243)
PIP = (26, 34, 54)


def _lerp(a: int, b: int, t: float) -> int:
    return int(round(a + (b - a) * t))


def _rounded_rect_sdf(px: float, py: float, half_w: float, half_h: float, r: float) -> float:
    qx = abs(px) - (half_w - r)
    qy = abs(py) - (half_h - r)
    outside = math.hypot(max(qx, 0.0), max(qy, 0.0))
    inside = min(max(qx, qy), 0.0)
    return outside + inside - r


def _background(x: float, y: float, size: float) -> tuple[int, int, int, int]:
    """Gradient rounded-square app icon background."""
    half = size / 2.0
    sdf = _rounded_rect_sdf(x - half, y - half, half, half, size * 0.22)
    if sdf > 0.5:
        return (0, 0, 0, 0)
    # Soft edge coverage (sdf is in pixels, so 1px AA is enough at 2x).
    alpha = 255 if sdf <= -0.5 else int(round(255 * (0.5 - sdf)))
    t = max(0.0, min(1.0, (x + y) / (2.0 * size)))
    r = _lerp(ACCENT_A[0], ACCENT_B[0], t)
    g = _lerp(ACCENT_A[1], ACCENT_B[1], t)
    b = _lerp(ACCENT_A[2], ACCENT_B[2], t)
    # Subtle top-left highlight.
    d = math.hypot(x - size * 0.22, y - size * 0.16) / size
    glow = max(0.0, 1.0 - d * 2.4) * 0.16
    return (
        min(255, int(r + (255 - r) * glow)),
        min(255, int(g + (255 - g) * glow)),
        min(255, int(b + (255 - b) * glow)),
        max(0, min(255, alpha)),
    )


def _shade(colour, factor: float):
    r, g, b, a = colour
    return (
        max(0, min(255, int(r * factor))),
        max(0, min(255, int(g * factor))),
        max(0, min(255, int(b * factor))),
        a,
    )


def _blend(dst, src):
    sr, sg, sb, sa = src
    if sa <= 0:
        return dst
    dr, dg, db, da = dst
    a = sa / 255.0
    out_a = sa + da * (1.0 - a)
    if out_a <= 0:
        return (0, 0, 0, 0)
    r = (sr * sa + dr * da * (1.0 - a)) / out_a
    g = (sg * sa + dg * da * (1.0 - a)) / out_a
    b = (sb * sa + db * da * (1.0 - a)) / out_a
    return (int(r), int(g), int(b), int(out_a))


def render(size: int, maskable: bool = False) -> list[bytearray]:
    """Render one icon at SCALE x then box-downsample to `size`."""
    big = size * SCALE
    pixels = [bytearray(big * 4) for _ in range(big)]

    die_ratio = 0.46 if maskable else 0.56
    die = big * die_ratio
    half = die / 2.0
    radius = die * 0.16
    cx = cy = big / 2.0
    pip_r = die * 0.075
    offset = die * 0.235
    pips = [
        (cx - offset, cy - offset),
        (cx + offset, cy - offset),
        (cx, cy),
        (cx - offset, cy + offset),
        (cx + offset, cy + offset),
    ]

    for y in range(big):
        fy = y + 0.5
        row = pixels[y]
        for x in range(big):
            fx = x + 0.5
            colour = _background(fx, fy, big)
            if colour[3] == 0:
                continue

            # Drop shadow under the die.
            shadow_sdf = _rounded_rect_sdf(
                fx - cx, fy - cy - die * 0.025, half, half, radius
            )
            if shadow_sdf <= 0.5:
                a = 70 if shadow_sdf <= -0.5 else int(70 * (0.5 - shadow_sdf))
                colour = _blend(colour, (10, 14, 28, max(0, a)))

            # Die body with a gentle top-to-bottom sheen.
            sdf = _rounded_rect_sdf(fx - cx, fy - cy, half, half, radius)
            if sdf <= 0.5:
                t = max(0.0, min(1.0, (fy - (cy - half)) / die))
                body = tuple(
                    _lerp(DIE_TOP[i], DIE_BOTTOM[i], t) for i in range(3)
                ) + (255,)
                if sdf > -0.5:
                    body = (body[0], body[1], body[2], int(255 * (0.5 - sdf)))
                colour = _blend(colour, body)

                # Pips.
                for px, py in pips:
                    if math.hypot(fx - px, fy - py) <= pip_r:
                        colour = _blend(colour, PIP + (255,))
            o = x * 4
            row[o:o + 4] = bytes((colour[0], colour[1], colour[2], colour[3]))

    # Box downsample SCALE x SCALE.
    out = [bytearray(size * 4) for _ in range(size)]
    area = SCALE * SCALE
    for y in range(size):
        for x in range(size):
            sr = sg = sb = sa = 0
            for dy in range(SCALE):
                row = pixels[y * SCALE + dy]
                for dx in range(SCALE):
                    o = (x * SCALE + dx) * 4
                    sr += row[o]
                    sg += row[o + 1]
                    sb += row[o + 2]
                    sa += row[o + 3]
            o = x * 4
            out[y][o:o + 4] = bytes(
                (sr // area, sg // area, sb // area, sa // area)
            )
    return out


def _chunk(kind: bytes, data: bytes) -> bytes:
    return (
        struct.pack(">I", len(data))
        + kind
        + data
        + struct.pack(">I", zlib.crc32(kind + data) & 0xFFFFFFFF)
    )


def write_png(path: str, size: int, rows: list[bytearray]) -> None:
    raw = b"".join(b"\x00" + bytes(row) for row in rows)
    png = (
        b"\x89PNG\r\n\x1a\n"
        + _chunk(b"IHDR", struct.pack(">IIBBBBB", size, size, 8, 6, 0, 0, 0))
        + _chunk(b"IDAT", zlib.compress(raw, 9))
        + _chunk(b"IEND", b"")
    )
    with open(path, "wb") as f:
        f.write(png)


def main() -> None:
    os.makedirs(OUT_DIR, exist_ok=True)
    jobs = [
        ("icon-192.png", 192, False),
        ("icon-512.png", 512, False),
        ("icon-maskable-512.png", 512, True),
        ("apple-touch-icon.png", 180, False),
    ]
    for name, size, maskable in jobs:
        rows = render(size, maskable=maskable)
        path = os.path.join(OUT_DIR, name)
        write_png(path, size, rows)
        print(f"  wrote {name} ({size}x{size})")


if __name__ == "__main__":
    main()

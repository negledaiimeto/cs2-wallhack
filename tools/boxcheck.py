#!/usr/bin/env python3
"""Find the green spawn-box outlines in a decoded radar BMP and print their
normalized centers, so txt landmarks / spawn ground truth can be checked
exactly instead of by eye.

Usage: boxcheck.py <map.bmp> [name]
"""
import struct
import sys
from collections import deque


def load_bmp24(path):
    with open(path, "rb") as f:
        data = f.read()
    off = struct.unpack_from("<I", data, 10)[0]
    w, h = struct.unpack_from("<ii", data, 18)
    bpp = struct.unpack_from("<H", data, 28)[0]
    if bpp != 24:
        raise SystemExit("expected 24bpp")
    bottom_up = h > 0
    h = abs(h)
    row_pad = (-(w * 3)) % 4
    px = bytearray(w * h * 3)
    p = off
    for row in range(h):
        y = (h - 1 - row) if bottom_up else row
        line = data[p:p + w * 3]
        px[y * w * 3:(y + 1) * w * 3] = line
        p += w * 3 + row_pad
    return px, w, h


def green(r, g, b):
    return g > 150 and g - r > 55 and g - b > 55


def clusters(px, w, h):
    mask = bytearray(w * h)
    for i in range(w * h):
        r, g, b = px[i * 3], px[i * 3 + 1], px[i * 3 + 2]
        if green(r, g, b):
            mask[i] = 1
    seen = bytearray(w * h)
    out = []
    for start in range(w * h):
        if mask[start] and not seen[start]:
            q = deque([start])
            seen[start] = 1
            pts = []
            while q:
                i = q.popleft()
                pts.append(i)
                x, y = i % w, i // w
                for nx, ny in ((x - 1, y), (x + 1, y), (x, y - 1), (x, y + 1)):
                    if 0 <= nx < w and 0 <= ny < h:
                        j = ny * w + nx
                        if mask[j] and not seen[j]:
                            seen[j] = 1
                            q.append(j)
            if len(pts) >= 40:  # ignore noise specks
                xs = [i % w for i in pts]
                ys = [i // w for i in pts]
                cx = sum(xs) / len(xs)
                cy = sum(ys) / len(ys)
                out.append((cx / w, cy / h, len(pts),
                            (min(xs), min(ys), max(xs), max(ys))))
    return out


def main():
    path = sys.argv[1]
    name = sys.argv[2] if len(sys.argv) > 2 else path
    px, w, h = load_bmp24(path)
    print("==", name)
    for cx, cy, n, bbox in sorted(clusters(px, w, h), key=lambda c: c[1]):
        print("  green box center u=%.4f v=%.4f  px=%d bbox=%s" % (cx, cy, n, bbox))


if __name__ == "__main__":
    main()

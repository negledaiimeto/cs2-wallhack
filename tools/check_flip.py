#!/usr/bin/env python3
"""Which source (and orientation) do the shipped radar BMPs actually contain?

Diffs each shipped bmp against every resampled source in 4 orientations
(normal/hflip/vflip/180). Lowest mean-abs-diff wins.
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from gen_radar import load_bmp24, resample, ART_DIR, PROJ


def nudge(px, w, h):
    """Undo the writer's black->(8,8,8) nudge so diffs compare like for like."""
    for row in px:
        for i in range(0, w * 3, 3):
            if row[i] == 8 and row[i + 1] == 8 and row[i + 2] == 8:
                row[i] = row[i + 1] = row[i + 2] = 0
    return px


def flip(rows, w, h, mode):
    if mode == "h":
        return [bytearray(r[:w * 3][::-1]) for r in rows]
    if mode == "v":
        return [bytearray(r) for r in rows[::-1]]
    if mode == "180":
        return [bytearray(r[:w * 3][::-1]) for r in rows[::-1]]
    return [bytearray(r) for r in rows]


def mean_diff(a, b, w, h):
    tot = n = 0
    for y in range(h):
        ra, rb = a[y], b[y]
        for x in range(0, w * 3, 3):
            for c in range(3):
                tot += abs(ra[x + c] - rb[x + c])
                n += 1
    return tot / n


def main():
    radar_dir = os.path.join(PROJ, "bin", "Release", "radar")
    shipped = sorted(f for f in os.listdir(radar_dir) if f.endswith(".bmp"))
    # cache resampled sources per (name, size)
    cache = {}

    def cand(name, w, h, mode):
        key = (name, w, h, mode)
        if key not in cache:
            rows, sw, sh = load_bmp24(os.path.join(ART_DIR, name + "_radar_psd.bmp"))
            rows = resample(rows, sw, sh, w, h)
            cache[key] = flip(rows, w, h, mode)
        return cache[key]

    sources = sorted(
        os.path.splitext(f)[0][: -len("_radar_psd")]
        for f in os.listdir(ART_DIR)
        if f.endswith("_radar_psd.bmp")
    )

    for sf in shipped:
        ship, w, h = load_bmp24(os.path.join(radar_dir, sf))
        nudge(ship, w, h)
        name = os.path.splitext(sf)[0]
        scores = []
        for src in sources:
            for mode in ("n", "h", "v", "180"):
                scores.append((mean_diff(cand(src, w, h, mode), ship, w, h), src, mode))
        scores.sort()
        best = scores[0]
        same = [s for s in scores if s[1] == name]
        tag = ""
        if name in sources:
            tag = "  own=%s/%s d=%.2f" % (same[0][2], same[0][1], same[0][0])
        print("%-16s %dx%d best=%s/%s d=%.2f%s"
              % (sf, w, h, best[1], best[2], best[0], tag))


if __name__ == "__main__":
    main()

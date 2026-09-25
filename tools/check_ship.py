#!/usr/bin/env python3
"""Is the shipped de_inferno.bmp really inferno art?

Box-resample both full-res sources to 120x120 and diff against the shipped
120x120 bmp (black->8 nudge accounted for). Lower mean-abs-diff wins.
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from gen_radar import load_bmp24, resample, ART_DIR, PROJ


def nudge(px):
    for row in px:
        for i in range(0, len(row), 3):
            if row[i] == 8 and row[i + 1] == 8 and row[i + 2] == 8:
                row[i] = row[i + 1] = row[i + 2] = 0
    return px


def mean_diff(a, b, w, h):
    tot = n = 0
    for y in range(h):
        ra, rb = a[y], b[y]
        for x in range(w * 3):
            tot += abs(ra[x] - rb[x])
            n += 1
    return tot / n


def to_size(name, dw, dh):
    rows, w, h = load_bmp24(os.path.join(ART_DIR, name + "_radar_psd.bmp"))
    return resample(rows, w, h, dw, dh)


ship, sw, sh = load_bmp24(os.path.join(PROJ, "bin", "Release", "radar",
                                       "de_inferno.bmp"))
nudge(ship)
print("shipped de_inferno.bmp %dx%d" % (sw, sh))
for src in ("de_inferno", "de_dust2", "de_mirage", "de_anubis"):
    cand = to_size(src, sw, sh)
    print("  vs resampled %-10s mean-abs-diff = %6.2f"
          % (src, mean_diff(cand, ship, sw, sh)))

ship2, w2, h2 = load_bmp24(os.path.join(PROJ, "bin", "Release", "radar",
                                        "de_dust2.bmp"))
nudge(ship2)
print("shipped de_dust2.bmp %dx%d" % (w2, h2))
for src in ("de_dust2", "de_inferno"):
    cand = to_size(src, w2, h2)
    print("  vs resampled %-10s mean-abs-diff = %6.2f"
          % (src, mean_diff(cand, ship2, w2, h2)))

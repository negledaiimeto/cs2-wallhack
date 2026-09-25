#!/usr/bin/env python3
"""Locate the row-order flip: write roundtrip vs resample orientation."""
import os
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from gen_radar import load_bmp24, write_bmp24, resample, ART_DIR


def rowdiff(a, b):
    n = sum(abs(x - y) for ra, rb in zip(a, b) for x, y in zip(ra, rb))
    return n / max(1, sum(len(r) for r in a))


def vflip(rows):
    return [bytearray(r) for r in rows[::-1]]


# 1) write -> load roundtrip on a real source
src = os.path.join(ART_DIR, "de_inferno_radar_psd.bmp")
rows, w, h = load_bmp24(src)
tmp = os.path.join(tempfile.gettempdir(), "rt_test.bmp")
write_bmp24(tmp, rows, w, h)
back, w2, h2 = load_bmp24(tmp)
print("roundtrip identity diff = %.4f  vflip diff = %.4f"
      % (rowdiff(rows, back), rowdiff(rows, vflip(back))))

# 2) resample orientation: 8-row image, top half white, bottom half red
test = []
for y in range(8):
    row = bytearray()
    for x in range(8):
        row += bytes((255, 255, 255)) if y < 4 else bytes((0, 0, 255))
    test.append(row)
small = resample(test, 8, 8, 4, 4)
top = small[0]
bot = small[3]
print("resample top row = %s (white=(255,255,255)) bottom row = %s (red=(0,0,255) BGR)"
      % (tuple(top[0:3]), tuple(bot[0:3])))

#!/usr/bin/env python3
"""Convert a 24bpp bmp to png (for eyeballing shipped radar art)."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from gen_radar import load_bmp24, write_png

src = sys.argv[1]
dst = sys.argv[2] if len(sys.argv) > 2 else os.path.splitext(src)[0] + ".png"
rows, w, h = load_bmp24(src)
write_png(dst, rows, w, h)
print("%s -> %s (%dx%d)" % (src, dst, w, h))

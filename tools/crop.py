#!/usr/bin/env python3
"""Crop a region of a png (nearest, no deps) for eyeballing."""
import sys
from struct import unpack
import zlib

import struct

def load_png(path):
    with open(path, "rb") as f:
        data = f.read()
    assert data[:8] == b"\x89PNG\r\n\x1a\n"
    pos, idat, w, h = 8, bytearray(), 0, 0
    channels = 3
    while pos < len(data):
        ln = unpack(">I", data[pos:pos + 4])[0]
        tag = data[pos + 4:pos + 8]
        chunk = data[pos + 8:pos + 8 + ln]
        if tag == b"IHDR":
            w, h, bd, ct = unpack(">IIBB", chunk[:10])
            channels = 3 if ct == 2 else 4
        elif tag == b"IDAT":
            idat += chunk
        pos += 12 + ln
    raw = zlib.decompress(bytes(idat))
    stride = w * channels
    out = bytearray(w * h * 3)
    prev = bytearray(stride)
    p = 0
    for y in range(h):
        ft = raw[p]; p += 1
        line = bytearray(raw[p:p + stride]); p += stride
        if ft == 1:
            for i in range(channels, stride):
                line[i] = (line[i] + line[i - channels]) & 255
        elif ft == 2:
            for i in range(stride):
                line[i] = (line[i] + prev[i]) & 255
        elif ft == 3:
            for i in range(stride):
                a = line[i - channels] if i >= channels else 0
                line[i] = (line[i] + ((a + prev[i]) >> 1)) & 255
        elif ft == 4:
            for i in range(stride):
                a = line[i - channels] if i >= channels else 0
                b = prev[i]
                c = prev[i - channels] if i >= channels else 0
                pa, pb, pc = abs(b - c), abs(a - c), abs(a + b - 2 * c)
                pr = a if (pa <= pb and pa <= pc) else (b if pb <= pc else c)
                line[i] = (line[i] + pr) & 255
        for x in range(w):
            o = (y * w + x) * 3
            s = x * channels
            out[o], out[o + 1], out[o + 2] = line[s], line[s + 1], line[s + 2]
        prev = line
    return out, w, h

src, dst = sys.argv[1], sys.argv[2]
x0, y0, x1, y1 = (int(v) for v in sys.argv[3:7])
scale = int(sys.argv[7]) if len(sys.argv) > 7 else 1
px, w, h = load_png(src)
rows = []
for y in range(y0, min(y1, h)):
    line = bytearray()
    for x in range(x0, min(x1, w)):
        o = (y * w + x) * 3
        line += bytes(px[o:o + 3])
        if scale > 1:
            row = bytearray()
            for p in range(0, len(line), 3):
                row += line[p:p + 3] * scale
        else:
            row = line
    rows.append(row)
ow = (min(x1, w) - x0) * scale
if scale > 1:
    rows = [r for r in rows for _ in range(scale)]
oh = len(rows)
raw = bytearray()
for r in rows:
    raw.append(0)
    raw += r

def chunk(tag, payload):
    return (struct.pack(">I", len(payload)) + tag + payload +
            struct.pack(">I", zlib.crc32(tag + payload) & 0xFFFFFFFF))

import struct
with open(dst, "wb") as f:
    f.write(b"\x89PNG\r\n\x1a\n")
    f.write(chunk(b"IHDR", struct.pack(">IIBBBBB", ow, oh, 8, 2, 0, 0, 0)))
    f.write(chunk(b"IDAT", zlib.compress(bytes(raw), 6)))
    f.write(chunk(b"IEND", b""))
print("%s -> %s (%dx%d x%d)" % (src, dst, ow, oh, scale))

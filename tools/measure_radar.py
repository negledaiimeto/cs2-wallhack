#!/usr/bin/env python3
"""Measure the radar panel in a screenshot: border rect, local (green) dot,
enemy (red) / teammate (blue) blips. Verifies the local dot sits on the
panel centre as DrawRadar intends."""
import sys
from struct import unpack
import zlib

def load_png(path):
    with open(path, "rb") as f:
        data = f.read()
    assert data[:8] == b"\x89PNG\r\n\x1a\n"
    pos, idat, w, h = 8, bytearray(), 0, 0
    while pos < len(data):
        ln = unpack(">I", data[pos:pos + 4])[0]
        tag = data[pos + 4:pos + 8]
        chunk = data[pos + 8:pos + 8 + ln]
        if tag == b"IHDR":
            w, h, bd, ct = unpack(">IIBB", chunk[:10])
            assert bd == 8 and ct in (2, 6), "expected rgb/rgba8"
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

def near(px, o, col, tol):
    return (abs(px[o] - col[0]) <= tol and abs(px[o + 1] - col[1]) <= tol
            and abs(px[o + 2] - col[2]) <= tol)

def clusters(pts, gap=6):
    cl = []
    for p in pts:
        for c in cl:
            if any(abs(p[0] - q[0]) <= gap and abs(p[1] - q[1]) <= gap for q in c):
                c.append(p); break
        else:
            cl.append([p])
    # merge clusters that grew into each other
    merged = True
    while merged:
        merged = False
        for i in range(len(cl)):
            for j in range(i + 1, len(cl)):
                if any(abs(a[0] - b[0]) <= gap and abs(a[1] - b[1]) <= gap
                       for a in cl[i] for b in cl[j]):
                    cl[i] += cl[j]; del cl[j]; merged = True; break
            if merged: break
    out = []
    for c in cl:
        xs = [p[0] for p in c]; ys = [p[1] for p in c]
        out.append((min(xs), min(ys), max(xs), max(ys),
                    len(c), sum(xs) // len(c), sum(ys) // len(c)))
    return out

path = sys.argv[1] if len(sys.argv) > 1 else "screen_chk.png"
px, w, h = load_png(path)
print("image %dx%d" % (w, h))

GREEN  = (60, 220, 90)
REDV   = (255, 70, 70)
REDNV  = (150, 45, 45)
BLUE   = (80, 180, 255)
BORDER = (70, 130, 200)
BG     = (24, 26, 32)

# scan only the top-right quadrant where the panel lives
x0 = w // 2
def scan(col, tol=18):
    pts = []
    for y in range(0, h // 2):
        for x in range(x0, w):
            if near(px, (y * w + x) * 3, col, tol):
                pts.append((x, y))
    return pts

bp = scan(BORDER, 10)
gp = scan(GREEN, 40)
rv = scan(REDV, 40)
rn = scan(REDNV, 30)
bl = scan(BLUE, 40)

def show(name, pts):
    if not pts:
        print("%-7s none" % name); return []
    cs = clusters(pts)
    cs.sort(key=lambda c: -c[4])
    for c in cs[:8]:
        print("%-7s bbox=(%d,%d)-(%d,%d) n=%d centre=(%d,%d)"
              % (name, c[0], c[1], c[2], c[3], c[4], c[5], c[6]))
    return cs

bcs = show("border", bp)
gcs = show("green", gp)
show("redv", rv)
show("rednv", rn)
show("blue", bl)

if bcs:
    b = bcs[0]
    bx0, by0, bx1, by1 = b[0], b[1], b[2], b[3]
    print("\npanel bbox=(%d,%d)-(%d,%d) size=%dx%d centre=(%d,%d)"
          % (bx0, by0, bx1, by1, bx1 - bx0, by1 - by0,
             (bx0 + bx1) // 2, (by0 + by1) // 2))
    if gcs:
        g = gcs[0]
        print("green dot centre=(%d,%d) offset from panel centre = (%+d,%+d)"
              % (g[5], g[6], g[5] - (bx0 + bx1) // 2, g[6] - (by0 + by1) // 2))
print("\nexpected panel centre at 1280x720: (1188,92); at 1920x1080: (1828,92)")

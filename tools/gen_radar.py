#!/usr/bin/env python3
"""Build radar assets for the cheat from decoded radar art + overview txts.

For every resource/overviews/<name>.txt that has decoded art in
tools/game/radar, this emits:
  * radar_cal.hpp          — {name, posX, posY, scale, rot, lowerZ} table
  * bin/<cfg>/radar/<name>.bmp[+_lower] — art box-resampled to the exact
    size it occupies on the minimap (kRadarSize/2-8 / kRadarRange px per
    world unit), so the runtime PlgBlt rotates ~1:1 instead of minifying
    1024:1 through nearest-neighbour.

Calibration rules (verified against spawn setpos ground truth):
  rot 0: worldX = posX + u*scale, worldY = posY - v*scale   (mirage, anubis)
  rot 1: worldX = posY - v*scale, worldY = posX + u*scale   (dust2)
lowerZ: local z <= lowerZ draws the _lower art (nuke/vertigo use the values
the working reference radar tuned visually; others come from the txt).
"""
import os
import re
import struct
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
PROJ = os.path.dirname(HERE)
GAME = os.path.join(HERE, "game")
TXT_DIR = os.path.join(GAME, "resource", "overviews")
ART_DIR = os.path.join(GAME, "radar")

# must match main.cpp: inner = U(kRadarSize)*0.5 - 8, s = inner / kRadarRange
# panel is kRadarSize=240 design px, *1.5 for the 150%-scaled display the
# overlay targets, so the art arrives ~1:1 instead of upscaling 2x blurry.
RADAR_PX_PER_UNIT = (240 * 0.5 - 8) * 1.5 / 3000.0

# visually tuned by the reference radar (txt boundary sits 15-20 units lower)
LOWER_Z_OVERRIDE = {"de_nuke": -480.0, "de_vertigo": 11720.0}

SUFFIXES = ["_night", "_v1", "_v2", "_s2", "_2v2"]


def field(text, key):
    m = re.search(r'"%s"\s+"(-?[\d.]+)"' % re.escape(key), text)
    return float(m.group(1)) if m else None


def lower_alt(text):
    # the key line carries a comment ("lower" // i.e. ...) before its brace,
    # so match non-greedily from "lower" to the block's own AltitudeMax
    m = re.search(r'"lower".*?"AltitudeMax"\s+"(-?[\d.]+)"', text, re.S)
    return float(m.group(1)) if m else None


def load_bmp24(path):
    with open(path, "rb") as f:
        data = f.read()
    if data[:2] != b"BM":
        raise ValueError("not a bmp: " + path)
    off = struct.unpack_from("<I", data, 10)[0]
    w, h = struct.unpack_from("<ii", data, 18)
    bpp, comp = struct.unpack_from("<HI", data, 28)
    if bpp != 24 or comp != 0:
        raise ValueError("expected plain 24bpp: " + path)
    bottom_up = h > 0
    h = abs(h)
    stride = (w * 3 + 3) & ~3
    px = [bytearray() for _ in range(h)]
    p = off
    rows = [data[p + i * stride: p + i * stride + w * 3] for i in range(h)]
    for row in range(h):
        # standard BMP: file row 0 is the bottom, so px[row] (top-down)
        # must take file row h-1-row; negative-height files are top-down.
        src = rows[h - 1 - row] if bottom_up else rows[row]
        px[row] = bytearray(src)   # top-down
    return px, w, h


def write_bmp24(path, rows, w, h):
    """24bpp bottom-up; pure black -> (8,8,8) so the overlay color key
    (black = transparent) cannot punch holes in the art."""
    stride = (w * 3 + 3) & ~3
    pad = b"\x00" * (stride - w * 3)
    body = bytearray()
    for y in range(h - 1, -1, -1):
        row = rows[y]
        if not any(row):            # fully black row: nudge whole row
            body += bytes((8, 8, 8)) * w + pad
            continue
        out = bytearray()
        for x in range(w):
            i = x * 3
            r, g, b = row[i], row[i + 1], row[i + 2]
            if r == 0 and g == 0 and b == 0:
                r = g = b = 8
            out += bytes((r, g, b))
        body += out + pad
    hdr = struct.pack("<2sIHHI", b"BM", 54 + len(body), 0, 0, 54)
    info = struct.pack("<IiiHHIIiiII", 40, w, h, 1, 24, 0, len(body),
                       2835, 2835, 0, 0)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "wb") as f:
        f.write(hdr + info + body)


def write_png(path, rows, w, h):
    import zlib
    raw = bytearray()
    for r in rows:
        raw.append(0)
        raw += r

    def chunk(tag, payload):
        return (struct.pack(">I", len(payload)) + tag + payload +
                struct.pack(">I", zlib.crc32(tag + payload) & 0xFFFFFFFF))

    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "wb") as f:
        f.write(b"\x89PNG\r\n\x1a\n")
        f.write(chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0)))
        f.write(chunk(b"IDAT", zlib.compress(bytes(raw), 6)))
        f.write(chunk(b"IEND", b""))


def axis_weights(src_n, dst_n):
    """For each destination index, [(src_index, weight)] covering its box."""
    out = []
    span = src_n / dst_n
    for i in range(dst_n):
        a = i * span
        b = (i + 1) * span
        lo, hi = int(a), min(int(b) + (0 if b == int(b) else 1), src_n)
        entries = []
        for s in range(lo, hi):
            w = min(b, s + 1) - max(a, s)
            if w > 0:
                entries.append((s, w))
        out.append(entries)
    return out


def resample(rows, sw, sh, dw, dh):
    """Area-average box filter (separable)."""
    cw = axis_weights(sw, dw)
    ch = axis_weights(sh, dh)
    # horizontal pass: dw x sh
    tmp = []
    for y in range(sh):
        src = rows[y]
        row = bytearray(dw * 3)
        for x in range(dw):
            acc0 = acc1 = acc2 = tw = 0
            for sx, w in cw[x]:
                i = sx * 3
                acc0 += src[i] * w
                acc1 += src[i + 1] * w
                acc2 += src[i + 2] * w
                tw += w
            row[x * 3] = round(acc0 / tw)
            row[x * 3 + 1] = round(acc1 / tw)
            row[x * 3 + 2] = round(acc2 / tw)
        tmp.append(row)
    # vertical pass: dw x dh
    out = []
    for y in range(dh):
        row = bytearray(dw * 3)
        for x in range(dw):
            acc0 = acc1 = acc2 = tw = 0
            for sy, w in ch[y]:
                i = x * 3
                acc0 += tmp[sy][i] * w
                acc1 += tmp[sy][i + 1] * w
                acc2 += tmp[sy][i + 2] * w
                tw += w
            row[x * 3] = round(acc0 / tw)
            row[x * 3 + 1] = round(acc1 / tw)
            row[x * 3 + 2] = round(acc2 / tw)
        out.append(row)
    return out


def resolve_art(name):
    """<txt name> -> decoded art base name (without _radar_psd)."""
    cand = name
    for _ in range(3):
        if os.path.exists(os.path.join(ART_DIR, cand + "_radar_psd.bmp")):
            return cand
        for suf in SUFFIXES:
            if cand.endswith(suf):
                cand = cand[: -len(suf)]
                break
        else:
            return None
    return None


def main():
    entries = []
    skipped = []
    preview_dir = os.path.join(GAME, "radar_small")
    for fn in sorted(os.listdir(TXT_DIR)):
        if not fn.endswith(".txt"):
            continue
        name = fn[:-4]
        with open(os.path.join(TXT_DIR, fn), "r", encoding="utf-8",
                  errors="replace") as f:
            text = f.read()
        px, py, scale = field(text, "pos_x"), field(text, "pos_y"), field(text, "scale")
        if px is None or py is None or scale is None:
            skipped.append((name, "no pos/scale"))
            continue
        art = resolve_art(name)
        if art is None:
            skipped.append((name, "no art"))
            continue
        rot = int(field(text, "rotate") or 0)
        lo = LOWER_Z_OVERRIDE.get(name, lower_alt(text))
        if lo is None:
            lo = 1e30

        # art files: exact-name first (so game map name == file name)
        made = []
        ow = oh = None
        for suffix, zmin in (("", None), ("_lower", lo)):
            src = os.path.join(ART_DIR, art + suffix + "_radar_psd.bmp")
            if not os.path.exists(src):
                if suffix and (name in LOWER_Z_OVERRIDE or lower_alt(text)):
                    print("warn: %s wants lower art but %s missing"
                          % (name, os.path.basename(src)))
                continue
            if suffix and lo >= 1e29:
                print("warn: %s has lower art but no verticalsections" % name)
                continue
            rows, w, h = load_bmp24(src)
            if ow is None:
                ow, oh = w, h
            elif (w, h) != (ow, oh):
                print("warn: %s lower art %dx%d differs from %dx%d"
                      % (name, w, h, ow, oh))
            dw = max(8, round(w * scale * RADAR_PX_PER_UNIT))
            dh = max(8, round(h * scale * RADAR_PX_PER_UNIT))
            small = resample(rows, w, h, dw, dh)
            for cfg in ("Release", "Debug"):
                out = os.path.join(PROJ, "bin", cfg, "radar",
                                   name + suffix + ".bmp")
                write_bmp24(out, small, dw, dh)
            write_png(os.path.join(preview_dir, name + suffix + ".png"),
                      small, dw, dh)
            made.append("%dx%d" % (dw, dh))
        if not made:
            skipped.append((name, "art missing"))
            continue
        entries.append((name, px, py, scale, rot, lo, ow, oh))
        print("ok  %-22s pos=(%.0f,%.0f) scale=%.3f rot=%d lowerZ=%s art=%s"
              % (name, px, py, scale, rot,
                 ("%.0f" % lo) if lo < 1e29 else "-", "+".join(made)))
    for name, why in skipped:
        print("skip %-22s (%s)" % (name, why))

    hdr = os.path.join(PROJ, "radar_cal.hpp")
    with open(hdr, "w", encoding="utf-8") as f:
        f.write("// Generated by tools/gen_radar.py — do not edit by hand.\n")
        f.write("// Calibration from resource/overviews/<name>.txt (CS2 VPK):\n")
        f.write("//   rot 0: worldX = posX + u*scale, worldY = posY - v*scale\n")
        f.write("//   rot 1: worldX = posY - v*scale, worldY = posX + u*scale\n")
        f.write("// Verified against spawn setpos ground truth (dust2/mirage/anubis).\n")
        f.write("#pragma once\n\n")
        f.write("struct RadarCal {\n")
        f.write("    const char* name;    // game map name (globalvars)\n")
        f.write("    float       posX;    // overview txt: upper-left world coord\n")
        f.write("    float       posY;\n")
        f.write("    float       scale;   // world units per art pixel\n")
        f.write("    int         rot;     // 0 = classic, 1 = 90 deg image variant\n")
        f.write("    float       lowerZ;  // local z <= lowerZ draws _lower art\n")
        f.write("    int         origW;   // full-res art px the txt scale refers to;\n")
        f.write("    int         origH;   //   the shipped bmp is a resample of that rect\n")
        f.write("};\n\n")
        f.write("static const RadarCal kRadarCals[] = {\n")
        for name, px, py, scale, rot, lo, ow, oh in entries:
            zs = "1e30f" if lo >= 1e29 else "%.1ff" % lo
            f.write("    { \"%s\", %.1ff, %.1ff, %.6ff, %d, %s, %d, %d },\n"
                    % (name, px, py, scale, rot, zs, ow, oh))
        f.write("};\n")
    print("\nwrote %s (%d entries)" % (hdr, len(entries)))


if __name__ == "__main__":
    sys.exit(main())

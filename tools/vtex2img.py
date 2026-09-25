#!/usr/bin/env python3
"""Decode a Source 2 vtex_c (BGRA8888, LZ4-compressed mip) to PNG and/or 24bpp BMP.

Usage:
  vtex2img.py <file.vtex_c> <out_base> [--png] [--bmp]

Resource layout (VRF Resource.cs): u32 FileSize, u16 HeaderVersion(12),
u16 Version, u32 blockOffset, u32 blockCount; blocks at 16 + blockOffset - 8,
entry = type4 + rel-offset + size, block data at entryPos + 4 + relOffset.

DATA block = vtex header: u16 ver(1), u16 flags, 4x f32 reflectivity,
u16 w, u16 h, u16 depth, u8 format, u8 numMips, u32 picmip0Res,
u32 extraDataOffset, u32 extraDataCount; extra entries at
blockPos + 28 + extraDataOffset - 8 (type/offset/size each; data at
entryPos + 4 + relOffset). COMPRESSED_MIP_SIZE(4): int1, mipsOffset, mips
then mips x u32 sizes at dataPos + 12 + mipsOffset - 8.

Pixel data starts at dataBlock.offset + dataBlock.size. Mip file order is
smallest-first (mip N-1 .. mip 0); to reach mip 0 skip mips N-1..1.
CompressedMips[i] < uncompressed size => LZ4 block-compressed.
Format 28 = BGRA8888.
"""
import struct
import sys
import zlib


def lz4_block_decode(src, max_out):
    """Raw LZ4 block format decoder."""
    out = bytearray()
    i = 0
    n = len(src)
    while i < n:
        token = src[i]
        i += 1
        lit = token >> 4
        if lit == 15:
            while True:
                b = src[i]
                i += 1
                lit += b
                if b != 255:
                    break
        out += src[i:i + lit]
        i += lit
        if i >= n:
            break
        offset = src[i] | (src[i + 1] << 8)
        i += 2
        if offset == 0 or offset > len(out):
            raise ValueError("bad LZ4 back-reference offset %d at %d" % (offset, i))
        match = (token & 15) + 4
        if match == 19:
            while True:
                b = src[i]
                i += 1
                match += b
                if b != 255:
                    break
        start = len(out) - offset
        for k in range(match):
            out.append(out[start + k])
        if len(out) > max_out:
            raise ValueError("LZ4 output overrun")
    if len(out) != max_out:
        raise ValueError("LZ4 output size %d != expected %d" % (len(out), max_out))
    return bytes(out)


def read_cstr(data, p):
    e = data.index(b"\x00", p)
    return data[p:e].decode("utf-8", "replace"), e + 1


def parse_resource(data):
    file_size, hdr_ver, ver, block_off, block_count = struct.unpack_from("<IHHII", data, 0)
    if hdr_ver != 12:
        raise ValueError("unexpected header version %d" % hdr_ver)
    p = 16 + block_off - 8
    blocks = {}
    for _ in range(block_count):
        btype = data[p:p + 4].decode("ascii", "replace")
        rel, size = struct.unpack_from("<II", data, p + 4)
        off = p + 4 + rel
        blocks[btype] = (off, size)
        p += 12
    return blocks


def decode_vtex(data):
    blocks = parse_resource(data)
    if "DATA" not in blocks:
        raise ValueError("no DATA block")
    doff, dsize = blocks["DATA"]
    ver, flags = struct.unpack_from("<HH", data, doff)
    if ver != 1:
        raise ValueError("unexpected vtex version %d" % ver)
    refl = struct.unpack_from("<4f", data, doff + 4)
    w, h, depth = struct.unpack_from("<HHH", data, doff + 20)
    fmt = data[doff + 26]
    num_mips = data[doff + 27]
    picmip = struct.unpack_from("<I", data, doff + 28)[0]
    extra_off, extra_cnt = struct.unpack_from("<II", data, doff + 32)
    info = dict(w=w, h=h, depth=depth, fmt=fmt, mips=num_mips, flags=flags,
                refl=refl, picmip=picmip, file_size=len(data))
    if fmt not in (1, 2, 28):
        raise ValueError("unsupported format %d" % fmt)

    # extra data entries
    compressed_mips = None
    ep = doff + 40 + extra_off - 8
    for _ in range(extra_cnt):
        etype, erel, esize = struct.unpack_from("<III", data, ep)
        edata = ep + 4 + erel
        if etype == 4:  # COMPRESSED_MIP_SIZE
            int1, mips_off, mips_cnt = struct.unpack_from("<iii", data, edata)
            compressed_mips = list(
                struct.unpack_from("<%dI" % mips_cnt, data, edata + 12 + mips_off - 8))
        ep += 12
    info["cmips"] = compressed_mips

    raw_start = doff + dsize
    if fmt == 28:
        max_out = w * h * 4
    elif fmt == 2:
        max_out = w * h          # DXT5: 16 B per 4x4 block = 1 B/px
    else:
        max_out = w * h // 2     # DXT1: 8 B per 4x4 block
    # skip smaller mips first (file order: mip N-1 .. mip 0)
    p = raw_start
    if compressed_mips:
        for j in range(num_mips - 1, 0, -1):
            p += compressed_mips[j]
        m0 = compressed_mips[0]
    else:
        m0 = len(data) - raw_start
    buf = data[p:p + m0]
    if len(buf) != max_out and compressed_mips and m0 < max_out:
        buf = lz4_block_decode(buf, max_out)
    elif len(buf) != max_out:
        raise ValueError("raw pixel size %d != %d" % (len(buf), max_out))
    info["pixel_bytes"] = len(buf)
    return buf, info


def dxt5_to_rgba(data, w, h):
    """Decode BC3/DXT5 blocks to RGBA."""
    out = bytearray(w * h * 4)
    bw = (w + 3) // 4
    bh = (h + 3) // 4
    p = 0

    def e565(v):
        r, g, b = (v >> 11) & 31, (v >> 5) & 63, v & 31
        return ((r << 3) | (r >> 2), (g << 2) | (g >> 4), (b << 3) | (b >> 2))

    for by in range(bh):
        for bx in range(bw):
            blk = data[p:p + 16]
            p += 16
            a0, a1 = blk[0], blk[1]
            abits = int.from_bytes(blk[2:8], "little")
            if a0 > a1:
                atab = [a0, a1] + [((8 - i) * a0 + (i - 1) * a1) // 7 for i in range(2, 8)]
            else:
                atab = ([a0, a1] + [((6 - i) * a0 + (i - 1) * a1) // 5 for i in range(2, 6)]
                        + [0, 255])
            c0 = blk[8] | (blk[9] << 8)
            c1 = blk[10] | (blk[11] << 8)
            ci = int.from_bytes(blk[12:16], "little")
            e0, e1 = e565(c0), e565(c1)
            if c0 > c1:
                pal = [e0, e1,
                       tuple((2 * e0[k] + e1[k]) // 3 for k in range(3)),
                       tuple((e0[k] + 2 * e1[k]) // 3 for k in range(3))]
            else:
                pal = [e0, e1,
                       tuple((e0[k] + e1[k]) // 2 for k in range(3)),
                       (0, 0, 0)]
            for py in range(4):
                Y = by * 4 + py
                if Y >= h:
                    break
                base = Y * w * 4
                for px in range(4):
                    X = bx * 4 + px
                    if X >= w:
                        break
                    idx = px + py * 4
                    col = pal[(ci >> (2 * idx)) & 3]
                    a = atab[(abits >> (3 * idx)) & 7]
                    o = base + X * 4
                    out[o], out[o + 1], out[o + 2], out[o + 3] = col[0], col[1], col[2], a
    return bytes(out)


def bgra_to_rgba(bgra, w, h):
    # BGRA -> RGBA, force alpha 255 (overlay keying handled at cheat side / BMP)
    out = bytearray(w * h * 4)
    out[0::4] = bgra[2::4]
    out[1::4] = bgra[1::4]
    out[2::4] = bgra[0::4]
    out[3::4] = b"\xff" * (w * h)
    return bytes(out)


def write_png(path, rgba, w, h):
    raw = bytearray()
    stride = w * 4
    for y in range(h):
        raw.append(0)  # filter: none
        raw += rgba[y * stride:(y + 1) * stride]

    def chunk(tag, payload):
        return (struct.pack(">I", len(payload)) + tag + payload +
                struct.pack(">I", zlib.crc32(tag + payload) & 0xFFFFFFFF))

    ihdr = struct.pack(">IIBBBBB", w, h, 8, 6, 0, 0, 0)
    with open(path, "wb") as f:
        f.write(b"\x89PNG\r\n\x1a\n")
        f.write(chunk(b"IHDR", ihdr))
        f.write(chunk(b"IDAT", zlib.compress(bytes(raw), 6)))
        f.write(chunk(b"IEND", b""))


def write_bmp24(path, rgba, w, h, black_nudge=True):
    """24bpp bottom-up BMP. Black (0,0,0) pixels become (8,8,8) so the
    overlay's black color key doesn't punch holes in the art."""
    row_pad = (-(w * 3)) % 4
    rows = bytearray()
    for y in range(h - 1, -1, -1):
        row = bytearray()
        base = y * w * 4
        for x in range(w):
            r = rgba[base + x * 4]
            g = rgba[base + x * 4 + 1]
            b = rgba[base + x * 4 + 2]
            if black_nudge and r == 0 and g == 0 and b == 0:
                r = g = b = 8
            row += bytes((b, g, r))
        row += b"\x00" * row_pad
        rows += row
    hdr = struct.pack("<2sIHHI", b"BM", 14 + 40 + len(rows), 0, 0, 14 + 40)
    info = struct.pack("<IiiHHIIiiII", 40, w, h, 1, 24, 0, len(rows), 2835, 2835, 0, 0)
    with open(path, "wb") as f:
        f.write(hdr + info + rows)


def main():
    args = sys.argv[1:]
    if not args or args[0] == "--info":
        path = args[1] if len(args) > 1 else None
        if not path:
            print(__doc__)
            return
        with open(path, "rb") as f:
            data = f.read()
        _, info = decode_vtex(data)
        print(info)
        return
    src, out_base = args[0], args[1]
    want_png = "--png" in args
    want_bmp = "--bmp" in args or not want_png
    with open(src, "rb") as f:
        data = f.read()
    buf, info = decode_vtex(data)
    if info["fmt"] == 28:
        rgba = bgra_to_rgba(buf, info["w"], info["h"])
    elif info["fmt"] == 2:
        rgba = dxt5_to_rgba(buf, info["w"], info["h"])
    else:
        raise SystemExit("no decoder for format %d" % info["fmt"])
    print("%s -> %dx%d fmt=%d mips=%d cmips=%s bytes=%d" %
          (src.split("/")[-1], info["w"], info["h"], info["fmt"], info["mips"],
           info["cmips"], info["pixel_bytes"]))
    if want_png:
        write_png(out_base + ".png", rgba, info["w"], info["h"])
    if want_bmp:
        write_bmp24(out_base + ".bmp", rgba, info["w"], info["h"])


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Extract files from a Source 2 VPK v2 (pak01_dir.vpk + pak01_NNN.vpk).

Usage:
  vpk_extract.py <vpk_root_dir> <out_dir> [--prefix P] [exact_path ...]

--prefix matches entries whose full path starts with P. Exact paths are used
as given. Writes with the same relative path under out_dir.
"""
import os
import struct
import sys


def parse_vpk(dir_vpk_path):
    with open(dir_vpk_path, "rb") as f:
        data = f.read()
    sig, ver, tree_size = struct.unpack_from("<III", data, 0)
    if sig != 0x55AA1234:
        raise SystemExit("not a VPK v2 file: %s" % dir_vpk_path)
    if ver != 2:
        raise SystemExit("unsupported VPK version %d" % ver)
    pos = 28
    end = 28 + tree_size
    entries = []

    def cstr(p):
        e = data.index(b"\x00", p)
        return data[p:e].decode("utf-8", "replace"), e + 1

    ext = ""
    while pos < end:
        ext, pos = cstr(pos)
        if not ext:
            break
        while True:
            directory, pos = cstr(pos)
            if not directory:
                break
            while True:
                name, pos = cstr(pos)
                if not name:
                    break
                crc, preload_len, archive, off, ln = struct.unpack_from("<IHHII", data, pos)
                term = struct.unpack_from("<H", data, pos + 16)[0]
                if term != 0xFFFF:
                    raise SystemExit("bad terminator for %s" % name)
                pos += 18 + preload_len
                path = ("%s/%s.%s" % (directory, name, ext)) if directory != " " else "%s.%s" % (name, ext)
                entries.append((path, archive, off, ln))
    return entries


def extract(root, entries, wanted, out_dir):
    out = []
    for path, archive, off, ln in wanted:
        if archive == 0x7FFF:
            src = os.path.join(root, "pak01_dir.vpk")
            # embedded data lives after the tree inside the dir vpk
            with open(src, "rb") as f:
                hdr = f.read(12)
                tree_size = struct.unpack_from("<I", hdr, 8)[0]
                f.seek(28 + tree_size + off)
                blob = f.read(ln)
        else:
            src = os.path.join(root, "pak01_%03d.vpk" % archive)
            with open(src, "rb") as f:
                f.seek(off)
                blob = f.read(ln)
        dst = os.path.join(out_dir, path.replace("/", os.sep))
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        with open(dst, "wb") as f:
            f.write(blob)
        out.append((path, len(blob)))
    return out


def main():
    args = sys.argv[1:]
    root = args[0]
    out_dir = args[1]
    args = args[2:]
    prefix = None
    if "--prefix" in args:
        i = args.index("--prefix")
        prefix = args[i + 1]
        del args[i:i + 2]
    entries = parse_vpk(os.path.join(root, "pak01_dir.vpk"))
    by_path = {p[0]: p for p in entries}
    if prefix:
        wanted = sorted(by_path[p] for p in by_path if p.startswith(prefix))
    else:
        missing = [p for p in args if p not in by_path]
        if missing:
            raise SystemExit("not in vpk: %s" % ", ".join(missing))
        seen = set()
        wanted = []
        for p in args:
            if p not in seen:
                seen.add(p)
                wanted.append(by_path[p])
    for path, size in extract(root, entries, wanted, out_dir):
        print("extracted %-72s %d" % (path, size))


if __name__ == "__main__":
    main()

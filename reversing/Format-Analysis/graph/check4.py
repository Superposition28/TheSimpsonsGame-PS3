#!/usr/bin/env python3
"""
graph_layouts.py

Scan all *.graph files, infer their internal block layouts, and group them by
"layout variant" so you can see how many distinct formats / arrangements exist.

A "layout variant" is defined by:
  - The ordered sequence of block kinds we detect for a file.
  - Which header offset fields (off40, off44, off48, off60, off64, off68, off70)
    are actually used as block boundaries.

Usage:
  python graph_layouts.py path/to/STROUT
  python graph_layouts.py path/to/file1.graph path/to/dir1 path/to/dir2

Add -v for per-file info, and -vv for extra unknown-block previews (per-file).
"""

from __future__ import annotations

import argparse
import os
import struct
from dataclasses import dataclass
from typing import List, Dict, Iterable, Tuple, Optional


# ---------- basic binary helpers ----------

def u32be(b: bytes, off: int) -> int:
    return struct.unpack_from(">I", b, off)[0]


def u16be(b: bytes, off: int) -> int:
    return struct.unpack_from(">H", b, off)[0]


def s16be(b: bytes, off: int) -> int:
    return struct.unpack_from(">h", b, off)[0]


def f32be(b: bytes, off: int) -> float:
    return struct.unpack_from(">f", b, off)[0]


# ---------- data structures ----------

@dataclass
class Header:
    node_count: int
    other_count: int
    guid_magic: int
    guid_tail: bytes

    node_offset: int
    node_end: int

    count_3c: int
    off40: int
    off44: int
    off48: int
    off60: int
    off64: int
    off68: int
    off70: int
    val74: int

    raw24: int
    raw68: int
    raw0c: int


@dataclass
class Node:
    x: float
    y: float
    z: float
    radius: float
    node_id: int
    area_id: int
    flags: int
    unk1: int
    unk2: int


@dataclass
class Edge:
    cost: float
    a: int
    b: int
    tag_c: int
    tag_d: int


@dataclass
class BlockInfo:
    start: int
    end: int
    kind: str
    notes: str


# ---------- header + nodes parsing ----------

def parse_header(data: bytes) -> Header:
    if len(data) < 0x80:
        raise ValueError("file too small for .graph header")

    raw0c = u32be(data, 0x0C)
    node_count = raw0c >> 16
    other_count = raw0c & 0xFFFF

    guid_magic = u32be(data, 0x10)         # constant across your samples (3DE57D8C)
    guid_tail = data[0x14:0x20]            # per-file id (12 bytes)

    node_offset = u32be(data, 0x20)
    raw24 = u32be(data, 0x24)
    count_3c = u32be(data, 0x3C)
    off40 = u32be(data, 0x40)
    off44 = u32be(data, 0x44)
    off48 = u32be(data, 0x48)
    off60 = u32be(data, 0x60)
    off64 = u32be(data, 0x64)
    off68 = u32be(data, 0x68)
    off70 = u32be(data, 0x70)
    val74 = u32be(data, 0x74)

    # Decide node_end: prefer raw24 if it looks like a node end, else off68, else derived.
    expected_end = node_offset + node_count * 0x20

    def looks_like_node_end(value: int) -> bool:
        if value == 0:
            return False
        if value <= node_offset:
            return False
        span = value - node_offset
        return (span % 0x20) == 0

    if looks_like_node_end(raw24):
        node_end = raw24
    elif looks_like_node_end(off68):
        node_end = off68
    else:
        node_end = expected_end

    return Header(
        node_count=node_count,
        other_count=other_count,
        guid_magic=guid_magic,
        guid_tail=guid_tail,
        node_offset=node_offset,
        node_end=node_end,
        count_3c=count_3c,
        off40=off40,
        off44=off44,
        off48=off48,
        off60=off60,
        off64=off64,
        off68=off68,
        off70=off70,
        val74=val74,
        raw24=raw24,
        raw68=off68,
        raw0c=raw0c,
    )


def parse_nodes(data: bytes, hdr: Header) -> List[Node]:
    nodes: List[Node] = []
    start = hdr.node_offset
    end = min(hdr.node_end, len(data))
    span = max(0, end - start)
    max_nodes = span // 0x20
    count = min(hdr.node_count, max_nodes)

    for i in range(count):
        base = start + i * 0x20
        if base + 0x20 > len(data):
            break
        x = f32be(data, base + 0x00)
        y = f32be(data, base + 0x04)
        z = f32be(data, base + 0x08)
        radius = f32be(data, base + 0x0C)
        node_id = u16be(data, base + 0x10)
        area_id = s16be(data, base + 0x12)
        flags = u32be(data, base + 0x14)
        unk1 = u32be(data, base + 0x18)
        unk2 = u32be(data, base + 0x1C)
        nodes.append(
            Node(
                x=x, y=y, z=z, radius=radius,
                node_id=node_id, area_id=area_id,
                flags=flags, unk1=unk1, unk2=unk2,
            )
        )
    return nodes


# ---------- edges parsing ----------

def parse_edges(data: bytes, hdr: Header) -> List[Edge]:
    """
    Heuristically parse an 'edge block' starting right after the node array.
    This may be absent in some .graph files.
    """
    edges: List[Edge] = []
    start = hdr.node_end

    candidate_offsets = [
        x for x in (hdr.off40, hdr.off44, hdr.off48, hdr.off60, hdr.off64, hdr.off68, hdr.off70)
        if x != 0 and x > start
    ]
    end = min(candidate_offsets) if candidate_offsets else len(data)

    if end <= start:
        return []

    off = start
    while off + 0x10 <= end:
        cost = f32be(data, off)
        a = u16be(data, off + 4)
        b = u16be(data, off + 6)
        c = s16be(data, off + 8)
        d = u16be(data, off + 0x0A)
        tail = data[off + 0x0C:off + 0x10]

        # sanity checks
        if not (0 <= a < hdr.node_count and 0 <= b < hdr.node_count):
            break
        if c not in (-1, 0):
            break
        if tail not in (b"\x00\x00\x00\x00",):
            break

        edges.append(Edge(cost=cost, a=a, b=b, tag_c=c, tag_d=d))
        off += 0x10

    return edges


# ---------- block discovery / classification ----------

def discover_blocks(data: bytes, hdr: Header) -> List[BlockInfo]:
    """
    Use header offsets + node region + file end to split the file into blocks,
    and classify each block heuristically.
    """
    blocks: List[BlockInfo] = []

    size = len(data)
    offsets = set()

    # known structural points
    offsets.add(0)            # file start
    offsets.add(0x80)         # end of header
    offsets.add(hdr.node_offset)
    offsets.add(hdr.node_end)

    for x in (hdr.off40, hdr.off44, hdr.off48, hdr.off60, hdr.off64, hdr.off68, hdr.off70):
        if 0 < x < size:
            offsets.add(x)

    offsets.add(size)

    offsets = sorted(offsets)

    # Precompute some helpers for classification:
    nodes = parse_nodes(data, hdr)
    edges = parse_edges(data, hdr)
    node_positions = {(round(n.x, 3), round(n.y, 3), round(n.z, 3)) for n in nodes}

    def classify_block(start: int, end: int) -> Tuple[str, str]:
        length = end - start
        if length <= 0:
            return "empty", ""

        # header region
        if start == 0 and end >= 0x80:
            return "header", "fixed 0x80-byte header"

        # node region
        if start == hdr.node_offset and end >= hdr.node_end:
            return "nodes", f"{len(nodes)} node(s)"

        # edge region (if any)
        if edges:
            first_edge_off = hdr.node_end
            last_edge_off = hdr.node_end + len(edges) * 0x10
            if start == first_edge_off and end == last_edge_off:
                return "edges", f"{len(edges)} edge(s)"

        # block starting at off40: often bitmask/flags region
        if start == hdr.off40 and length >= 0x10:
            buf = data[start:end]
            c_small = sum(1 for b in buf if b in (0x00, 0x10, 0x11))
            ratio = c_small / len(buf)
            if ratio > 0.9:
                return "bitmask/flags", f"high 0x10/0x11 density ({ratio:.2%})"

        # block starting at off44: usually lists of uint16 indices/sentinels
        if start == hdr.off44 and length >= 0x10:
            words = length // 2
            vals = [u16be(data, start + i * 2) for i in range(words)]
            idx_like = sum(1 for v in vals if (v == 0xFFFF) or (v < hdr.node_count))
            ratio = idx_like / max(1, len(vals))
            return "index-lists", f"{words} uint16 entries, {ratio:.2%} look like indices/sentinels"

        # block starting at off48: often 3-float triplets referencing node coords
        if start == hdr.off48 and length >= 0x20:
            hits = 0
            total_triplets = 0
            limit = min(end, size - 12)
            for off in range(start, limit, 12):
                x = f32be(data, off)
                y = f32be(data, off + 4)
                z = f32be(data, off + 8)
                pos = (round(x, 3), round(y, 3), round(z, 3))
                if pos in node_positions:
                    hits += 1
                total_triplets += 1
            if total_triplets > 0 and hits > 0:
                ratio = hits / total_triplets
                return "coord-ref", f"reuses {hits}/{total_triplets} node positions ({ratio:.2%})"

        # tiny tail at off70: often config/flags blob
        if start == hdr.off70 and length <= 0x20:
            return "config/mini", f"{length} bytes"

        return "unknown", f"{length} bytes"

    for i in range(len(offsets) - 1):
        s = offsets[i]
        e = offsets[i + 1]
        kind, notes = classify_block(s, e)
        blocks.append(BlockInfo(start=s, end=e, kind=kind, notes=notes))

    return blocks


# ---------- layout signature / grouping ----------

HEADER_OFFSET_FIELDS = ("off40", "off44", "off48", "off60", "off64", "off68", "off70")


def header_offset_usage(hdr: Header, data_len: int) -> Tuple[str, ...]:
    """
    Return a normalized signature of which header offsets are non-zero and
    fall inside the file: e.g. ("off40", "off44", "off48").
    """
    used = []
    for name in HEADER_OFFSET_FIELDS:
        val = getattr(hdr, name)
        if 0 < val < data_len:
            used.append(name)
    return tuple(used)


@dataclass
class FileLayout:
    path: str
    hdr: Header
    blocks: List[BlockInfo]


def iter_graph_files(root_or_file: str) -> Iterable[str]:
    path = os.path.abspath(root_or_file)
    if os.path.isdir(path):
        for dirpath, _, filenames in os.walk(path):
            for name in filenames:
                if name.lower().endswith(".graph"):
                    yield os.path.join(dirpath, name)
    else:
        if path.lower().endswith(".graph"):
            yield path


# ---------- printing helpers ----------

def short_guid(hdr: Header) -> str:
    return hdr.guid_tail.hex()


def print_file_detail(fl: FileLayout, verbose: int) -> None:
    rel = fl.path
    print(f"--- {rel} ---")
    hdr = fl.hdr
    print(f"  raw0C:        0x{hdr.raw0c:08X}  (nodes={hdr.node_count}, other={hdr.other_count})")
    print(f"  guid_magic:   0x{hdr.guid_magic:08X}")
    print(f"  guid_tail:    {short_guid(hdr)}")
    print(f"  node_offset:  0x{hdr.node_offset:08X}")
    print(f"  node_end:     0x{hdr.node_end:08X}")
    print(f"  off40/44/48:  0x{hdr.off40:08X} 0x{hdr.off44:08X} 0x{hdr.off48:08X}")
    print(f"  off60/64/68:  0x{hdr.off60:08X} 0x{hdr.off64:08X} 0x{hdr.off68:08X}")
    print(f"  off70/val74:  0x{hdr.off70:08X} 0x{hdr.val74:08X}")
    print("  blocks:")
    for blk in fl.blocks:
        print(f"    0x{blk.start:06X}..0x{blk.end:06X}: {blk.kind:12s} ({blk.notes})")

    if verbose >= 2:
        print("  unknown blocks preview:")
        try:
            with open(fl.path, "rb") as f:
                data = f.read()
        except OSError:
            data = b""
        for blk in fl.blocks:
            if blk.kind != "unknown":
                continue
            snippet = data[blk.start:blk.start + 32]
            hex_str = " ".join(f"{b:02X}" for b in snippet)
            print(f"    0x{blk.start:06X}: {hex_str} ...")
    print()


# ---------- main ----------

def main(argv: Optional[List[str]] = None) -> None:
    ap = argparse.ArgumentParser(
        description="Group .graph files by layout variant (block kinds + header offset usage).",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    ap.add_argument("paths", nargs="+", help="Files or directories to scan.")
    ap.add_argument(
        "-v", "--verbose",
        action="count",
        default=0,
        help="Increase verbosity (shows per-file details).",
    )
    args = ap.parse_args(argv)

    # Collect all .graph files from the provided paths
    files: List[str] = []
    for p in args.paths:
        for f in iter_graph_files(p):
            files.append(os.path.abspath(f))

    files = sorted(set(files))
    if not files:
        print("[!] No .graph files found.")
        return

    print(f"[i] Found {len(files)} .graph file(s).")
    print()

    layouts: Dict[Tuple[Tuple[str, ...], Tuple[str, ...]], List[FileLayout]] = {}

    for path in files:
        try:
            with open(path, "rb") as f:
                data = f.read()
        except OSError as e:
            print(f"[!] Error reading {path}: {e}")
            continue

        try:
            hdr = parse_header(data)
            blocks = discover_blocks(data, hdr)
        except Exception as e:
            print(f"[!] Error parsing {path}: {e}")
            continue

        fl = FileLayout(path=path, hdr=hdr, blocks=blocks)

        # Layout key = (block kinds in order, header offset usage)
        block_pattern = tuple(blk.kind for blk in blocks)
        offset_sig = header_offset_usage(hdr, len(data))
        key = (block_pattern, offset_sig)

        layouts.setdefault(key, []).append(fl)

        if args.verbose:
            print_file_detail(fl, verbose=args.verbose)

    # Summary of layout variants
    print("=== Layout variants ===")
    print(f"[i] Total distinct layouts: {len(layouts)}")
    print()

    # Sort layouts by popularity (most common first)
    items = sorted(layouts.items(), key=lambda kv: len(kv[1]), reverse=True)

    for idx, (key, fls) in enumerate(items):
        block_pattern, offset_sig = key
        print(f"Layout #{idx}: {len(fls)} file(s)")
        print(f"  block pattern: " + " -> ".join(block_pattern))
        if not offset_sig:
            print("  used offsets:  (none)")
        else:
            print("  used offsets:  " + " ".join(offset_sig))

        # Show a representative file and a little header info
        rep = fls[0]
        print(f"  example:       {rep.path}")
        print(f"  nodes range:   min={min(f.hdr.node_count for f in fls)}, "
              f"max={max(f.hdr.node_count for f in fls)}")
        print(f"  other_count:   min={min(f.hdr.other_count for f in fls)}, "
              f"max={max(f.hdr.other_count for f in fls)}")
        print()
    print("[i] Done.")


if __name__ == "__main__":
    main()

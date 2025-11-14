#!/usr/bin/env python3
"""
graph_explorer.py

Explorer / reverse-engineering helper for The Simpsons Game *.graph files.

Goals:
- Work on all observed variants without assuming a single rigid layout.
- Parse the common header + node array.
- Discover block boundaries using offsets embedded in the header.
- Classify each block heuristically (nodes, edges, index lists, coord-ref blocks, etc.).
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

    guid_magic = u32be(data, 0x10)         # always 0x3DE57D8C in your samples
    guid_tail = data[0x14:0x20]            # 12 bytes, per-file id

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

    # Decide node_end:
    expected_end = node_offset + node_count * 0x20

    def looks_like_node_end(value: int) -> bool:
        if value == 0:
            return False
        if value <= node_offset:
            return False
        span = value - node_offset
        return span % 0x20 == 0

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


# ---------- edge parsing ----------

def parse_edges(data: bytes, hdr: Header) -> List[Edge]:
    """
    Heuristically parse an 'edge block' directly after the node array.
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
    blocks: List[BlockInfo] = []

    size = len(data)
    offsets = set()

    offsets.add(0x80)  # end of header
    offsets.add(hdr.node_offset)
    offsets.add(hdr.node_end)

    for x in (hdr.off40, hdr.off44, hdr.off48, hdr.off60, hdr.off64, hdr.off68, hdr.off70):
        if 0 < x < size:
            offsets.add(x)

    offsets = sorted(o for o in offsets if o < size)
    if offsets and offsets[0] != 0:
        offsets.insert(0, 0)
    if offsets[-1] != size:
        offsets.append(size)

    nodes = parse_nodes(data, hdr)
    edges = parse_edges(data, hdr)
    node_positions = {(round(n.x, 3), round(n.y, 3), round(n.z, 3)) for n in nodes}

    def classify_block(start: int, end: int) -> Tuple[str, str]:
        length = end - start
        if length <= 0:
            return "empty", ""

        if start == 0 and end >= 0x80:
            return "header", "fixed 0x80-byte header"

        if start == hdr.node_offset and end >= hdr.node_end:
            return "nodes", f"{len(nodes)} node(s) @ 0x{start:X}"

        if edges:
            first_edge_off = hdr.node_end
            last_edge_off = hdr.node_end + len(edges) * 0x10
            if start == first_edge_off and end == last_edge_off:
                return "edges", f"{len(edges)} edge(s) of 16 bytes each"

        if start == hdr.off40 and length >= 0x10:
            sample = data[start:end]
            c_small = sum(1 for b in sample if b in (0x00, 0x10, 0x11))
            ratio = c_small / len(sample)
            if ratio > 0.9:
                return "bitmask/flags", f"high 0x10/0x11 density ({ratio:.2%})"

        if start == hdr.off44 and length >= 0x20:
            words = length // 2
            vals = [u16be(data, start + i * 2) for i in range(words)]
            small = sum(1 for v in vals if v == 0xFFFF or v < hdr.node_count)
            ratio = small / max(1, len(vals))
            return "index-lists", f"{words} uint16 entries, {ratio:.2%} look like indices/sentinels"

        if start == hdr.off48 and length >= 0x20:
            hits = 0
            total_triplets = 0
            for off in range(start, min(end, size - 12), 12):
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

        if start == hdr.off70 and length <= 0x20:
            return "config/mini", f"{length} bytes (small config/flag blob)"

        return "unknown", f"{length} bytes"

    for i in range(len(offsets) - 1):
        s = offsets[i]
        e = offsets[i + 1]
        kind, notes = classify_block(s, e)
        blocks.append(BlockInfo(start=s, end=e, kind=kind, notes=notes))

    return blocks


# ---------- utility formatting ----------

def short_guid(hdr: Header) -> str:
    return hdr.guid_tail.hex()


def summarize_nodes(nodes: List[Node]) -> Dict[str, object]:
    if not nodes:
        return {"count": 0}
    xs = [n.x for n in nodes]
    ys = [n.y for n in nodes]
    zs = [n.z for n in nodes]
    radii = [n.radius for n in nodes]
    flag_set = sorted(set(n.flags for n in nodes))
    area_set = sorted(set(n.area_id for n in nodes))
    return {
        "count": len(nodes),
        "bbox_x": (min(xs), max(xs)),
        "bbox_y": (min(ys), max(ys)),
        "bbox_z": (min(zs), max(zs)),
        "radius_minmax": (min(radii), max(radii)),
        "num_flag_variants": len(flag_set),
        "flags_sample": [hex(f) for f in flag_set[:8]],
        "num_area_ids": len(area_set),
        "area_ids_sample": area_set[:8],
    }


def iter_graph_files(root: str) -> Iterable[str]:
    root = os.path.abspath(root)
    for dirpath, _, filenames in os.walk(root):
        for name in filenames:
            if name.lower().endswith(".graph"):
                yield os.path.join(dirpath, name)


# ---------- main ----------

def analyze_file(path: str, verbose: int = 0) -> None:
    with open(path, "rb") as f:
        data = f.read()

    rel = os.path.basename(path)
    print(f"=== {rel} ===")

    try:
        hdr = parse_header(data)
    except Exception as e:
        print(f"  [!] header parse failed: {e}")
        print()
        return

    print(f"  size:           {len(data)} bytes")
    print(f"  raw0C:          0x{hdr.raw0c:08X}")
    print(f"    node_count:   {hdr.node_count}")
    print(f"    other_count:  {hdr.other_count}")
    print(f"  guid_magic:     0x{hdr.guid_magic:08X}")
    print(f"  guid_tail:      {short_guid(hdr)}")
    print(f"  node_offset:    0x{hdr.node_offset:08X}")
    print(f"  node_end:       0x{hdr.node_end:08X}")
    print(f"  count_3C:       {hdr.count_3c}")
    print(f"  off40:          0x{hdr.off40:08X}")
    print(f"  off44:          0x{hdr.off44:08X}")
    print(f"  off48:          0x{hdr.off48:08X}")
    print(f"  off60:          0x{hdr.off60:08X}")
    print(f"  off64:          0x{hdr.off64:08X}")
    print(f"  off68:          0x{hdr.off68:08X}")
    print(f"  off70:          0x{hdr.off70:08X}")
    print(f"  val74:          0x{hdr.val74:08X}")
    print()

    nodes = parse_nodes(data, hdr)
    node_info = summarize_nodes(nodes)
    print(f"  nodes:          {node_info['count']}")
    if node_info['count'] > 0:
        print(f"    bbox.x:       {node_info['bbox_x'][0]: .3f} .. {node_info['bbox_x'][1]: .3f}")
        print(f"    bbox.y:       {node_info['bbox_y'][0]: .3f} .. {node_info['bbox_y'][1]: .3f}")
        print(f"    bbox.z:       {node_info['bbox_z'][0]: .3f} .. {node_info['bbox_z'][1]: .3f}")
        rmin, rmax = node_info['radius_minmax']
        print(f"    radius:       {rmin:.6f} .. {rmax:.6f}")
        print(f"    flags:        {node_info['num_flag_variants']} variants; sample {node_info['flags_sample']}")
        print(f"    area_ids:     {node_info['num_area_ids']} variants; sample {node_info['area_ids_sample']}")
    print()

    edges = parse_edges(data, hdr)
    print(f"  edges:          {len(edges)}")
    if verbose and edges:
        for i, e in enumerate(edges[:min(8, len(edges))]):
            print(f"    [{i}] cost={e.cost:.3f} a={e.a} b={e.b} tag_c={e.tag_c} tag_d={e.tag_d}")
    print()

    blocks = discover_blocks(data, hdr)
    print("  blocks:")
    for blk in blocks:
        print(f"    0x{blk.start:06X} .. 0x{blk.end:06X} : {blk.kind:12s}  ({blk.notes})")

    if verbose >= 2:
        print()
        print("  unknown block previews:")
        for blk in blocks:
            if blk.kind != "unknown":
                continue
            start, end = blk.start, blk.end
            snippet = data[start:start+32]
            hex_str = " ".join(f"{b:02X}" for b in snippet)
            print(f"    0x{start:06X}: {hex_str} ...")

    print()


def main(argv: Optional[List[str]] = None) -> None:
    ap = argparse.ArgumentParser(
        description="Explore .graph files and infer their internal block structure.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    ap.add_argument("paths", nargs="+", help="One or more files or directories to analyze.")
    ap.add_argument("-v", "--verbose", action="count", default=0, help="Increase verbosity.")
    args = ap.parse_args(argv)

    to_process: List[str] = []
    for p in args.paths:
        if os.path.isdir(p):
            to_process.extend(iter_graph_files(p))
        else:
            to_process.append(p)

    if not to_process:
        print("[!] No .graph files found.")
        return

    for path in sorted(set(to_process)):
        analyze_file(path, verbose=args.verbose)


if __name__ == "__main__":
    main()

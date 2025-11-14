#!/usr/bin/env python3
"""
Validate that the .graph headers and parsed node metadata are consistent across assets.

Usage examples:

  # Scan current folder recursively, auto-pick first 2 .graph files as baseline
  python check_graph_headers.py .

  # Explicitly choose baseline files
  python check_graph_headers.py path/to/dir \
      --baseline A.graph B.graph \
      --header-size 0x80 --min-run 8

What it does:

1. Finds all *.graph files under the given root.
2. Uses 2+ "baseline" files to auto-derive universal header segments:
   - For each byte offset in the first N header bytes, if all baselines agree
     on the byte value, that offset is considered "universal".
   - Consecutive universal bytes are merged into segments (min length = --min-run).
3. For every .graph file, it:
   - Checks each universal segment; reports mismatches (i.e., variance).
   - Parses the graph header:
       * node_count (from 0x0C)
       * node_offset (0x20)
       * node_end (0x24 or 0x68, depending on variant)
       * derived node span & consistency checks
   - Optionally parses all nodes and prints a simple bbox + flag stats.
"""

from __future__ import annotations

import argparse
import os
import struct
from dataclasses import dataclass
from typing import Iterable, List, Tuple, Dict, Optional


# ---------- small helpers ----------

def u32be(data: bytes, off: int) -> int:
    return struct.unpack_from(">I", data, off)[0]


def u16be(data: bytes, off: int) -> int:
    return struct.unpack_from(">H", data, off)[0]


def s16be(data: bytes, off: int) -> int:
    return struct.unpack_from(">h", data, off)[0]


def f32be(data: bytes, off: int) -> float:
    return struct.unpack_from(">f", data, off)[0]


def to_hex(b: bytes) -> str:
    return " ".join(f"{x:02X}" for x in b)


def iter_graph_files(root: str) -> Iterable[str]:
    root = os.path.abspath(root)
    for dirpath, _dirnames, filenames in os.walk(root):
        for name in filenames:
            if name.lower().endswith(".graph"):
                yield os.path.join(dirpath, name)


# ---------- format-specific structs ----------

@dataclass
class GraphHeader:
    path: str
    total_size: int

    word_0c: int
    node_count: int
    other_count: int

    node_offset: int
    node_end_raw_24: int
    node_end_alt_68: int
    node_end_final: int

    header_ok: bool
    node_span_bytes: int
    node_span_count: int

    offset_40: int
    offset_44: int
    offset_48: int
    offset_70: int
    word_74: int


@dataclass
class GraphNode:
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
class HeaderSegment:
    offset: int
    length: int
    pattern: bytes  # universal bytes from baseline files


# ---------- header parsing ----------

def parse_graph_header(path: str, data: bytes) -> GraphHeader:
    size = len(data)
    if size < 0x80:
        raise ValueError("file too small to be a valid .graph")

    word_0c = u32be(data, 0x0C)
    node_count = word_0c >> 16
    other_count = word_0c & 0xFFFF

    node_offset = u32be(data, 0x20)
    raw_24 = u32be(data, 0x24)
    alt_68 = u32be(data, 0x68)

    # Heuristic for node_end:
    # - If 0x24 looks sane (non-zero, > node_offset, multiple of 0x20 distance),
    #   prefer it.
    # - Otherwise, fall back to 0x68 if it matches expected.
    # - As last resort, compute from node_count * 0x20.
    def looks_like_end(end_val: int) -> bool:
        if end_val == 0:
            return False
        if end_val <= node_offset:
            return False
        span = end_val - node_offset
        return span % 0x20 == 0

    expected_end = node_offset + node_count * 0x20
    if looks_like_end(raw_24):
        node_end = raw_24
    elif looks_like_end(alt_68):
        node_end = alt_68
    else:
        node_end = expected_end

    span_bytes = max(0, node_end - node_offset)
    span_count = span_bytes // 0x20
    header_ok = (span_bytes % 0x20 == 0) and (span_count == node_count)

    offset_40 = u32be(data, 0x40)
    offset_44 = u32be(data, 0x44)
    offset_48 = u32be(data, 0x48)
    offset_70 = u32be(data, 0x70)
    word_74 = u32be(data, 0x74)

    return GraphHeader(
        path=path,
        total_size=size,
        word_0c=word_0c,
        node_count=node_count,
        other_count=other_count,
        node_offset=node_offset,
        node_end_raw_24=raw_24,
        node_end_alt_68=alt_68,
        node_end_final=node_end,
        header_ok=header_ok,
        node_span_bytes=span_bytes,
        node_span_count=span_count,
        offset_40=offset_40,
        offset_44=offset_44,
        offset_48=offset_48,
        offset_70=offset_70,
        word_74=word_74,
    )


def parse_all_nodes(data: bytes, hdr: GraphHeader) -> List[GraphNode]:
    nodes: List[GraphNode] = []
    off = hdr.node_offset
    end = min(hdr.node_end_final, len(data))
    max_nodes_by_span = (end - off) // 0x20
    n = min(hdr.node_count, max_nodes_by_span)

    for i in range(n):
        base = off + i * 0x20
        if base + 0x20 > len(data):
            break
        x = f32be(data, base + 0x00)
        y = f32be(data, base + 0x04)
        z = f32be(data, base + 0x08)
        radius = f32be(data, base + 0x0C)
        node_id = u16be(data, base + 0x10)
        area = s16be(data, base + 0x12)
        flags = u32be(data, base + 0x14)
        unk1 = u32be(data, base + 0x18)
        unk2 = u32be(data, base + 0x1C)
        nodes.append(
            GraphNode(
                x=x,
                y=y,
                z=z,
                radius=radius,
                node_id=node_id,
                area_id=area,
                flags=flags,
                unk1=unk1,
                unk2=unk2,
            )
        )
    return nodes


def summarize_nodes(nodes: List[GraphNode]) -> Dict[str, object]:
    if not nodes:
        return {"count": 0}

    xs = [n.x for n in nodes]
    ys = [n.y for n in nodes]
    zs = [n.z for n in nodes]
    radii = [n.radius for n in nodes]
    flag_set = sorted({n.flags for n in nodes})
    area_set = sorted({n.area_id for n in nodes})

    return {
        "count": len(nodes),
        "bbox": {
            "x": (min(xs), max(xs)),
            "y": (min(ys), max(ys)),
            "z": (min(zs), max(zs)),
        },
        "radius_minmax": (min(radii), max(radii)),
        "num_flag_variants": len(flag_set),
        "flags": flag_set[:16],  # truncate for printing
        "num_area_ids": len(area_set),
        "area_ids_sample": area_set[:16],
    }


# ---------- universal header pattern discovery ----------

def derive_universal_segments(
    baseline_datas: List[bytes],
    header_size: int,
    min_run: int,
) -> List[HeaderSegment]:
    """Find offsets in the first header_size bytes where all baselines agree."""
    if not baseline_datas:
        return []

    limit = min(min(len(d) for d in baseline_datas), header_size)
    same_mask = [True] * limit  # same_mask[i] = all baselines agree at offset i
    first = baseline_datas[0]

    for i in range(limit):
        b0 = first[i]
        for d in baseline_datas[1:]:
            if d[i] != b0:
                same_mask[i] = False
                break

    segments: List[HeaderSegment] = []
    i = 0
    while i < limit:
        if not same_mask[i]:
            i += 1
            continue
        start = i
        while i < limit and same_mask[i]:
            i += 1
        length = i - start
        if length >= min_run:
            pattern = first[start:start + length]
            segments.append(HeaderSegment(offset=start, length=length, pattern=pattern))
    return segments


def check_segments_in_file(
    data: bytes,
    segments: List[HeaderSegment],
) -> List[Tuple[HeaderSegment, bytes]]:
    """
    Return a list of (segment, actual_bytes) for segments that DO NOT match
    the baseline pattern in this file.
    """
    mismatches: List[Tuple[HeaderSegment, bytes]] = []
    size = len(data)
    for seg in segments:
        if seg.offset + seg.length > size:
            actual = data[seg.offset:size]
            mismatches.append((seg, actual))
            continue
        actual = data[seg.offset:seg.offset + seg.length]
        if actual != seg.pattern:
            mismatches.append((seg, actual))
    return mismatches


# ---------- CLI / main ----------

def main(argv: Optional[List[str]] = None) -> None:
    ap = argparse.ArgumentParser(
        description="Scan .graph files, derive universal header bytes, and report variance + parsed metadata.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    ap.add_argument(
        "root",
        nargs="?",
        default=".",
        help="Root folder to recursively scan for *.graph files.",
    )
    ap.add_argument(
        "--baseline",
        nargs="+",
        metavar="FILE",
        help="One or more baseline .graph files to derive universal header patterns from. "
             "If omitted, the first 2 .graph files found under root are used.",
    )
    ap.add_argument(
        "--header-size",
        type=lambda x: int(x, 0),
        default=0x80,
        help="Number of bytes from start of file to include when deriving universal patterns.",
    )
    ap.add_argument(
        "--min-run",
        type=int,
        default=8,
        help="Minimum contiguous run length (in bytes) to treat as a header segment.",
    )
    ap.add_argument(
        "-v", "--verbose",
        action="count",
        default=0,
        help="Increase verbosity; repeat for more detail.",
    )

    args = ap.parse_args(argv)
    root = os.path.abspath(args.root)

    all_graphs = sorted(iter_graph_files(root))
    if not all_graphs:
        print(f"[!] No .graph files found under {root}")
        return

    if args.baseline:
        baseline_paths = [os.path.abspath(p) for p in args.baseline]
    else:
        baseline_paths = all_graphs[:2]

    print(f"[i] Found {len(all_graphs)} .graph files under {root}")
    print(f"[i] Using {len(baseline_paths)} baseline file(s):")
    for p in baseline_paths:
        print(f"    {p}")

    baseline_datas: List[bytes] = []
    for p in baseline_paths:
        try:
            with open(p, "rb") as f:
                baseline_datas.append(f.read())
        except OSError as e:
            print(f"[!] Error reading baseline {p}: {e}")
            return

    segments = derive_universal_segments(baseline_datas, args.header_size, args.min_run)
    print(f"[i] Derived {len(segments)} universal header segment(s) "
          f"(min_run={args.min_run}, header_size=0x{args.header_size:X})")
    for idx, seg in enumerate(segments):
        print(f"    [{idx}] off=0x{seg.offset:04X}, len=0x{seg.length:X}")

    print()
    print("=== Per-file analysis ===")
    print()

    for path in all_graphs:
        try:
            with open(path, "rb") as f:
                data = f.read()
        except OSError as e:
            print(f"[!] {path}: read error: {e}")
            continue

        rel = os.path.relpath(path, root)
        print(f"--- {rel} ---")
        try:
            hdr = parse_graph_header(path, data)
        except Exception as e:
            print(f"  [!] header parse error: {e}")
            print()
            continue

        print(f"  size:           {hdr.total_size} bytes")
        print(f"  word_0C:        0x{hdr.word_0c:08X}")
        print(f"    node_count:   {hdr.node_count}")
        print(f"    other_count:  {hdr.other_count}")
        print(f"  node_offset:    0x{hdr.node_offset:08X}")
        print(f"  node_end@0x24:  0x{hdr.node_end_raw_24:08X}")
        print(f"  node_end@0x68:  0x{hdr.node_end_alt_68:08X}")
        print(f"  node_end(final):0x{hdr.node_end_final:08X}")
        print(f"  node_span:      {hdr.node_span_bytes} bytes "
              f"({hdr.node_span_count} nodes inferred)")
        print(f"  header_ok:      {hdr.header_ok}")
        print(f"  offset_40:      0x{hdr.offset_40:08X}")
        print(f"  offset_44:      0x{hdr.offset_44:08X}")
        print(f"  offset_48:      0x{hdr.offset_48:08X}")
        print(f"  offset_70:      0x{hdr.offset_70:08X}")
        print(f"  word_74:        0x{hdr.word_74:08X}")

        if args.verbose >= 1:
            nodes = parse_all_nodes(data, hdr)
            summary = summarize_nodes(nodes)
            print(f"  nodes_parsed:   {summary.get('count', 0)}")
            if summary.get("count", 0) > 0:
                bbox = summary["bbox"]
                print(f"  bbox.x:         {bbox['x'][0]:.3f} .. {bbox['x'][1]:.3f}")
                print(f"  bbox.y:         {bbox['y'][0]:.3f} .. {bbox['y'][1]:.3f}")
                print(f"  bbox.z:         {bbox['z'][0]:.3f} .. {bbox['z'][1]:.3f}")
                rmin, rmax = summary["radius_minmax"]
                print(f"  radius:         {rmin:.6f} .. {rmax:.6f}")
                print(f"  flag_variants:  {summary['num_flag_variants']} "
                      f"(sample: {[hex(f) for f in summary['flags']]})")
                print(f"  area_ids:       {summary['num_area_ids']} "
                      f"(sample: {summary['area_ids_sample']})")

        mismatches = check_segments_in_file(data, segments)
        if not mismatches:
            print("  header pattern: OK (matches all universal segments)")
        else:
            print(f"  header pattern: {len(mismatches)} mismatching segment(s):")
            for seg, actual in mismatches[:5]:  # only show first few
                print(f"    off=0x{seg.offset:04X}, len=0x{seg.length:X}")
                print(f"      expected: {to_hex(seg.pattern[:32])}"
                      f"{' ...' if len(seg.pattern) > 32 else ''}")
                print(f"      actual:   {to_hex(actual[:32])}"
                      f"{' ...' if len(actual) > 32 else ''}")
            if len(mismatches) > 5:
                print(f"    ... {len(mismatches) - 5} more segments omitted")

        print()

    print("[i] Done.")


if __name__ == "__main__":
    main()

"""
validate that the hex headers found are correct and consistent accross all assets

"""
from __future__ import annotations

import argparse
import os
import sys
from dataclasses import dataclass
from typing import Dict, Iterable, List, Optional, Tuple
from concurrent.futures import ProcessPoolExecutor
from functools import partial
from collections import Counter, defaultdict


TARGET_SUFFIXES = (
    ".rws.ps3.preinstanced",
    ".dff.ps3.preinstanced",
)

@dataclass
class PatternDef:
    """Human-friendly description of a binary pattern segment.

    Attributes:
        name: Display name used in reports.
        pattern: Single wildcard-capable hex string (e.g., "2D 00 ** 1C").
        patterns: Alternate patterns for the same logical segment; any may match.
        required: If True, missing this segment makes the file fail.
        note: Informational note shown in reports.
        max_allowed: Optional upper bound on occurrences per file (0 = no limit).
        follows: Priority-ordered list of predecessor constraints. For each tuple
                 (parent_id, relation), if that parent pattern exists in the file,
                 this pattern must satisfy the relation with respect to some
                 occurrence of the parent. If none of the listed parents exist,
                 the dependency is not enforced for this pattern.
                 relation: 'immediate' (start == parent_end) or 'after' (start >= parent_end).
    """
    id: int
    name: str
    pattern: Optional[str] = None
    # Optional list of alternative patterns; if provided, any variant matching counts
    patterns: Optional[List[str]] = None
    required: bool = True
    note: str = ""
    max_allowed: int = 0  # 0 = no limit
    follows: Optional[List[Tuple[int, str]]] = None

PATTERN_DEFS: List[PatternDef] = [

    ## long headers are used in place of short ones to ensure correct detection avoiding any other instances of a similar hex string, Offsets cannot be used as there not consistant
    PatternDef(
        id=1,
        name="SOF long header",
        pattern=(
            "10 00 00 00 ?? ?? ?? 00 2D 00 02 1C 01 00 00 00 0C 00 00 00 2D 00 02 1C ** ** ** ** 00 00 00 00 00 00 00 00 0E 00 00 00 ** ** ** ** 2D 00 02 1C 01 00 00 00 ** ** ** ** "
        ),
        required=True,
        note="Start-of-file long header. After this, ~100/5533 files may have an unknown block before texture data.",
        max_allowed=1,
        # Root start-of-file header, no explicit dependency
        follows=None,
    ),
    PatternDef(
        id=2,
        name="SOF long header",
        pattern=(
            "2D 00 02 1C ** ** ** ** 00 00 80 3F 00 00 00 00 00 00 00 00 00 00 00 00 00 00 80 3F 00 00 00 00 00 00 00 00 00 00 00 00 00 00 80 3F ** ** ** ** ** ** ** ** ** ** ** ** "
        ),
        required=True,
        note="Start-of-file long header. After this, ~100/5533 files may have an unknown block before texture data.",
        max_allowed=1,
        # Should follow after id=1 if present
        follows=[(1, "after")],
    ),
    PatternDef(
        id=3,
        name="SOF long header",
        pattern=(
            "FF FF FF FF 00 00 00 00 ** ** ** ** ** ** ** ** ** ** ** ** ** ** ** ** ** ** ** ** ** ** ** ** ** ** ** ** ** ** ** ** ** ** 80 3F ** ** ** ** ** ** ** ** ** ** ** ** "
        ),
        required=True,
        note="Start-of-file long header. After this, ~100/5533 files may have an unknown block before texture data.",
        max_allowed=1,
        # Prefer immediately after id=2; if 2 isn't present, then after id=1
        follows=[(2, "immediate"), (1, "after")],
    ),

    ## this header indicates a following 12 byte sequence that is often followed by the same header then another 12 however many times until it reaches the 'Unknown DataBlock header'
    PatternDef(
        id=4,
        name="SOF Binary Block Data",
        patterns=[
            ## the 00 is the first instance of this section the 01 is all other section headers
            "00 00 00 00 00 00 00 00 00 00 80 3F 00 00 00 00 00 00 00 00 00 00 00 00 00 00 80 3F 00 00 00 00 00 00 00 00 00 00 00 00 00 00 80 3F",
            "01 00 00 00 00 00 00 00 00 00 80 3F 00 00 00 00 00 00 00 00 00 00 00 00 00 00 80 3F 00 00 00 00 00 00 00 00 00 00 00 00 00 00 80 3F"
        ],
        required=False,
        note="",
        max_allowed=1,
        # After 3, otherwise after 2, otherwise after 1
        follows=[(3, "after"), (2, "after"), (1, "after")],
    ),


    ## these mark an unknown segment of data before the texturs after the SOF and after an unknown binary block often seen right after SOF
    ## these two patterns appear mostly in .rws files and in very few .dff
    PatternDef(
        id=5,
        name="Unknown DataBlock header",
        pattern="01 00 00 00 00 00 00 00 03 00 00 00 00 00 00 00 2D 00 02 1C 03 00 00 00 18 00 00 00 2D 00 02 1C 1E 01 00 00 0C 00 00 00 2D 00 02 1C 00 01 00 00 00 00 00 00 00 00 00 00 03 00 00 00 18 00 00 00 2D 00 02 1C 1E 01 00 00 0C 00 00 00 2D 00 02 1C ",
        required=False,
        note="found after the unknown binary data just before texture data and mesh",
        max_allowed=1,
        # Typically after #4 block data; fallback to after #1
        follows=[(4, "after"), (1, "after")],
    ),

    # === String/Name-related markers (from FIXED_SIGNATURES_TO_CHECK) ===
    # === Pre-Texture Names / Texture Data boundary ===
    PatternDef(
        id=6,
        name="Pre-texture names marker String Block Header (General, 8B) ",
        patterns=[
            "02 11 01 00 02 00 00 00 14 00 00 00 2D 00 02 1C",
            "02 11 01 00 02 00 00 00 18 00 00 00 2D 00 02 1C",
        ],
        required=False,
        note="Observed before texture string names. // Fixed signature before embedded string(s); string usually starts +0x10.",
        max_allowed=0,  # max observed was 297
        # Usually appears after the unknown block (#5); fallback to after earlier anchors
        follows=[(5, "after"), (4, "after"), (1, "after")],
    ),
    PatternDef(
        id=7,
        name="TLFD (Texture Data start)",
        pattern="54 4C 46 44",
        required=False,
        note="Marks end of string names and start of Texture Data.",
        max_allowed=0,  # max observed was 138
        # Texture data starts after names (#6); allow fallback
        follows=[(6, "after"), (5, "after"), (4, "after"), (1, "after")],
    ),

    # === Mesh-chunk scanning (from mshBytes regex) ===
    PatternDef(
        id=8,
        name="Mesh chunk header",
        pattern="33 EA 00 00 ** ** ** ** 2D 00 02 1C",
        required=False,
        note="Header used to locate mesh chunks before reading counts/offsets.",
        max_allowed=0,
        # Mesh chunks appear after prior headers/blocks
        follows=[(7, "after"), (6, "after"), (5, "after"), (4, "after"), (1, "after")],
    ),

    # === Face/strip parsing delimiter ===
    #PatternDef(
    #    name="Triangle strip delimiter",
    #    pattern="FF FF",
    #    required=False,
    #    note="Index delimiter between strips (very common; non-unique).",
    #    max_allowed=0,
    #),

    # === EOF region ===
    PatternDef(
        id=9,
        name="EOF marker",
        pattern="16 EA 00 00 05 00 00 00 2D 00 02 1C 01 00 00 00 00",
        required=True,
        note="Expected near EOF (search after SOF segment).",
        max_allowed=1,
        # EOF should be after everything else
        follows=[(8, "after"), (7, "after"), (6, "after"), (5, "after"), (4, "after"), (1, "after")],
    ),
]


# ===== Implementation =====

@dataclass
class CompiledVariant:
    patt: bytes
    mask: bytes


@dataclass
class CompiledSegment:
    id: int
    name: str
    required: bool
    note: str
    variants: List[CompiledVariant]
    max_allowed: int
    follows: Optional[List[Tuple[int, str]]]


def iter_target_files(root: str) -> Iterable[str]:
    """Yield files under root whose suffix matches TARGET_SUFFIXES (case-insensitive)."""
    root = os.path.abspath(root)
    for dirpath, _dirnames, filenames in os.walk(root):
        for name in filenames:
            lower = name.lower()
            if lower.endswith(TARGET_SUFFIXES):
                yield os.path.join(dirpath, name)


def read_prefix(path: str, n: int) -> bytes:
    with open(path, "rb") as f:
        return f.read(n)


def to_hex(b: bytes) -> str:
    return " ".join(f"{x:02X}" for x in b)


def _parse_wildcard_pattern(pat: str) -> Tuple[bytes, bytes]:
    """Parse space-separated hex with **/?? wildcards into (pattern, mask)."""
    p: List[int] = []
    m: List[int] = []
    for raw_tok in pat.replace("\n", " ").split():
        tok = raw_tok.strip()
        if not tok:
            continue
        if tok in ("**", "??"):
            p.append(0)
            m.append(0)  # wildcard
            continue
        if len(tok) != 2:
            raise ValueError(f"invalid token length in pattern: {tok!r}")
        try:
            val = int(tok, 16)
        except ValueError:
            raise ValueError(f"invalid hex token in pattern: {tok!r}") from None
        p.append(val)
        m.append(0xFF)
    if not p:
        raise ValueError("pattern parsed to empty bytes")
    return bytes(p), bytes(m)


def compile_pattern_defs(defs: List[PatternDef]) -> List[CompiledSegment]:
    out: List[CompiledSegment] = []
    for d in defs:
        variants: List[CompiledVariant] = []
        patt_list: List[str] = []
        if d.patterns:
            patt_list.extend(d.patterns)
        if d.pattern is not None:
            if isinstance(d.pattern, (list, tuple)):
                patt_list.append(" ".join(d.pattern))
            else:
                patt_list.append(d.pattern)
        if not patt_list:
            raise ValueError(f"PatternDef {d.id} ({d.name}) has no pattern(s)")
        for s in patt_list:
            patt, mask = _parse_wildcard_pattern(s)
            variants.append(CompiledVariant(patt=patt, mask=mask))
        out.append(
            CompiledSegment(
                id=d.id,
                name=d.name,
                required=d.required,
                note=d.note,
                variants=variants,
                max_allowed=d.max_allowed,
                follows=d.follows,
            )
        )
    # Ensure deterministic evaluation order by id then definition order
    out.sort(key=lambda s: s.id)
    return out


def _find_masked(data: bytes, patt: bytes, mask: bytes, start: int = 0) -> int:
    need = len(patt)
    if need == 0:
        return start
    limit = len(data) - need
    for i in range(start, max(-1, limit) + 1):
        seg = data[i:i + need]
        # quick-check first masked byte
        if (seg[0] & mask[0]) != (patt[0] & mask[0]):
            continue
        ok = True
        for db, pb, mb in zip(seg, patt, mask):
            if (db & mb) != (pb & mb):
                ok = False
                break
        if ok:
            return i
    return -1


def _find_all_masked(data: bytes, patt: bytes, mask: bytes) -> List[int]:
    pos = 0
    found: List[int] = []
    step = max(1, len(patt))
    while True:
        i = _find_masked(data, patt, mask, pos)
        if i < 0:
            break
        found.append(i)
        pos = i + step  # non-overlapping per-variant
    return found


def collect_positions_per_segment(data: bytes, seg: CompiledSegment) -> Tuple[List[Tuple[int, int]], Dict[int, List[int]]]:
    """Return (positions, per_variant_positions) for a segment.

    positions: sorted list of (start, length) merged across variants.
    per_variant_positions: vidx -> list of start positions for that variant.
    """
    per_variant: Dict[int, List[int]] = {}
    merged: List[Tuple[int, int]] = []
    for vidx, v in enumerate(seg.variants):
        pos_list = _find_all_masked(data, v.patt, v.mask)
        if pos_list:
            per_variant[vidx] = pos_list
            L = len(v.patt)
            merged.extend((p, L) for p in pos_list)
    merged.sort(key=lambda t: t[0])
    # Deduplicate identical start positions coming from different variants by keeping the max length
    dedup: List[Tuple[int, int]] = []
    last_start = None
    for s, L in merged:
        if last_start is None or s != last_start:
            dedup.append((s, L))
            last_start = s
        else:
            # same start from another variant: keep longer
            if L > dedup[-1][1]:
                dedup[-1] = (s, L)
    return dedup, per_variant


@dataclass
class FileMatchResult:
    path: str
    ok: bool
    reason: str
    per_segment_counts: Dict[str, int]
    dependency_errors: List[str]


def _enforce_dependencies(
    compiled: List[CompiledSegment],
    all_positions: Dict[int, List[Tuple[int, int]]],
) -> Tuple[bool, List[str]]:
    """Check dependency constraints for all segments.

    Returns (ok, errors).
    Rules:
      - If a pattern has 'follows': choose the first parent in the list that exists in the file
        (has any occurrence). This becomes the active constraint.
      - If a parent exists, then the child must have at least one occurrence
        satisfying the relation to some occurrence of that parent:
           immediate: child_start == parent_start + parent_len
           after:     child_start >= parent_start + parent_len
      - If none of the listed parents exist, the dependency is not enforced for that child.
    """
    errors: List[str] = []
    # Build quick lookup of existence and end positions for parents
    exists: Dict[int, bool] = {seg.id: bool(all_positions.get(seg.id)) for seg in compiled}
    parent_end_positions: Dict[int, List[int]] = {
        seg.id: [(s + L) for (s, L) in all_positions.get(seg.id, [])] for seg in compiled
    }

    for seg in compiled:
        if not seg.follows:
            continue
        child_pos = all_positions.get(seg.id, [])
        # If the child doesn't exist at all, dependency will be handled by 'required' elsewhere.
        if not child_pos:
            # If the child isn't present, we can't check dependency; skip here.
            continue
        # pick the first parent rule whose parent exists
        active_rule: Optional[Tuple[int, str]] = None
        for pid, rel in seg.follows:
            if exists.get(pid, False):
                active_rule = (pid, rel)
                break
        if not active_rule:
            # no listed parents exist in the file; nothing to enforce
            continue
        pid, rel = active_rule
        ends = parent_end_positions.get(pid, [])
        if not ends:
            # Defensive: shouldn't happen if exists[pid] is True
            continue
        ok_for_this_child = False
        for c_start, c_len in child_pos:
            for pend in ends:
                if rel == "immediate":
                    if c_start == pend:
                        ok_for_this_child = True
                        break
                else:  # 'after'
                    if c_start >= pend:
                        ok_for_this_child = True
                        break
            if ok_for_this_child:
                break
        if not ok_for_this_child:
            parent_names = {s.id: s.name for s in compiled}
            errors.append(
                f"Dependency not satisfied: '{seg.name}' must follow {rel} '{parent_names.get(pid, str(pid))}'"
            )
    return (len(errors) == 0), errors


def check_file(path: str, compiled: List[CompiledSegment]) -> FileMatchResult:
    try:
        with open(path, "rb") as f:
            data = f.read()
    except OSError as e:
        return FileMatchResult(path, False, f"read error: {e}", {}, [f"read error: {e}"])

    # collect positions per segment
    all_positions: Dict[int, List[Tuple[int, int]]] = {}
    per_segment_counts: Dict[str, int] = {}
    required_missing: List[str] = []
    for seg in compiled:
        pos, _per_variant = collect_positions_per_segment(data, seg)
        all_positions[seg.id] = pos
        per_segment_counts[seg.name] = len(pos)
        if seg.required and len(pos) == 0:
            required_missing.append(seg.name)

    dep_ok, dep_errors = _enforce_dependencies(compiled, all_positions)
    ok = (len(required_missing) == 0) and dep_ok
    reason_parts: List[str] = []
    if required_missing:
        reason_parts.append("missing required: " + ", ".join(required_missing))
    if not dep_ok and dep_errors:
        reason_parts.extend(dep_errors)
    reason = "; ".join(reason_parts)
    return FileMatchResult(path, ok, reason, per_segment_counts, dep_errors)


def parse_args(argv: List[str]) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Validate preinstanced PS3 files with dependency-aware pattern matching")
    p.add_argument("path", nargs="?", default=".", help="Root folder to scan")
    p.add_argument("--quiet", "-q", action="store_true", help="Only print final summary")
    p.add_argument("--show-bytes", dest="show_bytes", action="store_true", help="Show first 256B of each file (debug)")
    return p.parse_args(argv)


def main(argv: List[str]) -> int:
    args = parse_args(argv)
    root = args.path
    try:
        compiled = compile_pattern_defs(PATTERN_DEFS)
    except ValueError as e:
        print(f"Pattern parse error: {e}")
        return 3

    files = list(iter_target_files(root))
    total = len(files)
    passes = 0
    fails = 0

    if not args.quiet:
        print(f"Scanning: {os.path.abspath(root)}")
        print(f"Target suffixes: {', '.join(TARGET_SUFFIXES)}")
        seg_info = ", ".join(f"#{s.id} {s.name}" for s in compiled)
        print(f"Segments: {seg_info}")
        print(f"Found {total} file(s)\n")

    for i, path in enumerate(files, 1):
        res = check_file(path, compiled)
        if res.ok:
            passes += 1
            if not args.quiet:
                print(f"PASS [{i}/{total}] {path}")
        else:
            fails += 1
            print(f"FAIL [{i}/{total}] {path} :: {res.reason}")
            if args.show_bytes:
                try:
                    head = read_prefix(path, 256)
                    print("  head:", to_hex(head))
                except Exception:
                    pass

    print()
    print("Summary:")
    print(f"  OK:   {passes}")
    print(f"  FAIL: {fails}")
    print(f"  TOTAL:{total}")
    return 0 if fails == 0 else 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))




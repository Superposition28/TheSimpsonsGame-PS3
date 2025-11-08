"""
Validate a single preinstanced PS3 asset (or a folder) by scanning for known
binary section headers with wildcard support and dependency rules.

Enhancements over earlier version:
- Accepts a single file path and prints a verbose, per-section report
    (which sections were found, which variant matched, offsets, and a timeline).
- Still supports the old directory-scan mode if a directory is provided.
- For segments intended to appear once (max_allowed == 1), only the first
    occurrence is considered to avoid red herrings:
        - If the segment has 'follows' constraints, the first occurrence that
            satisfies the active constraint is selected ("first after follows=").
        - If no 'follows' are provided, the first occurrence in the file is used.
    Other occurrences are ignored for reporting and dependency checks.
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
    # Optional end-of-segment pattern for this definition. If provided, we will
    # search for this pattern after the start pattern to determine the real end
    # of the segment. Dependency relations like 'immediate' will then use the
    # EOS end offset instead of start+header_len.
    EOSPattern: Optional[str] = None

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
        follows=[(1, "immediate")],
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
        note="Possible Header, found after the unknown binary data just before texture data and mesh",
        max_allowed=1,
        # After 3, otherwise after 2, otherwise after 1
        follows=[(3, "after"), (2, "after"), (1, "after")],
    ),
    PatternDef(
        id=4,
        name="SOF Binary Block Data v2",
        pattern=(
            # these two strings are one long pattern
            "00 00 00 00 00 00 00 00 03 00 00 00 00 00 00 00 2D 00 02 1C 03 00 00 00 ** 00 00 00 2D 00 02 1C 1E 01 00 00 ** 00 00 00 2D 00 02 1C 00 01 00 00 00 00 00 00 ** 00 00 00 "
            "02 80 03 00 00 00 00 00 ** ** ** ** 00 00 00 00 00 00 00 00 E9 1D BC 49 01 00 00 00 00 00 00 00 DC F6 DC 6E 02 00 00 00 00 00 00 00 ** ** ** ** 03 00 00 00 ** 00 00 00 ",
        ),
        EOSPattern=(
            "FF FF FF FF 07 00 00 00 E8 00 00 00 2D 00 02 1C 01 00 00 00 1C 00 00 00 2D 00 02 1C 00 00 00 00 FF FF FF FF 00 00 ** 18 01 00 00 00 00 00 80 3F 00 00 80 3F 00 00 80 3F 06 00 00 00 50 00 00 00 2D 00 02 1C 01 00 00 00 04 00 00 00 2D 00 02 1C ",
        ),
        required=False,
        note="alternative version of the SOF Binary Block Data",
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
    label: str
    eos_patt: Optional[bytes] = None
    eos_mask: Optional[bytes] = None


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
    """Compile pattern definitions into segments grouped by id.

    Multiple PatternDef entries with the same id are treated as alternative
    subformats of the same logical segment. Their patterns are merged as
    labeled variants under a single CompiledSegment, so that dependencies and
    ordering apply to "one of the versions" of that segment.
    """
    # Group defs by id in original order
    grouped: Dict[int, List[PatternDef]] = {}
    order: List[int] = []
    for d in defs:
        if d.id not in grouped:
            grouped[d.id] = []
            order.append(d.id)
        grouped[d.id].append(d)

    out: List[CompiledSegment] = []
    for sid in order:
        defs_for_id = grouped[sid]
        # Choose representative name/note from the first def; variants carry their own labels
        base_name = defs_for_id[0].name
        base_note = defs_for_id[0].note
        # Required if any def is required (conservative)
        required = any(d.required for d in defs_for_id)
        # Max allowed: take the max across defs (0 means unlimited)
        max_allowed = max((d.max_allowed for d in defs_for_id), default=0)
        # Follows: prefer the first non-empty; if multiple exist, union unique while keeping order
        follows: Optional[List[Tuple[int, str]]] = None
        for d in defs_for_id:
            if d.follows:
                if follows is None:
                    follows = list(d.follows)
                else:
                    for item in d.follows:
                        if item not in follows:
                            follows.append(item)

        variants: List[CompiledVariant] = []
        for d in defs_for_id:
            patt_sources: List[Tuple[str, str]] = []  # (pattern_str, label)
            if d.patterns:
                # label each with an index to disambiguate
                for idx, s in enumerate(d.patterns):
                    patt_sources.append((s, f"{d.name} [alt {idx}]") )
            if d.pattern is not None:
                if isinstance(d.pattern, (list, tuple)):
                    patt_sources.append((" ".join(d.pattern), d.name))
                else:
                    patt_sources.append((d.pattern, d.name))
            if not patt_sources:
                raise ValueError(f"PatternDef {d.id} ({d.name}) has no pattern(s)")
            # Compile optional EOS pattern once per definition
            eos_patt: Optional[bytes] = None
            eos_mask: Optional[bytes] = None
            if d.EOSPattern:
                eos_src: str
                if isinstance(d.EOSPattern, (list, tuple)):
                    eos_src = " ".join(d.EOSPattern)
                else:
                    eos_src = d.EOSPattern
                eos_patt, eos_mask = _parse_wildcard_pattern(eos_src)
            for s, label in patt_sources:
                patt, mask = _parse_wildcard_pattern(s)
                variants.append(CompiledVariant(patt=patt, mask=mask, label=label, eos_patt=eos_patt, eos_mask=eos_mask))

        out.append(
            CompiledSegment(
                id=sid,
                name=base_name,
                required=required,
                note=base_note,
                variants=variants,
                max_allowed=max_allowed,
                follows=follows,
            )
        )

    # Ensure deterministic evaluation order by id
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
            base_len = len(v.patt)
            # If we have an EOS pattern for this variant, try to find it to get the real segment end
            if v.eos_patt and v.eos_mask:
                eos_len = len(v.eos_patt)
                for p in pos_list:
                    # search for EOS starting at the start position; take the first match after or at p
                    eos_pos = _find_masked(data, v.eos_patt, v.eos_mask, start=p)
                    if eos_pos >= 0:
                        L = (eos_pos + eos_len) - p
                    else:
                        L = base_len
                    merged.append((p, L))
            else:
                merged.extend((p, base_len) for p in pos_list)
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
    size_bytes: int
    # seg.id -> list of (start, length)
    positions_by_segment: Dict[int, List[Tuple[int, int]]]
    # seg.id -> variant_index -> [start positions]
    per_variant_positions: Dict[int, Dict[int, List[int]]]


def _variant_signature(v: CompiledVariant) -> str:
    """Return a human-friendly hex string of a compiled variant, using '**' for wildcards."""
    out: List[str] = []
    for b, m in zip(v.patt, v.mask):
        if m == 0:
            out.append("**")
        else:
            out.append(f"{b:02X}")
    return " ".join(out)


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


def _filter_first_occurrence_after_follows(
    compiled: List[CompiledSegment],
    all_positions: Dict[int, List[Tuple[int, int]]],
) -> Dict[int, List[Tuple[int, int]]]:
    """For segments with max_allowed==1, keep only the first relevant occurrence.

    Selection rules:
      - If the segment defines 'follows', choose the first occurrence that
        satisfies the relation with respect to the active parent:
           * active parent = the first parent in 'follows' that exists
             (prefers the parent's already-selected occurrence; otherwise the
             parent's earliest occurrence if present).
      - If none of the listed parents exist, dependencies are not enforced and
        the first occurrence in the file is selected.
      - If the segment has no 'follows', select the first occurrence.
      - For segments with max_allowed != 1, return all occurrences unchanged.
    """
    # We'll build on top of selected parents so dependency chains are respected.
    selected: Dict[int, Optional[Tuple[int, int]]] = {}
    filtered: Dict[int, List[Tuple[int, int]]] = {}

    # Quick lookup for earliest parent occurrence when no selection yet.
    def _parent_first(pid: int) -> Optional[Tuple[int, int]]:
        pos = all_positions.get(pid) or []
        return pos[0] if pos else None

    # Process in deterministic order (already sorted by id in compile step)
    for seg in compiled:
        pos_list = all_positions.get(seg.id, [])
        if not pos_list:
            selected[seg.id] = None
            filtered[seg.id] = []
            continue

        # Only collapse to first if max_allowed==1; else, keep all positions
        if seg.max_allowed != 1:
            filtered[seg.id] = pos_list
            selected[seg.id] = pos_list[0] if pos_list else None
            continue

        chosen: Optional[Tuple[int, int]] = None
        if seg.follows:
            # Determine active parent: first listed that exists (selected first, else earliest)
            active_parent: Optional[Tuple[int, int]] = None
            active_rel: Optional[str] = None
            for pid, rel in seg.follows:
                psel = selected.get(pid)
                if psel is None:
                    psel = _parent_first(pid)
                if psel is not None:
                    active_parent = psel
                    active_rel = rel
                    break
            if active_parent is not None and active_rel is not None:
                p_start, p_len = active_parent
                p_end = p_start + p_len
                if active_rel == "immediate":
                    # first child at exactly parent end
                    for c_start, c_len in pos_list:
                        if c_start == p_end:
                            chosen = (c_start, c_len)
                            break
                else:  # 'after'
                    for c_start, c_len in pos_list:
                        if c_start >= p_end:
                            chosen = (c_start, c_len)
                            break
            # If none of the parents exist in the file, fall back to first occurrence
            if chosen is None:
                chosen = pos_list[0]
        else:
            # No follows: choose first in file
            chosen = pos_list[0]

        filtered[seg.id] = [chosen] if chosen is not None else []
        selected[seg.id] = chosen

    return filtered


def check_file(path: str, compiled: List[CompiledSegment]) -> FileMatchResult:
    try:
        with open(path, "rb") as f:
            data = f.read()
    except OSError as e:
        return FileMatchResult(path, False, f"read error: {e}", {}, [f"read error: {e}"], 0, {}, {})

    # collect positions per segment
    all_positions_raw: Dict[int, List[Tuple[int, int]]] = {}
    per_segment_counts: Dict[str, int] = {}
    required_missing: List[str] = []
    per_variant_positions_raw: Dict[int, Dict[int, List[int]]] = {}
    for seg in compiled:
        pos, _per_variant = collect_positions_per_segment(data, seg)
        all_positions_raw[seg.id] = pos
        per_segment_counts[seg.name] = len(pos)
        if _per_variant:
            per_variant_positions_raw[seg.id] = _per_variant
        if seg.required and len(pos) == 0:
            required_missing.append(seg.name)

    # Filter to first occurrence where appropriate (max_allowed==1), honoring 'follows='
    all_positions = _filter_first_occurrence_after_follows(compiled, all_positions_raw)

    # Reduce per-variant positions to only those starts we've kept
    kept_starts_by_seg: Dict[int, set] = {
        sid: set(s for s, _L in occ) for sid, occ in all_positions.items()
    }
    per_variant_positions: Dict[int, Dict[int, List[int]]] = {}
    for seg in compiled:
        raw = per_variant_positions_raw.get(seg.id)
        if not raw:
            continue
        kept_starts = kept_starts_by_seg.get(seg.id, set())
        if seg.max_allowed == 1:
            # keep only the first chosen start
            if kept_starts:
                chosen_start = next(iter(sorted(kept_starts)))
                filtered: Dict[int, List[int]] = {}
                for vidx, starts in raw.items():
                    if chosen_start in starts:
                        filtered[vidx] = [chosen_start]
                if filtered:
                    per_variant_positions[seg.id] = filtered
        else:
            # keep as-is but prune to kept positions (for consistency)
            filtered: Dict[int, List[int]] = {}
            for vidx, starts in raw.items():
                kept = [s for s in starts if s in kept_starts]
                if kept:
                    filtered[vidx] = sorted(kept)
            if filtered:
                per_variant_positions[seg.id] = filtered

    dep_ok, dep_errors = _enforce_dependencies(compiled, all_positions)
    ok = (len(required_missing) == 0) and dep_ok
    reason_parts: List[str] = []
    if required_missing:
        reason_parts.append("missing required: " + ", ".join(required_missing))
    if not dep_ok and dep_errors:
        reason_parts.extend(dep_errors)
    reason = "; ".join(reason_parts)
    return FileMatchResult(
        path=path,
        ok=ok,
        reason=reason,
        per_segment_counts=per_segment_counts,
        dependency_errors=dep_errors,
        size_bytes=len(data),
        positions_by_segment=all_positions,
        per_variant_positions=per_variant_positions,
    )


def parse_args(argv: List[str]) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description=(
            "Scan a single preinstanced file and print detailed sections/variants, or scan a directory for a quick pass/fail summary."
        )
    )
    p.add_argument(
        "path",
        nargs="?",
        default=".",
        help="Path to a single file to analyze verbosely, or a directory to scan (legacy mode)",
    )
    p.add_argument("--quiet", "-q", action="store_true", help="Only print final summary (directory mode)")
    p.add_argument(
        "--show-bytes",
        dest="show_bytes",
        action="store_true",
        help="Show first 256B of the file (debug)",
    )
    p.add_argument(
        "--timeline",
        action="store_true",
        help="Include a chronological timeline of all matched sections",
    )
    return p.parse_args(argv)


def _choose_variant_for_start(
    seg: CompiledSegment, per_variant: Dict[int, List[int]], start: int
) -> Optional[int]:
    for vidx, starts in per_variant.items():
        if start in starts:
            return vidx
    return None


def print_verbose_report(res: FileMatchResult, compiled: List[CompiledSegment], show_timeline: bool = True) -> None:
    print(f"File: {res.path}")
    print(f"Size: {res.size_bytes} bytes")
    print("Status:", "OK" if res.ok else f"FAIL ({res.reason})")
    if res.dependency_errors:
        for e in res.dependency_errors:
            print("  -", e)
    print()

    # Per-section details
    seg_by_id = {s.id: s for s in compiled}
    for seg in compiled:
        count = len(res.positions_by_segment.get(seg.id, []))
        req = "required" if seg.required else "optional"
        print(f"[{seg.id:02d}] {seg.name}: {count} hit(s) ({req})")
        if seg.note:
            print(f"      note: {seg.note}")
        if count == 0:
            print()
            continue
        # Variant breakdown
        per_var = res.per_variant_positions.get(seg.id, {})
        if per_var:
            for vidx in sorted(per_var.keys()):
                v = seg.variants[vidx]
                starts = sorted(per_var[vidx])
                patt_preview = _variant_signature(v)
                label = f" | {v.label}" if getattr(v, "label", None) else ""
                print(
                    f"      variant v{vidx} len={len(v.patt)}: {len(starts)} occ{label} | pattern: {patt_preview}"
                )
                # List offsets
                offs = ", ".join(f"0x{s:08X}" for s in starts)
                if offs:
                    print(f"        offsets: {offs}")
        else:
            # No variant mapping (shouldn't happen if count>0, but be robust)
            starts = [s for s, _L in res.positions_by_segment.get(seg.id, [])]
            offs = ", ".join(f"0x{s:08X}" for s in starts)
            print(f"      offsets: {offs}")
        print()

    if not show_timeline:
        return

    # Timeline (chronological) across all segments
    events: List[Tuple[int, int, int, str, Optional[int]]] = []
    for seg in compiled:
        occ = res.positions_by_segment.get(seg.id, [])
        if not occ:
            continue
        per_var = res.per_variant_positions.get(seg.id, {})
        for start, length in occ:
            vidx = _choose_variant_for_start(seg, per_var, start)
            events.append((start, length, seg.id, seg.name, vidx))
    events.sort(key=lambda t: t[0])

    if events:
        print("Timeline:")
        for start, length, sid, name, vidx in events:
            end = start + length
            vstr = f" v{vidx}" if vidx is not None else ""
            print(f"  0x{start:08X}-0x{end:08X} [{sid:02d}{vstr}] {name}")
        print()


def main(argv: List[str]) -> int:
    args = parse_args(argv)
    target_path = os.path.abspath(args.path)
    try:
        compiled = compile_pattern_defs(PATTERN_DEFS)
    except ValueError as e:
        print(f"Pattern parse error: {e}")
        return 3

    # If path is a file, run verbose single-file mode
    if os.path.isfile(target_path):
        res = check_file(target_path, compiled)
        print_verbose_report(res, compiled, show_timeline=args.timeline)
        if args.show_bytes:
            try:
                head = read_prefix(target_path, 256)
                print("Head (first 256B):")
                print(to_hex(head))
            except Exception:
                pass
        return 0 if res.ok else 2

    # If path is a directory, keep legacy scan behavior
    if not os.path.isdir(target_path):
        print(f"Path not found: {target_path}")
        return 4

    root = target_path
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




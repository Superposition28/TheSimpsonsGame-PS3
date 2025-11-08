#!/usr/bin/env python3
"""
Scan a directory recursively for files ending with:
  - .rws.ps3.preinstanced
  - .dff.ps3.preinstanced

For each file, confirm it starts (at offset 0 unless --offset is used) with the long SOF
pattern below. Token "**" means a wildcard byte (any value is accepted at that position).

Long SOF pattern (spaces/newlines ignored, "**" = any byte):

10 00 00 00 ** ** 00 00 2D 00 02 1C 01 00 00 00
0C 00 00 00 2D 00 02 1C 01 00 00 00 00 00 00 00
00 00 00 00 0E 00 00 00 ** ** 00 00 2D 00 02 1C
01 00 00 00 ** 00 00 00 2D 00 02 1C ** 00 00 00
00 00 80 3F 00 00 00 00 00 00 00 00 00 00 00 00
00 00 80 3F 00 00 00 00 00 00 00 00 00 00 00 00
00 00 80 3F ** ** ** ** ** ** ** ** ** ** ** **
FF FF FF FF 00 00 00 00 00 00 80 3F 00 00 00 00
00 00 00 00 00 00 00 00 00 00 80 3F 00 00 00 00
00 00 00 00 00 00 00 00 00 00 80 3F 00 00 00 00
00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00
00 00 00 00 ** 00 ** ** 00 00 00 00 ** 00 ** **
** 00 00 00 ** 00 ** ** ** 00 ** ** ** ** 00 00
** 00 00 00 ** 00 ** ** ** ** ** ** ** ** ** **
** ** ** 00 00 00 00 00 ** ** ** ** 00 00 00 00

Exit code is non-zero if any matching file fails the check.
"""

from __future__ import annotations

import argparse
import os
import sys
from dataclasses import dataclass
from typing import Iterable, List, Optional, Tuple
from concurrent.futures import ProcessPoolExecutor
from functools import partial


TARGET_SUFFIXES = (
    ".rws.ps3.preinstanced",
    ".dff.ps3.preinstanced",
)

@dataclass
class PatternDef:
    name: str
    pattern: str
    required: bool = True
    note: str = ""
    max_allowed: int = 0  # 0 = no limit


@dataclass
class CompiledSegment:
    name: str
    required: bool
    note: str
    patt: bytes
    mask: bytes
    max_allowed: int


# Long SOF/EOF patterns with wildcards (** or ?? tokens are single-byte wildcards)
# Define each segment with metadata for clarity and reporting.
# all **/?? sections are likly MetaData of the file or its contents or components or external data references
PATTERN_DEFS: List[PatternDef] = [
    PatternDef(
        name="SOF long header",
        pattern=(
            "10 00 00 00 ** ** ** ** 2D 00 02 1C 01 00 00 00 0C 00 00 00 2D 00 02 1C ** ** ** ** 00 00 00 00 "
            "00 00 00 00 0E 00 00 00 ** ** ** ** 2D 00 02 1C 01 00 00 00 ** ** ** ** 2D 00 02 1C ** ** ** ** "
            "00 00 80 3F 00 00 00 00 00 00 00 00 00 00 00 00 00 00 80 3F 00 00 00 00 00 00 00 00 00 00 00 00 "
            "00 00 80 3F ** ** ** ** ** ** ** ** ** ** ** ** FF FF FF FF 00 00 00 00 "
        ),
        required=True,
        note="Start-of-file long header. After this, ~100/5533 files may have an unknown block before texture data.",
        max_allowed=1,
    ),

    # === String/Name-related markers (from FIXED_SIGNATURES_TO_CHECK) ===
    # === Pre-Texture Names / Texture Data boundary ===
    PatternDef(
        name="Pre-texture names marker",
        pattern="02 11 01 00 02 00 00 00 ** ** ** ** 2D 00 02 1C",
        required=False,
        note="Observed before texture string names.",
        max_allowed=0,  # max observed was 297
    ),
    PatternDef(
        name="TLFD (Texture Data start)",
        pattern="54 4C 46 44",
        required=False,
        note="Marks end of string names and start of Texture Data.",
        max_allowed=0,  # max observed was 138
    ),

    # === Mesh-chunk scanning (from mshBytes regex) ===
    PatternDef(
        name="Mesh chunk header",
        pattern="33 EA 00 00 ** ** ** ** 2D 00 02 1C",
        required=False,
        note="Header used to locate mesh chunks before reading counts/offsets.",
        max_allowed=0,
    ),

    # === Face/strip parsing delimiter ===
    PatternDef(
        name="Triangle strip delimiter",
        pattern="FF FF",
        required=False,
        note="Index delimiter between strips (very common; non-unique).",
        max_allowed=0,
    ),

    # === EOF region ===
    PatternDef(
        name="EOF marker",
        pattern="16 EA 00 00 05 00 00 00 2D 00 02 1C 01 00 00 00 00",
        required=True,
        note="Expected near EOF (search after SOF segment).",
        max_allowed=1,
    ),
]


@dataclass
class CheckResult:
    path: str
    ok: bool
    reason: str = ""
    head_hex: str = ""
    matched_segments: List[str] = None  # names of segments matched in this file
    matched_segments_counts: Optional[dict[str, int]] = None
    matched_segments_first_start: Optional[dict[str, int]] = None


def iter_target_files(root: str) -> Iterable[str]:
    """Yield file paths under root that end with the target suffixes (case-insensitive)."""
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


def parse_wildcard_pattern_to_bytes_and_mask(pat: str) -> tuple[bytes, bytes]:
    """Parse a wildcard hex pattern into (pattern_bytes, mask_bytes).

    - Accepts tokens separated by whitespace
    - Wildcards: "**" or "??" (match any byte) → mask 0x00 at that position
    - Hex byte tokens: two hex digits (e.g., "2D") → mask 0xFF and corresponding byte value
    - Raises ValueError on any invalid token
    """
    p: List[int] = []
    m: List[int] = []
    for raw_tok in pat.replace("\n", " ").split():
        tok = raw_tok.strip()
        if not tok:
            continue
        # ">>" is handled by higher-level parser; reject it here to avoid silent misuse
        if tok == ">>":
            raise ValueError("'>>' skip token must be handled by parse_pattern_with_skips()")
        if tok in ("**", "??"):
            p.append(0x00)
            m.append(0x00)
            continue
        if len(tok) != 2:
            raise ValueError(f"Invalid token length in pattern: {tok!r}")
        try:
            val = int(tok, 16)
        except ValueError as e:
            raise ValueError(f"Invalid hex token in pattern: {tok!r}") from e
        p.append(val)
        m.append(0xFF)
    if not p:
        raise ValueError("Pattern parsed to empty list")
    return bytes(p), bytes(m)


def compile_pattern_defs(defs: List[PatternDef]) -> List[CompiledSegment]:
    """Compile human-friendly pattern definitions into byte/mask segments.

    The segments are meant to be matched in order. The first required segment is
    checked at the given offset; subsequent segments are searched after the
    previous match, skipping any bytes in between. Optional segments (required=False)
    are reported but do not fail the overall check if not found.
    """
    compiled: List[CompiledSegment] = []
    for d in defs:
        p, m = parse_wildcard_pattern_to_bytes_and_mask(d.pattern)
        if not p or len(p) != len(m):
            raise ValueError(f"Invalid pattern for segment '{d.name}'")
        compiled.append(CompiledSegment(name=d.name, required=d.required, note=d.note, patt=p, mask=m, max_allowed=d.max_allowed))
    if not compiled:
        raise ValueError("No pattern segments defined")
    return compiled


def find_masked(data: bytes, patt: bytes, mask: bytes, start: int) -> int:
    """Search for patt/mask in data at or after 'start'. Return index or -1 if not found."""
    need = len(patt)
    limit = len(data) - need
    if need == 0:
        return start
    for i in range(max(0, start), max(-1, limit) + 1):
        seg = data[i:i + need]
        # Fast path: check first byte with mask before full compare
        if (seg[0] & mask[0]) != (patt[0] & mask[0]):
            continue
        match = True
        for db, pb, mb in zip(seg, patt, mask):
            if (db & mb) != (pb & mb):
                match = False
                break
        if match:
            return i
    return -1


def count_occurrences_masked(data: bytes, patt: bytes, mask: bytes, start: int = 0) -> Tuple[int, List[int]]:
    """Count non-overlapping occurrences of patt/mask in data starting at 'start'.

    Returns (count, positions) where positions is a list of start indices of each match.
    """
    positions: List[int] = []
    pos = start
    step = max(1, len(patt))
    while True:
        found = find_masked(data, patt, mask, pos)
        if found == -1:
            break
        positions.append(found)
        pos = found + step  # non-overlapping
    return len(positions), positions


def match_prefix_masked(data: bytes, patt: bytes, mask: bytes, offset: int = 0) -> Optional[str]:
    """Match data[offset:offset+len(patt)] against patt using mask bytes.

    For each i: (data[offset+i] & mask[i]) must equal (patt[i] & mask[i]).
    Returns None if it matches, otherwise a short reason string.
    """
    if len(patt) != len(mask):
        return "internal error: pattern/mask length mismatch"
    need = len(patt)
    have = len(data)
    if have < offset + need:
        return f"too short: have {have}B, need at least {offset + need}B"
    seg = data[offset:offset + need]
    for i, (db, pb, mb) in enumerate(zip(seg, patt, mask)):
        if (db & mb) != (pb & mb):
            return f"mismatch @+0x{i:02X}: expected {(pb & mb):02X} mask {mb:02X}, got {(db & mb):02X}"
    return None


# Removed global worker state; we'll pass arguments via functools.partial in ProcessPoolExecutor.


def match_segments_with_skips_meta(
    data: bytes, segments: List[CompiledSegment], _offset: int = 0
) -> Tuple[bool, List[str], List[Tuple[str, int, int]], List[Tuple[str, int]]]:
    """Evaluate segments with metadata.

    Validation: each required segment must appear at least once anywhere in the data
    (ignoring offset ordering). The 'offset' parameter is retained for compatibility
    but not enforced for validation in this mode.

    Returns (ok, errors, matches, counts), where:
      - matches: list of (name, first_start, first_end) for segments that appeared at least once
      - counts: list of (name, total_count) for all segments
    """
    # _offset retained for compatibility in case ordering/offset is reintroduced
    if _offset:
        pass
    errors: List[str] = []
    matches: List[Tuple[str, int, int]] = []
    counts: List[Tuple[str, int]] = []

    if not segments:
        return False, ["internal error: no segments"], matches, counts

    for seg in segments:
        cnt, positions = count_occurrences_masked(data, seg.patt, seg.mask, 0)
        counts.append((seg.name, cnt))
        if cnt > 0:
            first_start = positions[0]
            matches.append((seg.name, first_start, first_start + len(seg.patt)))
        else:
            if seg.required:
                errors.append(f"{seg.name}: not found")
        # If a limit is set, we do not hard-fail currently; just warn in errors as info
        if seg.max_allowed > 0 and cnt > seg.max_allowed:
            errors.append(f"{seg.name}: count {cnt} exceeds max_allowed {seg.max_allowed}")

    ok = all(not (seg.required and cnt == 0) for seg, cnt in zip(segments, [c for (_n, c) in counts]))
    return ok, errors, matches, counts


def check_file(path: str, segments: List[CompiledSegment], offset: int) -> CheckResult:
    try:
        with open(path, "rb") as f:
            data = f.read()
    except OSError as e:
        return CheckResult(path=path, ok=False, reason=f"read error: {e}")

    # For display, capture the initial bytes needed for the first segment check
    first_len = len(segments[0].patt) if segments else 0
    head_len = min(len(data), offset + first_len)
    head_hex = to_hex(data[:head_len])

    ok, errors, _matches, counts = match_segments_with_skips_meta(data, segments, offset)
    reason = "; ".join(errors)
    matched_names = [n for (n, _s, _e) in _matches]
    # Convert counts to a simple mapping for aggregation
    matched_counts = {name: cnt for (name, cnt) in counts}
    # Map first-start offsets for segments that matched
    first_start_map = {name: start for (name, start, _end) in _matches}
    # Reuse matched_segments field for presence; attach counts as an attribute for aggregation
    return CheckResult(
        path=path,
        ok=ok,
        reason=reason,
        head_hex=head_hex,
        matched_segments=matched_names,
        matched_segments_counts=matched_counts,
        matched_segments_first_start=first_start_map,
    )


def parse_args(argv: List[str]) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Validate pattern (with wildcards) at file start for preinstanced PS3 files.")
    p.add_argument(
        "path",
        nargs="?",
        default=".",
        help="Root directory to scan (defaults to current directory)",
    )
    p.add_argument(
        "--quiet",
        "-q",
        action="store_true",
        help="Only print the summary (suppress per-file lines)",
    )
    p.add_argument(
        "--show-bytes",
        action="store_true",
        help="Include the head bytes read for each file in output",
    )
    p.add_argument(
        "--offset",
        type=int,
        default=0,
        help="Byte offset at which to match the pattern (default: 0)",
    )
    p.add_argument(
        "--workers",
        "-j",
        type=int,
        default=None,
        help="Number of worker processes to use (default: CPU count). Use 1 to disable multiprocessing.",
    )
    # Prevent AttributeError from references to args.json in existing output paths
    p.add_argument(
        "--json",
        action="store_true",
        help="Emit JSON output (placeholder flag; enables JSON-friendly streams)",
    )
    return p.parse_args(argv)


def main(argv: List[str]) -> int:
    args = parse_args(argv)
    root = args.path
    files = list(iter_target_files(root))

    total = len(files)
    failures = 0
    pass_lines = []
    fail_lines = []
    # Per-segment coverage counters
    per_segment_found = { }
    per_segment_max_in_file = { }
    all_required_ok = 0

    # Prepare pattern segments and masks (pure hex under the hood) with metadata
    try:
        compiled_segments = compile_pattern_defs(PATTERN_DEFS)
    except ValueError as e:
        print(f"Pattern parse error: {e}")
        return 3

    def _progress_write(msg: str) -> None:
        stream = sys.stderr if args.json else sys.stdout
        stream.write(msg)
        stream.flush()

    if not args.quiet:
        header = [
            f"Scanning: {os.path.abspath(root)}\n",
            f"Target suffixes: {', '.join(TARGET_SUFFIXES)}\n",
        ]
        seg_info = ", ".join(
            f"{seg.name}{{len={len(seg.patt)}, req={seg.required}}}" for seg in compiled_segments
        )
        header.append(f"Pattern segments (masked, in-order, skip gaps): [{seg_info}] @ offset {args.offset}\n")
        header.append(f"Found {total} file(s)\n\n")
        for line in header:
            _progress_write(line)

    # Initialize per-segment counters after compilation
    for seg in compiled_segments:
        per_segment_found[seg.name] = 0
        per_segment_max_in_file[seg.name] = 0

    def _accumulate_result(res: CheckResult, path: str) -> None:
        nonlocal failures, all_required_ok
        # Accumulate per-file and per-segment stats
        if res.matched_segments:
            for name in res.matched_segments:
                if name in per_segment_found:
                    per_segment_found[name] += 1
        # Update per-segment max occurrence across files
        counts_map = getattr(res, "matched_segments_counts", {}) or {}
        for name, cnt in counts_map.items():
            if name in per_segment_max_in_file:
                if cnt > per_segment_max_in_file[name]:
                    per_segment_max_in_file[name] = cnt
        # Build per-file JSON entry (currently not emitted; retained for future JSON output)
        per_file_segments = []
        missing_segments = []
        first_map = getattr(res, "matched_segments_first_start", {}) or {}
        for seg in compiled_segments:
            cnt = counts_map.get(seg.name, 0)
            per_file_segments.append({
                "name": seg.name,
                "required": seg.required,
                "count": cnt,
                "first_offset": first_map.get(seg.name),
            })
            if cnt == 0:
                missing_segments.append(seg.name)

        if res.ok:
            all_required_ok += 1
            line = None
            if not args.quiet and not args.json:
                line = f"PASS - {path}"
                if args.show_bytes:
                    line += f"  |  HEAD[{len(res.head_hex.split())}]: {res.head_hex}"
            if line is not None:
                pass_lines.append(line)
        else:
            failures += 1
            if not args.json:
                line = f"FAIL - {path} :: {res.reason or 'pattern mismatch'}"
                if args.show_bytes and res.head_hex:
                    line += f"  |  HEAD[{len(res.head_hex.split())}]: {res.head_hex}"
                fail_lines.append(line)
                print(line)  # debug

    # Choose execution mode: multiprocessing or sequential
    workers = args.workers if args.workers and args.workers > 0 else (os.cpu_count() or 1)
    use_mp = workers > 1 and total > 1

    if use_mp:
        # ProcessPool; pass segments and offset using partial to avoid globals
        chunksize = max(1, total // (workers * 4) if workers else 1)
        if not args.quiet:
            _progress_write(f"Using {workers} workers (chunksize={chunksize})\n")
        with ProcessPoolExecutor(max_workers=workers) as ex:
            worker_fn = partial(check_file, segments=compiled_segments, offset=args.offset)
            for idx, res in enumerate(ex.map(worker_fn, files, chunksize=chunksize), 1):
                _accumulate_result(res, res.path)
                if not args.quiet:
                    _progress_write(f"\rScanned {idx}/{total} files")
    else:
        # Sequential fallback (or workers==1)
        for idx, path in enumerate(files, 1):
            res = check_file(path, compiled_segments, args.offset)
            _accumulate_result(res, path)
            if not args.quiet:
                _progress_write(f"\rScanned {idx}/{total} files")

    # Summary
    overall_status = "OK" if failures == 0 else "ERROR"

    # ensure progress line ends
    if not args.quiet:
        _progress_write("\n")
    print()
    print("Summary:")
    # Per-pattern coverage report
    print("  Pattern coverage:")
    for idx, seg in enumerate(compiled_segments, 1):
        found = per_segment_found.get(seg.name, 0)
        missing = total - found
        max_in_file = per_segment_max_in_file.get(seg.name, 0)
        if seg.required:
            limit_txt = f", limit={seg.max_allowed}" if seg.max_allowed > 0 else ""
            print(f"    Pattern {idx} ({seg.name}) [required]: {found} pass, {missing} fail; max/file={max_in_file}{limit_txt}")
        else:
            limit_txt = f", limit={seg.max_allowed}" if seg.max_allowed > 0 else ""
            print(f"    Pattern {idx} ({seg.name}) [optional]: {found} present, {missing} missing; max/file={max_in_file}{limit_txt}")
    print(f"  All required patterns OK: {all_required_ok}/{total}")
    print(f"  Long SOF pattern: {overall_status} - {total - failures} pass, {failures} fail, {total} total")

    return 0 if failures == 0 else 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))


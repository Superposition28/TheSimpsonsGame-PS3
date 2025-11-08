#!/usr/bin/env python3
"""
validate that the hex headers found are correct and consistent accross all assets

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
    """Human-friendly description of a binary pattern segment.

    Attributes:
        name: Display name used in reports.
        pattern: Single wildcard-capable hex string (e.g., "2D 00 ** 1C").
        patterns: Alternate patterns for the same logical segment; any may match.
        required: If True, missing this segment makes the file fail (unless later
                  heuristics override).
        note: Informational note shown in reports.
        max_allowed: Optional upper bound on occurrences per file (0 = no limit).
    """
    name: str
    pattern: Optional[str] = None
    # Optional list of alternative patterns; if provided, any variant matching counts
    patterns: Optional[List[str]] = None
    required: bool = True
    note: str = ""
    max_allowed: int = 0  # 0 = no limit


@dataclass
class CompiledVariant:
    """Concrete (pattern, mask) pair derived from a wildcard hex string."""
    patt: bytes
    mask: bytes


@dataclass
class CompiledSegment:
    """Compiled pattern segment with metadata and variant encodings.

    Attributes:
        name: Segment name.
        required: Whether presence is required for a PASS.
        note: Additional context shown in output.
        variants: One or more compiled pattern/mask variants.
        max_allowed: Optional limit for how many times this segment may appear.
    """
    name: str
    required: bool
    note: str
    variants: List[CompiledVariant]
    max_allowed: int


"""
these are the absolute hex variations

    SOF # three metadata bytes
    10 00 00 00 ?? ?? ?? 00 2D 00 02 1C

    String Block Header ### always followed by a variant 14 or 18 otherwise is not string header block
    02 11 01 00 02 00 00 00

    String Block Header and variant 14
    02 11 01 00 02 00 00 00 14 00 00 00 2D 00 02 1C

    String Block Header and variant 18
    02 11 01 00 02 00 00 00 18 00 00 00 2D 00 02 1C

    ## not observed to exist in any files. why does it exist ?
    Float-pattern Block Header (803F x3)
    90 59 20 01 00 00 80 3F 00 00 80 3F 00 00 80 3F

    ## not observed to exist in any files. why does it exist ?
    Mesh chunk header (gap=16)
    33 EA 00 00 ** ** ** ** ** ** ** ** ** ** ** ** 2D 00 02 1C

"""
# Long SOF/EOF patterns with wildcards (** or ?? tokens are single-byte wildcards)
# Define each segment with metadata for clarity and reporting.
# all **/?? sections are likly MetaData of the file or its contents or components or external data references
PATTERN_DEFS: List[PatternDef] = [
    PatternDef(
        name="SOF long header",
        pattern=(
            "10 00 00 00 ** ** ** 00 2D 00 02 1C 01 00 00 00 0C 00 00 00 2D 00 02 1C ** ** ** ** 00 00 00 00 "
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
        name="Pre-texture names marker String Block Header (General, 8B) ",
        patterns=[
            "02 11 01 00 02 00 00 00 14 00 00 00 2D 00 02 1C",
            "02 11 01 00 02 00 00 00 18 00 00 00 2D 00 02 1C",
        ],
        required=False,
        note="Observed before texture string names. // Fixed signature before embedded string(s); string usually starts +0x10.",
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
    classification: str = ""


def iter_target_files(root: str) -> Iterable[str]:
    """Yield matching files recursively.

    Scans the given root directory for files whose names end with any of
    TARGET_SUFFIXES (case-insensitive) and yields absolute paths.
    """
    root = os.path.abspath(root)
    for dirpath, _dirnames, filenames in os.walk(root):
        for name in filenames:
            lower = name.lower()
            if lower.endswith(TARGET_SUFFIXES):
                yield os.path.join(dirpath, name)


def read_prefix(path: str, n: int) -> bytes:
    """Read the first n bytes of a file (helper for small peeks)."""
    with open(path, "rb") as f:
        return f.read(n)


def to_hex(b: bytes) -> str:
    """Return a space-separated hex string for the given bytes."""
    return " ".join(f"{x:02X}" for x in b)


def parse_wildcard_pattern_to_bytes_and_mask(pat: str) -> tuple[bytes, bytes]:
    """Parse a wildcard hex pattern into (pattern_bytes, mask_bytes).

    Rules:
    - Tokens separated by whitespace
    - Wildcards: "**" or "??" (match any byte) → mask 0x00 at that position
    - Hex byte tokens: two hex digits (e.g., "2D") → mask 0xFF and corresponding byte
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
    """Compile pattern definitions into concrete byte/mask segments.

    Accepts `PatternDef` items that may have multiple alternative encodings,
    transforms each into a list of `CompiledVariant`s, and returns `CompiledSegment`s
    with metadata preserved for matching and reporting.
    """
    compiled: List[CompiledSegment] = []
    for d in defs:
        # Gather patterns: either a single 'pattern' or a list in 'patterns'
        patt_list: List[str] = []
        if d.patterns and len(d.patterns) > 0:
            patt_list = d.patterns
        elif d.pattern:
            patt_list = [d.pattern]
        else:
            raise ValueError(f"PatternDef '{d.name}' must define 'pattern' or 'patterns'")

        variants: List[CompiledVariant] = []
        for pat in patt_list:
            p, m = parse_wildcard_pattern_to_bytes_and_mask(pat)
            if not p or len(p) != len(m):
                raise ValueError(f"Invalid pattern for segment '{d.name}'")
            variants.append(CompiledVariant(patt=p, mask=m))

        compiled.append(
            CompiledSegment(
                name=d.name,
                required=d.required,
                note=d.note,
                variants=variants,
                max_allowed=d.max_allowed,
            )
        )
    if not compiled:
        raise ValueError("No pattern segments defined")
    return compiled


def find_masked(data: bytes, patt: bytes, mask: bytes, start: int) -> int:
    """Find the first masked match.

    Returns the starting index of the first occurrence of `patt` under `mask`
    at or after `start`, or -1 if not found.
    """
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
    """Count non-overlapping masked matches and return (count, positions)."""
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


def count_occurrences_any_variants(
    data: bytes, variants: List[CompiledVariant], start: int = 0
) -> Tuple[int, List[Tuple[int, int]]]:
    """Count total masked matches across any variant.

    Returns (count, first_matches) where first_matches is [(pos, length)] for
    each variant's first occurrence. Counts are per-variant and not de-duplicated
    across variants.
    """
    total = 0
    first_matches: List[Tuple[int, int]] = []
    for v in variants:
        cnt, positions = count_occurrences_masked(data, v.patt, v.mask, start)
        total += cnt
        if positions:
            first_matches.append((positions[0], len(v.patt)))
    return total, first_matches


def match_prefix_masked(data: bytes, patt: bytes, mask: bytes, offset: int = 0) -> Optional[str]:
    """Check that a slice matches the masked pattern.

    For each i: (data[offset+i] & mask[i]) == (patt[i] & mask[i]).
    Returns None on success, or a short reason string on mismatch.
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
    """Evaluate presence and counts of segments within data.

    Each required segment must appear at least once anywhere in the payload.
    Offset ordering is ignored in this "meta" mode. Returns:
      - ok: overall boolean pass/fail
      - errors: list of human-readable issues
      - matches: [(name, first_start, first_end)] of first sightings
      - counts: [(name, total_count)] occurrence counts for all segments
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
        cnt, firsts = count_occurrences_any_variants(data, seg.variants, 0)
        counts.append((seg.name, cnt))
        if cnt > 0:
            # Pick earliest first occurrence among variants
            first_start, first_len = min(firsts, key=lambda t: t[0])
            matches.append((seg.name, first_start, first_start + first_len))
        else:
            if seg.required:
                errors.append(f"{seg.name}: not found")
        # If a limit is set, we do not hard-fail currently; just warn in errors as info
        if seg.max_allowed > 0 and cnt > seg.max_allowed:
            errors.append(f"{seg.name}: count {cnt} exceeds max_allowed {seg.max_allowed}")

    ok = all(not (seg.required and cnt == 0) for seg, cnt in zip(segments, [c for (_n, c) in counts]))
    return ok, errors, matches, counts


def check_file(path: str, segments: List[CompiledSegment], offset: int) -> CheckResult:
    """Read a file and evaluate pattern-segment presence.

    Applies heuristics to classify the file (renderable/texture-bearing vs.
    renderless/container) and may relax strict requirements for recognized
    renderless containers that still include an EOF marker.
    """
    try:
        with open(path, "rb") as f:
            data = f.read()
    except OSError as e:
        return CheckResult(path=path, ok=False, reason=f"read error: {e}")

    # Classify the file once for summary reporting
    def classify_file(data: bytes, path: str) -> str:
        name = os.path.basename(path).lower()
        has_mesh_sig  = (b"\x33\xEA\x00\x00" in data) and (b"\x2D\x00\x02\x1C" in data)
        has_tlfd      = b"TLFD" in data
        has_pre_names = b"\x02\x11\x01\x00\x02\x00\x00\x00" in data
        tok_renderless = any(t in name for t in ("bound","collision","col","icb","nopathseek","placeholder","fragment"))
        id1 = data[:2048].count(b"\x00\x00\x80\x3F")
        looks_renderless = (not has_mesh_sig) and (not has_tlfd) and id1 >= 12

        if has_mesh_sig:
            if has_tlfd:
                return "RENDERABLE_TEX_EMBEDDED"
            if has_pre_names:
                return "RENDERABLE_TEX_STRINGS_ONLY"
            return "RENDERABLE_NO_TEX"
        if tok_renderless or looks_renderless:
            return "RENDERLESS"
        return "CONTAINER"

    classification = classify_file(data, path)

    # For display, capture the initial bytes needed for the first segment check
    first_len = len(segments[0].variants[0].patt) if segments else 0
    head_len = min(len(data), offset + first_len)
    head_hex = to_hex(data[:head_len])

    ok, errors, _matches, counts = match_segments_with_skips_meta(data, segments, offset)
    reason = "; ".join(errors)
    matched_names = [n for (n, _s, _e) in _matches]
    # Convert counts to a simple mapping for aggregation
    matched_counts = {name: cnt for (name, cnt) in counts}
    # Map first-start offsets for segments that matched
    first_start_map = {name: start for (name, start, _end) in _matches}

    # Heuristic: detect renderless container/bounds-style files and relax strict SOF requirement
    # Conditions:
    #   - No mesh header signature and no TLFD present
    #   - First ~1KB contains many 1.0f bytes (00 00 80 3F), typical of identity transforms
    #   - EOF marker should still be present to confirm file type
    def _looks_like_renderless_container(payload: bytes) -> bool:
        head = payload[:1024]
        id1 = head.count(b"\x00\x00\x80\x3F")
        has_mesh_sig = (b"\x33\xEA\x00\x00" in payload) and (b"\x2D\x00\x02\x1C" in payload)
        has_tlfd = (b"TLFD" in payload)
        return (not has_mesh_sig) and (not has_tlfd) and (id1 >= 12)

    # Filename hints can also signal a renderless/bounds-like file
    name_hint = os.path.basename(path).lower()
    name_screams_renderless = any(hint in name_hint for hint in (
        "bound", "collision", "col", "icb", "nopathseek", "placeholder", "fragment"
    ))

    if not ok:
        eof_cnt = matched_counts.get("EOF marker", 0)
        # Prefer classifier decision for renderless, fall back to heuristic
        is_renderless = (classification == "RENDERLESS") or _looks_like_renderless_container(data) or name_screams_renderless
        if is_renderless and eof_cnt > 0:
            ok = True
            reason = f"renderless-container override ({reason})" if reason else "renderless-container override"

    # Reuse matched_segments field for presence; attach counts as an attribute for aggregation
    return CheckResult(
        path=path,
        ok=ok,
        reason=reason,
        head_hex=head_hex,
        matched_segments=matched_names,
        matched_segments_counts=matched_counts,
        matched_segments_first_start=first_start_map,
        classification=classification,
    )


def parse_args(argv: List[str]) -> argparse.Namespace:
    """Define and parse CLI arguments for the checker script."""
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
    """Entry point for the preinstanced PS3 file pattern validator.

    Scans for target-suffixed files, checks for required/optional signature
    segments, prints per-file results (unless quiet), and a summary. Returns
    0 on success (no failures), 2 if any file failed, 3 on pattern parse error.
    """
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
    classification_counts: dict[str, int] = {}

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
            f"{seg.name}{{len={len(seg.variants[0].patt)}, req={seg.required}}}" for seg in compiled_segments
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
        # Classification aggregation
        cls = getattr(res, "classification", "") or "(unknown)"
        classification_counts[cls] = classification_counts.get(cls, 0) + 1
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

    # Classification summary
    if total > 0:
        print()
        print("Classification summary:")
        # Deterministic order
        order = [
            ("RENDERABLE+TEX", "good game meshes with texture linkage"),
            ("RENDERABLE_NO_TEX", "meshes likely using shared TXDs / vertex colors / lightmaps"),
            ("RENDERLESS", "bounds/occluders/ICB/etc."),
            ("CONTAINER", "structural/instance tables without local mesh/texture payloads"),
        ]
        for key, desc in order:
            cnt = classification_counts.get(key, 0)
            print(f"  {key:18} : {cnt:5d}  — {desc}")
        # Any unexpected labels
        extras = [k for k in classification_counts.keys() if k not in {k for k, _ in order}]
        for key in sorted(extras):
            print(f"  {key:18} : {classification_counts.get(key, 0):5d}")

    return 0 if failures == 0 else 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))


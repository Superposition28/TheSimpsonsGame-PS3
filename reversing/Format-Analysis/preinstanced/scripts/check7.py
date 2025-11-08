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


    "10 00 00 00 ** ** ** 00 2D 00 02 1C 01 00 00 00 "
    "0C 00 00 00 2D 00 02 1C ** ** ** ** 00 00 00 00 "
    "00 00 00 00 0E 00 00 00 ** ** ** ** 2D 00 02 1C "
    "01 00 00 00 ** ** ** ** 2D 00 02 1C ** ** ** ** "
    "00 00 80 3F 00 00 00 00 00 00 00 00 00 00 00 00 "
    "00 00 80 3F 00 00 00 00 00 00 00 00 00 00 00 00 "
    "00 00 80 3F ** ** ** ** ** ** ** ** ** ** ** ** "
    "FF FF FF FF 00 00 00 00 ",

"""
# Long SOF/EOF patterns with wildcards (** or ?? tokens are single-byte wildcards)
# Define each segment with metadata for clarity and reporting.
# all **/?? sections are likly MetaData of the file or its contents or components or external data references
PATTERN_DEFS: List[PatternDef] = [


    ## long headers are used in place of short ones to ensure correct detection avoiding any other instances of a similar hex string, Offsets cannot be used as there not consistant
    PatternDef(
        name="SOF long header",
        pattern=(
            "10 00 00 00 ?? ?? ?? 00 2D 00 02 1C 01 00 00 00 0C 00 00 00 2D 00 02 1C ** ** ** ** 00 00 00 00 00 00 00 00 0E 00 00 00 ** ** ** ** 2D 00 02 1C 01 00 00 00 ** ** ** ** "
            "2D 00 02 1C ** ** ** ** 00 00 80 3F 00 00 00 00 00 00 00 00 00 00 00 00 00 00 80 3F 00 00 00 00 00 00 00 00 00 00 00 00 00 00 80 3F ** ** ** ** ** ** ** ** ** ** ** ** "
            "FF FF FF FF 00 00 00 00 ** ** ** ** ** ** ** ** ** ** ** ** ** ** ** ** ** ** ** ** ** ** ** ** ** ** ** ** ** ** ** ** ** ** 80 3F ** ** ** ** ** ** ** ** ** ** ** ** ",
        ),
        required=True,
        note="Start-of-file long header. After this, ~100/5533 files may have an unknown block before texture data.",
        max_allowed=1,
    ),

    ## this header indicates a following 12 byte sequence that is often followed by the same header then another 12 however many times until it reaches the 'Unknown DataBlock header'
    PatternDef(
        name="SOF Binary Block Data",
        patterns=[
            ## the 00 is the first instance of this section the 01 is all other section headers
            "00 00 00 00 00 00 00 00 00 00 80 3F 00 00 00 00 00 00 00 00 00 00 00 00 00 00 80 3F 00 00 00 00 00 00 00 00 00 00 00 00 00 00 80 3F",
            "01 00 00 00 00 00 00 00 00 00 80 3F 00 00 00 00 00 00 00 00 00 00 00 00 00 00 80 3F 00 00 00 00 00 00 00 00 00 00 00 00 00 00 80 3F"
        ],
        required=False,
        note="Possible Header, found after the unknown binary data just before texture data and mesh",
        max_allowed=1,
    ),

    ## these mark an unknown segment of data before the texturs after the SOF and after an unknown binary block often seen right after SOF
    ## these two patterns appear mostly in .rws files and in very few .dff
    PatternDef(
        name="Unknown DataBlock header",
        pattern="01 00 00 00 00 00 00 00 03 00 00 00 00 00 00 00 2D 00 02 1C 03 00 00 00 18 00 00 00 2D 00 02 1C 1E 01 00 00 0C 00 00 00 2D 00 02 1C 00 01 00 00 00 00 00 00 00 00 00 00 03 00 00 00 18 00 00 00 2D 00 02 1C 1E 01 00 00 0C 00 00 00 2D 00 02 1C ",
        required=False,
        note="found after the unknown binary data just before texture data and mesh",
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
    #PatternDef(
    #    name="Triangle strip delimiter",
    #    pattern="FF FF",
    #    required=False,
    #    note="Index delimiter between strips (very common; non-unique).",
    #    max_allowed=0,
    #),

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
    # per-pattern → per-variant → Counter(wildcardKeyHex → occurrences)
    variant_keys: Optional[dict[str, dict[int, Counter]]] = None
    # Texture-vs-Mesh ordering analysis
    ordering_status: str = ""  # one of: ORDER_OK, ORDER_MISMATCH, NO_TEXTURE, NO_MESH
    num_textures: int = 0
    num_meshes: int = 0
    textures_with_later_mesh: int = 0
    textures_after_last_mesh: int = 0
    earliest_texture_pos: Optional[int] = None
    earliest_mesh_pos: Optional[int] = None


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
        # Gather patterns: either a single 'pattern' or a list in 'patterns'.
        # Be defensive: if 'pattern' was accidentally provided as a tuple/list
        # of string literals (e.g., due to a trailing comma), join them into a
        # single long string so it's treated as one pattern.
        patt_list: List[str] = []
        if d.patterns and len(d.patterns) > 0:
            patt_list = d.patterns
        elif d.pattern is not None:
            patt_val = d.pattern
            # Normalize tuple/list of strings into a single concatenated string
            if isinstance(patt_val, (list, tuple)):
                if all(isinstance(x, str) for x in patt_val):
                    patt_list = ["".join(patt_val)]
                else:
                    raise ValueError(f"PatternDef '{d.name}' has non-string entries in 'pattern' sequence")
            elif isinstance(patt_val, str):
                patt_list = [patt_val]
            else:
                raise ValueError(f"PatternDef '{d.name}' has unsupported type for 'pattern': {type(patt_val).__name__}")
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


def find_all_occurrences_any_variants(data: bytes, variants: List[CompiledVariant]) -> List[int]:
    """Return sorted unique start offsets of all non-overlapping matches of any variant.

    Non-overlap is enforced per-variant; if two variants would match at the same
    offset, deduplication is applied by using a set before sorting.
    """
    positions: set[int] = set()
    for v in variants:
        _cnt, pos_list = count_occurrences_masked(data, v.patt, v.mask, 0)
        for p in pos_list:
            positions.add(p)
    return sorted(positions)


# === Wildcard instantiation enumeration helpers ===
def _wildcard_indices(mask: bytes) -> list[int]:
    """Indices where mask==0 (wildcards)."""
    return [i for i, mb in enumerate(mask) if mb == 0]


def _collect_variant_keys_for_variant(data: bytes, patt: bytes, mask: bytes) -> Counter:
    """
    Count unique wildcard-instantiation keys for a single compiled variant.
    Key is the hex of all wildcard bytes in-order.
    For no-wildcard variants, we return Counter({'(no-wildcards)': occurrences}).
    """
    wc_idx = _wildcard_indices(mask)
    cnt, positions = count_occurrences_masked(data, patt, mask, 0)
    c = Counter()
    if not wc_idx:
        if cnt > 0:
            c["(no-wildcards)"] += cnt
        return c
    for pos in positions:
        key_bytes = bytes(data[pos + j] for j in wc_idx)
        c[key_bytes.hex()] += 1
    return c


def collect_variant_keys_for_segment(data: bytes, segment: CompiledSegment) -> dict[int, Counter]:
    """
    For a CompiledSegment with one or more variants, return:
      { variant_idx: Counter({ wildcardKeyHex: occurrences, ... }), ... }
    Only includes variants that occur at least once in 'data'.
    """
    out: dict[int, Counter] = {}
    for vidx, var in enumerate(segment.variants):
        c = _collect_variant_keys_for_variant(data, var.patt, var.mask)
        if c:
            out[vidx] = c
    return out


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

    # Collect wildcard-instantiation keys per segment/variant
    per_segment_variant_keys: dict[str, dict[int, Counter]] = {}
    for seg in segments:
        vk = collect_variant_keys_for_segment(data, seg)
        if vk:
            per_segment_variant_keys[seg.name] = vk

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

    # Texture-vs-Mesh ordering analysis
    # Identify relevant segments
    seg_by_name = {s.name: s for s in segments}
    tex_names_seg = seg_by_name.get("Pre-texture names marker String Block Header (General, 8B) ")
    tlfd_seg = seg_by_name.get("TLFD (Texture Data start)")
    mesh_seg = seg_by_name.get("Mesh chunk header")

    texture_positions: List[int] = []
    mesh_positions: List[int] = []
    if tex_names_seg:
        texture_positions.extend(find_all_occurrences_any_variants(data, tex_names_seg.variants))
    if tlfd_seg:
        texture_positions.extend(find_all_occurrences_any_variants(data, tlfd_seg.variants))
    if mesh_seg:
        mesh_positions = find_all_occurrences_any_variants(data, mesh_seg.variants)

    # Deduplicate and sort texture positions
    texture_positions = sorted(set(texture_positions))

    num_textures = len(texture_positions)
    num_meshes = len(mesh_positions)
    earliest_texture_pos = texture_positions[0] if texture_positions else None
    earliest_mesh_pos = mesh_positions[0] if mesh_positions else None

    textures_with_later_mesh = 0
    textures_after_last_mesh = 0
    if num_textures > 0 and num_meshes > 0:
        last_mesh = mesh_positions[-1]
        for tpos in texture_positions:
            # Any mesh strictly after this texture marker?
            has_later = any(mpos > tpos for mpos in mesh_positions)
            if has_later:
                textures_with_later_mesh += 1
            else:
                textures_after_last_mesh += 1
    elif num_textures > 0 and num_meshes == 0:
        textures_after_last_mesh = num_textures

    if num_textures == 0:
        ordering_status = "NO_TEXTURE"
    elif num_meshes == 0:
        ordering_status = "NO_MESH"
    elif textures_with_later_mesh == num_textures:
        ordering_status = "ORDER_OK"
    else:
        ordering_status = "ORDER_MISMATCH"

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
        variant_keys=per_segment_variant_keys,
        ordering_status=ordering_status,
        num_textures=num_textures,
        num_meshes=num_meshes,
        textures_with_later_mesh=textures_with_later_mesh,
        textures_after_last_mesh=textures_after_last_mesh,
        earliest_texture_pos=earliest_texture_pos,
        earliest_mesh_pos=earliest_mesh_pos,
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
    # Global aggregator: pattern name -> variant_idx -> Counter(wildcardKeyHex -> occurrences)
    global_variant_keys: dict[str, dict[int, Counter]] = defaultdict(lambda: defaultdict(Counter))
    # Also track total occurrences per pattern (sum over variants)
    total_occurrences_by_pattern: dict[str, int] = defaultdict(int)
    # Ordering aggregation
    ordering_counts: dict[str, int] = defaultdict(int)
    files_with_textures = 0
    textures_total = 0
    textures_with_later_mesh_total = 0

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
        nonlocal failures, all_required_ok, files_with_textures, textures_total, textures_with_later_mesh_total
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
        # Merge variant keys (wildcard-instantiation enumeration)
        vk_map = getattr(res, "variant_keys", None) or {}
        for pname, altmap in vk_map.items():
            for vidx, counter in altmap.items():
                global_variant_keys[pname][vidx].update(counter)
                total_occurrences_by_pattern[pname] += sum(counter.values())
        # Ordering aggregation
        status = getattr(res, "ordering_status", "") or "(unknown)"
        ordering_counts[status] = ordering_counts.get(status, 0) + 1
        if res.num_textures > 0:
            files_with_textures += 1
            textures_total += res.num_textures
            textures_with_later_mesh_total += res.textures_with_later_mesh
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
                # Append ordering status for visibility
                line += f"  |  order={status} (tex={res.num_textures}, mesh={res.num_meshes}, tex->mesh={res.textures_with_later_mesh})"
            if line is not None:
                pass_lines.append(line)
        else:
            failures += 1
            if not args.json:
                line = f"FAIL - {path} :: {res.reason or 'pattern mismatch'}"
                if args.show_bytes and res.head_hex:
                    line += f"  |  HEAD[{len(res.head_hex.split())}]: {res.head_hex}"
                line += f"  |  order={status} (tex={res.num_textures}, mesh={res.num_meshes}, tex->mesh={res.textures_with_later_mesh})"
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

    # Variant enumeration summary
    print()
    print("Variant enumeration (wildcard instantiations):")
    for seg in compiled_segments:
        pname = seg.name
        altmap = global_variant_keys.get(pname, {})
        total_occ = total_occurrences_by_pattern.get(pname, 0)
        # Unique variants = unique keys across all alternatives
        unique_keys_overall = set()
        for counter in altmap.values():
            unique_keys_overall.update(counter.keys())
        unique_count = len(unique_keys_overall) if total_occ > 0 else 0

        print(f"  - {pname}: occurrences={total_occ}, unique_variants={unique_count}")
        if not altmap:
            continue

        # Per-alternative breakdown (useful when 'patterns=[...]')
        for vidx, counter in sorted(altmap.items()):
            alt_occ = sum(counter.values())
            alt_unique = len(counter)
            print(f"      alt[{vidx}]: occ={alt_occ}, unique={alt_unique}")
            # Top 5 most common keys
            if alt_occ:
                for key, n in counter.most_common(5):
                    pct = (100.0 * n / alt_occ)
                    print(f"         - {key}  x{n}  ({pct:.1f}%)")

    # Classification summary
    if total > 0:
        print()
        print("Classification summary:")
        # Deterministic order
        order = [
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

    # Ordering summary
    if total > 0:
        print()
        print("Texture-vs-Mesh ordering summary:")
        # Deterministic ordering of statuses
        order_keys = ["ORDER_OK", "ORDER_MISMATCH", "NO_TEXTURE", "NO_MESH", "(unknown)"]
        for k in order_keys:
            if k in ordering_counts:
                print(f"  {k:14} : {ordering_counts[k]:5d}")
        # Overall ratio across files that actually contain textures
        if files_with_textures > 0:
            pct = 100.0 * (textures_with_later_mesh_total / textures_total) if textures_total else 0.0
            print(f"  Per-texture linkage: {textures_with_later_mesh_total}/{textures_total} ({pct:.1f}%) textures have a subsequent mesh in-file")

    return 0 if failures == 0 else 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))


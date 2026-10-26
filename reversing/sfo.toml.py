#!/usr/bin/env python3
"""Read PS3 PARAM.SFO/PSF files and export documented, valid UTF-8 TOML.

The default export has:
  [sfo]       file identity and PSF header
  [values]    convenient, typed key/value dictionary (when unambiguous)
  [[entries]] every original index record, decoded value if known, context,
              and raw data (including otherwise uninterpretable formats)

The binary PSF/PS3 details are based on the supplied PSDevWiki PARAM.SFO
reference and the Simpsons EU/US/demo research notes. Interpretations are
metadata descriptions, NOT guarantees of actual runtime hardware behaviour.

Requires only Python 3.9+ standard library. Use Python 3.11+ 'tomllib' to
independently parse/verify the generated TOML.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass, field
import hashlib
import json
from pathlib import Path
import re
import struct
import sys
from typing import Optional, Union

MAGIC = b"\x00PSF"
HEADER_SIZE = 20
ENTRY_SIZE = 16
FORMAT_NAMES = {
    0x0004: "Byte array / UTF-8 special (not necessarily text)",
    0x0204: "NUL-terminated UTF-8 string",
    0x0404: "Little-endian unsigned 32-bit integer",
}

# PSDevWiki PS3 PARAM.SFO parameter descriptions. 'Unknown' semantics remain
# explicitly unknown; a description here does not imply a decoded value.
DESCRIPTIONS = {
    "ACCOUNT_ID": "Save-data PSN account identifier; may bind a save to its owner. Treat as sensitive metadata.",
    "ANALOG_MODE": "Analog-input or controller-mode metadata; meaning depends on content category.",
    "APP_VER": "Application/executable version, often increased by an update; distinct from VERSION and the PSF header version.",
    "ATTRIBUTE": "Category-dependent bitmask of special content features and boot-related attributes.",
    "BOOTABLE": "Content boot mode: 0 not bootable, 1 bootable game, 2 alternate software boot mode (firmware-dependent).",
    "CATEGORY": "PS3 XMB content category code. A category alone is not proof that a game is a demo.",
    "CONTENT_ID": "PlayStation Network content/license identifier; distinct from TITLE_ID.",
    "DETAIL": "Long description shown with save-data metadata.",
    "GAMEDATA_ID": "Game-data identifier; detailed semantics are not fully established in the PSDevWiki reference.",
    "ITEM_PRIORITY": "XMB item ordering or priority metadata; meaning depends on content type.",
    "LANG": "Language identifier used by trophy data; numeric code is not text itself.",
    "LICENSE": "License/copyright notice carried by the content; may not be shown by retail system software.",
    "NP_COMMUNICATION_ID": "PlayStation Network trophy/communication identifier, distinct from TITLE_ID.",
    "PADDING": "Reserved/padding field. Its contents have no documented user-facing meaning.",
    "PARAMS": "Opaque PS3 save-data parameters, counters and reserved fields; cannot generally be decoded into text.",
    "PARAMS2": "Additional save-data/system parameters; preserve as opaque bytes unless separately specified.",
    "PARENTAL_LEVEL": "PS3 parental-control restriction level (not a player's age or an ESRB/PEGI rating).",
    "PATCH_FILE": "Patch-related content metadata; contents depend on the package/content type.",
    "PS3_SYSTEM_VER": "Minimum declared PS3 system-software version required by this content.",
    "REGION_DENY": "Regional restriction bitmask; set bits restrict regions. Check the content type before interpreting region numbers.",
    "RESOLUTION": "Bitmask of declared supported video-output modes; not the measured in-game rendering resolution.",
    "SAVEDATA_DIRECTORY": "Save-data directory name associated with this content.",
    "SAVEDATA_FILE_LIST": "Save-data file listing/metadata; may be opaque rather than a human-readable string.",
    "SAVEDATA_LIST_PARAM": "Save-data listing parameters used by the XMB.",
    "SAVEDATA_PARAMS": "Opaque save-data parameters; not necessarily textual even if stored in a byte-array format.",
    "SOUND_FORMAT": "Bitmask of supported PS3 output audio formats; not the codec or channel count of every game asset.",
    "SOURCE": "Source identifier/flags in certain content types; detailed meaning is not established.",
    "SUB_TITLE": "Secondary XMB/save-data display title.",
    "TARGET_APP_VER": "Target application version for update-related content.",
    "TITLE": "Default title displayed in the PS3 XMB.",
    "TITLE_ID": "Sony platform content title identifier; identifies this release, not an in-game text asset.",
    "VERSION": "Disc/package revision string; distinct from APP_VER and the binary PSF header version.",
    "XMB_APPS": "XMB application-related bitmask; individual flag meanings are not established here.",
}

LANGUAGES = {
    0: "Japanese", 1: "English (United States)", 2: "French",
    3: "Spanish (Spain)", 4: "German", 5: "Italian",
    6: "Dutch", 7: "Portuguese (Portugal)", 8: "Russian",
    9: "Korean", 10: "Chinese (Traditional)", 11: "Chinese (Simplified)",
    12: "Finnish", 13: "Swedish", 14: "Danish", 15: "Norwegian",
    16: "Polish", 17: "Portuguese (Brazil)",
    18: "English (United Kingdom)", 19: "Turkish", 20: "Spanish (Latin America)",
}

# Labels follow PSDevWiki and RPCS3. Do not invent names for unspecified bits.
RESOLUTION_FLAGS = {
    0x01: "480-line (4:3)", 0x02: "576-line (4:3)",
    0x04: "720-line (16:9)", 0x08: "1080-line (16:9)",
    0x10: "480-line (16:9)", 0x20: "576-line (16:9)",
}
SOUND_FLAGS = {
    0x01: "Linear PCM 2.0",
    0x02: "format support flag used with Dolby Digital/DTS (not itself an audio mode)",
    0x04: "Linear PCM 5.1", 0x10: "Linear PCM 7.1",
    0x100: "Dolby Digital (AC-3) 5.1", 0x200: "DTS 5.1",
}

Value = Union[str, int]


@dataclass
class Entry:
    index: int
    key: str
    key_bytes: bytes
    key_offset: int
    data_format: int
    data_length: int
    data_max_length: int
    data_offset: int
    key_position: int
    data_position: int
    raw: bytes
    unused: bytes
    value: Optional[Value] = None
    text_preview: Optional[str] = None
    notes: list[str] = field(default_factory=list)


@dataclass
class SFO:
    source: str
    size: int
    sha256: str
    version: int
    key_table_start: int
    data_table_start: int
    entries: list[Entry]
    key_table_bytes: bytes
    raw_file: bytes
    warnings: list[str] = field(default_factory=list)


def _decode_entry(e: Entry) -> None:
    if e.data_format == 0x0404:
        if len(e.raw) != 4:
            e.notes.append("Integer format expects exactly 4 used bytes; raw data retained without guessing.")
        else:
            e.value = struct.unpack("<I", e.raw)[0]
    elif e.data_format == 0x0204:
        # Do not use errors='replace', and do not discard multiple terminators.
        if not e.raw.endswith(b"\0"):
            e.notes.append("UTF-8 string lacks the expected final NUL terminator.")
        content = e.raw[:-1] if e.raw.endswith(b"\0") else e.raw
        if b"\0" in content:
            e.notes.append("Embedded NUL byte in string; decoded value preserves it.")
        try:
            e.value = content.decode("utf-8", errors="strict")
        except UnicodeDecodeError:
            e.notes.append("Invalid UTF-8: raw bytes retained; no replacement characters inserted.")
    elif e.data_format == 0x0004:
        # This format is used for byte arrays as well as certain strings. Raw
        # data remains authoritative even when a text preview is possible.
        try:
            preview = e.raw.decode("utf-8", errors="strict")
            if preview and all(c.isprintable() or c in "\t\r\n" for c in preview):
                e.text_preview = preview
                e.notes.append("Readable UTF-8 preview only; the 0x0004 byte array remains authoritative.")
        except UnicodeDecodeError:
            pass
        e.notes.append("Byte-array payload has no universally safe semantic translation.")
    else:
        e.notes.append("Unrecognized format tag; raw bytes retained without attempting interpretation.")


def parse_sfo(file_path: Union[str, Path]) -> SFO:
    path = Path(file_path)
    data = path.read_bytes()
    if len(data) < HEADER_SIZE:
        raise ValueError("Truncated PSF header (requires at least 20 bytes).")
    if data[:4] != MAGIC:
        raise ValueError("Not a PSF/PARAM.SFO file (missing 00 50 53 46 signature).")

    version, key_start, data_start, count = struct.unpack_from("<IIII", data, 4)
    # Reject arithmetic/bounds issues BEFORE reading untrusted index records.
    max_count = (len(data) - HEADER_SIZE) // ENTRY_SIZE
    if count > max_count:
        raise ValueError(f"Index table requests {count} entries; only {max_count} records can fit.")
    index_end = HEADER_SIZE + count * ENTRY_SIZE
    if not (index_end <= key_start <= data_start <= len(data)):
        raise ValueError("Invalid index/key/data table offsets or table ordering.")

    result = SFO(str(path), len(data), hashlib.sha256(data).hexdigest(),
                 version, key_start, data_start, [], data[key_start:data_start], data)
    if version != 0x00000101:
        result.warnings.append(f"Unusual PSF header version 0x{version:08X}; decoded as little-endian.")

    claimed_ranges = []
    for i in range(count):
        k_off, fmt, length, capacity, d_off = struct.unpack_from("<HHIII", data, HEADER_SIZE + i * ENTRY_SIZE)
        if length > capacity:
            raise ValueError(f"Entry {i}: used length exceeds allocated length ({length} > {capacity}).")
        kp = key_start + k_off
        if not (key_start <= kp < data_start):
            raise ValueError(f"Entry {i}: key offset is outside the key table.")
        terminator = data.find(b"\0", kp, data_start)
        if terminator < 0:
            raise ValueError(f"Entry {i}: unterminated key inside key table.")
        key_bytes = data[kp:terminator]
        if not key_bytes:
            raise ValueError(f"Entry {i}: empty key is not supported.")
        try:
            key = key_bytes.decode("ascii", errors="strict")
        except UnicodeDecodeError:
            raise ValueError(f"Entry {i}: non-ASCII PSF key at 0x{kp:X}.") from None

        pos = data_start + d_off
        if pos < data_start or pos > len(data) or capacity > len(data) - pos:
            raise ValueError(f"Entry {i} ({key}): allocated data range exceeds file size.")
        e = Entry(i, key, key_bytes, k_off, fmt, length, capacity, d_off,
                  kp, pos, data[pos:pos + length], data[pos + length:pos + capacity])
        if pos % 4:
            e.notes.append("Data address is not four-byte aligned (unusual for PS3 SFO).")
        if any(e.unused):
            e.notes.append("Unused capacity contains nonzero bytes; retained as hex.")
        _decode_entry(e)
        result.entries.append(e)
        if capacity:
            claimed_ranges.append((pos, pos + capacity, i))

    # Flag unexpected overlapping value allocations; never discard either.
    claimed_ranges.sort()
    for a, b in zip(claimed_ranges, claimed_ranges[1:]):
        if b[0] < a[1]:
            result.warnings.append(f"Data allocations overlap: entries {a[2]} and {b[2]}.")
    return result


def _description(e: Entry) -> str:
    k = e.key
    m = re.fullmatch(r"TITLE_(\d{2})", k)
    if m:
        lang = LANGUAGES.get(int(m.group(1)), "unrecognized language slot")
        return f"Localized XMB display title for language slot {m.group(1)} ({lang})."
    m = re.fullmatch(r"PARENTAL_LEVEL_(\d+)", k)
    if m:
        return f"Parental-level override for license area {m.group(1)}; not a player age."
    return DESCRIPTIONS.get(k, "Unrecognized PSF key: platform-specific meaning not established; consult the original content documentation.")


def _hex(x: int, digits: int = 8) -> str:
    return f"0x{x:0{digits}X}"


def _flags(num: int, names: dict[int, str]) -> tuple[list[str], int]:
    decoded = [f"{_hex(bit)}: {label}" for bit, label in sorted(names.items()) if num & bit]
    known_mask = 0
    for bit in names:
        known_mask |= bit
    return decoded, num & (~known_mask & 0xFFFFFFFF)


def _interpret(e: Entry) -> tuple[str, list[str], int]:
    """Human reading, specific flag labels, and any uninterpreted flag bits."""
    v = e.value
    if not isinstance(v, int):
        if v is None:
            return "No safe decoded scalar; see raw_hex, format and notes.", [], 0
        if e.key == "CATEGORY":
            categories = {
                "DG": "Disc Game (PS3_GAME on a PS3 game disc)",
                "HG": "HDD Game (installed/downloaded content; not automatically a demo)",
            }
            return categories.get(v, "Unrecognized category code: platform placement/type is not inferred."), [], 0
        if e.key == "PS3_SYSTEM_VER":
            return f"Requires at least declared PS3 system software version {v}.", [], 0
        if e.key == "APP_VER":
            return f"Declared application/patch version {v}.", [], 0
        if e.key == "VERSION":
            return f"Declared disc/package revision {v} (not necessarily executable version).", [], 0
        if e.key == "TITLE_ID":
            return f"Content title ID {v}; identifies the product/release.", [], 0
        if e.key == "TITLE" or re.fullmatch(r"TITLE_\d{2}", e.key):
            return "XMB display title; localized language (if any) is specified in description.", [], 0
        return "String decoded as UTF-8; see value for the original metadata text.", [], 0
    k = e.key
    if k in ("RESOLUTION", "SOUND_FORMAT"):
        found, other = _flags(v, RESOLUTION_FLAGS if k == "RESOLUTION" else SOUND_FLAGS)
        return ("Declared video-output modes" if k == "RESOLUTION" else "Declared audio-output formats"), found, other
    if k == "BOOTABLE":
        return {0: "Not bootable", 1: "Bootable (game mode 1)",
                2: "Bootable (software mode 2; firmware/content dependent)"}.get(v, "Unrecognized boot mode; preserve numeric value."), [], 0
    if k == "ATTRIBUTE":
        return ("No ATTRIBUTE feature bits set" if not v else "ATTRIBUTE is a content-category-dependent flag mask; per-bit meaning is not inferred here."), [], 0
    if k == "PARENTAL_LEVEL":
        return ("Parental controls disabled" if v == 0 else f"Restriction level {v} (PS3 scale, not an age rating)."), [], 0
    if k == "LANG":
        return f"Language code: {LANGUAGES.get(v, 'unknown / outside documented language list')}", [], 0
    if k == "REGION_DENY":
        return "Regional exclusion bitmask; set bits mean denied territories (mapping depends on platform and context).", [], 0
    return "PSF unsigned 32-bit integer; see field description. No key-specific decoding is assumed.", [], 0


def _toml_value(value: Union[str, int, bool, list]) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, int):
        return str(value)
    if isinstance(value, str):
        # JSON basic-string escaping is also legal TOML for the valid Unicode
        # and control sequences produced from strictly decoded PSF text.
        return json.dumps(value, ensure_ascii=False).replace("\x7f", "\\u007F")
    if isinstance(value, list):
        return "[" + ", ".join(_toml_value(v) for v in value) + "]"
    raise TypeError(f"Cannot write {type(value)} as TOML")


def _emit(lines: list[str], name: str, value: Union[str, int, bool, list]) -> None:
    lines.append(f"{name} = {_toml_value(value)}")


def render_toml(sfo: SFO, *, embed_binary: bool = False) -> str:
    lines = [
        "# PARAM.SFO metadata: decoded values plus source-preserving index context.",
        "# Hex fields are strings; offsets and lengths are decimal byte positions.",
        "# [[entries]] is authoritative if a key occurs more than once.",
        "# Unknown formats/flags remain explicit rather than being guessed.",
        "",
        "[sfo]",
    ]
    for name, val in [
        ("source_file", Path(sfo.source).name), ("file_size_bytes", sfo.size),
        ("sha256", sfo.sha256), ("magic_hex", MAGIC.hex().upper()),
        ("header_version", _hex(sfo.version)),
        ("header_version_explanation", "PSF container header version; 0x00000101 corresponds to version 1.1, not the game VERSION key."),
        ("header_size_bytes", HEADER_SIZE), ("index_entry_size_bytes", ENTRY_SIZE),
        ("entry_count", len(sfo.entries)),
        ("key_table_start", sfo.key_table_start),
        ("data_table_start", sfo.data_table_start),
        ("key_table_hex", sfo.key_table_bytes.hex().upper()),
        ("warnings", sfo.warnings),
    ]:
        _emit(lines, name, val)
    if embed_binary:
        # Enables exact byte-for-byte recovery (including gaps, unreferenced
        # bytes, unknown key-table content and trailing data) if needed.
        _emit(lines, "full_file_hex", sfo.raw_file.hex().upper())

    counts: dict[str, int] = {}
    for e in sfo.entries:
        counts[e.key] = counts.get(e.key, 0) + 1
    duplicates = [k for k, n in counts.items() if n > 1]
    lines += ["", "[values]", "# Convenience map of unambiguous decoded scalars only.",
              "# For missing/opaque/duplicate keys, read [[entries]] instead."]
    for e in sfo.entries:
        if counts[e.key] == 1 and e.value is not None:
            _emit(lines, _toml_value(e.key), e.value)
    lines += ["", "[sfo_index]", "# Counts help detect data omitted from the convenience [values] view."]
    _emit(lines, "duplicate_keys", duplicates)
    _emit(lines, "decoded_unique_values", sum(counts[e.key] == 1 and e.value is not None for e in sfo.entries))
    _emit(lines, "opaque_or_duplicate_entries", sum(e.value is None or counts[e.key] > 1 for e in sfo.entries))

    for e in sfo.entries:
        meaning, flags, unknown = _interpret(e)
        lines.extend(["", "[[entries]]"])
        fields = [
            ("index", e.index), ("key", e.key), ("description", _description(e)),
            ("interpretation", meaning),
            ("format_code", _hex(e.data_format, 4)),
            ("format_description", FORMAT_NAMES.get(e.data_format, "Unknown PSF data format")),
            ("key_offset", e.key_offset), ("key_position", e.key_position),
            ("index_record_position", HEADER_SIZE + e.index * ENTRY_SIZE),
            ("data_offset", e.data_offset), ("data_position", e.data_position),
            ("used_bytes", e.data_length), ("capacity_bytes", e.data_max_length),
            ("unused_bytes", len(e.unused)),
            ("raw_hex", e.raw.hex().upper()),
        ]
        if e.value is not None:
            fields.append(("value", e.value))
            if isinstance(e.value, int):
                fields.extend([("value_hex", _hex(e.value)),
                               ("value_binary", f"{e.value:032b}")])
        if e.text_preview is not None:
            fields.append(("text_preview_not_authoritative", e.text_preview))
        if flags:
            fields.append(("set_flags", flags))
        if e.key in ("RESOLUTION", "SOUND_FORMAT") and isinstance(e.value, int):
            fields.append(("unknown_flag_bits_hex", _hex(unknown)))
        if any(e.unused):
            fields.append(("unused_nonzero_hex", e.unused.hex().upper()))
        fields.append(("notes", e.notes))
        for name, val in fields:
            _emit(lines, name, val)
    return "\n".join(lines) + "\n"


def parse_sfo_to_toml(file_path: Union[str, Path]) -> dict[str, Value]:
    """Legacy compatibility: decoded scalars as a flat mapping.

    Prefer parse_sfo()/render_toml(), which retain duplicate/opaque entries.
    """
    sfo = parse_sfo(file_path)
    if len({e.key for e in sfo.entries}) != len(sfo.entries):
        raise ValueError("Duplicate keys cannot be represented by a flat TOML table; use the rich export.")
    return {e.key: e.value if e.value is not None else "RAW_HEX:" + e.raw.hex().upper()
            for e in sfo.entries}


def generate_toml(parsed_data: dict[str, Value]) -> str:
    """Legacy compatibility: generate a valid flat key/value TOML file."""
    return "\n".join(f"{_toml_value(k)} = {_toml_value(v)}"
                     for k, v in parsed_data.items()) + "\n"


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Extract PS3 SFO to rich human-readable TOML (no third-party dependencies).")
    parser.add_argument("files", nargs="+", type=Path, help="One or more PARAM.SFO files")
    parser.add_argument("-o", "--output", type=Path, help="Output filename (single input only)")
    parser.add_argument("--flat", action="store_true", help="Original legacy-style flat TOML; loses structural metadata")
    parser.add_argument("--embed-binary", action="store_true", help="Include full_file_hex for exact raw file archival (rich mode only)")
    args = parser.parse_args(argv)
    if args.output and len(args.files) != 1:
        parser.error("--output may only be used with one input")
    if args.flat and args.embed_binary:
        parser.error("--embed-binary requires rich mode (omit --flat)")
    error = False
    for path in args.files:
        try:
            sfo = parse_sfo(path)
            output = (generate_toml(parse_sfo_to_toml(path)) if args.flat
                      else render_toml(sfo, embed_binary=args.embed_binary))
            destination = args.output if args.output else Path(str(path) + ".toml")
            if destination.resolve() == path.resolve():
                raise ValueError("Output must not overwrite input SFO")
            with destination.open("w", encoding="utf-8", newline="\n") as out:
                out.write(output)
            print(f"Exported {len(sfo.entries)} entries: {path} -> {destination}")
            if sfo.warnings:
                for warning in sfo.warnings:
                    print(f"  Warning: {warning}", file=sys.stderr)
        except (OSError, ValueError, UnicodeError) as exc:
            print(f"Error exporting {path}: {exc}", file=sys.stderr)
            error = True
    return int(error)


if __name__ == "__main__":
    sys.exit(main())

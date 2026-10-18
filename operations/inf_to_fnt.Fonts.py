#!/usr/bin/env python3
"""
The Simpsons Game (PS3) - EA 'FONT' v6 (.inf) to AngelCode BMFont (.fnt) Converter
==================================================================================

Maps extracted `.inf` binary font descriptor files from The Simpsons Game (PS3) to their
corresponding extracted `.png` texture atlases and converts them into Godot-compatible
AngelCode BMFont (`.fnt`) files.

Binary Format Summary (`FONT` v6, Big-Endian):
  - 0x000..0x028 (40 bytes): File Header
      0x00: char[4]  Magic             ("FONT" = 46 4F 4E 54)
      0x04: uint32   FileSize          Exact size of the .inf file in bytes
      0x08: uint16   Version           Format version (always 6)
      0x0A: uint16   GlyphCount        Number of 24-byte glyph records (33, 95, or 191)
      0x0C: uint32   GlyphTableOffset  Offset to Glyph Table (always 0x00000434 = 1076)
      0x10: uint32   Flags             Reserved / flags (0x00000000)
      0x14: uint32   MaxGlyphWidth     Nominal maximum character width / advance in pixels
      0x18: uint32   LineHeight        Vertical line height in pixels (max(YOffset + Height))
      0x1C: uint32   Baseline          Vertical baseline in pixels from top of line
      0x20: uint32   LookupTableOffset Offset to post-glyph runtime lookup table (0x0434 + GlyphCount * 24)
      0x24: uint32   Alignment         Constant 4 (0x00000004)
  - 0x028..0x428 (1024 bytes): Zero-initialized runtime character index table (256 x uint32)
  - 0x428..0x434 (12 bytes): Kerning Table Header
      0x428: uint16  KerningCount        Total kerning pairs declared across all glyphs
      0x42A: uint16  Padding             0x0000
      0x42C: uint32  KerningTableOffset  Offset to Kerning Table (LookupTableOffset + 0x404, or 0 if none)
      0x430: uint32  Padding             0x00000000
  - 0x434..LookupTableOffset (GlyphCount * 24 bytes): Glyph Table
      +0x00: uint8   CharCode            8-bit character ID (followed by 1-byte 0x00 pad at +0x01)
      +0x02: uint16  Width               Bounding box width in pixels
      +0x04: uint16  Height              Bounding box height in pixels
      +0x06: uint16  XAdvance            Horizontal advance in pixels
      +0x08: int16   XOffset             Signed horizontal bearing offset in pixels
      +0x0A: int16   YOffset             Signed vertical offset from top of line in pixels
      +0x0C: uint16  X0_Fixed            Left atlas coordinate in 12.4 fixed-point subpixels (X0 = X0_Fixed >> 4)
      +0x0E: uint16  Y0_Fixed            Top atlas coordinate in 12.4 fixed-point subpixels (Y0 = Y0_Fixed >> 4)
      +0x10: uint16  X1_Fixed            Right atlas coordinate in 12.4 fixed-point subpixels (X1 = X1_Fixed >> 4)
      +0x12: uint16  Y1_Fixed            Bottom atlas coordinate in 12.4 fixed-point subpixels (Y1 = Y1_Fixed >> 4)
      +0x14: uint16  KerningCount        Number of kerning pairs starting with this glyph
      +0x16: uint16  KerningStartIndex   0-based index into the active kerning pair array
  - LookupTableOffset..LookupTableOffset+0x404 (1028 bytes): Zero-initialized runtime lookup buffer
  - KerningTableOffset..EOF (KerningCount * 3 bytes): Kerning Table
      Starts with a 6-byte preamble (2-byte flag + 4-byte sentinel record with FirstChar=0x00),
      followed by 4-byte records at KerningTableOffset + 6:
        +0x00: uint8 FirstChar
        +0x01: uint8 SecondChar
        +0x02: uint8 Padding (0x00)
        +0x03: int8  Amount (signed pixel adjustment)
      Note: EA's offline font exporter allocated `KerningCount * 3` bytes instead of `6 + KerningCount * 4`,
      truncating the final ~25% of kerning pairs at EOF.

Usage:
  python operations/inf_to_fnt.Fonts.py [--input-dir <GameFilesDir>] [--output-dir <OutDir>] [--copy-png]
"""

from __future__ import annotations

import argparse
import os
import re
import shutil
import struct
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple


# Regex to strip the 6-character hex hash suffix added by QuickBMS / STR extraction (e.g. "_ff9566")
HASH_SUFFIX_RE = re.compile(r"_[0-9a-fA-F]{6}$")

# In the 191-glyph European font sets, 7 byte codes in the 0xA0..0xFF block are repurposed
# to store Windows-1252 / MacRoman characters that lie outside ISO-8859-1.
# We emit both the raw byte ID (for raw 8-bit lookups) and the Unicode codepoint alias
# (so standard UTF-8 strings in Godot render the glyphs automatically).
EXTENDED_UNICODE_ALIASES: Dict[int, int] = {
    0xAC: 0x2122,  # '™' Trade Mark Sign (U+2122)
    0xB1: 0x0160,  # 'Š' Latin Capital Letter S with Caron (U+0160)
    0xB2: 0x0152,  # 'Œ' Latin Capital Ligature OE (U+0152)
    0xB3: 0x0161,  # 'š' Latin Small Letter S with Caron (U+0161)
    0xBC: 0x221E,  # '∞' Infinity / Simpsons Special Symbol (U+221E)
    0xBD: 0x20AC,  # '€' Euro Sign (U+20AC)
    0xBE: 0x0153,  # 'œ' Latin Small Ligature OE (U+0153)
}

# For button icon fonts (char codes 0x00..0x20), control codes like 0x00 (NUL), 0x09 (TAB),
# 0x0A (LF), and 0x0D (CR) cannot be typed directly in standard Godot Label text without
# triggering control behavior. We keep raw IDs 0..32 AND alias them to Unicode Private Use
# Area U+E000..U+E020 (57344..57376).
BUTTON_PUA_BASE = 0xE000


@dataclass
class GlyphRecord:
    """Represents a single 24-byte glyph entry from the .inf Glyph Table."""
    char_code: int
    width: int
    height: int
    xadvance: int
    xoffset: int
    yoffset: int
    x0_fixed: int
    y0_fixed: int
    x1_fixed: int
    y1_fixed: int
    kerning_count: int
    kerning_start_index: int

    @property
    def x(self) -> int:
        """Top-left X pixel coordinate in the texture atlas (12.4 fixed-point -> integer)."""
        return self.x0_fixed >> 4

    @property
    def y(self) -> int:
        """Top-left Y pixel coordinate in the texture atlas (12.4 fixed-point -> integer)."""
        return self.y0_fixed >> 4

    @property
    def x1(self) -> int:
        """Bottom-right X pixel coordinate in the texture atlas (12.4 fixed-point -> integer)."""
        return self.x1_fixed >> 4

    @property
    def y1(self) -> int:
        """Bottom-right Y pixel coordinate in the texture atlas (12.4 fixed-point -> integer)."""
        return self.y1_fixed >> 4


@dataclass
class KerningRecord:
    """Represents a single 4-byte kerning pair entry from the .inf Kerning Table."""
    first_char: int
    second_char: int
    amount: int


@dataclass
class InfFont:
    """Complete parsed representation of an EA 'FONT' v6 (.inf) binary file."""
    filepath: Path
    file_size: int
    version: int
    glyph_count: int
    glyph_table_offset: int
    flags: int
    max_glyph_width: int
    line_height: int
    baseline: int
    lookup_table_offset: int
    alignment: int
    declared_kerning_count: int
    kerning_table_offset: int
    glyphs: List[GlyphRecord] = field(default_factory=list)
    kernings: List[KerningRecord] = field(default_factory=list)


def strip_hash_suffix(stem: str) -> str:
    """Strips a trailing 6-hex-digit hash suffix (e.g. 'buttons_37bb42' -> 'buttons')."""
    return HASH_SUFFIX_RE.sub("", stem)


def read_png_dimensions(png_path: Path) -> Tuple[int, int]:
    """Reads (width, height) from a PNG file's IHDR chunk using only the Python standard library."""
    with png_path.open("rb") as f:
        header = f.read(24)
    if len(header) < 24 or header[:8] != b"\x89PNG\r\n\x1a\n" or header[12:16] != b"IHDR":
        raise ValueError(f"Invalid or corrupt PNG header in {png_path}")
    width, height = struct.unpack(">II", header[16:24])
    return width, height


def parse_inf_file(filepath: Path) -> InfFont:
    """Parses and validates an EA 'FONT' v6 (.inf) binary file."""
    data = filepath.read_bytes()
    actual_size = len(data)
    if actual_size < 0x434:
        raise ValueError(f"{filepath.name}: File too small ({actual_size} bytes < 1076 bytes minimum).")

    magic = data[0:4]
    if magic != b"FONT":
        raise ValueError(f"{filepath.name}: Invalid magic {magic!r}, expected b'FONT'.")

    (
        file_size,
        version,
        glyph_count,
        glyph_table_offset,
        flags,
        max_glyph_width,
        line_height,
        baseline,
        lookup_table_offset,
        alignment,
    ) = struct.unpack(">IHHIIIIIII", data[0x04:0x28])

    if file_size != actual_size:
        raise ValueError(f"{filepath.name}: Header size mismatch (declared {file_size}, actual {actual_size}).")

    declared_kerning_count, _pad1, kerning_table_offset, _pad2 = struct.unpack(">HHII", data[0x428:0x434])

    expected_glyph_end = glyph_table_offset + (glyph_count * 24)
    if expected_glyph_end > actual_size:
        raise ValueError(
            f"{filepath.name}: Glyph table (offset 0x{glyph_table_offset:X} + {glyph_count}*24) exceeds file size."
        )

    glyphs: List[GlyphRecord] = []
    offset = glyph_table_offset
    for i in range(glyph_count):
        char_code = data[offset]
        char_pad = data[offset + 1]
        if char_pad != 0:
            raise ValueError(f"{filepath.name}: Unexpected non-zero char pad 0x{char_pad:02X} at glyph {i}.")

        (
            width,
            height,
            xadvance,
            xoffset,
            yoffset,
            x0_fixed,
            y0_fixed,
            x1_fixed,
            y1_fixed,
            k_count,
            k_index,
        ) = struct.unpack(">HHHhhHHHHHH", data[offset + 2 : offset + 24])

        glyph = GlyphRecord(
            char_code=char_code,
            width=width,
            height=height,
            xadvance=xadvance,
            xoffset=xoffset,
            yoffset=yoffset,
            x0_fixed=x0_fixed,
            y0_fixed=y0_fixed,
            x1_fixed=x1_fixed,
            y1_fixed=y1_fixed,
            kerning_count=k_count,
            kerning_start_index=k_index,
        )

        # Verify 12.4 fixed-point bounding box matches pixel width and height
        if (glyph.x1 - glyph.x) != glyph.width or (glyph.y1 - glyph.y) != glyph.height:
            raise ValueError(
                f"{filepath.name}: Glyph {i} (char 0x{char_code:02X}) UV box "
                f"({glyph.x},{glyph.y})..({glyph.x1},{glyph.y1}) does not match WxH ({glyph.width}x{glyph.height})."
            )

        glyphs.append(glyph)
        offset += 24

    # Parse Kerning Table (if present)
    kernings: List[KerningRecord] = []
    if declared_kerning_count > 0 and kerning_table_offset > 0:
        # Build lookup from glyph kerning index ranges to verify ownership
        # Active 4-byte kerning records begin at kerning_table_offset + 6 (after 6-byte preamble)
        k_offset = kerning_table_offset + 6
        while k_offset + 4 <= actual_size and len(kernings) < declared_kerning_count:
            first_char, second_char, pad, amount = struct.unpack(">BBBb", data[k_offset : k_offset + 4])
            if pad != 0:
                break
            if first_char != 0 and second_char != 0:
                kernings.append(
                    KerningRecord(
                        first_char=first_char,
                        second_char=second_char,
                        amount=amount,
                    )
                )
            k_offset += 4

    return InfFont(
        filepath=filepath,
        file_size=file_size,
        version=version,
        glyph_count=glyph_count,
        glyph_table_offset=glyph_table_offset,
        flags=flags,
        max_glyph_width=max_glyph_width,
        line_height=line_height,
        baseline=baseline,
        lookup_table_offset=lookup_table_offset,
        alignment=alignment,
        declared_kerning_count=declared_kerning_count,
        kerning_table_offset=kerning_table_offset,
        glyphs=glyphs,
        kernings=kernings,
    )


def build_png_index(root_dir: Path) -> List[Path]:
    """Finds all .png files recursively under root_dir."""
    return sorted(root_dir.rglob("*.png"))


def match_png_for_inf(inf_path: Path, all_pngs: List[Path], root_dir: Path) -> Path:
    """
    Maps an .inf font file to its companion .png texture atlas.

    Matching rules:
      1. Strip the 6-hex-character hash suffix from the .inf filename stem
         (e.g. 'HighlanderStdBold6060b_1d35c8.inf' -> 'HighlanderStdBold6060b').
      2. Identify the parent archive group (e.g. 'A2_Characters/simpsonsCharsGlobalStr'
         or 'A2_Frontend/frontendStr').
      3. Find the .png in the same archive group whose clean stem matches the font's clean stem.
      4. Fall back to any matching .png in root_dir if not found in the same archive group.
    """
    clean_font_name = strip_hash_suffix(inf_path.stem).lower()

    try:
        inf_rel = inf_path.relative_to(root_dir)
        archive_prefix = inf_rel.parts[:2] if len(inf_rel.parts) >= 2 else inf_rel.parts[:1]
    except ValueError:
        archive_prefix = ()

    same_archive_matches: List[Path] = []
    global_matches: List[Path] = []

    for png_path in all_pngs:
        clean_png_name = strip_hash_suffix(png_path.stem).lower()
        if clean_png_name == clean_font_name:
            global_matches.append(png_path)
            try:
                png_rel = png_path.relative_to(root_dir)
                if archive_prefix and png_rel.parts[: len(archive_prefix)] == archive_prefix:
                    same_archive_matches.append(png_path)
            except ValueError:
                pass

    if same_archive_matches:
        return same_archive_matches[0]
    if global_matches:
        return global_matches[0]

    raise FileNotFoundError(
        f"Could not find a matching .png texture for {inf_path} (clean name: '{clean_font_name}')."
    )


def format_bmfont_fnt(
    font: InfFont,
    face_name: str,
    png_rel_path: str,
    scale_w: int,
    scale_h: int,
    include_unicode_aliases: bool = True,
) -> str:
    """
    Serializes a parsed InfFont into an AngelCode BMFont (.fnt) text descriptor compatible with Godot 4.
    """
    is_bold = 1 if "bold" in face_name.lower() else 0
    # Use the font's LineHeight as the nominal BMFont size and lineHeight.
    # For button icon sheets where baseline is 0, set base to line_height so inline icons align cleanly.
    line_height = font.line_height if font.line_height > 0 else 60
    base = font.baseline if font.baseline > 0 else line_height
    is_button_font = face_name.lower().startswith("buttons")

    # Prepare glyph entries (sorted by char ID for clean, deterministic BMFont output)
    char_entries: List[Tuple[int, GlyphRecord]] = []
    seen_ids = set()

    for g in sorted(font.glyphs, key=lambda item: item.char_code):
        if g.x + g.width > scale_w or g.y + g.height > scale_h:
            raise ValueError(
                f"{font.filepath.name}: Glyph 0x{g.char_code:02X} rect "
                f"({g.x},{g.y},{g.width},{g.height}) exceeds PNG dimensions ({scale_w}x{scale_h})."
            )
        char_entries.append((g.char_code, g))
        seen_ids.add(g.char_code)

        if include_unicode_aliases:
            if is_button_font and 0x00 <= g.char_code <= 0x20:
                pua_id = BUTTON_PUA_BASE + g.char_code
                if pua_id not in seen_ids:
                    char_entries.append((pua_id, g))
                    seen_ids.add(pua_id)
            elif g.char_code in EXTENDED_UNICODE_ALIASES:
                unicode_id = EXTENDED_UNICODE_ALIASES[g.char_code]
                if unicode_id not in seen_ids:
                    char_entries.append((unicode_id, g))
                    seen_ids.add(unicode_id)

    char_entries.sort(key=lambda pair: pair[0])

    # Prepare kerning entries (including Unicode aliases for remapped extended chars)
    kerning_entries: List[Tuple[int, int, int]] = []
    seen_kern_pairs = set()

    for k in font.kernings:
        first_ids = [k.first_char]
        second_ids = [k.second_char]
        if include_unicode_aliases and not is_button_font:
            if k.first_char in EXTENDED_UNICODE_ALIASES:
                first_ids.append(EXTENDED_UNICODE_ALIASES[k.first_char])
            if k.second_char in EXTENDED_UNICODE_ALIASES:
                second_ids.append(EXTENDED_UNICODE_ALIASES[k.second_char])

        for f_id in first_ids:
            for s_id in second_ids:
                if (f_id, s_id) not in seen_kern_pairs:
                    seen_kern_pairs.add((f_id, s_id))
                    kerning_entries.append((f_id, s_id, k.amount))

    lines: List[str] = []
    lines.append(
        f'info face="{face_name}" size={line_height} bold={is_bold} italic=0 charset="" '
        f"unicode=1 stretchH=100 smooth=1 aa=1 padding=0,0,0,0 spacing=1,1 outline=0"
    )
    lines.append(
        f"common lineHeight={line_height} base={base} scaleW={scale_w} scaleH={scale_h} "
        f"pages=1 packed=0 alphaChnl=0 redChnl=0 greenChnl=0 blueChnl=0"
    )
    lines.append(f'page id=0 file="{png_rel_path}"')
    lines.append(f"chars count={len(char_entries)}")

    for char_id, g in char_entries:
        lines.append(
            f"char id={char_id} x={g.x} y={g.y} width={g.width} height={g.height} "
            f"xoffset={g.xoffset} yoffset={g.yoffset} xadvance={g.xadvance} page=0 chnl=15"
        )

    if kerning_entries:
        lines.append(f"kernings count={len(kerning_entries)}")
        for first_id, second_id, amount in kerning_entries:
            lines.append(f"kerning first={first_id} second={second_id} amount={amount}")

    return "\n".join(lines) + "\n"


def convert_all_fonts(
    input_dir: Path,
    output_dir: Optional[Path] = None,
    copy_png: bool = False,
    include_unicode_aliases: bool = True,
) -> int:
    """
    Discovers all .inf files in `input_dir`, maps them to their .png textures, and writes
    Godot-compatible .fnt files.
    """
    if not input_dir.exists():
        raise FileNotFoundError(f"Input directory does not exist: {input_dir}")

    inf_files = sorted(input_dir.rglob("*.inf"))
    if not inf_files:
        print(f"[WARN] No .inf files found under: {input_dir}")
        return 0

    all_pngs = build_png_index(input_dir)
    print(f"Found {len(inf_files)} .inf font file(s) and {len(all_pngs)} .png texture(s) under {input_dir}\n")

    converted_count = 0
    for inf_path in inf_files:
        font = parse_inf_file(inf_path)
        png_path = match_png_for_inf(inf_path, all_pngs, input_dir)
        scale_w, scale_h = read_png_dimensions(png_path)
        clean_name = strip_hash_suffix(inf_path.stem)

        target_dir = output_dir if output_dir is not None else inf_path.parent
        target_dir.mkdir(parents=True, exist_ok=True)

        fnt_path = target_dir / f"{inf_path.stem}.fnt"

        if copy_png:
            copied_png_path = target_dir / png_path.name
            if copied_png_path.resolve() != png_path.resolve():
                shutil.copy2(png_path, copied_png_path)
            png_rel_str = png_path.name
        else:
            png_rel_str = os.path.relpath(png_path, target_dir).replace("\\", "/")

        fnt_content = format_bmfont_fnt(
            font=font,
            face_name=clean_name,
            png_rel_path=png_rel_str,
            scale_w=scale_w,
            scale_h=scale_h,
            include_unicode_aliases=include_unicode_aliases,
        )
        fnt_path.write_text(fnt_content, encoding="utf-8", newline="\n")

        rel_inf = inf_path.relative_to(input_dir).as_posix()
        rel_png = png_path.relative_to(input_dir).as_posix()
        rel_fnt = fnt_path.relative_to(input_dir).as_posix() if output_dir is None else str(fnt_path)

        print(f"[OK] {rel_inf}")
        print(f"     -> Texture : {rel_png} ({scale_w}x{scale_h} px)")
        print(
            f"     -> Metrics : glyphs={font.glyph_count}, lineHeight={font.line_height}px, "
            f"base={font.baseline}px, maxW={font.max_glyph_width}px, "
            f"kernings={len(font.kernings)}/{font.declared_kerning_count}"
        )
        print(f"     -> Output  : {rel_fnt} (page file=\"{png_rel_str}\")\n")
        converted_count += 1

    print(f"Successfully converted {converted_count}/{len(inf_files)} .inf font files to Godot .fnt format.")
    return converted_count


def build_arg_parser() -> argparse.ArgumentParser:
    game_root = Path(__file__).resolve().parent.parent
    default_input = game_root / "GameFiles" / "PS3-EU-FullFlattened-audio_reorg-isRenamed"

    parser = argparse.ArgumentParser(
        description="Convert The Simpsons Game (PS3) .inf font files to Godot-compatible AngelCode .fnt files."
    )
    parser.add_argument(
        "--input-dir",
        "-i",
        type=Path,
        default=default_input,
        help=f"Root directory containing extracted GameFiles (default: {default_input})",
    )
    parser.add_argument(
        "--output-dir",
        "-o",
        type=Path,
        default=None,
        help="Optional directory to write all .fnt files into (defaults to alongside each .inf file).",
    )
    parser.add_argument(
        "--copy-png",
        action="store_true",
        help="Copy the matched .png texture atlas next to each generated .fnt file.",
    )
    parser.add_argument(
        "--no-unicode-aliases",
        action="store_true",
        help="Disable emitting Unicode codepoint aliases for extended chars (0xAC..0xBE) and PUA button icons.",
    )
    return parser


def main(argv: Optional[List[str]] = None) -> int:
    parser = build_arg_parser()
    args = parser.parse_args(argv)

    try:
        convert_all_fonts(
            input_dir=args.input_dir.resolve(),
            output_dir=args.output_dir.resolve() if args.output_dir else None,
            copy_png=args.copy_png,
            include_unicode_aliases=not args.no_unicode_aliases,
        )
        return 0
    except Exception as exc:
        print(f"[ERROR] {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())


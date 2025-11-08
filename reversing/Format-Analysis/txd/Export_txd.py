#!/usr/bin/env python3
"""Modular rebuild of the TXD texture exporter with identical behaviour to Export_txd."""

import argparse
import os
import re
import struct
import sys
import time
from dataclasses import dataclass
from typing import List, Optional, Tuple

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '.')))
from LegacyEnginePy.Utils.printer import print, Colours
from LegacyEnginePy.Utils import Engine_sdk as sdk  # prompt, progress, warn, error, start, end


# --- Morton Unswizzling Helpers -------------------------------------------------

def _part_bits_by_1(n: int, bits: int) -> int:
    """Legacy helper kept for parity; unused but retained for completeness."""
    mask_shifts: List[Tuple[int, int, int]] = []
    if bits > 8:
        mask_shifts.append((0x0000FF00, 0xFF0000FF, 8))
    if bits > 4:
        mask_shifts.append((0x00F000F0, 0xF00FF00F, 4))
    if bits > 2:
        mask_shifts.append((0x0C0C0C0C, 0xC30C30C3, 2))
    if bits > 1:
        mask_shifts.append((0x22222222, 0x49249249, 1))

    res = 0
    for i in range(bits):
        res |= (n & (1 << i)) << i
    return res

def morton_encode_2d(x: int, y: int) -> int:
    x = (x | (x << 8)) & 0x00FF00FF
    x = (x | (x << 4)) & 0x0F0F0F0F
    x = (x | (x << 2)) & 0x33333333
    x = (x | (x << 1)) & 0x55555555

    y = (y | (y << 8)) & 0x00FF00FF
    y = (y | (y << 4)) & 0x0F0F0F0F
    y = (y | (y << 2)) & 0x33333333
    y = (y | (y << 1)) & 0x55555555
    return x | (y << 1)

def unswizzle_data(swizzled_data: Optional[bytes], width: int, height: int, bytes_per_pixel: int) -> Optional[bytearray]:
    """Unswizzles Morton ordered data to linear ordering."""
    linear_data_size = width * height * bytes_per_pixel
    if not swizzled_data or len(swizzled_data) < linear_data_size:
        print(colour=Colours.YELLOW, message=f"      Warning: Swizzled data length ({len(swizzled_data) if swizzled_data else 0}) is less than expected ({linear_data_size}) for {width}x{height}@{bytes_per_pixel}bpp. Skipping unswizzle.")
        return None

    linear_data = bytearray(linear_data_size)

    for y_coord in range(height):
        for x_coord in range(width):
            morton_idx = morton_encode_2d(x_coord, y_coord)
            pixel_start = morton_idx * bytes_per_pixel
            if pixel_start + bytes_per_pixel > len(swizzled_data):
                continue
            linear_pixel_start = (y_coord * width + x_coord) * bytes_per_pixel
            linear_data[linear_pixel_start: linear_pixel_start + bytes_per_pixel] = swizzled_data[pixel_start: pixel_start + bytes_per_pixel]

    return linear_data

# --- Filename sanitisation ------------------------------------------------------

def sanitize_filename(name: str) -> Optional[str]:
    name = re.sub(r'[<>:"/\\|?*]', '_', name)
    name = re.sub(r'[\x00-\x1f\x7f]', '_', name)
    if not name.strip():
        return None
    return name

# --- DDS header helpers ---------------------------------------------------------

def calculate_dxt_level_size(width: int, height: int, fourcc_str: str) -> int:
    if width <= 0 or height <= 0:
        return 0
    blocks_wide = max(1, (width + 3) // 4)
    blocks_high = max(1, (height + 3) // 4)
    if fourcc_str == 'DXT1':
        bytes_per_block = 8
    elif fourcc_str in {'DXT3', 'DXT5'}:
        bytes_per_block = 16
    else:
        return 0
    return blocks_wide * blocks_high * bytes_per_block

def create_dds_header_dxt(width: int, height: int, mip_map_count_from_file: int, fourcc_str: str) -> bytes:
    DDS_MAGIC = b'DDS '
    dwSize = 124
    DDSD_CAPS = 0x1
    DDSD_HEIGHT = 0x2
    DDSD_WIDTH = 0x4
    DDSD_PIXELFORMAT = 0x1000
    DDSD_MIPMAPCOUNT = 0x20000
    DDSD_LINEARSIZE = 0x80000

    dwFlags = DDSD_CAPS | DDSD_HEIGHT | DDSD_WIDTH | DDSD_PIXELFORMAT | DDSD_LINEARSIZE
    if mip_map_count_from_file > 0:
        dwFlags |= DDSD_MIPMAPCOUNT

    dwHeight = height
    dwWidth = width
    dwPitchOrLinearSize = calculate_dxt_level_size(width, height, fourcc_str)
    dwDepth = 0
    dwMipMapCount_dds = mip_map_count_from_file if mip_map_count_from_file > 0 else 1

    pf_dwSize = 32
    DDPF_FOURCC = 0x4
    pf_dwFlags = DDPF_FOURCC
    pf_dwFourCC = fourcc_str.encode('ascii').ljust(4, b'\x00')
    pf_dwRGBBitCount = 0
    pf_dwRBitMask = 0
    pf_dwGBitMask = 0
    pf_dwBBitMask = 0
    pf_dwABitMask = 0

    DDSCAPS_TEXTURE = 0x1000
    DDSCAPS_MIPMAP = 0x400000
    DDSCAPS_COMPLEX = 0x8
    dwCaps = DDSCAPS_TEXTURE
    if dwMipMapCount_dds > 1:
        dwCaps |= DDSCAPS_MIPMAP | DDSCAPS_COMPLEX

    dwCaps2 = 0
    dwCaps3 = 0
    dwCaps4 = 0
    dwReserved2 = 0

    header_part1 = struct.pack('<4sLLLLLLL', DDS_MAGIC, dwSize, dwFlags, dwHeight, dwWidth, dwPitchOrLinearSize, dwDepth, dwMipMapCount_dds)
    header_reserved1 = b'\x00' * (11 * 4)
    header_pixelformat = struct.pack('<LL4sLLLLL', pf_dwSize, pf_dwFlags, pf_dwFourCC, pf_dwRGBBitCount, pf_dwRBitMask, pf_dwGBitMask, pf_dwBBitMask, pf_dwABitMask)
    header_caps = struct.pack('<LLLLL', dwCaps, dwCaps2, dwCaps3, dwCaps4, dwReserved2)
    return header_part1 + header_reserved1 + header_pixelformat + header_caps

def create_dds_header_rgba(width: int, height: int, mip_map_count_from_file: int) -> bytes:
    DDS_MAGIC = b'DDS '
    dwSize = 124
    DDSD_CAPS = 0x1
    DDSD_HEIGHT = 0x2
    DDSD_WIDTH = 0x4
    DDSD_PIXELFORMAT = 0x1000
    DDSD_MIPMAPCOUNT = 0x20000
    DDSD_PITCH = 0x8

    dwFlags = DDSD_CAPS | DDSD_HEIGHT | DDSD_WIDTH | DDSD_PIXELFORMAT | DDSD_PITCH
    if mip_map_count_from_file > 0:
        dwFlags |= DDSD_MIPMAPCOUNT

    dwHeight = height
    dwWidth = width
    dwPitchOrLinearSize = width * 4
    dwDepth = 0
    dwMipMapCount_dds = 1

    pf_dwSize = 32
    DDPF_RGB = 0x40
    DDPF_ALPHAPIXELS = 0x1
    pf_dwFlags = DDPF_RGB | DDPF_ALPHAPIXELS
    pf_dwFourCC = 0
    pf_dwRGBBitCount = 32
    pf_dwRBitMask = 0x000000FF
    pf_dwGBitMask = 0x0000FF00
    pf_dwBBitMask = 0x00FF0000
    pf_dwABitMask = 0xFF000000

    DDSCAPS_TEXTURE = 0x1000
    dwCaps = DDSCAPS_TEXTURE
    dwCaps2 = 0
    dwCaps3 = 0
    dwCaps4 = 0
    dwReserved2 = 0

    header_part1 = struct.pack('<4sLLLLLLL', DDS_MAGIC, dwSize, dwFlags, dwHeight, dwWidth, dwPitchOrLinearSize, dwDepth, dwMipMapCount_dds)
    header_reserved1 = b'\x00' * (11 * 4)
    header_pixelformat = struct.pack('<LLLLLLLL', pf_dwSize, pf_dwFlags, pf_dwFourCC, pf_dwRGBBitCount, pf_dwRBitMask, pf_dwGBitMask, pf_dwBBitMask, pf_dwABitMask)
    header_caps = struct.pack('<LLLLL', dwCaps, dwCaps2, dwCaps3, dwCaps4, dwReserved2)
    return header_part1 + header_reserved1 + header_pixelformat + header_caps

@dataclass
class NameInfo:
    name: str
    processed_meta: bool
    name_sig_offset_in_segment: int
    original_file_offset: int

    def mark_processed(self) -> None:
        self.processed_meta = True

@dataclass
class Segment:
    start_offset: int
    data: bytes

class TextureFormatConverter:
    """Transforms swizzled texture payloads into DDS-ready buffers."""

    def convert(
        self,
        fmt_code: int,
        width: int,
        height: int,
        mip_map_count_from_file: int,
        swizzled_base_mip_data: bytes,
        actual_mip_data_to_process_size: int,
        segment_original_start_offset: int,
        name_info: NameInfo,
    ) -> Tuple[Optional[bytes], Optional[bytearray], Optional[str], bool, int]:
        needs_unswizzle = False
        bytes_per_pixel_for_unswizzle = 0
        dds_header: Optional[bytes] = None
        output_pixel_data: Optional[bytearray] = None
        export_format_str: Optional[str] = None

        if fmt_code == 0x52:
            dds_header = create_dds_header_dxt(width, height, mip_map_count_from_file, 'DXT1')
            output_pixel_data = bytearray(swizzled_base_mip_data)
            export_format_str = "DXT1"
            print(colour=Colours.CYAN, message=f"        (Debug) DXT1 format detected. Size: {actual_mip_data_to_process_size} bytes.")
        elif fmt_code == 0x53:
            dds_header = create_dds_header_dxt(width, height, mip_map_count_from_file, 'DXT3')
            output_pixel_data = bytearray(swizzled_base_mip_data)
            export_format_str = "DXT3"
            print(colour=Colours.CYAN, message=f"        (Debug) DXT3 format detected. Size: {actual_mip_data_to_process_size} bytes.")
        elif fmt_code == 0x54:
            dds_header = create_dds_header_dxt(width, height, mip_map_count_from_file, 'DXT5')
            output_pixel_data = bytearray(swizzled_base_mip_data)
            export_format_str = "DXT5"
            print(colour=Colours.CYAN, message=f"        (Debug) DXT5 format detected. Size: {actual_mip_data_to_process_size} bytes.")
        elif fmt_code == 0x86:
            export_format_str = "RGBA8888 (from Swizzled BGRA)"
            expected_size = width * height * 4
            bytes_per_pixel_for_unswizzle = 4
            needs_unswizzle = True
            print(colour=Colours.CYAN, message=f"        (Debug) Swizzled BGRA format detected. Size: {actual_mip_data_to_process_size} bytes.")
            if actual_mip_data_to_process_size != expected_size:
                print(colour=Colours.RED, message=f"          FATAL ERROR: Data size mismatch for BGRA '{name_info.name}' (File 0x{name_info.original_file_offset:X}): expected {expected_size}, got {actual_mip_data_to_process_size}.")
                exit(1)
            linear_bgra_data = unswizzle_data(swizzled_base_mip_data, width, height, bytes_per_pixel_for_unswizzle)
            if linear_bgra_data:
                output_pixel_data = bytearray(len(linear_bgra_data))
                for pixel_index in range(0, len(linear_bgra_data), 4):
                    output_pixel_data[pixel_index + 0] = linear_bgra_data[pixel_index + 2]
                    output_pixel_data[pixel_index + 1] = linear_bgra_data[pixel_index + 1]
                    output_pixel_data[pixel_index + 2] = linear_bgra_data[pixel_index + 0]
                    output_pixel_data[pixel_index + 3] = linear_bgra_data[pixel_index + 3]
                dds_header = create_dds_header_rgba(width, height, 1)
        elif fmt_code == 0x02:
            export_format_str = "RGBA8888 (from Swizzled A8 or P8A8)"
            needs_unswizzle = True
            print(colour=Colours.CYAN, message=f"        (Debug) Swizzled A8 or P8A8 format detected. Size: {actual_mip_data_to_process_size} bytes.")
            if actual_mip_data_to_process_size == width * height * 1:
                print(colour=Colours.CYAN, message=f"        (Debug) A8 format detected. Size: {actual_mip_data_to_process_size} bytes.")
                bytes_per_pixel_for_unswizzle = 1
                linear_a8_data = unswizzle_data(swizzled_base_mip_data, width, height, bytes_per_pixel_for_unswizzle)
                if linear_a8_data:
                    output_pixel_data = bytearray(width * height * 4)
                    for pixel_index in range(width * height):
                        alpha = linear_a8_data[pixel_index]
                        output_pixel_data[pixel_index * 4 + 0] = 0
                        output_pixel_data[pixel_index * 4 + 1] = 0
                        output_pixel_data[pixel_index * 4 + 2] = 0
                        output_pixel_data[pixel_index * 4 + 3] = alpha
                    dds_header = create_dds_header_rgba(width, height, 1)
            elif actual_mip_data_to_process_size == width * height * 2:
                bytes_per_pixel_for_unswizzle = 2
                linear_p8a8_data = unswizzle_data(swizzled_base_mip_data, width, height, bytes_per_pixel_for_unswizzle)
                if linear_p8a8_data:
                    output_pixel_data = bytearray(width * height * 4)
                    print(colour=Colours.CYAN, message=f"        (Debug) P8A8/L8A8 format detected. Size: {actual_mip_data_to_process_size} bytes.")
                    for pixel_index in range(width * height):
                        p8_or_l8 = linear_p8a8_data[pixel_index * 2 + 0]
                        a8 = linear_p8a8_data[pixel_index * 2 + 1]
                        output_pixel_data[pixel_index * 4 + 0] = p8_or_l8
                        output_pixel_data[pixel_index * 4 + 1] = p8_or_l8
                        output_pixel_data[pixel_index * 4 + 2] = p8_or_l8
                        output_pixel_data[pixel_index * 4 + 3] = a8
                    dds_header = create_dds_header_rgba(width, height, 1)
            else:
                print(colour=Colours.RED, message=f"          FATAL ERROR: Data size mismatch for Format 0x02 '{name_info.name}' (File 0x{name_info.original_file_offset:X}): expected {width*height} or {width*height*2}, got {actual_mip_data_to_process_size}.")
                exit(1)
        else:
            print(colour=Colours.RED, message=f"          FATAL ERROR: Unknown or unsupported format code 0x{fmt_code:02X} for texture '{name_info.name}' (File 0x{name_info.original_file_offset:X}).")
            exit(1)

        if not (dds_header and output_pixel_data):
            return dds_header, output_pixel_data, export_format_str, needs_unswizzle, bytes_per_pixel_for_unswizzle

        return dds_header, output_pixel_data, export_format_str, needs_unswizzle, bytes_per_pixel_for_unswizzle

class SegmentScanner:
    SIG_FILE_START = b'\x16\x00\x00\x00'
    SIG_BLOCK_START = b'\x03\x00\x00\x00\x14\x00\x00\x00'
    LEN_BLOCK_MARKER = len(SIG_BLOCK_START)
    SIG_COMPOUND_END_MARKER = SIG_BLOCK_START
    TEXTURE_NAME_SIGNATURE = b'\x2D\x00\x02\x1C\x00\x00\x00\x0A'

    EOF_PREFIX = b'\x03\x00\x00\x00\x14\x00\x00\x00\x2D\x00\x02\x1C\x2F\xEA\x00\x00\x08\x00\x00\x00\x2D\x00\x02\x1C'
    EOF_SUFFIX = b'\x03\x00\x00\x00\x00\x00\x00\x00\x2D\x00\x02\x1C'
    LEN_EOF_VARIABLE_PART = 8

    def __init__(self, data: bytes, txd_filepath: str) -> None:
        self.data = data
        self.txd_filepath = txd_filepath
        self.len_eof_signature = len(self.EOF_PREFIX) + self.LEN_EOF_VARIABLE_PART + len(self.EOF_SUFFIX)

    # --- EOF pattern helpers -------------------------------------------------
    def _find_eof_pattern(self, search_start_offset: int = 0) -> int:
        current_pos = search_start_offset
        data_bytes = self.data
        while current_pos <= len(data_bytes) - self.len_eof_signature:
            prefix_pos = data_bytes.find(self.EOF_PREFIX, current_pos)
            if prefix_pos == -1:
                return -1
            if prefix_pos + self.len_eof_signature > len(data_bytes):
                current_pos = prefix_pos + 1
                continue
            expected_suffix_pos = prefix_pos + len(self.EOF_PREFIX) + self.LEN_EOF_VARIABLE_PART
            if data_bytes.startswith(self.EOF_SUFFIX, expected_suffix_pos):
                return prefix_pos
            current_pos = prefix_pos + 1
        return -1

    def _is_eof_pattern_at_pos(self, pos: int) -> bool:
        if pos < 0 or pos + self.len_eof_signature > len(self.data):
            return False
        if not self.data.startswith(self.EOF_PREFIX, pos):
            return False
        expected_suffix_start = pos + len(self.EOF_PREFIX) + self.LEN_EOF_VARIABLE_PART
        return self.data.startswith(self.EOF_SUFFIX, expected_suffix_start)

    # --- Segment discovery ---------------------------------------------------
    def collect_segments(self) -> Tuple[List[Segment], int]:
        data = self.data
        txd_filepath = self.txd_filepath

        total_textures_exported_from_file = 0

        texture_name_signature_alt_one = self.TEXTURE_NAME_SIGNATURE + b'\x00\x00\x11\x02'
        texture_name_signature_alt_two = self.TEXTURE_NAME_SIGNATURE + b'\x00\x00\x11\x06'
        texture_name_signature_alt_three = self.TEXTURE_NAME_SIGNATURE + b'\x00\x00\x33\x02'
        texture_name_signature_alt_four = self.TEXTURE_NAME_SIGNATURE + b'\x00\x00\x33\x06'
        _ = (texture_name_signature_alt_one, texture_name_signature_alt_two, texture_name_signature_alt_three, texture_name_signature_alt_four)

        eof_occurrences: List[int] = []
        search_idx = 0
        while True:
            pos = self._find_eof_pattern(search_idx)
            if pos != -1:
                eof_occurrences.append(pos)
                search_idx = pos + 1
            else:
                break
        total_EOF_SIGNATURE_patterns = len(eof_occurrences)
        print(colour=Colours.BLUE, message=f"  Found {total_EOF_SIGNATURE_patterns} occurrences of EOF_SIGNATURE pattern in the entire file.")
        if total_EOF_SIGNATURE_patterns != 1:
            if total_EOF_SIGNATURE_patterns == 0:
                print(colour=Colours.RED, message="  ERROR: EOF pattern not found in the file. This may indicate a corrupted or incomplete TXD file.")
            else:
                print(colour=Colours.RED, message=f"  ERROR: Expected 1 EOF pattern, found {total_EOF_SIGNATURE_patterns}. This may indicate a corrupted or incomplete TXD file.")
            exit(1)

        total_sig_file_start = data.count(self.SIG_FILE_START)
        print(colour=Colours.BLUE, message=f"  Found {total_sig_file_start} occurrences of sig_file_start in the entire file.")

        total_sig_block_start = data.count(self.SIG_BLOCK_START)
        print(colour=Colours.BLUE, message=f"  Found {total_sig_block_start} occurrences of sig_block_start in the entire file.")

        total_sig_compound_end_marker = data.count(self.SIG_COMPOUND_END_MARKER)
        print(colour=Colours.BLUE, message=f"  Found {total_sig_compound_end_marker} occurrences of sig_compound_end_marker in the entire file.")

        total_texture_name_signature = data.count(self.TEXTURE_NAME_SIGNATURE)
        print(colour=Colours.BLUE, message=f"  Found {total_texture_name_signature} occurrences of texture_name_signature in the entire file.")

        total_textures = 0
        if total_sig_block_start == total_sig_compound_end_marker and total_sig_block_start == total_texture_name_signature:
            total_textures = total_texture_name_signature

        data_segments_to_scan: List[Segment] = []
        search_ptr = 0

        if data.startswith(self.SIG_FILE_START):
            print(colour=Colours.CYAN, message="  File starts with sig_file_start (0x16). Processing initial segment.")
            start_of_data_after_0x16 = len(self.SIG_FILE_START)
            try:
                pos_marker = data.index(self.SIG_COMPOUND_END_MARKER, start_of_data_after_0x16)
                if self._is_eof_pattern_at_pos(pos_marker):
                    print(colour=Colours.CYAN, message=f"      0x16 segment data (offset 0x{start_of_data_after_0x16:X}) ends before EOF_SIGNATURE pattern found at 0x{pos_marker:X}.")
                    segment_data = data[start_of_data_after_0x16: pos_marker]
                    if segment_data:
                        data_segments_to_scan.append(Segment(start_of_data_after_0x16, segment_data))
                    search_ptr = len(data)
                else:
                    print(colour=Colours.CYAN, message=f"      0x16 segment data (offset 0x{start_of_data_after_0x16:X}) ends before sig_compound_end_marker at 0x{pos_marker:X}.")
                    segment_data = data[start_of_data_after_0x16: pos_marker]
                    if segment_data:
                        data_segments_to_scan.append(Segment(start_of_data_after_0x16, segment_data))
                    search_ptr = pos_marker
            except ValueError:
                pos_eof = self._find_eof_pattern(start_of_data_after_0x16)
                if pos_eof != -1:
                    print(colour=Colours.CYAN, message=f"      0x16 segment data (offset 0x{start_of_data_after_0x16:X}) ends before EOF_SIGNATURE pattern (direct find) at 0x{pos_eof:X}.")
                    segment_data = data[start_of_data_after_0x16: pos_eof]
                    if segment_data:
                        data_segments_to_scan.append(Segment(start_of_data_after_0x16, segment_data))
                    search_ptr = len(data)
                else:
                    print(colour=Colours.YELLOW, message="      Warning: No sig_compound_end_marker or EOF_SIGNATURE pattern found after 0x16 segment start. Assuming 0x16 data to end of file.")
                    segment_data = data[start_of_data_after_0x16:]
                    if segment_data:
                        data_segments_to_scan.append(Segment(start_of_data_after_0x16, segment_data))
                    search_ptr = len(data)
        else:
            print(colour=Colours.YELLOW, message="  File does not start with sig_file_start (0x16). Will scan for 0x14 blocks from beginning.")
            search_ptr = 0

        current_scan_pos = search_ptr
        while current_scan_pos < len(data):
            try:
                found_block_start_at = data.index(self.SIG_BLOCK_START, current_scan_pos)
                if self._is_eof_pattern_at_pos(found_block_start_at):
                    print(colour=Colours.CYAN, message=f"  Encountered EOF_SIGNATURE pattern at 0x{found_block_start_at:X} while searching for a 0x14 block start. Ending block scan.")
                    break
                print(colour=Colours.CYAN, message=f"  Found 0x14 block start signature at file offset 0x{found_block_start_at:X}.")
                start_of_data_after_0x14 = found_block_start_at + self.LEN_BLOCK_MARKER
                try:
                    pos_next_marker = data.index(self.SIG_COMPOUND_END_MARKER, start_of_data_after_0x14)
                    if self._is_eof_pattern_at_pos(pos_next_marker):
                        print(colour=Colours.CYAN, message=f"      0x14 block (data from 0x{start_of_data_after_0x14:X}) ends before EOF_SIGNATURE pattern (found as next marker) at 0x{pos_next_marker:X}.")
                        segment_data = data[start_of_data_after_0x14: pos_next_marker]
                        if segment_data:
                            data_segments_to_scan.append(Segment(start_of_data_after_0x14, segment_data))
                        current_scan_pos = len(data)
                    else:
                        print(colour=Colours.CYAN, message=f"      0x14 block (data from 0x{start_of_data_after_0x14:X}) ends before next sig_compound_end_marker at 0x{pos_next_marker:X}.")
                        segment_data = data[start_of_data_after_0x14: pos_next_marker]
                        if segment_data:
                            data_segments_to_scan.append(Segment(start_of_data_after_0x14, segment_data))
                        current_scan_pos = pos_next_marker
                except ValueError:
                    pos_eof = self._find_eof_pattern(start_of_data_after_0x14)
                    if pos_eof != -1:
                        print(colour=Colours.CYAN, message=f"      0x14 block (data from 0x{start_of_data_after_0x14:X}) ends before EOF_SIGNATURE pattern (direct find) at 0x{pos_eof:X}.")
                        segment_data = data[start_of_data_after_0x14: pos_eof]
                        if segment_data:
                            data_segments_to_scan.append(Segment(start_of_data_after_0x14, segment_data))
                        current_scan_pos = len(data)
                    else:
                        print(colour=Colours.YELLOW, message=f"      Warning: For 0x14 block (data from 0x{start_of_data_after_0x14:X}), no subsequent marker or EOF pattern found. Assuming data to end of file.")
                        segment_data = data[start_of_data_after_0x14:]
                        if segment_data:
                            data_segments_to_scan.append(Segment(start_of_data_after_0x14, segment_data))
                        current_scan_pos = len(data)
            except ValueError:
                print(colour=Colours.BLUE, message=f"  No more sig_block_start (or EOF pattern prefix) found after offset 0x{current_scan_pos:X}. Ending 0x14 block scan.")
                break

        if not data_segments_to_scan and data.startswith(self.SIG_FILE_START) and len(data) > 0x28:
            print(colour=Colours.YELLOW, message="  No segments found by primary rules, but file starts with 0x16. Defaulting to process from offset 0x28 (Noesis-style).")
            eof_pos_fallback = self._find_eof_pattern(0x28)
            if eof_pos_fallback != -1:
                data_segments_to_scan.append(Segment(0x28, data[0x28: eof_pos_fallback]))
            else:
                data_segments_to_scan.append(Segment(0x28, data[0x28:]))
        elif not data_segments_to_scan:
            print(colour=Colours.RED, message=f"  No data segments identified for processing in '{txd_filepath}' based on defined block signatures.")

        if not data_segments_to_scan:
            print(colour=Colours.RED, message=f"  No processable data segments ultimately found in '{txd_filepath}'.")
            return [], total_textures

        print(colour=Colours.BLUE, message=f"\n  Found {len(data_segments_to_scan)} segment(s) to process in '{txd_filepath}'.")
        return data_segments_to_scan, total_textures

class TextureSegmentProcessor:
    def __init__(self) -> None:
        self.converter = TextureFormatConverter()
        self.texture_name_signature = SegmentScanner.TEXTURE_NAME_SIGNATURE
        self.len_texture_name_signature = len(self.texture_name_signature)

    def process_segment(self, segment: Segment, output_dir: str) -> int:
        segment_data = segment.data
        segment_original_start_offset = segment.start_offset
        textures_found_in_segment = 0
        i = 0
        current_name_info: Optional[NameInfo] = None

        print(colour=Colours.CYAN, message=f"  Scanning data segment (len {len(segment_data)}) for textures using signature {self.texture_name_signature.hex()}...")

        while i < len(segment_data):
            if current_name_info and current_name_info.processed_meta:
                current_name_info = None

            if i + self.len_texture_name_signature <= len(segment_data) and segment_data[i: i + self.len_texture_name_signature] == self.texture_name_signature:
                name_sig_offset_in_segment = i
                name_str_val: Optional[str] = None
                name_string_start_offset_in_segment = name_sig_offset_in_segment + 12
                name_end_scan_in_segment = name_string_start_offset_in_segment
                print(colour=Colours.GREEN, message=f"    name_sig_offset_in_segment = 0x{name_sig_offset_in_segment:X} (file offset 0x{segment_original_start_offset + name_sig_offset_in_segment:X})")
                print(colour=Colours.GREEN, message=f"    name_string_start_offset_in_segment = 0x{name_string_start_offset_in_segment:X} (file offset 0x{segment_original_start_offset + name_string_start_offset_in_segment:X})")
                print(colour=Colours.GREEN, message=f"    name_end_scan_in_segment = 0x{name_end_scan_in_segment:X} (file offset 0x{segment_original_start_offset + name_end_scan_in_segment:X})")
                print(colour=Colours.GREEN, message=f"    Found name signature {self.texture_name_signature.hex()} at seg_offset 0x{name_sig_offset_in_segment:X} (file offset 0x{segment_original_start_offset + name_sig_offset_in_segment:X})")

                if name_string_start_offset_in_segment + 2 > len(segment_data):
                    print(colour=Colours.YELLOW, message=f"    WARNING: Found name signature {self.texture_name_signature.hex()} at seg_offset 0x{name_sig_offset_in_segment:X}, but not enough data for name string (expected at 0x{name_string_start_offset_in_segment:X}).")
                    i = name_sig_offset_in_segment + 1
                    time.sleep(5)
                    continue

                while name_end_scan_in_segment < len(segment_data) - 1 and segment_data[name_end_scan_in_segment: name_end_scan_in_segment + 2] != b'\x00\x00':
                    name_end_scan_in_segment += 1

                if name_end_scan_in_segment < len(segment_data) - 1 and segment_data[name_end_scan_in_segment: name_end_scan_in_segment + 2] == b'\x00\x00':
                    name_bytes = segment_data[name_string_start_offset_in_segment: name_end_scan_in_segment]
                    try:
                        name_str_val = name_bytes.decode('utf-8', errors='ignore').strip()
                    except UnicodeDecodeError:
                        name_str_val = name_bytes.hex()

                    if not name_str_val:
                        name_str_val = f"unnamed_texture_at_0x{segment_original_start_offset + name_sig_offset_in_segment:08X}"
                        print(colour=Colours.RED, message=f"    WARNING: Name string parsing failed for signature {self.texture_name_signature.hex()} at seg_offset 0x{name_sig_offset_in_segment:X}. Using fallback name '{name_str_val}' (sig at file 0x{segment_original_start_offset + name_sig_offset_in_segment:X}).")
                        exit(1)

                    if current_name_info and not current_name_info.processed_meta:
                        print(colour=Colours.YELLOW, message=f"    WARNING: Previous name '{current_name_info.name}' (sig at file 0x{current_name_info.original_file_offset:X}) was pending metadata but new name '{name_str_val}' was found.")
                        time.sleep(5)

                    current_name_info = NameInfo(
                        name=name_str_val,
                        processed_meta=False,
                        name_sig_offset_in_segment=name_sig_offset_in_segment,
                        original_file_offset=segment_original_start_offset + name_sig_offset_in_segment,
                    )
                    print(colour=Colours.CYAN, message=f"    Parsed name: '{current_name_info.name}' (signature {self.texture_name_signature.hex()} at seg_offset 0x{name_sig_offset_in_segment:X}, file 0x{current_name_info.original_file_offset:X})")
                    i = name_end_scan_in_segment + 2

                    first_n00_after_name_offset = -1
                    scan_ptr_for_n00 = i
                    while scan_ptr_for_n00 < len(segment_data):
                        if segment_data[scan_ptr_for_n00] != 0x00:
                            first_n00_after_name_offset = scan_ptr_for_n00
                            break
                        scan_ptr_for_n00 += 1

                    if first_n00_after_name_offset == -1:
                        print(colour=Colours.RED, message=f"      FATAL ERROR: No non-00 byte found after name '{current_name_info.name}' (File Offset: 0x{current_name_info.original_file_offset:X}) to start metadata search.")
                        exit(1)

                    known_format_codes = {0x52, 0x53, 0x54, 0x86, 0x02}
                    offset_of_01_marker = -1
                    scanned_fmt_code = -1
                    scan_ptr_for_01_fmt = first_n00_after_name_offset
                    search_limit_for_01_fmt = len(segment_data) - 1

                    while scan_ptr_for_01_fmt < search_limit_for_01_fmt:
                        if segment_data[scan_ptr_for_01_fmt] == 0x01:
                            potential_fmt_code = segment_data[scan_ptr_for_01_fmt + 1]
                            if potential_fmt_code in known_format_codes:
                                offset_of_01_marker = scan_ptr_for_01_fmt
                                scanned_fmt_code = potential_fmt_code
                                break
                        scan_ptr_for_01_fmt += 1

                    if offset_of_01_marker == -1:
                        print(colour=Colours.RED, message=f"      FATAL ERROR: Metadata signature (01 <known_fmt_code>) not found for '{current_name_info.name}' (File Offset: 0x{current_name_info.original_file_offset:X}) after first non-00 byte at seg_offset 0x{first_n00_after_name_offset:X}.")
                        exit(1)

                    meta_offset_in_segment = offset_of_01_marker - 2

                    if meta_offset_in_segment < 0:
                        print(colour=Colours.RED, message=f"      FATAL ERROR: Calculated metadata block start (seg_offset 0x{meta_offset_in_segment:X}) is negative for '{current_name_info.name}' (01_marker at 0x{offset_of_01_marker:X}). Structural issue.")
                        exit(1)

                    if not (meta_offset_in_segment + 16 <= len(segment_data)):
                        print(colour=Colours.RED, message=f"      FATAL ERROR: Not enough data for 16-byte metadata block for '{current_name_info.name}' (File Offset: 0x{current_name_info.original_file_offset:X}). Needed 16 bytes from calculated seg_offset 0x{meta_offset_in_segment:X}, segment length {len(segment_data)}.")
                        exit(1)

                    metadata_bytes = segment_data[meta_offset_in_segment: meta_offset_in_segment + 16]
                    fmt_code_from_block = metadata_bytes[3]

                    if fmt_code_from_block != scanned_fmt_code:
                        print(colour=Colours.RED, message=f"      FATAL ERROR: Format code mismatch for '{current_name_info.name}'. Scanned 01 {scanned_fmt_code:02X} (fmt_code at seg_offset 0x{offset_of_01_marker + 1:X}), but metadata_bytes[3] (at seg_offset 0x{meta_offset_in_segment + 3:X}) is {fmt_code_from_block:02X}. Alignment error.")
                        exit(1)

                    fmt_code = fmt_code_from_block
                    print(colour=Colours.CYAN, message=f"      Processing metadata for '{current_name_info.name}' (Format Code 0x{fmt_code:02X} from metadata at seg_offset 0x{meta_offset_in_segment:X})")
                    width = struct.unpack('>H', metadata_bytes[4:6])[0]
                    height = struct.unpack('>H', metadata_bytes[6:8])[0]
                    mip_map_count_from_file = metadata_bytes[9]
                    total_pixel_data_size = struct.unpack('<I', metadata_bytes[12:16])[0]
                    print(colour=Colours.CYAN, message=f"        Meta Details - W: {width}, H: {height}, MipsFromFile: {mip_map_count_from_file}, DataSize: {total_pixel_data_size}")

                    if width == 0 or height == 0:
                        if width == 0 and height == 0:
                            print(colour=Colours.YELLOW, message=f"          Skipping '{current_name_info.name}' (File Offset: 0x{current_name_info.original_file_offset:X}) due to zero dimensions (placeholder).")
                            current_name_info.mark_processed()
                            i = meta_offset_in_segment + 16
                            if i > len(segment_data):
                                i = len(segment_data)
                            time.sleep(5)
                            continue
                        else:
                            print(colour=Colours.RED, message=f"          FATAL ERROR: Invalid metadata (W:{width}, H:{height}, one is zero) for '{current_name_info.name}' (File Offset: 0x{current_name_info.original_file_offset:X}).")
                            exit(1)
                    elif total_pixel_data_size == 0:
                        print(colour=Colours.RED, message=f"          FATAL ERROR: Invalid metadata (Size:{total_pixel_data_size} with W:{width}, H:{height}) for '{current_name_info.name}' (File Offset: 0x{current_name_info.original_file_offset:X}).")
                        exit(1)

                    pixel_data_start_offset_in_segment = meta_offset_in_segment + 16
                    actual_mip_data_to_process_size = total_pixel_data_size

                    if pixel_data_start_offset_in_segment + actual_mip_data_to_process_size > len(segment_data):
                        print(colour=Colours.RED, message=f"          FATAL ERROR: Not enough pixel data for '{current_name_info.name}' (File Offset: 0x{current_name_info.original_file_offset:X}). Expected {actual_mip_data_to_process_size} from seg_offset 0x{pixel_data_start_offset_in_segment:X}, available: {len(segment_data) - pixel_data_start_offset_in_segment}.")
                        exit(1)

                    swizzled_base_mip_data = segment_data[pixel_data_start_offset_in_segment: pixel_data_start_offset_in_segment + actual_mip_data_to_process_size]

                    dds_header, output_pixel_data, export_format_str, needs_unswizzle, bytes_per_pixel_for_unswizzle = self.converter.convert(
                        fmt_code,
                        width,
                        height,
                        mip_map_count_from_file,
                        swizzled_base_mip_data,
                        actual_mip_data_to_process_size,
                        segment_original_start_offset,
                        current_name_info,
                    )

                    if not (dds_header and output_pixel_data):
                        error_reason = "pixel data processing failed"
                        if needs_unswizzle and not output_pixel_data:
                            error_reason = f"failed to unswizzle data (format 0x{fmt_code:02X}, {bytes_per_pixel_for_unswizzle}bpp)"
                            print(colour=Colours.RED, message=f"          FATAL ERROR: Failed to unswizzle data for '{current_name_info.name}' (File 0x{current_name_info.original_file_offset:X}). Reason: {error_reason}.")
                        if fmt_code in [0x52, 0x53, 0x54, 0x86, 0x02]:
                            print(colour=Colours.RED, message=f"          FATAL ERROR: Failed to generate exportable DDS data for known format 0x{fmt_code:02X} for texture '{current_name_info.name}' (File 0x{current_name_info.original_file_offset:X}). Reason: {error_reason}.")
                        else:
                            print(colour=Colours.RED, message=f"          FATAL ERROR: Unknown or unsupported format code 0x{fmt_code:02X} for texture '{current_name_info.name}' (File 0x{current_name_info.original_file_offset:X}).")
                        print(colour=Colours.RED, message=f"          FATAL ERROR: Failed to export texture '{current_name_info.name}' (File 0x{current_name_info.original_file_offset:X}).")
                        exit(1)

                    clean_name = sanitize_filename(current_name_info.name)
                    if not clean_name:
                        clean_name = f"texture_at_0x{current_name_info.original_file_offset:08X}"
                    dds_filename = os.path.join(output_dir, f"{clean_name}.dds")
                    try:
                        with open(dds_filename, 'wb') as dds_file:
                            dds_file.write(dds_header)
                            dds_file.write(output_pixel_data)
                        print(colour=Colours.CYAN, message=f"          Successfully exported: {dds_filename} (Format: {export_format_str}, {width}x{height})")
                        textures_found_in_segment += 1
                    except IOError as e:
                        print(colour=Colours.RED, message=f"          FATAL ERROR: IOError writing DDS file {dds_filename} for '{current_name_info.name}': {e}")
                        exit(1)
                    except Exception as e:  # noqa: BLE001
                        print(colour=Colours.RED, message=f"          FATAL ERROR: Unexpected error writing DDS file {dds_filename} for '{current_name_info.name}': {e}")
                        exit(1)

                    current_name_info.mark_processed()
                    i = pixel_data_start_offset_in_segment + actual_mip_data_to_process_size
                    if i > len(segment_data):
                        i = len(segment_data)
                    continue
                else:
                    print(colour=Colours.YELLOW, message=f"    WARNING: Name signature {self.texture_name_signature.hex()} at seg_offset 0x{name_sig_offset_in_segment:X} (file 0x{segment_original_start_offset + name_sig_offset_in_segment:X}) failed full name parsing (no double null found).")
                    if current_name_info and not current_name_info.processed_meta:
                        print(colour=Colours.YELLOW, message=f"      WARNING: Discarding pending name '{current_name_info.name}' (sig at file 0x{current_name_info.original_file_offset:X}) due to malformed subsequent name signature.")
                    current_name_info = None
                    i = name_sig_offset_in_segment + 1
                    time.sleep(5)
                    continue
            else:
                i += 1

        if current_name_info and not current_name_info.processed_meta:
            print(colour=Colours.YELLOW, message=f"  WARNING: End of segment reached. Pending name '{current_name_info.name}' (sig at file 0x{current_name_info.original_file_offset:X}) did not find or complete its metadata processing.")
            exit(1)
        if textures_found_in_segment == 0:
            print(colour=Colours.YELLOW, message=f"  No textures successfully exported from segment starting at file offset 0x{segment_original_start_offset:X} that met all processing criteria.")
            exit(1)
        return textures_found_in_segment

class TxdExporter:
    def __init__(self) -> None:
        self.segment_processor = TextureSegmentProcessor()

    def export_textures_from_txd(self, txd_filepath: str, output_dir_base: str) -> int:
        print(colour=Colours.CYAN, message=f"Processing TXD file: {txd_filepath}")
        try:
            with open(txd_filepath, 'rb') as f:
                data = f.read()
        except FileNotFoundError:
            print(colour=Colours.RED, message=f"Error: File not found: {txd_filepath}")
            return 0
        except Exception as e:  # noqa: BLE001
            print(colour=Colours.RED, message=f"Error reading file {txd_filepath}: {e}")
            return 0

        txd_file_name_no_ext = os.path.splitext(os.path.basename(txd_filepath))[0]
        safe_txd_folder_name = sanitize_filename(txd_file_name_no_ext)
        if not safe_txd_folder_name:
            safe_txd_folder_name = f"txd_output_{abs(hash(txd_filepath))}"

        if not os.path.exists(output_dir_base):
            try:
                os.makedirs(output_dir_base)
                print(colour=Colours.CYAN, message=f"  Created output directory: {output_dir_base}")
            except OSError as e:
                print(colour=Colours.RED, message=f"  Error: Could not create output directory {output_dir_base}: {e}. Textures from this TXD cannot be saved.")
                exit(1)

        scanner = SegmentScanner(data, txd_filepath)
        segments, total_textures = scanner.collect_segments()
        if not segments:
            return 0

        total_textures_exported_from_file = 0
        for index, segment in enumerate(segments, start=1):
            if not segment.data:
                print(colour=Colours.YELLOW, message=f"\n  Skipping zero-length segment #{index} (intended to start at file offset 0x{segment.start_offset:X}).")
                continue
            print(colour=Colours.CYAN, message=f"\n  Processing segment #{index}: data starts at file offset 0x{segment.start_offset:X}, segment length {len(segment.data)} bytes.")
            textures_in_segment = self.segment_processor.process_segment(segment, output_dir_base)
            total_textures_exported_from_file += textures_in_segment

        if total_textures_exported_from_file > 0:
            print(colour=Colours.CYAN, message=f"\nFinished processing for '{txd_filepath}'. Exported {total_textures_exported_from_file} textures to '{output_dir_base}'.")
        else:
            print(colour=Colours.RED, message=f"\nNo textures were successfully exported from any identified segments in '{txd_filepath}'.")

        if total_textures_exported_from_file != total_textures:
            print(colour=Colours.YELLOW, message=f"  WARNING: Number of raw name signatures found ({total_textures}) does not match number of textures reported as exported ({total_textures_exported_from_file}). This could be due to segmentation logic, invalid texture data, or duplicate/unused name entries.")

        return total_textures_exported_from_file

    def export_path(self, input_path_abs: str, output_dir_base_arg: Optional[str]) -> Tuple[int, int, int]:
        overall_textures_exported = 0
        files_processed_count = 0
        files_with_exports = 0

        if not os.path.exists(input_path_abs):
            print(colour=Colours.RED, message=f"Error: Input path '{input_path_abs}' does not exist.")
            exit(1)

        txd_files_to_process: List[str] = []
        if os.path.isfile(input_path_abs):
            if input_path_abs.lower().endswith('.txd'):
                txd_files_to_process.append(input_path_abs)
            else:
                print(colour=Colours.RED, message=f"Error: Input file '{input_path_abs}' is not a .txd file.")
                exit(1)
        elif os.path.isdir(input_path_abs):
            print(colour=Colours.CYAN, message=f"Scanning directory: {input_path_abs}")
            for root, _, files in os.walk(input_path_abs):
                for file in files:
                    if file.lower().endswith('.txd'):
                        txd_files_to_process.append(os.path.join(root, file))
            if not txd_files_to_process:
                print(colour=Colours.RED, message=f"No .txd files found in directory '{input_path_abs}'.")
                return overall_textures_exported, files_processed_count, files_with_exports
        else:
            print(colour=Colours.RED, message=f"Error: Input path '{input_path_abs}' is not a valid file or directory.")
            exit(1)

        if not txd_files_to_process:
            print(colour=Colours.RED, message="No .txd files to process.")
            return overall_textures_exported, files_processed_count, files_with_exports

        print(colour=Colours.CYAN, message=f"Found {len(txd_files_to_process)} .txd file(s) to process.")

        last_used_output_base_for_summary = ""
        for txd_file_path in txd_files_to_process:
            current_output_dir_base_for_txd = output_dir_base_arg
            if current_output_dir_base_for_txd is None:
                current_output_dir_base_for_txd = os.path.join(os.path.dirname(txd_file_path), f"{os.path.basename(txd_file_path).rstrip('.txd')}_txd")
            last_used_output_base_for_summary = current_output_dir_base_for_txd
            print(colour=Colours.CYAN, message=f"\n--- Processing file: {txd_file_path} ---")
            textures_in_current_file = self.export_textures_from_txd(txd_file_path, current_output_dir_base_for_txd)
            overall_textures_exported += textures_in_current_file
            files_processed_count += 1
            if textures_in_current_file > 0:
                files_with_exports += 1

        print(colour=Colours.CYAN, message="\n--- Summary ---")
        print(colour=Colours.CYAN, message=f"Attempted to process {len(txd_files_to_process)} .txd file(s).")
        if files_processed_count > 0:
            print(colour=Colours.CYAN, message=f"Files fully processed: {files_processed_count}.")
            print(colour=Colours.CYAN, message=f"Files with at least one texture exported: {files_with_exports}.")
            print(colour=Colours.CYAN, message=f"Total textures exported across all files: {overall_textures_exported}.")
            if overall_textures_exported > 0:
                if output_dir_base_arg:
                    print(colour=Colours.CYAN, message=f"Base output directory specified: '{output_dir_base_arg}' (TXD-specific subfolders created within).")
                else:
                    print(colour=Colours.CYAN, message=f"Output subdirectories created relative to each input TXD file's location (e.g., '{os.path.join(last_used_output_base_for_summary, 'examplename_txd')}').")
            if files_processed_count == 858 and overall_textures_exported != 7318:
                print(colour=Colours.YELLOW, message=f"WARNING: Only {overall_textures_exported} textures were exported. This may indicate that some textures were not processed or exported due to errors.")
        else:
            print(colour=Colours.YELLOW, message="No .txd files ended up being processed.")

        return overall_textures_exported, files_processed_count, files_with_exports

def main() -> None:
    parser = argparse.ArgumentParser(description="Extract textures from .txd files (typically Renderware TXD for GTA games).")
    parser.add_argument("input_path", help="Path to a .txd file or a directory containing .txd files.")
    parser.add_argument("-o", "--output_dir", default=None, help="Base directory to save extracted textures. Default: A subfolder named '<txd_filename>_txd' will be created in the same directory as each input .txd file.")
    args = parser.parse_args()

    input_path_abs = os.path.abspath(args.input_path)
    output_dir_base_arg = os.path.abspath(args.output_dir) if args.output_dir else None

    exporter = TxdExporter()
    exporter.export_path(input_path_abs, output_dir_base_arg)


if __name__ == '__main__':
    main()

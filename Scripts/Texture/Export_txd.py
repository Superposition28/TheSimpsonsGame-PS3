#!/usr/bin/env python3
import struct
import re
import argparse # Added for CLI argument parsing
import time

import os
import sys
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..', '..', '..', 'Utils')))
from printer import print, Colours, print_error, print_verbose, print_debug, printc

# --- Morton Unswizzling Helper ---
# The morton_encode_2d function uses a more direct bit manipulation approach.
def _part_bits_by_1(n, BITS):

    # Generic version for up to 16-bit coordinates (max texture dim 65536)
    # Max val of n will be 2^16 - 1. Result needs 32 bits.
    mask_shifts = []
    if BITS > 8: mask_shifts.append((0x0000FF00, 0xFF0000FF, 8)) # Interleave groups of 8 bits
    if BITS > 4: mask_shifts.append((0x00F000F0, 0xF00FF00F, 4)) # Interleave groups of 4 bits
    if BITS > 2: mask_shifts.append((0x0C0C0C0C, 0xC30C30C3, 2)) # Interleave groups of 2 bits
    if BITS > 1: mask_shifts.append((0x22222222, 0x49249249, 1)) # Interleave groups of 1 bit

    # Simplified version adequate for texture coordinates up to 16-bits (65536 dim)
    # Spreads BITS of n into 2*BITS positions
    res = 0
    for i in range(BITS):
        res |= (n & (1 << i)) << i
    return res

def morton_encode_2d(x, y):
    # Interleaves the bits of x and y.
    # Using a common bit manipulation pattern for this:
    # (Assumes x and y are <= 16-bit integers)
    x = (x | (x << 8)) & 0x00FF00FF
    x = (x | (x << 4)) & 0x0F0F0F0F
    x = (x | (x << 2)) & 0x33333333
    x = (x | (x << 1)) & 0x55555555

    y = (y | (y << 8)) & 0x00FF00FF
    y = (y | (y << 4)) & 0x0F0F0F0F
    y = (y | (y << 2)) & 0x33333333
    y = (y | (y << 1)) & 0x55555555
    return x | (y << 1)

def unswizzle_data(swizzled_data, width, height, bytes_per_pixel):
    """Unswizzles Morton ordered data to linear."""
    linear_data_size = width * height * bytes_per_pixel
    if not swizzled_data or len(swizzled_data) < linear_data_size : # Should be exactly linear_data_size for base mip
        print(Colours.YELLOW, f"      Warning: Swizzled data length ({len(swizzled_data)}) is less than expected ({linear_data_size}) for {width}x{height}@{bytes_per_pixel}bpp. Skipping unswizzle.")
        return None

    linear_data = bytearray(linear_data_size)

    for y_coord in range(height):
        for x_coord in range(width):
            morton_idx = morton_encode_2d(x_coord, y_coord)

            if (morton_idx * bytes_per_pixel) + bytes_per_pixel > len(swizzled_data):
                # This case should ideally not be hit if dimensions and bpp are correct for swizzled_data length
                #print(Colours.YELLOW, f"      Warning: Morton index {morton_idx} out of bounds for swizzled data. ({x_coord},{y_coord})")
                #time.sleep(5)
                continue # Or handle error appropriately

            swizzled_pixel_start = morton_idx * bytes_per_pixel
            linear_pixel_start = (y_coord * width + x_coord) * bytes_per_pixel

            linear_data[linear_pixel_start : linear_pixel_start + bytes_per_pixel] = \
                swizzled_data[swizzled_pixel_start : swizzled_pixel_start + bytes_per_pixel]

    return linear_data

# --- End Morton Unswizzling ---

def sanitize_filename(name):
    name = re.sub(r'[<>:"/\\|?*]', '_', name)
    name = re.sub(r'[\x00-\x1f\x7f]', '_', name)
    if not name.strip():
        return None
    return name

def calculate_dxt_level_size(width, height, fourcc_str):
    if width <= 0 or height <= 0:
        return 0
    blocks_wide = max(1, (width + 3) // 4)
    blocks_high = max(1, (height + 3) // 4)
    bytes_per_block = 0
    if fourcc_str == 'DXT1':
        bytes_per_block = 8
    elif fourcc_str == 'DXT3' or fourcc_str == 'DXT5':
        bytes_per_block = 16
    else:
        return 0
    return blocks_wide * blocks_high * bytes_per_block

def create_dds_header_dxt(width, height, mip_map_count_from_file, fourcc_str):
    DDS_MAGIC = b'DDS '
    dwSize = 124
    DDSD_CAPS = 0x1; DDSD_HEIGHT = 0x2; DDSD_WIDTH = 0x4
    DDSD_PIXELFORMAT = 0x1000; DDSD_MIPMAPCOUNT = 0x20000; DDSD_LINEARSIZE = 0x80000

    dwFlags = DDSD_CAPS | DDSD_HEIGHT | DDSD_WIDTH | DDSD_PIXELFORMAT | DDSD_LINEARSIZE
    if mip_map_count_from_file > 0:
        dwFlags |= DDSD_MIPMAPCOUNT

    dwHeight = height; dwWidth = width
    dwPitchOrLinearSize = calculate_dxt_level_size(width, height, fourcc_str)
    dwDepth = 0
    dwMipMapCount_dds = mip_map_count_from_file if mip_map_count_from_file > 0 else 1

    pf_dwSize = 32; DDPF_FOURCC = 0x4; pf_dwFlags = DDPF_FOURCC
    pf_dwFourCC = fourcc_str.encode('ascii').ljust(4, b'\x00')
    pf_dwRGBBitCount = 0; pf_dwRBitMask = 0; pf_dwGBitMask = 0; pf_dwBBitMask = 0; pf_dwABitMask = 0

    DDSCAPS_TEXTURE = 0x1000; DDSCAPS_MIPMAP = 0x400000; DDSCAPS_COMPLEX = 0x8
    dwCaps = DDSCAPS_TEXTURE
    if dwMipMapCount_dds > 1:
        dwCaps |= DDSCAPS_MIPMAP | DDSCAPS_COMPLEX

    dwCaps2 = 0; dwCaps3 = 0; dwCaps4 = 0; dwReserved2 = 0

    header_part1 = struct.pack('<4sLLLLLLL', DDS_MAGIC, dwSize, dwFlags, dwHeight, dwWidth, dwPitchOrLinearSize, dwDepth, dwMipMapCount_dds)
    header_reserved1 = b'\x00' * (11 * 4)
    header_pixelformat = struct.pack('<LL4sLLLLL', pf_dwSize, pf_dwFlags, pf_dwFourCC, pf_dwRGBBitCount, pf_dwRBitMask, pf_dwGBitMask, pf_dwBBitMask, pf_dwABitMask)
    header_caps = struct.pack('<LLLLL', dwCaps, dwCaps2, dwCaps3, dwCaps4, dwReserved2)
    return header_part1 + header_reserved1 + header_pixelformat + header_caps

def create_dds_header_rgba(width, height, mip_map_count_from_file): # Assuming RGBA8888
    DDS_MAGIC = b'DDS '
    dwSize = 124
    DDSD_CAPS = 0x1; DDSD_HEIGHT = 0x2; DDSD_WIDTH = 0x4
    DDSD_PIXELFORMAT = 0x1000; DDSD_MIPMAPCOUNT = 0x20000; DDSD_PITCH = 0x8 # For uncompressed

    dwFlags = DDSD_CAPS | DDSD_HEIGHT | DDSD_WIDTH | DDSD_PIXELFORMAT | DDSD_PITCH
    if mip_map_count_from_file > 0: # For raw, we are only doing base mip, so this will be 0 or 1
        dwFlags |= DDSD_MIPMAPCOUNT

    dwHeight = height; dwWidth = width
    dwPitchOrLinearSize = width * 4 # Bytes per scanline for RGBA8888
    dwDepth = 0
    # For raw formats, we're currently only extracting the base mip
    dwMipMapCount_dds = 1 #mip_map_count_from_file if mip_map_count_from_file > 0 else 1

    pf_dwSize = 32
    DDPF_RGB = 0x40; DDPF_ALPHAPIXELS = 0x1
    pf_dwFlags = DDPF_RGB | DDPF_ALPHAPIXELS
    pf_dwFourCC = 0 # Not FourCC for uncompressed
    pf_dwRGBBitCount = 32
    # Standard RGBA (bytes R,G,B,A) order in memory for many tools
    pf_dwRBitMask = 0x000000FF
    pf_dwGBitMask = 0x0000FF00
    pf_dwBBitMask = 0x00FF0000
    pf_dwABitMask = 0xFF000000

    DDSCAPS_TEXTURE = 0x1000; DDSCAPS_MIPMAP = 0x400000; DDSCAPS_COMPLEX = 0x8
    dwCaps = DDSCAPS_TEXTURE
    # if dwMipMapCount_dds > 1: # Since we only save base mip for raw, this won't be hit
    #     dwCaps |= DDSCAPS_MIPMAP | DDSCAPS_COMPLEX

    dwCaps2 = 0; dwCaps3 = 0; dwCaps4 = 0; dwReserved2 = 0

    header_part1 = struct.pack('<4sLLLLLLL', DDS_MAGIC, dwSize, dwFlags, dwHeight, dwWidth, dwPitchOrLinearSize, dwDepth, dwMipMapCount_dds)
    header_reserved1 = b'\x00' * (11 * 4)
    header_pixelformat = struct.pack(
        '<LLLLLLLL', # Corrected format string: 8 unsigned longs
        pf_dwSize, pf_dwFlags, pf_dwFourCC, pf_dwRGBBitCount,
        pf_dwRBitMask, pf_dwGBitMask, pf_dwBBitMask, pf_dwABitMask
    )
    header_caps = struct.pack('<LLLLL', dwCaps, dwCaps2, dwCaps3, dwCaps4, dwReserved2)
    return header_part1 + header_reserved1 + header_pixelformat + header_caps

def process_texture_data_segment(segment_data, segment_original_start_offset, output_dir):
    textures_found_in_segment = 0
    i = 0
    current_name_info = None
    # Define the new name signature
    texture_name_signature = b'\x2D\x00\x02\x1C\x00\x00\x00\x0A'
    len_texture_name_signature = len(texture_name_signature)

    print(Colours.CYAN, f"  Scanning data segment (len {len(segment_data)}) for textures using signature {texture_name_signature.hex()}...")

    # before extracting data
    segments_processed_successfully = 0

    while i < len(segment_data):
        # Clear fully processed name info before looking for a new name or advancing
        if current_name_info and current_name_info.get('processed_meta', False):
            current_name_info = None

        # --- 1. TRY TO PARSE A NAME ---
        # Check for the new, longer NAME signature
        if i + len_texture_name_signature <= len(segment_data) and \
           segment_data[i : i + len_texture_name_signature] == texture_name_signature:

            name_sig_offset_in_segment = i
            name_str_val = None
            # The name string is assumed to start 8 bytes AFTER the beginning of the (now 8-byte) signature.
            # This interpretation means the '00 00 00 0A' part effectively acts as a header within the signature,
            # and the name string follows a similar relative offset as before from that sub-part.
            # Or, simply, the rule is "+8 from start of identified signature block".
            name_string_start_offset_in_segment = name_sig_offset_in_segment + 12
            name_end_scan_in_segment = name_string_start_offset_in_segment
            print(Colours.GREEN, f"    name_sig_offset_in_segment = 0x{name_sig_offset_in_segment:X} (file offset 0x{segment_original_start_offset + name_sig_offset_in_segment:X})")
            print(Colours.GREEN, f"    name_string_start_offset_in_segment = 0x{name_string_start_offset_in_segment:X} (file offset 0x{segment_original_start_offset + name_string_start_offset_in_segment:X})")
            print(Colours.GREEN, f"    name_end_scan_in_segment = 0x{name_end_scan_in_segment:X} (file offset 0x{segment_original_start_offset + name_end_scan_in_segment:X})")
            print(Colours.GREEN, f"    Found name signature {texture_name_signature.hex()} at seg_offset 0x{name_sig_offset_in_segment:X} (file offset 0x{segment_original_start_offset + name_sig_offset_in_segment:X})")

            # Ensure there's space for name string and its null terminators after the +8 offset
            if name_string_start_offset_in_segment + 2 > len(segment_data): # Need at least 2 bytes for \x00\x00
                # This implies the signature was found, but the segment ends before a name string could exist.
                print(Colours.YELLOW, f"    WARNING: Found name signature {texture_name_signature.hex()} at seg_offset 0x{name_sig_offset_in_segment:X}, "
                      f"but not enough data for name string (expected at 0x{name_string_start_offset_in_segment:X}).")
                i = name_sig_offset_in_segment + 1 # Advance past the start of this problematic signature
                time.sleep(5)
                continue

            while name_end_scan_in_segment < len(segment_data) - 1 and \
                  segment_data[name_end_scan_in_segment : name_end_scan_in_segment+2] != b'\x00\x00':
                name_end_scan_in_segment += 1

            if name_end_scan_in_segment < len(segment_data) - 1 and \
               segment_data[name_end_scan_in_segment : name_end_scan_in_segment+2] == b'\x00\x00':
                name_bytes = segment_data[name_string_start_offset_in_segment : name_end_scan_in_segment]
                try: name_str_val = name_bytes.decode('utf-8', errors='ignore').strip()
                except UnicodeDecodeError: name_str_val = name_bytes.hex()

                if not name_str_val:
                    name_str_val = f"unnamed_texture_at_0x{segment_original_start_offset + name_sig_offset_in_segment:08X}"
                    print(Colours.RED, f"    WARNING: Name string parsing failed for signature {texture_name_signature.hex()} at seg_offset 0x{name_sig_offset_in_segment:X}. "
                          f"Using fallback name '{name_str_val}' (sig at file 0x{segment_original_start_offset + name_sig_offset_in_segment:X}).")
                    exit(1)

                if current_name_info and not current_name_info['processed_meta']:
                    print(Colours.YELLOW, f"    WARNING: Previous name '{current_name_info['name']}' (sig at file 0x{current_name_info['original_file_offset']:X}) "
                          f"was pending metadata but new name '{name_str_val}' was found.")
                    time.sleep(5)

                current_name_info = {
                    'name': name_str_val,
                    'processed_meta': False,
                    'name_sig_offset_in_segment': name_sig_offset_in_segment,
                    'original_file_offset': segment_original_start_offset + name_sig_offset_in_segment
                }
                print(Colours.CYAN, f"    Parsed name: '{current_name_info['name']}' (signature {texture_name_signature.hex()} at seg_offset 0x{name_sig_offset_in_segment:X}, file 0x{current_name_info['original_file_offset']:X})")
                i = name_end_scan_in_segment + 2

                # --- Metadata Search Step 1: Find first non-00 byte after name ---
                first_n00_after_name_offset = -1
                scan_ptr_for_n00 = i
                while scan_ptr_for_n00 < len(segment_data):
                    if segment_data[scan_ptr_for_n00] != 0x00:
                        first_n00_after_name_offset = scan_ptr_for_n00
                        break
                    scan_ptr_for_n00 += 1

                if first_n00_after_name_offset == -1:
                    print(Colours.RED, f"      FATAL ERROR: No non-00 byte found after name '{current_name_info['name']}' (File Offset: 0x{current_name_info['original_file_offset']:X}) to start metadata search.")
                    exit(1)

                # print(Colours.CYAN, f"      (Debug) First non-00 byte after name found at seg_offset 0x{first_n00_after_name_offset:X}.") # Optional Debug

                # --- Metadata Search Step 2: From first_n00_after_name_offset, scan for "01 <known_fmt_code>" ---
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
                            # print(Colours.CYAN, f"      (Debug) Found metadata signature 0x01 {scanned_fmt_code:02X} at seg_offset 0x{offset_of_01_marker:X}.") # Optional Debug
                            break
                    scan_ptr_for_01_fmt += 1

                if offset_of_01_marker == -1:
                    print(Colours.RED, f"      FATAL ERROR: Metadata signature (01 <known_fmt_code>) not found for '{current_name_info['name']}' (File Offset: 0x{current_name_info['original_file_offset']:X}) "
                          f"after first non-00 byte at seg_offset 0x{first_n00_after_name_offset:X}.")
                    exit(1)

                # --- Metadata Search Step 3: Calculate meta_offset_in_segment ---
                meta_offset_in_segment = offset_of_01_marker - 2

                if meta_offset_in_segment < 0:
                    print(Colours.RED, f"      FATAL ERROR: Calculated metadata block start (seg_offset 0x{meta_offset_in_segment:X}) is negative for '{current_name_info['name']}' "
                          f"(01_marker at 0x{offset_of_01_marker:X}). Structural issue.")
                    exit(1)

                if not (meta_offset_in_segment + 16 <= len(segment_data)):
                    print(Colours.RED, f"      FATAL ERROR: Not enough data for 16-byte metadata block for '{current_name_info['name']}' (File Offset: 0x{current_name_info['original_file_offset']:X}). "
                          f"Needed 16 bytes from calculated seg_offset 0x{meta_offset_in_segment:X}, segment length {len(segment_data)}.")
                    exit(1)

                metadata_bytes = segment_data[meta_offset_in_segment : meta_offset_in_segment + 16]
                fmt_code_from_block = metadata_bytes[3]

                if fmt_code_from_block != scanned_fmt_code:
                    print(Colours.RED, f"      FATAL ERROR: Format code mismatch for '{current_name_info['name']}'. Scanned 01 {scanned_fmt_code:02X} (fmt_code at seg_offset 0x{offset_of_01_marker + 1:X}), "
                          f"but metadata_bytes[3] (at seg_offset 0x{meta_offset_in_segment + 3:X}) is {fmt_code_from_block:02X}. Alignment error.")
                    exit(1)

                fmt_code = fmt_code_from_block
                # print(Colours.CYAN, f"      (Debug) metadata_bytes = {metadata_bytes.hex()}") # Optional Debug
                print(Colours.CYAN, f"      Processing metadata for '{current_name_info['name']}' (Format Code 0x{fmt_code:02X} from metadata at seg_offset 0x{meta_offset_in_segment:X})")
                width = struct.unpack('>H', metadata_bytes[4:6])[0]
                height = struct.unpack('>H', metadata_bytes[6:8])[0]
                mip_map_count_from_file = metadata_bytes[9]
                total_pixel_data_size = struct.unpack('<I', metadata_bytes[12:16])[0]
                print(Colours.CYAN, f"        Meta Details - W: {width}, H: {height}, MipsFromFile: {mip_map_count_from_file}, DataSize: {total_pixel_data_size}")

                if width == 0 or height == 0:
                    if width == 0 and height == 0 :
                        print(Colours.YELLOW, f"          Skipping '{current_name_info['name']}' (File Offset: 0x{current_name_info['original_file_offset']:X}) due to zero dimensions (placeholder).")
                        current_name_info['processed_meta'] = True
                        i = meta_offset_in_segment + 16
                        if i > len(segment_data): i = len(segment_data)
                        time.sleep(5)
                        continue
                    else:
                        print(Colours.RED, f"          FATAL ERROR: Invalid metadata (W:{width}, H:{height}, one is zero) for '{current_name_info['name']}' (File Offset: 0x{current_name_info['original_file_offset']:X}).")
                        exit(1)
                elif total_pixel_data_size == 0:
                    print(Colours.RED, f"          FATAL ERROR: Invalid metadata (Size:{total_pixel_data_size} with W:{width}, H:{height}) for '{current_name_info['name']}' (File Offset: 0x{current_name_info['original_file_offset']:X}).")
                    exit(1)

                pixel_data_start_offset_in_segment = meta_offset_in_segment + 16
                actual_mip_data_to_process_size = total_pixel_data_size

                if pixel_data_start_offset_in_segment + actual_mip_data_to_process_size > len(segment_data):
                    print(Colours.RED, f"          FATAL ERROR: Not enough pixel data for '{current_name_info['name']}' (File Offset: 0x{current_name_info['original_file_offset']:X}). "
                          f"Expected {actual_mip_data_to_process_size} from seg_offset 0x{pixel_data_start_offset_in_segment:X}, available: {len(segment_data) - pixel_data_start_offset_in_segment}.")
                    exit(1)

                swizzled_base_mip_data = segment_data[pixel_data_start_offset_in_segment :
                                                      pixel_data_start_offset_in_segment + actual_mip_data_to_process_size]
                dds_header, output_pixel_data, export_format_str = None, None, ""
                needs_unswizzle = False
                bytes_per_pixel_for_unswizzle = 0

                # --- FMT CODE SPECIFIC LOGIC ---
                if fmt_code == 0x52: # DXT1
                    dds_header = create_dds_header_dxt(width, height, mip_map_count_from_file, 'DXT1')
                    output_pixel_data = swizzled_base_mip_data; export_format_str = "DXT1"
                    print(Colours.CYAN, f"        (Debug) DXT1 format detected. Size: {actual_mip_data_to_process_size} bytes.")
                elif fmt_code == 0x53: # DXT3
                    dds_header = create_dds_header_dxt(width, height, mip_map_count_from_file, 'DXT3')
                    output_pixel_data = swizzled_base_mip_data; export_format_str = "DXT3"
                    print(Colours.CYAN, f"        (Debug) DXT3 format detected. Size: {actual_mip_data_to_process_size} bytes.")
                elif fmt_code == 0x54: # DXT5
                    dds_header = create_dds_header_dxt(width, height, mip_map_count_from_file, 'DXT5')
                    output_pixel_data = swizzled_base_mip_data; export_format_str = "DXT5"
                    print(Colours.CYAN, f"        (Debug) DXT5 format detected. Size: {actual_mip_data_to_process_size} bytes.")
                elif fmt_code == 0x86: # Morton swizzled BGRA8888
                    export_format_str = "RGBA8888 (from Swizzled BGRA)"
                    expected_size = width * height * 4
                    bytes_per_pixel_for_unswizzle = 4
                    needs_unswizzle = True
                    print(Colours.CYAN, f"        (Debug) Swizzled BGRA format detected. Size: {actual_mip_data_to_process_size} bytes.")
                    if actual_mip_data_to_process_size != expected_size:
                        print(Colours.RED, f"          FATAL ERROR: Data size mismatch for BGRA '{current_name_info['name']}' (File 0x{current_name_info['original_file_offset']:X}): expected {expected_size}, got {actual_mip_data_to_process_size}.")
                        exit(1)
                    linear_bgra_data = unswizzle_data(swizzled_base_mip_data, width, height, bytes_per_pixel_for_unswizzle)
                    if linear_bgra_data:
                        output_pixel_data = bytearray(len(linear_bgra_data))
                        for p_idx in range(0, len(linear_bgra_data), 4): # BGRA to RGBA
                            output_pixel_data[p_idx+0] = linear_bgra_data[p_idx+2]; output_pixel_data[p_idx+1] = linear_bgra_data[p_idx+1]
                            output_pixel_data[p_idx+2] = linear_bgra_data[p_idx+0]; output_pixel_data[p_idx+3] = linear_bgra_data[p_idx+3]
                        dds_header = create_dds_header_rgba(width, height, 1)
                elif fmt_code == 0x02: # Morton swizzled A8 or P8A8/L8A8
                    export_format_str = "RGBA8888 (from Swizzled A8 or P8A8)"
                    needs_unswizzle = True
                    print(Colours.CYAN, f"        (Debug) Swizzled A8 or P8A8 format detected. Size: {actual_mip_data_to_process_size} bytes.")
                    if actual_mip_data_to_process_size == width * height * 1: # A8
                        print(Colours.CYAN, f"        (Debug) A8 format detected. Size: {actual_mip_data_to_process_size} bytes.")
                        bytes_per_pixel_for_unswizzle = 1
                        linear_a8_data = unswizzle_data(swizzled_base_mip_data, width, height, bytes_per_pixel_for_unswizzle)
                        if linear_a8_data:
                            output_pixel_data = bytearray(width * height * 4)
                            for p_idx in range(width * height):
                                alpha = linear_a8_data[p_idx]
                                output_pixel_data[p_idx*4+0]=0; output_pixel_data[p_idx*4+1]=0
                                output_pixel_data[p_idx*4+2]=0; output_pixel_data[p_idx*4+3]=alpha
                            dds_header = create_dds_header_rgba(width, height, 1)
                    elif actual_mip_data_to_process_size == width * height * 2: # P8A8/L8A8
                        bytes_per_pixel_for_unswizzle = 2
                        linear_p8a8_data = unswizzle_data(swizzled_base_mip_data, width, height, bytes_per_pixel_for_unswizzle)
                        if linear_p8a8_data:
                            output_pixel_data = bytearray(width * height * 4)
                            print(Colours.CYAN, f"        (Debug) P8A8/L8A8 format detected. Size: {actual_mip_data_to_process_size} bytes.")
                            for p_idx in range(width * height):
                                p8_or_l8, a8 = linear_p8a8_data[p_idx*2+0], linear_p8a8_data[p_idx*2+1]
                                output_pixel_data[p_idx*4+0]=p8_or_l8; output_pixel_data[p_idx*4+1]=p8_or_l8
                                output_pixel_data[p_idx*4+2]=p8_or_l8; output_pixel_data[p_idx*4+3]=a8
                            dds_header = create_dds_header_rgba(width, height, 1)
                    else:
                        print(Colours.RED, f"          FATAL ERROR: Data size mismatch for Format 0x02 '{current_name_info['name']}' (File 0x{current_name_info['original_file_offset']:X}): expected {width*height} or {width*height*2}, got {actual_mip_data_to_process_size}.")
                        exit(1)
                else:
                    print(Colours.RED, f"          FATAL ERROR: Unknown or unsupported format code 0x{fmt_code:02X} for texture '{current_name_info['name']}' (File 0x{current_name_info['original_file_offset']:X}).")
                    exit(1)

                if not (dds_header and output_pixel_data):
                    error_reason = "pixel data processing failed"
                    if needs_unswizzle and not output_pixel_data:
                        error_reason = f"failed to unswizzle data (format 0x{fmt_code:02X}, {bytes_per_pixel_for_unswizzle}bpp)"
                        print(Colours.RED, f"          FATAL ERROR: Failed to unswizzle data for '{current_name_info['name']}' (File 0x{current_name_info['original_file_offset']:X}). Reason: {error_reason}.")
                    if fmt_code in [0x52,0x53,0x54,0x86,0x02]:
                        print(Colours.RED, f"          FATAL ERROR: Failed to generate exportable DDS data for known format 0x{fmt_code:02X} for texture '{current_name_info['name']}' (File 0x{current_name_info['original_file_offset']:X}). Reason: {error_reason}.")
                    else:
                        print(Colours.RED, f"          FATAL ERROR: Unknown or unsupported format code 0x{fmt_code:02X} for texture '{current_name_info['name']}' (File 0x{current_name_info['original_file_offset']:X}).")
                    print(Colours.RED, f"          FATAL ERROR: Failed to export texture '{current_name_info['name']}' (File 0x{current_name_info['original_file_offset']:X}).")
                    exit(1)

                clean_name = sanitize_filename(current_name_info['name'])
                if not clean_name:
                    clean_name = f"texture_at_0x{current_name_info['original_file_offset']:08X}"
                dds_filename = os.path.join(output_dir, f"{clean_name}.dds")
                try:
                    with open(dds_filename, "wb") as dds_file:
                        dds_file.write(dds_header); dds_file.write(output_pixel_data)
                    print(Colours.CYAN, f"          Successfully exported: {dds_filename} (Format: {export_format_str}, {width}x{height})")
                    textures_found_in_segment += 1
                except IOError as e:
                    print(Colours.RED, f"          FATAL ERROR: IOError writing DDS file {dds_filename} for '{current_name_info['name']}': {e}")
                    exit(1)
                except Exception as e:
                    print(Colours.RED, f"          FATAL ERROR: Unexpected error writing DDS file {dds_filename} for '{current_name_info['name']}': {e}")
                    exit(1)

                current_name_info['processed_meta'] = True
                i = pixel_data_start_offset_in_segment + actual_mip_data_to_process_size
                if i > len(segment_data): i = len(segment_data)
                continue
            else: # Name signature found, but name string parsing failed (no double null)
                print(Colours.YELLOW, f"    WARNING: Name signature {texture_name_signature.hex()} at seg_offset 0x{name_sig_offset_in_segment:X} (file 0x{segment_original_start_offset + name_sig_offset_in_segment:X}) "
                      f"failed full name parsing (no double null found).")
                if current_name_info and not current_name_info['processed_meta']:
                    print(Colours.YELLOW, f"      WARNING: Discarding pending name '{current_name_info['name']}' (sig at file 0x{current_name_info['original_file_offset']:X}) due to malformed subsequent name signature.")
                current_name_info = None
                i = name_sig_offset_in_segment + 1
                time.sleep(5)
                continue
        else: # No name signature at current i, just advance
            i += 1
        # Loop continues

    if current_name_info and not current_name_info['processed_meta']:
        print(Colours.YELLOW, f"  WARNING: End of segment reached. Pending name '{current_name_info['name']}' (sig at file 0x{current_name_info['original_file_offset']:X}) did not find or complete its metadata processing.")
        #time.sleep(5)
        exit(1)
    if textures_found_in_segment == 0:
        print(Colours.YELLOW, f"  No textures successfully exported from segment starting at file offset 0x{segment_original_start_offset:X} that met all processing criteria.")
        #time.sleep(5)
        exit(1)
    return textures_found_in_segment

def export_textures_from_txd(txd_filepath, output_dir_base):
    print(Colours.CYAN, f"Processing TXD file: {txd_filepath}")
    try:
        with open(txd_filepath, "rb") as f: data = f.read()
    except FileNotFoundError:
        print(Colours.RED, f"Error: File not found: {txd_filepath}")
        return 0
    except Exception as e:
        print(Colours.RED, f"Error reading file {txd_filepath}: {e}")
        return 0

    txd_file_name_no_ext = os.path.splitext(os.path.basename(txd_filepath))[0]
    safe_txd_folder_name = sanitize_filename(txd_file_name_no_ext)
    if not safe_txd_folder_name:
        safe_txd_folder_name = f"txd_output_{abs(hash(txd_filepath))}" # Unique fallback

    if not os.path.exists(output_dir_base):
        try:
            os.makedirs(output_dir_base)
            print(Colours.CYAN, f"  Created output directory: {output_dir_base}") # Should this be CYAN or BLUE for success?
        except OSError as e:
            print(Colours.RED, f"  Error: Could not create output directory {output_dir_base}: {e}. Textures from this TXD cannot be saved.")
            exit(1)


    # --- START: Define EOF pattern components ---
    EOF_PREFIX = b'\x03\x00\x00\x00\x14\x00\x00\x00\x2D\x00\x02\x1C\x2F\xEA\x00\x00\x08\x00\x00\x00\x2D\x00\x02\x1C'
    EOF_SUFFIX = b'\x03\x00\x00\x00\x00\x00\x00\x00\x2D\x00\x02\x1C'
    LEN_EOF_VARIABLE_PART = 8
    LEN_EOF_PREFIX = len(EOF_PREFIX)
    LEN_EOF_SUFFIX = len(EOF_SUFFIX)
    # This variable name is kept for consistency with the original code's usage for total length
    len_eof_signature = LEN_EOF_PREFIX + LEN_EOF_VARIABLE_PART + LEN_EOF_SUFFIX
    # --- END: Define EOF pattern components ---

    # --- START: Helper functions for EOF pattern ---
    def _find_eof_pattern(data_bytes, search_start_offset=0):
        """Finds the start of the EOF pattern in data_bytes from search_start_offset."""
        current_pos = search_start_offset
        # Ensure there's enough space for the entire EOF pattern from current_pos
        while current_pos <= len(data_bytes) - len_eof_signature:
            prefix_pos = data_bytes.find(EOF_PREFIX, current_pos)
            
            if prefix_pos == -1:
                return -1 # Prefix not found in the rest of the data

            # Check if there's enough data from prefix_pos for the full EOF signature
            if prefix_pos + len_eof_signature > len(data_bytes):
                # This prefix occurrence is too close to the end to form a full EOF pattern.
                # Advance search beyond this found prefix.
                current_pos = prefix_pos + 1
                continue

            # Check for the suffix at the expected position
            expected_suffix_pos = prefix_pos + LEN_EOF_PREFIX + LEN_EOF_VARIABLE_PART
            if data_bytes.startswith(EOF_SUFFIX, expected_suffix_pos):
                return prefix_pos # Found the full EOF pattern

            # Prefix found, but suffix didn't match. Continue search after this prefix.
            current_pos = prefix_pos + 1
            
        return -1 # Reached end of data or not enough space without finding the pattern

    def _is_eof_pattern_at_pos(data_bytes, pos):
        """Checks if the EOF pattern starts exactly at 'pos' in data_bytes."""
        if pos < 0 or pos + len_eof_signature > len(data_bytes):
            return False
        # Check prefix
        if not data_bytes.startswith(EOF_PREFIX, pos):
            return False
        
        # Check suffix
        expected_suffix_start = pos + LEN_EOF_PREFIX + LEN_EOF_VARIABLE_PART
        # The check `pos + len_eof_signature > len(data_bytes)` already ensures suffix fits
        if data_bytes.startswith(EOF_SUFFIX, expected_suffix_start):
            return True
            
        return False
    # --- END: Helper functions for EOF pattern ---

    total_textures_exported_from_file = 0

    # Marker definitions
    sig_file_start = b'\x16\x00\x00\x00'
    sig_block_start = b'\x03\x00\x00\x00\x14\x00\x00\x00' # This is also the start of EOF_PREFIX
    len_block_marker = len(sig_block_start)
    sig_compound_end_marker = sig_block_start # They are the same

    texture_name_signature = b'\x2D\x00\x02\x1C\x00\x00\x00\x0A'

    # Unique 4 four-byte sequences found after texture_name_signature
    texture_name_signature_alt_one = texture_name_signature + b'\x00\x00\x11\x02'
    texture_name_signature_alt_two = texture_name_signature + b'\x00\x00\x11\x06'
    texture_name_signature_alt_three = texture_name_signature + b'\x00\x00\x33\x02'
    texture_name_signature_alt_four = texture_name_signature + b'\x00\x00\x33\x06'
    # Removed: len_eof_signature = len(EOF_SIGNATURE) as EOF_SIGNATURE is not defined
    # and len_eof_signature is correctly defined above from pattern components.

    # --- START: Count EOF_SIGNATURE pattern in the entire file ---
    eof_occurrences = []
    search_idx = 0
    while True:
        pos = _find_eof_pattern(data, search_idx)
        if pos != -1:
            eof_occurrences.append(pos)
            search_idx = pos + 1 # Start next search after the found signature
        else:
            break
    total_EOF_SIGNATURE_patterns = len(eof_occurrences)
    print(Colours.BLUE, f"  Found {total_EOF_SIGNATURE_patterns} occurrences of EOF_SIGNATURE pattern in the entire file.")
    # --- END: Count EOF_SIGNATURE pattern ---
    if total_EOF_SIGNATURE_patterns != 1:
        if total_EOF_SIGNATURE_patterns == 0:
            print(Colours.RED, f"  ERROR: EOF pattern not found in the file. This may indicate a corrupted or incomplete TXD file.")
        else:
            print(Colours.RED, f"  ERROR: Expected 1 EOF pattern, found {total_EOF_SIGNATURE_patterns}. This may indicate a corrupted or incomplete TXD file.")
        exit(1)

    # --- START: Count sig_file_start in the entire file ---
    total_sig_file_start = data.count(sig_file_start)
    print(Colours.BLUE, f"  Found {total_sig_file_start} occurrences of sig_file_start in the entire file.")
    # --- END: Count sig_file_start ---

    # --- START: Count sig_block_start in the entire file ---
    total_sig_block_start = data.count(sig_block_start)
    print(Colours.BLUE, f"  Found {total_sig_block_start} occurrences of sig_block_start in the entire file.")
    # --- END: Count sig_block_start ---

    # --- START: Count sig_compound_end_marker in the entire file ---
    total_sig_compound_end_marker = data.count(sig_compound_end_marker) # Same as sig_block_start
    print(Colours.BLUE, f"  Found {total_sig_compound_end_marker} occurrences of sig_compound_end_marker in the entire file.")
    # --- END: Count sig_compound_end_marker ---

    # --- START: Count texture_name_signature in the entire file ---
    total_texture_name_signature = data.count(texture_name_signature)
    print(Colours.BLUE, f"  Found {total_texture_name_signature} occurrences of texture_name_signature in the entire file.")
    # --- END: Count texture_name_signature ---

    total_textures = 0
    if total_sig_block_start == total_sig_compound_end_marker and total_sig_block_start == total_texture_name_signature:
        total_textures = total_texture_name_signature

    data_segments_to_scan = []
    search_ptr = 0

    # --- Phase 1: Process initial 0x16 segment (if present) ---
    if data.startswith(sig_file_start):
        print(Colours.CYAN, f"  File starts with sig_file_start (0x16). Processing initial segment.")
        start_of_data_after_0x16 = len(sig_file_start)
        
        try:
            # Find the first occurrence of sig_compound_end_marker after the 0x16 header data.
            pos_marker = data.index(sig_compound_end_marker, start_of_data_after_0x16)

            # Check if this marker is actually the EOF_SIGNATURE pattern
            if _is_eof_pattern_at_pos(data, pos_marker):
                print(Colours.CYAN, f"      0x16 segment data (offset 0x{start_of_data_after_0x16:X}) ends before EOF_SIGNATURE pattern found at 0x{pos_marker:X}.")
                segment_data = data[start_of_data_after_0x16 : pos_marker]
                if segment_data:
                    data_segments_to_scan.append((start_of_data_after_0x16, segment_data))
                search_ptr = len(data) # EOF hit, no more blocks to process
            else:
                # It's a genuine sig_compound_end_marker (which is also a sig_block_start)
                print(Colours.CYAN, f"      0x16 segment data (offset 0x{start_of_data_after_0x16:X}) ends before sig_compound_end_marker at 0x{pos_marker:X}.")
                segment_data = data[start_of_data_after_0x16 : pos_marker]
                if segment_data:
                    data_segments_to_scan.append((start_of_data_after_0x16, segment_data))
                search_ptr = pos_marker # Next search for 0x14 block will start AT this marker
        
        except ValueError: # sig_compound_end_marker not found after start_of_data_after_0x16
            # No sig_compound_end_marker found. Check if EOF_SIGNATURE pattern is present instead.
            pos_eof = _find_eof_pattern(data, start_of_data_after_0x16)
            if pos_eof != -1: # If EOF pattern found
                print(Colours.CYAN, f"      0x16 segment data (offset 0x{start_of_data_after_0x16:X}) ends before EOF_SIGNATURE pattern (direct find) at 0x{pos_eof:X}.")
                segment_data = data[start_of_data_after_0x16 : pos_eof]
                if segment_data:
                    data_segments_to_scan.append((start_of_data_after_0x16, segment_data))
                search_ptr = len(data) # EOF hit, no more blocks
            else: # EOF pattern also not found
                # Neither sig_compound_end_marker nor EOF_SIGNATURE pattern found after 0x16 header.
                # This implies the 0x16 data runs to the end of the file.
                print(Colours.YELLOW, f"      Warning: No sig_compound_end_marker or EOF_SIGNATURE pattern found after 0x16 segment start. Assuming 0x16 data to end of file.")
                segment_data = data[start_of_data_after_0x16:]
                if segment_data:
                    data_segments_to_scan.append((start_of_data_after_0x16, segment_data))
                search_ptr = len(data) # Reached end of file
    else:
        print(Colours.YELLOW, "  File does not start with sig_file_start (0x16). Will scan for 0x14 blocks from beginning.")
        search_ptr = 0 # Start scanning for 0x14 blocks from the beginning of the file


    # --- Phase 2: Process subsequent 0x14 blocks ---
    current_scan_pos = search_ptr
    while current_scan_pos < len(data):
        try:
            # Find the start of the current 0x14 block (sig_block_start).
            # Search must begin at current_scan_pos.
            found_block_start_at = data.index(sig_block_start, current_scan_pos)

            # CRITICAL CHECK: Is this sig_block_start actually the EOF_SIGNATURE pattern?
            if _is_eof_pattern_at_pos(data, found_block_start_at):
                print(Colours.CYAN, f"  Encountered EOF_SIGNATURE pattern at 0x{found_block_start_at:X} while searching for a 0x14 block start. Ending block scan.")
                break # EOF found, no more valid blocks.

            # If not EOF, it's a genuine start of a 0x14 block.
            print(Colours.CYAN, f"  Found 0x14 block start signature at file offset 0x{found_block_start_at:X}.")
            start_of_data_after_0x14 = found_block_start_at + len_block_marker
            
            # Now, find the end of this 0x14 block's data.
            # It ends before the *next* sig_compound_end_marker (which is sig_block_start)
            # or before EOF_SIGNATURE pattern, whichever comes first.
            # The search for this end marker must start *after* the current block's data begins.
            try:
                pos_next_marker = data.index(sig_compound_end_marker, start_of_data_after_0x14)

                # Check if this next_marker is actually the EOF_SIGNATURE pattern
                if _is_eof_pattern_at_pos(data, pos_next_marker):
                    print(Colours.CYAN, f"      0x14 block (data from 0x{start_of_data_after_0x14:X}) ends before EOF_SIGNATURE pattern (found as next marker) at 0x{pos_next_marker:X}.")
                    segment_data = data[start_of_data_after_0x14 : pos_next_marker]
                    if segment_data:
                        data_segments_to_scan.append((start_of_data_after_0x14, segment_data))
                    current_scan_pos = len(data) # EOF hit, stop all scanning.
                else:
                    # Genuine next sig_compound_end_marker. Current block data ends before it.
                    print(Colours.CYAN, f"      0x14 block (data from 0x{start_of_data_after_0x14:X}) ends before next sig_compound_end_marker at 0x{pos_next_marker:X}.")
                    segment_data = data[start_of_data_after_0x14 : pos_next_marker]
                    if segment_data:
                        data_segments_to_scan.append((start_of_data_after_0x14, segment_data))
                    current_scan_pos = pos_next_marker # Next scan for a 0x14 block will start AT this marker.
            
            except ValueError: # No further sig_compound_end_marker found after this 0x14 block's data started.
                # This implies the current 0x14 block might be the last one, ending at EOF pattern or physical EOF.
                pos_eof = _find_eof_pattern(data, start_of_data_after_0x14)
                if pos_eof != -1: # If EOF pattern found
                    print(Colours.CYAN, f"      0x14 block (data from 0x{start_of_data_after_0x14:X}) ends before EOF_SIGNATURE pattern (direct find) at 0x{pos_eof:X}.")
                    segment_data = data[start_of_data_after_0x14 : pos_eof]
                    if segment_data:
                        data_segments_to_scan.append((start_of_data_after_0x14, segment_data))
                    current_scan_pos = len(data) # EOF hit, stop.
                else: # EOF pattern also not found
                    # No sig_compound_end_marker AND no EOF_SIGNATURE pattern found after this block's data started.
                    # This means this 0x14 block's data runs to the physical end of the file.
                    print(Colours.YELLOW, f"      Warning: For 0x14 block (data from 0x{start_of_data_after_0x14:X}), no subsequent marker or EOF pattern found. Assuming data to end of file.")
                    segment_data = data[start_of_data_after_0x14:]
                    if segment_data:
                        data_segments_to_scan.append((start_of_data_after_0x14, segment_data))
                    current_scan_pos = len(data) # Reached end of file.

        except ValueError: # data.index(sig_block_start, current_scan_pos) failed.
            # No more sig_block_start (and thus no more 0x14 blocks or EOF prefix) found from current_scan_pos.
            print(Colours.BLUE, f"  No more sig_block_start (or EOF pattern prefix) found after offset 0x{current_scan_pos:X}. Ending 0x14 block scan.")
            break # Exit the while loop.


    # Fallback logic from original code (Noesis-style) - can be adapted or removed based on TXD format strictness
    if not data_segments_to_scan and data.startswith(sig_file_start) and len(data) > 0x28 :
        print(Colours.YELLOW, "  No segments found by primary rules, but file starts with 0x16. Defaulting to process from offset 0x28 (Noesis-style).")
        # Ensure this doesn't read past EOF if EOF is close to 0x28
        eof_pos_fallback = _find_eof_pattern(data, 0x28)
        if eof_pos_fallback != -1:
            data_segments_to_scan.append( (0x28, data[0x28:eof_pos_fallback]) )
        else:
            data_segments_to_scan.append( (0x28, data[0x28:]) )
    elif not data_segments_to_scan:
        print(Colours.RED, f"  No data segments identified for processing in '{txd_filepath}' based on defined block signatures.")
        # time.sleep(5) # Original had sleep here

    if not data_segments_to_scan:
        print(Colours.RED, f"  No processable data segments ultimately found in '{txd_filepath}'.")
        # time.sleep(5) # Original had sleep here
        return 0

    num_segments_to_process = len(data_segments_to_scan)
    print(Colours.BLUE, f"\n  Found {num_segments_to_process} segment(s) to process in '{txd_filepath}'.")

    for i, (seg_start_offset, seg_data) in enumerate(data_segments_to_scan):
        if not seg_data:
            print(Colours.YELLOW, f"\n  Skipping zero-length segment #{i+1} (intended to start at file offset 0x{seg_start_offset:X}).")
            # time.sleep(5) # Original had sleep here
            continue
        print(Colours.CYAN, f"\n  Processing segment #{i+1}: data starts at file offset 0x{seg_start_offset:X}, segment length {len(seg_data)} bytes.")
        textures_in_segment = process_texture_data_segment(seg_data, seg_start_offset, output_dir_base) # Pass output_dir_base
        total_textures_exported_from_file += textures_in_segment


    if total_textures_exported_from_file > 0:
        print(Colours.CYAN, f"\nFinished processing for '{txd_filepath}'. Exported {total_textures_exported_from_file} textures to '{output_dir_base}'.")
    else:
        print(Colours.RED, f"\nNo textures were successfully exported from any identified segments in '{txd_filepath}'.")

    # Compare exported count with estimated count from raw name signatures
    if total_textures_exported_from_file != total_textures:
        print(Colours.YELLOW, f"  WARNING: Number of raw name signatures found ({total_textures}) does not match number of textures reported as exported ({total_textures_exported_from_file}). This could be due to segmentation logic, invalid texture data, or duplicate/unused name entries.")
        # time.sleep(5) # Original had sleep here

    return total_textures_exported_from_file

def main():
    parser = argparse.ArgumentParser(description="Extract textures from .txd files (typically Renderware TXD for GTA games).")
    parser.add_argument("input_path", help="Path to a .txd file or a directory containing .txd files.")
    parser.add_argument("-o", "--output_dir", default=None,
                        help="Base directory to save extracted textures. Default: A subfolder named '<txd_filename>_txd' will be created in the same directory as each input .txd file.")
    args = parser.parse_args()

    input_path_abs = os.path.abspath(args.input_path) # Work with absolute paths
    output_dir_base_arg = os.path.abspath(args.output_dir) if args.output_dir else None

    overall_textures_exported = 0
    files_processed_count = 0 # Count of files where processing was attempted and completed (even if 0 textures found)
    files_with_exports = 0 # Count of files from which at least one texture was exported

    if not os.path.exists(input_path_abs):
        print(Colours.RED, f"Error: Input path '{input_path_abs}' does not exist.")
        exit(1)

    txd_files_to_process = []
    if os.path.isfile(input_path_abs):
        if input_path_abs.lower().endswith(".txd"):
            txd_files_to_process.append(input_path_abs)
        else:
            print(Colours.RED, f"Error: Input file '{input_path_abs}' is not a .txd file.")
            exit(1) # #exit if a single specified file is not TXD
    elif os.path.isdir(input_path_abs):
        print(Colours.CYAN, f"Scanning directory: {input_path_abs}")
        for root, _, files in os.walk(input_path_abs):
            for file in files:
                if file.lower().endswith(".txd"):
                    txd_files_to_process.append(os.path.join(root, file))
        if not txd_files_to_process:
            print(Colours.RED, f"No .txd files found in directory '{input_path_abs}'.")
            return # Not a fatal error, just no work.
    else: # Should not be reached if os.path.exists passed
        print(Colours.RED, f"Error: Input path '{input_path_abs}' is not a valid file or directory.")
        exit(1)

    if not txd_files_to_process:
        print(Colours.RED, "No .txd files to process.")
        return

    print(Colours.CYAN, f"Found {len(txd_files_to_process)} .txd file(s) to process.")

    last_used_output_base_for_summary = ""

    for txd_file_path in txd_files_to_process:
        # Determine the base directory for this specific TXD's output subfolder
        current_output_dir_base_for_txd = output_dir_base_arg
        if current_output_dir_base_for_txd is None: # If -o was not specified
            current_output_dir_base_for_txd = os.path.join(os.path.dirname(txd_file_path), f"{os.path.basename(txd_file_path).rstrip('.txd')}_txd")

        last_used_output_base_for_summary = current_output_dir_base_for_txd # For summary message

        print(Colours.CYAN, f"\n--- Processing file: {txd_file_path} ---")
        # export_textures_from_txd will create its own "filename_txd" subfolder within current_output_dir_base_for_txd
        textures_in_current_file = export_textures_from_txd(txd_file_path, current_output_dir_base_for_txd)

        overall_textures_exported += textures_in_current_file
        files_processed_count += 1 # Increment for every file attempted
        if textures_in_current_file > 0:
            files_with_exports +=1


    print(Colours.CYAN, "\n--- Summary ---")
    print(Colours.CYAN, f"Attempted to process {len(txd_files_to_process)} .txd file(s).")
    if files_processed_count > 0 : # If any file was actually processed (even if it had 0 textures)
        print(Colours.CYAN, f"Files fully processed: {files_processed_count}.") # Should match len(txd_files_to_process) if no early #exits
        print(Colours.CYAN, f"Files with at least one texture exported: {files_with_exports}.")
        print(Colours.CYAN, f"Total textures exported across all files: {overall_textures_exported}.")
        if overall_textures_exported > 0:
            if output_dir_base_arg: # If -o was used
                print(Colours.CYAN, f"Base output directory specified: '{output_dir_base_arg}' (TXD-specific subfolders created within).")
            else: # -o not used, output relative to each TXD
                print(Colours.CYAN, f"Output subdirectories created relative to each input TXD file's location (e.g., '{os.path.join(last_used_output_base_for_summary, 'examplename_txd')}').")

        if files_processed_count == 858 and overall_textures_exported != 7318:
            print(Colours.YELLOW, f"WARNING: Only {overall_textures_exported} textures were exported. This may indicate that some textures were not processed or exported due to errors.")

    else: # This case should ideally not be hit if txd_files_to_process was not empty
        print(Colours.YELLOW, "No .txd files ended up being processed.")

if __name__ == '__main__':
    main()

#!/usr/bin/env python3
import struct
import os
import re
import argparse # Added for CLI argument parsing

# --- Morton Unswizzling Helper ---
# Note: _part_bits_by_1 is defined but not directly used by morton_encode_2d or unswizzle_data.
# The morton_encode_2d function uses a more direct bit manipulation approach.
def _part_bits_by_1(n, BITS):
    # Spread BITS of n by inserting 0s between bits.
    # Example for 16-bit BITS=8 (part_bits1_by1 from common Morton code)
    # n = (n ^ (n << 8)) & 0x00FF00FF  # Not needed for up to 16-bit width/height
    # n = (n ^ (n << 4)) & 0x0F0F0F0F  # For up to 8 bits per coord (256x256)
    # n = (n ^ (n << 2)) & 0x33333333  # For up to 4 bits per coord (16x16)
    # n = (n ^ (n << 1)) & 0x55555555  # For up to 2 bits per coord (4x4)

    # Generic version for up to 16-bit coordinates (max texture dim 65536)
    # Max val of n will be 2^16 - 1. Result needs 32 bits.
    mask_shifts = []
    if BITS > 8: mask_shifts.append((0x0000FF00, 0xFF0000FF, 8)) # Interleave groups of 8 bits
    if BITS > 4: mask_shifts.append((0x00F000F0, 0xF00FF00F, 4)) # Interleave groups of 4 bits
    if BITS > 2: mask_shifts.append((0x0C0C0C0C, 0xC30C30C3, 2)) # Interleave groups of 2 bits
    if BITS > 1: mask_shifts.append((0x22222222, 0x49249249, 1)) # Interleave groups of 1 bit

    # Filter masks based on BITS actually needed for current coordinate value range
    # Example: if max coordinate is 255 (8 bits), BITS = 8
    # We need to spread these 8 bits into 16 positions for one coordinate in a 32-bit Morton index

    # Simplified version adequate for texture coordinates up to 16-bits (65536 dim)
    # Spreads BITS of n into 2*BITS positions
    res = 0
    for i in range(BITS):
        res |= (n & (1 << i)) << i
    return res

    # More general bit-spreading (for one coordinate to be interleaved)
    # This is a common, more efficient way:
    # Assuming n is at most 16 bits
    # n &= 0xFFFF # Ensure n is 16-bit
    # n = (n | (n << 8)) & 0x00FF00FF
    # n = (n | (n << 4)) & 0x0F0F0F0F
    # n = (n | (n << 2)) & 0x33333333
    # n = (n | (n << 1)) & 0x55555555
    # return n

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
        print(f"      Warning: Swizzled data length ({len(swizzled_data)}) is less than expected ({linear_data_size}) for {width}x{height}@{bytes_per_pixel}bpp. Skipping unswizzle.")
        return None

    linear_data = bytearray(linear_data_size)

    for y_coord in range(height):
        for x_coord in range(width):
            morton_idx = morton_encode_2d(x_coord, y_coord)

            if (morton_idx * bytes_per_pixel) + bytes_per_pixel > len(swizzled_data):
                # This case should ideally not be hit if dimensions and bpp are correct for swizzled_data length
                # print(f"      Warning: Morton index {morton_idx} out of bounds for swizzled data. ({x_coord},{y_coord})")
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


def process_texture_data_segment_modified(segment_data, segment_original_start_offset, output_dir):
    textures_found_in_segment = 0
    i = 0
    current_name_info = None
    print(f"  Scanning data segment (len {len(segment_data)}) for textures...")

    while i < len(segment_data):
        # --- 1. TRY TO PARSE A NAME ---
        # Check for NAME signature (b'\x00\x00\x00\x0A')
        # Need at least 4 bytes for sig, plus more for name itself.
        if i + 4 <= len(segment_data) and segment_data[i : i+4] == b'\x00\x00\x00\x0A':
            name_sig_offset_in_segment = i
            name_str_val = None
            # print(f"  Found potential name signature at seg_offset 0x{name_sig_offset_in_segment:X} (file 0x{segment_original_start_offset + name_sig_offset_in_segment:X})")

            name_string_start_offset_in_segment = name_sig_offset_in_segment + 8
            name_end_scan_in_segment = name_string_start_offset_in_segment

            # Ensure there's space for name string and its null terminators
            if name_string_start_offset_in_segment + 2 > len(segment_data): # Need at least 2 bytes for \x00\x00
                # print(f"    Not enough data for name string after signature at seg_offset 0x{name_sig_offset_in_segment:X}.")
                i = name_sig_offset_in_segment + 1 # Advance past the signature start
                continue

            while name_end_scan_in_segment < len(segment_data) - 1 and \
                  segment_data[name_end_scan_in_segment : name_end_scan_in_segment+2] != b'\x00\x00':
                name_end_scan_in_segment += 1

            if name_end_scan_in_segment < len(segment_data) - 1 and \
               segment_data[name_end_scan_in_segment : name_end_scan_in_segment+2] == b'\x00\x00':
                name_bytes = segment_data[name_string_start_offset_in_segment : name_end_scan_in_segment]
                try:
                    name_str_val = name_bytes.decode('utf-8', errors='ignore').strip()
                except UnicodeDecodeError:
                    name_str_val = name_bytes.hex()

                if not name_str_val:
                    name_str_val = f"unnamed_texture_at_0x{segment_original_start_offset + name_sig_offset_in_segment:08X}"

                if current_name_info and not current_name_info['processed_meta']:
                    print(f"    WARNING: Previous name '{current_name_info['name']}' (sig at file 0x{current_name_info['original_file_offset']:X}) "
                          f"did not get metadata processed before new name '{name_str_val}' found.")

                current_name_info = {
                    'name': name_str_val,
                    'processed_meta': False,
                    'name_sig_offset_in_segment': name_sig_offset_in_segment,
                    'original_file_offset': segment_original_start_offset + name_sig_offset_in_segment
                }
                print(f"    Parsed name: '{name_str_val}' (signature at seg_offset 0x{name_sig_offset_in_segment:X})")
                i = name_end_scan_in_segment + 2 # Advance i past the name and its double null terminators

                # --- Immediately look for metadata for THIS name ---
                first_n00_after_name_offset = -1
                scan_ptr_for_n00 = i

                while scan_ptr_for_n00 < len(segment_data):
                    if segment_data[scan_ptr_for_n00] != 0x00:
                        first_n00_after_name_offset = scan_ptr_for_n00
                        break
                    scan_ptr_for_n00 += 1

                if first_n00_after_name_offset != -1:
                    # print(f"      Found first non-00 byte at seg_offset 0x{first_n00_after_name_offset:X} for '{current_name_info['name']}'.")
                    # Rule: meta_block_start = first_n00_offset + 2
                    meta_offset_in_segment = first_n00_after_name_offset + 2

                    if meta_offset_in_segment + 16 <= len(segment_data): # Check for 16-byte metadata block
                        # print(f"      Deduced potential metadata block for '{current_name_info['name']}' starting at seg_offset 0x{meta_offset_in_segment:X} (file 0x{segment_original_start_offset + meta_offset_in_segment:X})")
                        metadata_bytes = segment_data[meta_offset_in_segment : meta_offset_in_segment + 16]
                        fmt_code = metadata_bytes[3] # Format code is the 4th byte

                        print(f"      Processing metadata for '{current_name_info['name']}' (Format Code 0x{fmt_code:02X} from seg_offset 0x{meta_offset_in_segment+3:X})")
                        width = struct.unpack('>H', metadata_bytes[4:6])[0]
                        height = struct.unpack('>H', metadata_bytes[6:8])[0]
                        mip_map_count_from_file = metadata_bytes[9] # Note: often 0 or 1, might not be reliable for all formats
                        total_pixel_data_size = struct.unpack('<I', metadata_bytes[12:16])[0]

                        print(f"        Meta Details - W: {width}, H: {height}, MipsFromFile: {mip_map_count_from_file}, DataSize: {total_pixel_data_size}")

                        if width == 0 or height == 0 or total_pixel_data_size == 0:
                            print(f"          Skipping '{current_name_info['name']}' due to invalid dimensions/size in metadata.")
                            current_name_info['processed_meta'] = True
                            i = meta_offset_in_segment + 16 # Advance past this metadata block
                        else:
                            pixel_data_start_offset_in_segment = meta_offset_in_segment + 16
                            actual_mip_data_to_process_size = total_pixel_data_size

                            if pixel_data_start_offset_in_segment + actual_mip_data_to_process_size > len(segment_data):
                                print(f"          Error: Not enough data in segment for pixel data of '{current_name_info['name']}'. "
                                      f"Expected {actual_mip_data_to_process_size} bytes from seg_offset 0x{pixel_data_start_offset_in_segment:X}.")
                                current_name_info['processed_meta'] = True
                                i = meta_offset_in_segment + 16 # Advance past metadata block
                            else:
                                swizzled_base_mip_data = segment_data[pixel_data_start_offset_in_segment :
                                                                  pixel_data_start_offset_in_segment + actual_mip_data_to_process_size]
                                dds_header, output_pixel_data, export_format_str = None, None, ""

                                # --- FMT CODE SPECIFIC LOGIC ---
                                if fmt_code == 0x52: # DXT1
                                    dds_header = create_dds_header_dxt(width, height, mip_map_count_from_file if mip_map_count_from_file > 0 else 1, 'DXT1')
                                    output_pixel_data = swizzled_base_mip_data
                                    export_format_str = "DXT1"
                                    # print(f"          Format 0x52 (DXT1). No unswizzling needed.")
                                elif fmt_code == 0x53: # DXT3
                                    dds_header = create_dds_header_dxt(width, height, mip_map_count_from_file if mip_map_count_from_file > 0 else 1, 'DXT3')
                                    output_pixel_data = swizzled_base_mip_data
                                    export_format_str = "DXT3"
                                    # print(f"          Format 0x53 (DXT3). No unswizzling needed.")
                                elif fmt_code == 0x54: # DXT5
                                    dds_header = create_dds_header_dxt(width, height, mip_map_count_from_file if mip_map_count_from_file > 0 else 1, 'DXT5')
                                    output_pixel_data = swizzled_base_mip_data
                                    export_format_str = "DXT5"
                                    # print(f"          Format 0x54 (DXT5). No unswizzling needed.")
                                elif fmt_code == 0x86: # Morton swizzled BGRA8888 (Xbox 360 style)
                                    export_format_str = "RGBA8888 (from Swizzled BGRA)"
                                    # print(f"          Format 0x86 (Morton swizzled BGRA8888). Attempting unswizzle.")
                                    expected_size = width * height * 4 # 4 bytes per pixel for BGRA8888
                                    if actual_mip_data_to_process_size == expected_size:
                                        linear_bgra_data = unswizzle_data(swizzled_base_mip_data, width, height, 4)
                                        if linear_bgra_data:
                                            output_pixel_data = bytearray(len(linear_bgra_data))
                                            for p_idx in range(0, len(linear_bgra_data), 4):
                                                output_pixel_data[p_idx+0] = linear_bgra_data[p_idx+2] # R from B
                                                output_pixel_data[p_idx+1] = linear_bgra_data[p_idx+1] # G from G
                                                output_pixel_data[p_idx+2] = linear_bgra_data[p_idx+0] # B from R
                                                output_pixel_data[p_idx+3] = linear_bgra_data[p_idx+3] # A from A
                                            dds_header = create_dds_header_rgba(width, height, 1) # Exporting base mip only
                                        else: print(f"          Failed to unswizzle BGRA data for {current_name_info['name']}.")
                                    else: print(f"          Data size mismatch for BGRA of '{current_name_info['name']}': expected {expected_size}, got {actual_mip_data_to_process_size}.")
                                elif fmt_code == 0x02: # Often A8 or sometimes a P8A8 like format (e.g. L8A8)
                                    export_format_str = "RGBA8888 (from Swizzled A8 or P8A8)"
                                    # print(f"          Format 0x02 (Morton swizzled A8 or P8A8). Attempting unswizzle.")
                                    if actual_mip_data_to_process_size == width * height * 1: # Likely A8 (1 byte per pixel)
                                        # print(f"            Treating as Swizzled A8 for '{current_name_info['name']}'.")
                                        linear_a8_data = unswizzle_data(swizzled_base_mip_data, width, height, 1)
                                        if linear_a8_data:
                                            output_pixel_data = bytearray(width * height * 4) # RGBA output
                                            for p_idx in range(width * height):
                                                alpha = linear_a8_data[p_idx]
                                                output_pixel_data[p_idx*4+0] = 0   # R
                                                output_pixel_data[p_idx*4+1] = 0   # G
                                                output_pixel_data[p_idx*4+2] = 0   # B
                                                output_pixel_data[p_idx*4+3] = alpha # A
                                            dds_header = create_dds_header_rgba(width, height, 1)
                                        else: print(f"          Failed to unswizzle A8 data for {current_name_info['name']}.")
                                    elif actual_mip_data_to_process_size == width * height * 2: # Likely P8A8 or L8A8 (2 bytes per pixel)
                                        # print(f"            Treating as Swizzled P8A8 (L8A8) for '{current_name_info['name']}'.")
                                        linear_p8a8_data = unswizzle_data(swizzled_base_mip_data, width, height, 2)
                                        if linear_p8a8_data:
                                            output_pixel_data = bytearray(width * height * 4) # RGBA output
                                            for p_idx in range(width * height):
                                                p8_or_l8 = linear_p8a8_data[p_idx*2+0]
                                                a8 = linear_p8a8_data[p_idx*2+1]
                                                output_pixel_data[p_idx*4+0] = p8_or_l8 # R
                                                output_pixel_data[p_idx*4+1] = p8_or_l8 # G
                                                output_pixel_data[p_idx*4+2] = p8_or_l8 # B
                                                output_pixel_data[p_idx*4+3] = a8       # A
                                            dds_header = create_dds_header_rgba(width, height, 1)
                                        else: print(f"          Failed to unswizzle P8A8/L8A8 data for {current_name_info['name']}.")
                                    else: print(f"          Data size mismatch for Format 0x02 of '{current_name_info['name']}': expected {width*height} or {width*height*2}, got {actual_mip_data_to_process_size}.")
                                else:
                                    print(f"          Skipping '{current_name_info['name']}' due to unknown/unsupported format code: 0x{fmt_code:02X}")

                                if dds_header and output_pixel_data:
                                    clean_name = sanitize_filename(current_name_info['name'])
                                    if not clean_name: # Fallback if sanitize results in empty
                                        clean_name = f"texture_at_0x{current_name_info['original_file_offset']:08X}"
                                    dds_filename = os.path.join(output_dir, f"{clean_name}.dds")
                                    try:
                                        with open(dds_filename, "wb") as dds_file:
                                            dds_file.write(dds_header)
                                            dds_file.write(output_pixel_data)
                                        print(f"          Successfully exported: {dds_filename} (Format: {export_format_str}, {width}x{height})")
                                        textures_found_in_segment += 1
                                    except IOError as e:
                                        print(f"          Error writing DDS file {dds_filename}: {e}")
                                    except Exception as e:
                                        print(f"          An unexpected error occurred while writing DDS file {dds_filename}: {e}")
                                elif fmt_code in [0x52,0x53,0x54,0x86,0x02] and not (dds_header and output_pixel_data):
                                     print(f"          Export failed for '{current_name_info['name']}' (Format 0x{fmt_code:02X}) due to processing error or data issue.")


                                current_name_info['processed_meta'] = True
                                i = pixel_data_start_offset_in_segment + actual_mip_data_to_process_size
                                if i > len(segment_data): i = len(segment_data) # Cap i at segment length
                    else: # Not enough data for the potential metadata block
                        print(f"      Not enough data for full 16-byte metadata block for '{current_name_info['name']}' after first non-00 byte at seg_offset 0x{first_n00_after_name_offset:X} (deduced meta start would be 0x{meta_offset_in_segment:X}).")
                        # Metadata not found/processed. current_name_info remains pending.
                        # Advance i past the first_n00_byte that led to this failed path to avoid re-processing it as a start.
                        i = first_n00_after_name_offset + 1
                else: # No non-00 byte found after the name until end of segment_data
                    print(f"      No non-00 byte found after name '{current_name_info['name']}' (ended at seg_offset 0x{i:X}) to indicate metadata start. Name remains pending.")
                    # current_name_info remains pending. i is already at scan_ptr_for_n00 (which is len(segment_data) or where scan stopped).
                    i = scan_ptr_for_n00 # Ensure i is updated to where scan stopped
                # End of metadata search for the current name
                continue # Continue main while loop from the updated 'i'

            else: # Name signature found, but name parsing failed (no double null)
                print(f"    Name signature at seg_offset 0x{name_sig_offset_in_segment:X} (file 0x{segment_original_start_offset + name_sig_offset_in_segment:X}) failed full parsing (no double null found).")
                if current_name_info and not current_name_info['processed_meta']:
                     print(f"      WARNING: Discarding pending name '{current_name_info['name']}' (sig at file 0x{current_name_info['original_file_offset']:X}) due to malformed subsequent name signature.")
                current_name_info = None # Clear any pending name as context is broken
                i = name_sig_offset_in_segment + 1 # Advance by one from the failed signature start
                continue
        # --- END OF NAME PARSING BLOCK ---

        # --- 2. IF NO NAME SIGNATURE AT CURRENT i ---
        else:
            # If a name was fully processed (meta found or skipped due to error), clear it.
            if current_name_info and current_name_info.get('processed_meta', False):
                # print(f"  Clearing processed/resolved name: {current_name_info['name']}")
                current_name_info = None

            # If no name signature was found at current `i`, and no specific jump occurred, advance by one byte.
            # print(f"No name signature at seg_offset 0x{i:X}, advancing.") # Can be very verbose
            i += 1
        # Loop continues

    if current_name_info and not current_name_info['processed_meta']:
        print(f"  WARNING: End of segment reached. Pending name '{current_name_info['name']}' (sig at file 0x{current_name_info['original_file_offset']:X}) did not find its metadata.")

    print(f"Finished processing segment. Textures found in this segment: {textures_found_in_segment}")
    return textures_found_in_segment

    if textures_found_in_segment == 0:
        print(f"  No textures successfully exported from segment starting at file offset 0x{segment_original_start_offset:X} matching criteria.")
    return textures_found_in_segment

def export_textures_from_txd(txd_filepath, output_dir):
    print(f"Processing TXD file: {txd_filepath}")
    try:
        with open(txd_filepath, "rb") as f: data = f.read()
    except FileNotFoundError: print(f"Error: File not found: {txd_filepath}"); return 0
    except Exception as e: print(f"Error reading file: {e}"); return 0

    if not os.path.exists(output_dir):
        try:
            os.makedirs(output_dir)
            print(f"Created output directory: {output_dir}")
        except OSError as e:
            print(f"Error: Could not create output directory {output_dir}: {e}")
            return 0


    total_textures_found_in_file = 0
    sig_file_start = b'\x16\x00\x00\x00'; sig_block_start = b'\x14\x00\x00\x00'; sig_block_end_marker = b'\x03\x00\x00\x00'
    data_segments_to_scan = []; search_ptr = 0

    if data.startswith(sig_file_start):
        start_of_first_segment_rule = len(sig_file_start)
        try:
            end_marker_pos = data.index(sig_block_end_marker, start_of_first_segment_rule)
            if end_marker_pos > start_of_first_segment_rule:
                segment = data[start_of_first_segment_rule : end_marker_pos]
                data_segments_to_scan.append( (start_of_first_segment_rule, segment) )
                search_ptr = end_marker_pos + len(sig_block_end_marker)
                print(f" Identified initial segment (16-03 rule): data from 0x{start_of_first_segment_rule:X} to 0x{end_marker_pos:X}. Length: {len(segment)}")
        except ValueError: pass

    current_scan_start_for_14_blocks = search_ptr
    while current_scan_start_for_14_blocks < len(data):
        try:
            block_start_sig_pos = data.index(sig_block_start, current_scan_start_for_14_blocks)
            start_of_segment_data = block_start_sig_pos + len(sig_block_start)
            try:
                block_end_marker_pos = data.index(sig_block_end_marker, start_of_segment_data)
                if block_end_marker_pos > start_of_segment_data:
                    segment = data[start_of_segment_data : block_end_marker_pos]
                    data_segments_to_scan.append( (start_of_segment_data, segment) )
                    current_scan_start_for_14_blocks = block_end_marker_pos + len(sig_block_end_marker)
                    print(f" Identified segment (14-03 rule): sig at 0x{block_start_sig_pos:X}, data from 0x{start_of_segment_data:X} to 0x{block_end_marker_pos:X}. Length: {len(segment)}")
                else: current_scan_start_for_14_blocks = start_of_segment_data
            except ValueError:
                segment = data[start_of_segment_data:]
                data_segments_to_scan.append( (start_of_segment_data, segment) )
                print(f" Identified segment (14-EOF rule): sig at 0x{block_start_sig_pos:X}, data from 0x{start_of_segment_data:X} to EOF. Length: {len(segment)}")
                break
        except ValueError: break

    if not data_segments_to_scan and data.startswith(sig_file_start) and len(data) > 0x28:
        print(" No segments found by 16-03/14-03 rules. File starts with 0x16. Defaulting to process from offset 0x28 (Noesis-style).")
        data_segments_to_scan.append( (0x28, data[0x28:]) )

    if not data_segments_to_scan: print(" No data segments identified for processing based on the provided rules."); return 0

    for seg_start_offset, seg_data in data_segments_to_scan:
        if not seg_data: print(f"\nSkipping zero-length segment intended to start at file offset 0x{seg_start_offset:X}."); continue
        print(f"\nProcessing segment: data starts at file offset 0x{seg_start_offset:X}, original segment length {len(seg_data)} bytes.")
        total_textures_found_in_file += process_texture_data_segment_modified(seg_data, seg_start_offset, output_dir)

    if total_textures_found_in_file > 0: print(f"\nFinished processing for '{txd_filepath}'. Exported {total_textures_found_in_file} textures to '{output_dir}'.")
    else: print(f"\nNo textures were successfully exported from any identified segments in '{txd_filepath}'.")
    return total_textures_found_in_file


def main():
    parser = argparse.ArgumentParser(description="Extract textures from .txd files.")
    parser.add_argument("input_path", help="Path to a .txd file or a directory containing .txd files.")
    parser.add_argument("-o", "--output_dir", default=None, help="Directory to save extracted textures (default: SameDir as input).")

    args = parser.parse_args()

    input_path = args.input_path
    output_dir = args.output_dir

    if output_dir is None:
        has_output_dir = False

    overall_textures_exported = 0
    files_processed = 0

    if not os.path.exists(input_path):
        print(f"Error: Input path '{input_path}' does not exist.")
        return

    if os.path.isfile(input_path):
        if input_path.lower().endswith(".txd"):
            if output_dir is None:
                # make output dir the path to the input file with the file name as the directory name within that path,
                output_dir = os.path.join(os.path.dirname(input_path), f"{os.path.basename(input_path).rstrip('.txd')}_txd")
                print(f"Output directory not specified. Using: {output_dir}")

            overall_textures_exported += export_textures_from_txd(input_path, output_dir)
            files_processed = 1
        else:
            print(f"Error: Input file '{input_path}' is not a .txd file.")
            return
    elif os.path.isdir(input_path):
        print(f"Scanning directory: {input_path}")
        txd_files_found = []
        for root, _, files in os.walk(input_path):
            for file in files:
                if file.lower().endswith(".txd"):
                    txd_files_found.append(os.path.join(root, file))

        if not txd_files_found:
            print(f"No .txd files found in directory '{input_path}'.")
            return

        print(f"Found {len(txd_files_found)} .txd file(s) to process.")
        for txd_file_path in txd_files_found:
            if has_output_dir is False:
                # make output dir the path to the input file with the file name as the directory name within that path,
                output_dir = os.path.join(os.path.dirname(txd_file_path), f"{os.path.basename(txd_file_path).rstrip('.txd')}_txd")
                print(f"Output directory not specified. Using: {output_dir}")

            overall_textures_exported += export_textures_from_txd(txd_file_path, output_dir)
            files_processed +=1
            print("-" * 30) # Separator between files

    else:
        print(f"Error: Input path '{input_path}' is not a valid file or directory.")
        return

    print("\n--- Summary ---")
    if files_processed > 0:
        print(f"Processed {files_processed} .txd file(s).")
        print(f"Total textures exported: {overall_textures_exported}")
        if overall_textures_exported > 0:
            print(f"Output directory: '{os.path.abspath(output_dir)}'")
    else:
        print("No .txd files were processed.")


if __name__ == '__main__':
    main()
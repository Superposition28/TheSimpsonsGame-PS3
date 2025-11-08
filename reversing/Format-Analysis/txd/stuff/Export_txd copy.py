import struct
import os
import re

# --- Morton Unswizzling Helper ---
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

    while i < len(segment_data) - 16: 
        if segment_data[i : i+4] == b'\x00\x00\x00\x0A':
            name_sig_offset_in_segment = i
            # print(f"    Found potential name signature at seg_offset 0x{name_sig_offset_in_segment:X} (file 0x{segment_original_start_offset + name_sig_offset_in_segment:X})")
            name_string_start_offset_in_segment = name_sig_offset_in_segment + 8
            name_end_scan_in_segment = name_string_start_offset_in_segment
            while name_end_scan_in_segment < len(segment_data) -1 and segment_data[name_end_scan_in_segment : name_end_scan_in_segment+2] != b'\x00\x00':
                name_end_scan_in_segment += 1
            if name_end_scan_in_segment < len(segment_data) -1 and segment_data[name_end_scan_in_segment : name_end_scan_in_segment+2] == b'\x00\x00':
                name_bytes = segment_data[name_string_start_offset_in_segment : name_end_scan_in_segment]
                try: name_str = name_bytes.decode('utf-8', errors='ignore').strip()
                except UnicodeDecodeError: name_str = name_bytes.hex()
                if not name_str: name_str = f"unnamed_texture_at_0x{segment_original_start_offset + name_sig_offset_in_segment:08X}"
                current_name_info = {'name': name_str, 'processed_meta': False}
                print(f"      Parsed name: '{name_str}'")
                i = name_end_scan_in_segment + 2; continue
            else: 
                print(f"      Name signature at seg_offset 0x{name_sig_offset_in_segment:X} failed full parsing.")
                current_name_info = None; i = name_sig_offset_in_segment + 1; continue
        
        if segment_data[i : i+3] == b'\x1A\x20\x01' or segment_data[i : i+3] == b'\x28\x00\x01':
            meta_offset_in_segment = i
            # print(f"    Found potential metadata signature ({segment_data[i:i+3].hex()}) at seg_offset 0x{meta_offset_in_segment:X} (file 0x{segment_original_start_offset + meta_offset_in_segment:X})")
            if current_name_info is None:
                # print(f"      Skipping metadata: No current name is pending.")
                i = meta_offset_in_segment + 1; continue
            elif current_name_info.get('processed_meta', True):
                # print(f"      Skipping metadata: Name '{current_name_info['name']}' already processed.")
                i = meta_offset_in_segment + 1; continue
            if len(segment_data) < meta_offset_in_segment + 16:
                # print(f"      Not enough data in segment for full metadata block.")
                i += 1; continue

            metadata_bytes = segment_data[meta_offset_in_segment : meta_offset_in_segment + 16]
            fmt_code = metadata_bytes[3]
            width = struct.unpack('>H', metadata_bytes[4:6])[0]
            height = struct.unpack('>H', metadata_bytes[6:8])[0]
            mip_map_count_from_file = metadata_bytes[9] 
            total_pixel_data_size = struct.unpack('<I', metadata_bytes[12:16])[0]
            
            print(f"      Processing metadata for name: '{current_name_info['name']}'")
            print(f"        Format Code: 0x{fmt_code:02X}, W: {width}, H: {height}, MipsFromFile: {mip_map_count_from_file}, DataSize: {total_pixel_data_size}")

            if width == 0 or height == 0 or total_pixel_data_size == 0:
                print(f"        Skipping '{current_name_info['name']}' due to invalid dimensions/size."); current_name_info['processed_meta'] = True
                i = meta_offset_in_segment + 16; continue

            # Prepare for pixel data extraction (base mip only for raw)
            pixel_data_start_offset_in_segment = meta_offset_in_segment + 16
            # For raw formats, assume total_pixel_data_size is for the base (largest) mip
            # For DXT, it's for all mips.
            actual_mip_data_to_process_size = total_pixel_data_size 

            if pixel_data_start_offset_in_segment + actual_mip_data_to_process_size > len(segment_data):
                print(f"        Error: Not enough data in segment for pixel data of '{current_name_info['name']}'. Expected {actual_mip_data_to_process_size} bytes from seg_offset 0x{pixel_data_start_offset_in_segment:X}.")
                current_name_info['processed_meta'] = True; i = meta_offset_in_segment + 16; continue
            
            swizzled_base_mip_data = segment_data[pixel_data_start_offset_in_segment : pixel_data_start_offset_in_segment + actual_mip_data_to_process_size]

            dds_header = None
            output_pixel_data = None
            export_format_str = ""

            if fmt_code == 0x52: # DXT1
                dds_header = create_dds_header_dxt(width, height, mip_map_count_from_file, 'DXT1')
                output_pixel_data = swizzled_base_mip_data # DXT data is used as is (already "processed" by GPU)
                export_format_str = "DXT1"
            elif fmt_code == 0x53: # DXT3
                dds_header = create_dds_header_dxt(width, height, mip_map_count_from_file, 'DXT3')
                output_pixel_data = swizzled_base_mip_data
                export_format_str = "DXT3"
            elif fmt_code == 0x54: # DXT5
                dds_header = create_dds_header_dxt(width, height, mip_map_count_from_file, 'DXT5')
                output_pixel_data = swizzled_base_mip_data
                export_format_str = "DXT5"
            
            elif fmt_code == 0x86: # Morton swizzled BGRA8888
                print(f"        Format 0x86 (Morton swizzled BGRA8888) for '{current_name_info['name']}'. Attempting unswizzle.")
                export_format_str = "RGBA8888 (from Swizzled BGRA)"
                expected_size = width * height * 4
                if actual_mip_data_to_process_size == expected_size:
                    linear_bgra_data = unswizzle_data(swizzled_base_mip_data, width, height, 4)
                    if linear_bgra_data:
                        # Convert BGRA to RGBA
                        output_pixel_data = bytearray(len(linear_bgra_data))
                        for p_idx in range(0, len(linear_bgra_data), 4):
                            output_pixel_data[p_idx+0] = linear_bgra_data[p_idx+2] # R
                            output_pixel_data[p_idx+1] = linear_bgra_data[p_idx+1] # G
                            output_pixel_data[p_idx+2] = linear_bgra_data[p_idx+0] # B
                            output_pixel_data[p_idx+3] = linear_bgra_data[p_idx+3] # A
                        dds_header = create_dds_header_rgba(width, height, 1) # Base mip only
                    else: print(f"        Failed to unswizzle BGRA data for {current_name_info['name']}.")
                else: print(f"        Data size mismatch for BGRA: expected {expected_size}, got {actual_mip_data_to_process_size}.")

            elif fmt_code == 0x02: # Morton swizzled "p8a8" (or A8)
                export_format_str = "RGBA8888 (from Swizzled P8A8 or A8)"
                # Case 1: A8 (like fakeshdw)
                if actual_mip_data_to_process_size == width * height * 1:
                    print(f"        Format 0x02 for '{current_name_info['name']}' treated as Swizzled A8. Attempting unswizzle.")
                    linear_a8_data = unswizzle_data(swizzled_base_mip_data, width, height, 1)
                    if linear_a8_data:
                        output_pixel_data = bytearray(width * height * 4) # RGBA output
                        for p_idx in range(width * height):
                            alpha = linear_a8_data[p_idx]
                            output_pixel_data[p_idx*4+0] = 0 # R (black for shadow/alpha)
                            output_pixel_data[p_idx*4+1] = 0 # G
                            output_pixel_data[p_idx*4+2] = 0 # B
                            output_pixel_data[p_idx*4+3] = alpha # A
                        dds_header = create_dds_header_rgba(width, height, 1)
                    else: print(f"        Failed to unswizzle A8 data for {current_name_info['name']}.")
                # Case 2: P8A8 (2bpp)
                elif actual_mip_data_to_process_size == width * height * 2:
                    print(f"        Format 0x02 for '{current_name_info['name']}' treated as Swizzled P8A8 (2bpp). Attempting unswizzle.")
                    linear_p8a8_data = unswizzle_data(swizzled_base_mip_data, width, height, 2)
                    if linear_p8a8_data:
                        output_pixel_data = bytearray(width * height * 4) # RGBA output
                        for p_idx in range(width * height):
                            p8 = linear_p8a8_data[p_idx*2+0]
                            a8 = linear_p8a8_data[p_idx*2+1]
                            output_pixel_data[p_idx*4+0] = p8 # R (P8 as grayscale)
                            output_pixel_data[p_idx*4+1] = p8 # G
                            output_pixel_data[p_idx*4+2] = p8 # B
                            output_pixel_data[p_idx*4+3] = a8 # A
                        dds_header = create_dds_header_rgba(width, height, 1)
                    else: print(f"        Failed to unswizzle P8A8 data for {current_name_info['name']}.")
                else:
                    print(f"        Data size mismatch for Format 0x02: expected {width*height} or {width*height*2}, got {actual_mip_data_to_process_size}.")
            else: # Unknown format code
                print(f"        Skipping '{current_name_info['name']}' due to unknown/unsupported format code: 0x{fmt_code:02X}")
            
            # Export if header and data are ready
            if dds_header and output_pixel_data:
                clean_name = sanitize_filename(current_name_info['name'])
                if not clean_name: clean_name = f"texture_at_0x{segment_original_start_offset + meta_offset_in_segment:08X}"
                dds_filename = os.path.join(output_dir, f"{clean_name}.dds")
                try:
                    with open(dds_filename, "wb") as dds_file:
                        dds_file.write(dds_header)
                        dds_file.write(output_pixel_data)
                    print(f"        Successfully exported: {dds_filename} (Format: {export_format_str}, {width}x{height}, Mips: 1 (Base Only for Raw))")
                    textures_found_in_segment += 1
                except Exception as e: print(f"        Error writing DDS file {dds_filename}: {e}")
            
            current_name_info['processed_meta'] = True
            i = pixel_data_start_offset_in_segment + actual_mip_data_to_process_size # Advance past this texture's base mip data
            if i > len(segment_data): i = len(segment_data)
            continue
        i += 1
    
    if textures_found_in_segment == 0:
        print(f"  No textures successfully exported from segment starting at file offset 0x{segment_original_start_offset:X} matching criteria.")
    return textures_found_in_segment

def export_textures_from_txd(txd_filepath, output_dir="output_textures"):
    print(f"Processing TXD file: {txd_filepath}")
    try:
        with open(txd_filepath, "rb") as f: data = f.read()
    except FileNotFoundError: print(f"Error: File not found: {txd_filepath}"); return
    except Exception as e: print(f"Error reading file: {e}"); return

    if not os.path.exists(output_dir): os.makedirs(output_dir); print(f"Created output directory: {output_dir}")

    total_textures_found = 0
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
                print(f"Identified initial segment (16-03 rule): data from 0x{start_of_first_segment_rule:X} to 0x{end_marker_pos:X}. Length: {len(segment)}")
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
                    print(f"Identified segment (14-03 rule): sig at 0x{block_start_sig_pos:X}, data from 0x{start_of_segment_data:X} to 0x{block_end_marker_pos:X}. Length: {len(segment)}")
                else: current_scan_start_for_14_blocks = start_of_segment_data 
            except ValueError: 
                segment = data[start_of_segment_data:]
                data_segments_to_scan.append( (start_of_segment_data, segment) )
                print(f"Identified segment (14-EOF rule): sig at 0x{block_start_sig_pos:X}, data from 0x{start_of_segment_data:X} to EOF. Length: {len(segment)}")
                break 
        except ValueError: break
            
    if not data_segments_to_scan and data.startswith(sig_file_start) and len(data) > 0x28:
         print("No segments found by 16-03/14-03 rules. File starts with 0x16. Defaulting to process from offset 0x28 (Noesis-style).")
         data_segments_to_scan.append( (0x28, data[0x28:]) )

    if not data_segments_to_scan: print("No data segments identified for processing based on the provided rules."); return

    for seg_start_offset, seg_data in data_segments_to_scan:
        if not seg_data: print(f"\nSkipping zero-length segment intended to start at file offset 0x{seg_start_offset:X}."); continue
        print(f"\nProcessing segment: data starts at file offset 0x{seg_start_offset:X}, original segment length {len(seg_data)} bytes.")
        total_textures_found += process_texture_data_segment_modified(seg_data, seg_start_offset, output_dir)

    if total_textures_found > 0: print(f"\nFinished processing. Exported {total_textures_found} textures to '{output_dir}'.")
    else: print(f"\nNo textures were successfully exported from any identified segments in '{txd_filepath}'.")

if __name__ == '__main__':
    txd_file_path = input("Enter the path to the .txd file: ")
    if os.path.exists(txd_file_path): export_textures_from_txd(txd_file_path)
    else: print(f"File not found: {txd_file_path}")
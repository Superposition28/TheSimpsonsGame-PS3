import os
import hashlib
import collections
import struct # For unpacking binary data
import math # For entropy calculation
import string # For checking printable characters
import argparse
from pathlib import Path
import gc

# --- Configuration ---
DEFAULT_HEADER_SIZE = 64       # Bytes to consider for header comparison
DEFAULT_PATTERN_LENGTH = 16    # Length of byte patterns to search for
DEFAULT_MIN_PATTERN_COUNT = 5  # Minimum times a pattern must appear to be reported
MIN_STRING_LENGTH = 5          # Minimum length for ASCII string extraction
MAX_STRINGS_PER_FILE = 20      # Limit strings reported per file
MAX_LUMPS_PER_FILE = 30        # Limit potential lumps reported per file
MAX_LUMP3_NODES_TO_REPORT = 10 # Limit nodes reported per file for lump 3

# Header Field Offsets (Assuming Big Endian)
OFFSET_MAGIC_VER = 0x00
OFFSET_COUNT = 0x08
OFFSET_NEXT_SECTION = 0x0C
OFFSET_LUMP_DIR_START = 0x10
OFFSET_LUMP_DIR_END = 0x70 # Up to (not including) 0x70

# Specific sequences to count (bytes)
SEQ_NEG_ONE = b'\xFF\xFF\xFF\xFF'
SEQ_FLOAT_ONE = b'\x00\x00\x80\x3F' # Big Endian 1.0f

# Hypothesized Node Structure (Lump 3) - Big Endian
# Corrected Guess: 8 floats, 8 ints = 16 fields, 64 bytes total
# Fields: Plane(4f), BBox/Tex?(4f), Flags?(i), ChildF(i), ChildB(i), Unk1(i), Unk2(i), Unk3(i), Unk4(i), Unk5(i)
NODE_LUMP3_FORMAT = ">ffffffffiiiiiiii" # 8 floats, 8 ints
NODE_LUMP3_SIZE = struct.calcsize(NODE_LUMP3_FORMAT) # Should be 64

# --- End Configuration ---

# Helper for entropy calculation
def calculate_entropy(byte_data):
    """Calculates the Shannon entropy of byte data (0-8)."""
    byte_counts = collections.Counter(byte_data)
    total_bytes = len(byte_data)
    entropy = 0.0
    if total_bytes == 0:
        return 0.0

    for count in byte_counts.values():
        probability = count / total_bytes
        if probability > 0:
            entropy -= probability * math.log2(probability)
    return entropy # Result is in bits per byte (0-8 range)


def find_bsp_files(start_dir):
    """Recursively finds all files ending with .bsp (case-insensitive)."""
    bsp_files = []
    print(f"[*] Searching for .bsp files in: {start_dir}")
    for root, _, files in os.walk(start_dir):
        for file in files:
            if file.lower().endswith(".bsp"):
                bsp_files.append(os.path.join(root, file))
    print(f"[+] Found {len(bsp_files)} .bsp files.")
    return bsp_files

def analyze_lump_3_data(lump_data, filename):
    """Parses lump 3 data using the hypothesized 64-byte node structure."""
    nodes = []
    data_len = len(lump_data)
    num_nodes = data_len // NODE_LUMP3_SIZE

    if data_len % NODE_LUMP3_SIZE != 0:
        status_update(f"    [!] Warning ({filename}): Lump 3 size ({data_len}) is not a multiple of node size ({NODE_LUMP3_SIZE}). Parsing {num_nodes} full nodes.", newline=True)

    if num_nodes == 0:
        return "Lump 3 data is too small to contain any nodes."

    for i in range(num_nodes):
        offset = i * NODE_LUMP3_SIZE
        node_bytes = lump_data[offset : offset + NODE_LUMP3_SIZE]
        try:
            parsed_node = struct.unpack(NODE_LUMP3_FORMAT, node_bytes)
            nodes.append(parsed_node)
        except struct.error as e:
            return f"Error unpacking node {i} in {filename}: {e}"
        except Exception as e:
             return f"Unexpected error parsing node {i} in {filename}: {e}"

    return nodes


def analyze_file(filepath, header_size, pattern_length):
    """
    Analyzes a single BSP file for header hash, fields, patterns, strings, etc.
    Reads the ENTIRE file.
    """
    results = {
        'filepath': filepath,
        'filename': Path(filepath).name,
        'error': None,
        'size': 0,
        'header_hash': None,
        'header_fields': {},
        'frequent_patterns': collections.Counter(),
        'specific_counts': {},
        'entropy': 0.0,
        'strings': [],
        'potential_lumps': [],
        'lump_3_nodes': None # Added for lump 3 analysis
    }
    full_data = None

    try:
        results['size'] = os.path.getsize(filepath)
        status_update(f"    - Reading {results['size'] / (1024*1024):.2f} MB...")

        with open(filepath, 'rb') as f:
            full_data = f.read()
            data_len = len(full_data)

        # --- Analysis Stage ---
        status_update("    - Analyzing Header...")

        # 1. Header Hash & Fields
        header_data = full_data[:header_size]
        if data_len > 0 :
            results['header_hash'] = hashlib.sha256(header_data).hexdigest()
        else: # Empty file
             results['header_hash'] = hashlib.sha256(b'').hexdigest()

        # Unpack specific header fields (Big Endian >)
        if data_len >= 4:
             results['header_fields']['magic_ver'] = struct.unpack('>I', full_data[OFFSET_MAGIC_VER:OFFSET_MAGIC_VER+4])[0]
        if data_len >= OFFSET_COUNT + 4:
             results['header_fields']['count_0x08'] = struct.unpack('>I', full_data[OFFSET_COUNT:OFFSET_COUNT+4])[0]
        if data_len >= OFFSET_NEXT_SECTION + 4:
             results['header_fields']['offset_0x0C'] = struct.unpack('>I', full_data[OFFSET_NEXT_SECTION:OFFSET_NEXT_SECTION+4])[0]

        # 2. Potential Lump Directory (Speculative)
        status_update("    - Analyzing Lumps...")
        if data_len >= OFFSET_LUMP_DIR_END:
            lump_dir_data = full_data[OFFSET_LUMP_DIR_START:OFFSET_LUMP_DIR_END]
            num_potential_lumps = len(lump_dir_data) // 8 # Assuming 8 bytes per entry (Offset, Length)
            for i in range(num_potential_lumps):
                try:
                    offset, length = struct.unpack('>II', lump_dir_data[i*8 : i*8+8])
                    # Basic validity checks
                    if length > 0 and offset >= OFFSET_LUMP_DIR_END and (offset + length) <= data_len:
                         results['potential_lumps'].append({'id': i, 'offset': offset, 'length': length})
                    # Add less strict check? Maybe length 0 is okay? Or offset within header? Add if needed.
                except struct.error:
                    break # Stop if unpacking fails (e.g., not enough data)

        # 2b. Analyze Lump 3 Data (if found)
        status_update("    - Analyzing Lump 3...")
        lump3_info = next((lump for lump in results['potential_lumps'] if lump['id'] == 3), None)
        if lump3_info:
            lump3_offset = lump3_info['offset']
            lump3_length = lump3_info['length']
            # Ensure we don't read past the end of the file data
            if lump3_offset + lump3_length <= data_len:
                lump3_data = full_data[lump3_offset : lump3_offset + lump3_length]
                results['lump_3_nodes'] = analyze_lump_3_data(lump3_data, results['filename'])
                del lump3_data # Free memory
            else:
                 results['lump_3_nodes'] = f"Lump 3 definition points outside file bounds (Offset: {lump3_offset}, Length: {lump3_length}, File Size: {data_len})"
        else:
            # Check if lump dir parsing stopped early or if lump 3 just wasn't valid
            if data_len >= OFFSET_LUMP_DIR_START + (3 * 8) + 8: # Check if enough data existed for lump 3 entry
                 results['lump_3_nodes'] = "Lump 3 entry not found or invalid in header section 0x10-0x6F."
            # else: lump dir data was too short, already handled implicitly


        # 3. Frequent Patterns
        status_update("    - Analyzing Patterns...")
        if data_len >= pattern_length:
            for i in range(data_len - pattern_length + 1):
                pattern = full_data[i : i + pattern_length]
                results['frequent_patterns'][pattern] += 1

        # 4. Specific Byte Sequence Counts
        status_update("    - Counting Sequences...")
        if data_len > 0:
            results['specific_counts']['neg_one'] = full_data.count(SEQ_NEG_ONE)
            results['specific_counts']['float_one'] = full_data.count(SEQ_FLOAT_ONE)

        # 5. Entropy
        status_update("    - Calculating Entropy...")
        if data_len > 0:
            results['entropy'] = calculate_entropy(full_data)

        # 6. String Extraction
        status_update("    - Extracting Strings...")
        if data_len > 0:
            current_string = ""
            for byte in full_data:
                char = chr(byte)
                # Check if byte corresponds to a printable ASCII character
                if char in string.printable and char not in ('\n', '\r', '\t', '\v', '\f'): # Exclude whitespace controls except space
                     current_string += char
                else:
                    if len(current_string) >= MIN_STRING_LENGTH:
                        results['strings'].append(current_string)
                    current_string = ""
            # Catch trailing string
            if len(current_string) >= MIN_STRING_LENGTH:
                 results['strings'].append(current_string)


    except FileNotFoundError:
        results['error'] = "File not found"
    except PermissionError:
        results['error'] = "Permission denied"
    except MemoryError:
        results['error'] = f"MemoryError ({results['size'] / (1024*1024):.2f} MB)"
    except Exception as e:
        results['error'] = f"Unexpected error: {e}"
    finally:
        del full_data # Explicitly delete potentially large data
        # If an error occurred, some results might be missing/incomplete
        gc.collect() # Suggest garbage collection

    status_update(" " * 80, newline=False) # Clear status line

    return results

def status_update(message, newline=False):
     """Prints status message, overwriting previous one unless newline=True."""
     end_char = '\n' if newline else '\r'
     print(message.ljust(80), end=end_char, flush=True)


# --- Reporting Functions ---

def report_file_stats(analysis_results):
    print("\n--- File Size Statistics ---")
    sizes = [r['size'] for r in analysis_results if not r['error']]
    if not sizes:
        print("[*] No files successfully analyzed for size.")
        return
    min_size = min(sizes)
    max_size = max(sizes)
    avg_size = sum(sizes) / len(sizes)
    print(f"[*] Files Analyzed: {len(sizes)}")
    print(f"[*] Min Size: {min_size / (1024*1024):.2f} MB ({min_size} bytes)")
    print(f"[*] Max Size: {max_size / (1024*1024):.2f} MB ({max_size} bytes)")
    print(f"[*] Avg Size: {avg_size / (1024*1024):.2f} MB ({avg_size:.0f} bytes)")

def report_header_fields(analysis_results):
    print("\n--- Header Field Analysis ---")
    # Group by the 'count_0x08' field if it exists
    grouped_results = collections.defaultdict(list)
    errors = []
    no_count_field = []

    for r in analysis_results:
        if r['error']:
            errors.append(r['filename'])
            continue
        if 'count_0x08' in r['header_fields']:
            grouped_results[r['header_fields']['count_0x08']].append(r)
        else:
            no_count_field.append(r['filename'])

    if errors:
        print(f"[!] Errors prevented header analysis for: {', '.join(errors)}")
    if no_count_field:
         print(f"[*] Header field 'count_0x08' missing/unreadable for: {', '.join(no_count_field)}")

    if not grouped_results:
         print("[*] No header fields successfully extracted.")
         return

    print("[*] Files grouped by value at offset 0x08 ('Count'):")
    for count_val, results_list in sorted(grouped_results.items()):
        print(f"\n[+] Count = {count_val} (Found in {len(results_list)} files):")
        # Print details for the first few files in each group
        limit = 5
        for i, r in enumerate(results_list):
             if i < limit:
                 magic = r['header_fields'].get('magic_ver', 'N/A')
                 offset = r['header_fields'].get('offset_0x0C', 'N/A')
                 # Format magic as hex
                 magic_hex = f"0x{magic:08X}" if isinstance(magic, int) else magic
                 offset_hex = f"0x{offset:08X}" if isinstance(offset, int) else offset
                 print(f"  - {r['filename']:<25} | Magic/Ver: {magic_hex} | Offset@0x0C: {offset_hex}")
        if len(results_list) > limit:
             print(f"  ... ({len(results_list) - limit} more files)")


def report_specific_counts(analysis_results):
    print("\n--- Specific Sequence Counts ---")
    limit = 10
    count = 0
    reported = False
    for r in analysis_results:
        if r['error'] or not r['specific_counts']:
            continue
        count+=1
        if count > limit and limit > 0: continue # Limit output

        neg_one = r['specific_counts'].get('neg_one', 0)
        float_one = r['specific_counts'].get('float_one', 0)
        if neg_one > 0 or float_one > 0: # Only report if counts are non-zero
            reported = True
            print(f"[*] {r['filename']}:")
            print(f"  - Count(FFFFFFFF): {neg_one}")
            print(f"  - Count(0000803F): {float_one}")

    if not reported:
        print("[*] No occurrences of specified sequences (FFFFFFFF, 0000803F) found.")
    if count > limit and limit > 0:
        print(f"[*] (Report limited to first {limit} files with counts)")


def report_entropy(analysis_results):
    print("\n--- Byte Entropy Report (0=Uniform, 8=Random) ---")
    entropies = []
    for r in analysis_results:
        if not r['error']:
             entropies.append((r['entropy'], r['filename']))

    if not entropies:
         print("[*] No entropy calculated (all files might have errors).")
         return

    # Sort by entropy (e.g., lowest first)
    entropies.sort()
    limit = 15
    print("[*] Files sorted by entropy (lowest first):")
    for i, (entropy, filename) in enumerate(entropies):
        if i < limit or limit <= 0:
            print(f"  - {entropy:<6.4f} | {filename}")
    if len(entropies) > limit and limit > 0:
         print(f"  ... ({len(entropies) - limit} more files)")


def report_strings(analysis_results):
    print("\n--- Extracted Strings Report ---")
    limit = 5 # Limit files to report strings for
    count = 0
    reported = False
    for r in analysis_results:
         if r['error'] or not r['strings']:
             continue
         count += 1
         if count > limit and limit > 0: continue # Limit file output

         reported = True
         print(f"[*] Strings found in {r['filename']} (limited to {MAX_STRINGS_PER_FILE}):")
         display_count = 0
         unique_strings = sorted(list(set(r['strings']))) # Show unique strings, sorted
         for s in unique_strings:
              if display_count >= MAX_STRINGS_PER_FILE:
                  print(f"  ... ({len(unique_strings) - display_count} more unique strings)")
                  break
              print(f"  - \"{s}\"")
              display_count += 1

    if not reported:
         print(f"[*] No strings of minimum length {MIN_STRING_LENGTH} found.")
    if count > limit and limit > 0:
         print(f"[*] (String report limited to first {limit} files containing strings)")


def report_potential_lumps(analysis_results):
    print("\n--- Potential Lump Directory Analysis (Offsets 0x10-0x6F) ---")
    print("[!] Treats data as pairs of Big Endian (Offset, Length). Highly speculative!")
    limit = 5 # Limit files to report lumps for
    count = 0
    reported = False
    for r in analysis_results:
         if r['error'] or not r['potential_lumps']:
             continue
         count += 1
         if count > limit and limit > 0: continue

         reported = True
         print(f"[*] Potential Lumps in {r['filename']} (limited to {MAX_LUMPS_PER_FILE}):")
         display_count = 0
         for lump in r['potential_lumps']:
              if display_count >= MAX_LUMPS_PER_FILE:
                   print(f"  ... ({len(r['potential_lumps']) - display_count} more potential lumps)")
                   break
              # Report ID (index in dir), Offset, Length
              print(f"  - ID: {lump['id']:<2} | Offset: 0x{lump['offset']:08X} ({lump['offset']:<10}) | Length: 0x{lump['length']:08X} ({lump['length']:<10})")
              display_count += 1

    if not reported:
        print(f"[*] No potential valid lump entries found in header section 0x10-0x6F.")
    if count > limit and limit > 0:
        print(f"[*] (Potential lump report limited to first {limit} files with entries)")


def report_lump_3_analysis(analysis_results):
    """Reports the analysis results for Lump 3 (Nodes)."""
    print("\n--- Lump 3 (Node Structure) Analysis ---")
    print(f"[*] Attempting to parse Lump 3 data as {NODE_LUMP3_SIZE}-byte nodes:")
    print(f"[*] Format: {NODE_LUMP3_FORMAT} (BE: 8 float, 8 int)")
    print(f"[*] Fields: Plane(4f), BBox/Tex?(4f), Flags?(i), ChildF(i), ChildB(i), Unk1(i), Unk2(i), Unk3(i), Unk4(i), Unk5(i)")

    reported_files = 0
    special_files_reported = {'zone01.bsp': False, 'zone13.bsp': False}

    # Prioritize special files
    files_to_report = []
    other_files = []
    for r in analysis_results:
        if r['error'] or not r['lump_3_nodes']:
            continue
        if r['filename'] in special_files_reported:
            files_to_report.append(r)
        else:
            other_files.append(r)
    
    # Combine lists, special files first
    all_analyzed_files = files_to_report + other_files

    for r in all_analyzed_files:
        filename = r['filename']
        lump3_result = r['lump_3_nodes']
        is_special = filename in special_files_reported

        print(f"\n[*] File: {filename}" + (" (SPECIAL INTEREST)" if is_special else ""))

        if isinstance(lump3_result, str): # Error message
            print(f"  - Analysis Result: {lump3_result}")
            if is_special: special_files_reported[filename] = True
            reported_files += 1
        elif isinstance(lump3_result, list): # List of nodes
            num_nodes = len(lump3_result)
            print(f"  - Successfully parsed {num_nodes} nodes.")
            if is_special: special_files_reported[filename] = True
            reported_files += 1

            # Print first few nodes
            for i, node in enumerate(lump3_result):
                if i >= MAX_LUMP3_NODES_TO_REPORT:
                    print(f"  ... ({num_nodes - i} more nodes not shown)")
                    break

                # Unpack the tuple for clarity (8 floats, 8 ints)
                f1, f2, f3, f4, f5, f6, f7, f8, i1, i2, i3, i4, i5, i6, i7, i8 = node

                # --- Child Pointer Interpretation ---
                # Next Steps:
                # 1. Determine exact meaning: Are i2, i3 byte offsets (from lump start? node start?), node indices, or something else?
                # 2. Negative values: Often indicate leaf nodes. The format ~index = -(value + 1) is common.
                #    Test this hypothesis by examining leaf data referenced by negative indices.
                # 3. Positive values: Likely point to child nodes. Verify if they align with expected node offsets/indices.
                # --------------------------------------

                # Assume Child Front/Back are i2 and i3 based on common BSP structures
                child_f = i2
                child_b = i3

                # Format children (check if leaf node ~(-index))
                # This implements the common -(leaf_index + 1) convention
                child_f_str = f"~{-(child_f + 1)}" if child_f < 0 else str(child_f)
                child_b_str = f"~{-(child_b + 1)}" if child_b < 0 else str(child_b)

                # Format floats nicely (grouping the first 4 and next 4)
                plane_str = f"({f1:,.1f}, {f2:,.1f}, {f3:,.1f}, {f4:,.1f})"
                bbox_tex_str = f"({f5:,.1f}, {f6:,.1f}, {f7:,.1f}, {f8:,.1f})"
                # Group remaining ints
                ints_str = f"[{i1}, {i4}, {i5}, {i6}, {i7}, {i8}]" # Exclude children i2, i3

                print(f"  - Node {i:<3}: Plane={plane_str:<35} BBox/Tex?={bbox_tex_str:<35} Children=[{child_f_str:<5}, {child_b_str:<5}] Ints={ints_str}")

    # Report if special files were not found or analyzed
    for fname, reported in special_files_reported.items():
        if not reported:
            # Check if it was even in the input list
            found_in_input = any(r['filename'] == fname for r in analysis_results)
            if found_in_input:
                 print(f"\n[*] Note: {fname} was analyzed but had no valid Lump 3 data or encountered an error.")
            # else: It wasn't in the list of found BSPs, so no need to report absence.

    if reported_files == 0:
        print("[*] No files with analyzable Lump 3 data found.")


# --- Main Execution ---

def main():
    parser = argparse.ArgumentParser(
        description="Analyze BSP files for similarities and patterns. Reads ENTIRE files - Use with caution on large files / low RAM systems.",
        formatter_class=argparse.RawTextHelpFormatter
    )
    parser.add_argument("-d", "--directory", type=str, default=".",
                        help="Directory to search recursively (default: current directory)")
    parser.add_argument("--header", type=int, default=DEFAULT_HEADER_SIZE,
                        help=f"Size of the header in bytes to compare for hashing (default: {DEFAULT_HEADER_SIZE})")
    parser.add_argument("--patternlen", type=int, default=DEFAULT_PATTERN_LENGTH,
                        help=f"Length of byte patterns to search for (default: {DEFAULT_PATTERN_LENGTH})")
    parser.add_argument("--mincount", type=int, default=DEFAULT_MIN_PATTERN_COUNT,
                        help=f"Minimum occurrence count for reporting a pattern (default: {DEFAULT_MIN_PATTERN_COUNT})")

    args = parser.parse_args()

    script_dir = Path(args.directory).resolve()

    if not script_dir.is_dir():
        status_update(f"[!] Error: Directory not found: {script_dir}", newline=True)
        return

    if args.patternlen <= 0:
        status_update("[!] Error: Pattern length must be greater than 0.", newline=True)
        return

    if args.header <= 0: # Header for hashing, distinct from field extraction
        status_update("[!] Error: Header hash size must be greater than 0.", newline=True)
        return

    bsp_files = find_bsp_files(script_dir)

    if not bsp_files:
        status_update("[*] No .bsp files found in the specified directory or subdirectories.", newline=True)
        return

    analysis_results = []
    status_update(f"[*] Analyzing {len(bsp_files)} files (reading entire content)...", newline=True)
    status_update("[!] WARNING: This may consume significant RAM and take time for large files.", newline=True)

    total_size_mb = 0
    for filepath in bsp_files:
         try:
             total_size_mb += os.path.getsize(filepath) / (1024*1024)
         except Exception: pass
    status_update(f"[*] Total estimated size of files to analyze: {total_size_mb:.2f} MB", newline=True)


    count = 0
    for filepath in bsp_files:
        count += 1
        filename = Path(filepath).name
        # Print filename before starting its analysis stages
        status_update(f"\n({count}/{len(bsp_files)}) Analyzing: {filename}...", newline=True)
        result = analyze_file(filepath, args.header, args.patternlen)
        analysis_results.append(result)
        if result['error']:
             status_update(f"    [!] Error for {filename}: {result['error']}", newline=True)


    status_update("\n[*] Analysis phase complete.", newline=True)

    # --- Reporting ---
    report_file_stats(analysis_results)
    report_header_fields(analysis_results)
    report_specific_counts(analysis_results)
    report_entropy(analysis_results)
    report_strings(analysis_results)
    report_potential_lumps(analysis_results)
    report_lump_3_analysis(analysis_results) # Added lump 3 report


    status_update("\n--- End of Report ---", newline=True)

if __name__ == "__main__":
    main()
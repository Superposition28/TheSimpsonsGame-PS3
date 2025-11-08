#!/usr/bin/env python3
import struct
import os
import re
import argparse
import sys
import time

from printer import print, colours

# Define the long signature and component lengths
START_END_DATA_SEGMENT = b'\x14\x00\x00\x00\x2D\x00\x02\x1C\x2F\xEA\x00\x00\x08\x00\x00\x00\x2D\x00\x02\x1C'
LEN_START_END_DATA_SEGMENT = 0  # 24 bytes

# Original component lengths A-J
LEN_BYTES_A = 20
LEN_BYTES_B = 8
LEN_BYTES_C = 4
LEN_BYTES_D = 4
LEN_BYTES_E = 8
LEN_BYTES_F = 4
LEN_BYTES_G = 8
LEN_BYTES_H = 4 # indicates the four possible values before the name of the textures 12
LEN_BYTES_I = 66 # this is the block of bytes that contains the name of the textures 66
LEN_BYTES_J = 4
# this is the one byte that indicate the format type for texture image data 1
# next meta data like width, height, etc 12

# everything after meta should be raw image data until end marker x03\x00\x00\x00\ followed by start marker x14\x00\x00\x00

# Total length of the full structure: START_END_DATA_SEGMENT + A + B + ... + J
TOTAL_STRUCTURE_LEN = (LEN_START_END_DATA_SEGMENT +
                       LEN_BYTES_A + LEN_BYTES_B + LEN_BYTES_C + LEN_BYTES_D +
                       LEN_BYTES_E + LEN_BYTES_F + LEN_BYTES_G + LEN_BYTES_H +
                       LEN_BYTES_I + LEN_BYTES_J)

def extract_byte_sequences(txd_filepath,
                           unique_bytes_a_set, unique_bytes_b_set, unique_bytes_c_set,
                           unique_bytes_d_set, unique_bytes_e_set, unique_bytes_f_set,
                           unique_bytes_g_set, unique_bytes_h_set, unique_bytes_i_set,
                           unique_bytes_j_set
                           ):
    """
    Scans the entire TXD file for START_END_DATA_SEGMENT. If found, extracts subsequent
    byte sequences (BYTES_A to J with specified lengths) and adds them to their respective unique sets.
    """
    print(Colours.CYAN, f"Processing TXD file: {txd_filepath}")
    try:
        with open(txd_filepath, "rb") as f:
            data = f.read()
    except FileNotFoundError:
        print(Colours.RED, f"Error: File not found: {txd_filepath}")
        return 0
    except Exception as e:
        print(Colours.RED, f"Error reading file {txd_filepath}: {e}")
        return 0

    structures_found_in_file = 0
    current_pos = 0

    while current_pos < len(data):
        found_idx = data.find(START_END_DATA_SEGMENT, current_pos)
        if found_idx == -1:
            break

        if found_idx + TOTAL_STRUCTURE_LEN <= len(data):
            current_offset = found_idx + LEN_START_END_DATA_SEGMENT

            bytes_a = data[current_offset : current_offset + LEN_BYTES_A]; unique_bytes_a_set.add(bytes_a); current_offset += LEN_BYTES_A
            bytes_b = data[current_offset : current_offset + LEN_BYTES_B]; unique_bytes_b_set.add(bytes_b); current_offset += LEN_BYTES_B
            bytes_c = data[current_offset : current_offset + LEN_BYTES_C]; unique_bytes_c_set.add(bytes_c); current_offset += LEN_BYTES_C
            bytes_d = data[current_offset : current_offset + LEN_BYTES_D]; unique_bytes_d_set.add(bytes_d); current_offset += LEN_BYTES_D
            bytes_e = data[current_offset : current_offset + LEN_BYTES_E]; unique_bytes_e_set.add(bytes_e); current_offset += LEN_BYTES_E
            bytes_f = data[current_offset : current_offset + LEN_BYTES_F]; unique_bytes_f_set.add(bytes_f); current_offset += LEN_BYTES_F
            bytes_g = data[current_offset : current_offset + LEN_BYTES_G]; unique_bytes_g_set.add(bytes_g); current_offset += LEN_BYTES_G
            bytes_h = data[current_offset : current_offset + LEN_BYTES_H]; unique_bytes_h_set.add(bytes_h); current_offset += LEN_BYTES_H
            bytes_i = data[current_offset : current_offset + LEN_BYTES_I]; unique_bytes_i_set.add(bytes_i); current_offset += LEN_BYTES_I
            bytes_j = data[current_offset : current_offset + LEN_BYTES_J]; unique_bytes_j_set.add(bytes_j); current_offset += LEN_BYTES_J
            
            structures_found_in_file += 1
        
        current_pos = found_idx + 1

    if structures_found_in_file > 0:
        print(Colours.GREEN, f"  Found and processed {structures_found_in_file} full {TOTAL_STRUCTURE_LEN}-byte structure(s) in '{os.path.basename(txd_filepath)}'.")
    else:
        print(Colours.BLUE, f"  No full structures starting with '{START_END_DATA_SEGMENT[:8].hex()}...' found in '{os.path.basename(txd_filepath)}'.")

    return structures_found_in_file

def main():
    description_text_lengths = (
        f"A:{LEN_BYTES_A}, B:{LEN_BYTES_B}, C:{LEN_BYTES_C}, D:{LEN_BYTES_D}, E:{LEN_BYTES_E}, "
        f"F:{LEN_BYTES_F}, G:{LEN_BYTES_G}, H:{LEN_BYTES_H}, I:{LEN_BYTES_I}, J:{LEN_BYTES_J} bytes"
    )
    description_text = (
        f"Scans .txd files for a specific {LEN_START_END_DATA_SEGMENT}-byte signature ({START_END_DATA_SEGMENT[:8].hex()}...), "
        f"then extracts ten subsequent byte sequences (A-J with varying lengths: "
        f"{description_text_lengths}). "
        f"Logs unique sequences for each set to separate files."
    )
    parser = argparse.ArgumentParser(description=description_text)
    parser.add_argument("input_path", help="Path to a .txd file or a directory containing .txd files.")

    arg_configs = [
        ("o1", "output_log_A", f"reverse_engineering/Source/TODO/txd/unique_bytes_A.log", f"BYTES_A ({LEN_BYTES_A} bytes) after signature"),
        ("o2", "output_log_B", f"reverse_engineering/Source/TODO/txd/unique_bytes_B.log", f"BYTES_B ({LEN_BYTES_B} bytes) after BYTES_A"),
        ("o3", "output_log_C", f"reverse_engineering/Source/TODO/txd/unique_bytes_C.log", f"BYTES_C ({LEN_BYTES_C} bytes) after BYTES_B"),
        ("o4", "output_log_D", f"reverse_engineering/Source/TODO/txd/unique_bytes_D.log", f"BYTES_D ({LEN_BYTES_D} bytes) after BYTES_C"),
        ("o5", "output_log_E", f"reverse_engineering/Source/TODO/txd/unique_bytes_E.log", f"BYTES_E ({LEN_BYTES_E} bytes) after BYTES_D"),
        ("o6", "output_log_F", f"reverse_engineering/Source/TODO/txd/unique_bytes_F.log", f"BYTES_F ({LEN_BYTES_F} bytes) after BYTES_E"),
        ("o7", "output_log_G", f"reverse_engineering/Source/TODO/txd/unique_bytes_G.log", f"BYTES_G ({LEN_BYTES_G} bytes) after BYTES_F"),
        ("o8", "output_log_H", f"reverse_engineering/Source/TODO/txd/unique_bytes_H.log", f"BYTES_H ({LEN_BYTES_H} bytes) after BYTES_G"),
        ("o9", "output_log_I", f"reverse_engineering/Source/TODO/txd/unique_bytes_I.log", f"BYTES_I ({LEN_BYTES_I} bytes) after BYTES_H"),
        ("o10", "output_log_J", f"reverse_engineering/Source/TODO/txd/unique_bytes_J.log", f"BYTES_J ({LEN_BYTES_J} bytes) after BYTES_I"),
    ]

    for short_arg, long_arg_name, default_val, help_text_suffix in arg_configs:
        parser.add_argument(
            f"-{short_arg}", f"--{long_arg_name}", default=default_val,
            help=f"Log file for unique {help_text_suffix} (default: {default_val})."
        )

    args = parser.parse_args()
    input_path_abs = os.path.abspath(args.input_path)

    log_file_paths = {name: getattr(args, name) for _, name, _, _ in arg_configs}

    overall_structures_found = 0
    files_processed_count = 0

    master_unique_sets = {
        "BYTES_A": set(), "BYTES_B": set(), "BYTES_C": set(), "BYTES_D": set(),
        "BYTES_E": set(), "BYTES_F": set(), "BYTES_G": set(), "BYTES_H": set(),
        "BYTES_I": set(), "BYTES_J": set()
    }

    if not os.path.exists(input_path_abs):
        print(Colours.RED, f"Error: Input path '{input_path_abs}' does not exist.")
        sys.exit(1)

    txd_files_to_process = []
    if os.path.isfile(input_path_abs):
        if input_path_abs.lower().endswith(".txd"):
            txd_files_to_process.append(input_path_abs)
        else:
            print(Colours.RED, f"Error: Input file '{input_path_abs}' is not a .txd file.")
            sys.exit(1)
    elif os.path.isdir(input_path_abs):
        print(Colours.CYAN, f"Scanning directory: {input_path_abs}")
        for root, _, files in os.walk(input_path_abs):
            for file_name in files:
                if file_name.lower().endswith(".txd"):
                    txd_files_to_process.append(os.path.join(root, file_name))
        if not txd_files_to_process:
            print(Colours.YELLOW, f"No .txd files found in directory '{input_path_abs}'.")
            return
    else: 
        print(Colours.RED, f"Error: Input path '{input_path_abs}' is not a valid file or directory.")
        sys.exit(1)

    if not txd_files_to_process:
        print(Colours.YELLOW, "No .txd files to process.")
        return

    print(Colours.CYAN, f"Found {len(txd_files_to_process)} .txd file(s) to process.")
    print(Colours.CYAN, f"Searching for {TOTAL_STRUCTURE_LEN}-byte structures starting with signature: {START_END_DATA_SEGMENT.hex()}")

    for txd_file_path in txd_files_to_process:
        print(Colours.CYAN, f"\n--- Analyzing file: {os.path.basename(txd_file_path)} ---")
        structures_in_current_file = extract_byte_sequences(
            txd_file_path,
            master_unique_sets["BYTES_A"], master_unique_sets["BYTES_B"], master_unique_sets["BYTES_C"],
            master_unique_sets["BYTES_D"], master_unique_sets["BYTES_E"], master_unique_sets["BYTES_F"],
            master_unique_sets["BYTES_G"], master_unique_sets["BYTES_H"], master_unique_sets["BYTES_I"],
            master_unique_sets["BYTES_J"]
        )

        if structures_in_current_file > 0:
            overall_structures_found += structures_in_current_file
        files_processed_count += 1

    print(Colours.CYAN, "\n--- Summary ---")
    print(Colours.CYAN, f"Attempted to process {len(txd_files_to_process)} .txd file(s).")
    print(Colours.CYAN, f"Files scanned: {files_processed_count}.")
    print(Colours.CYAN, f"Total instances of the full {TOTAL_STRUCTURE_LEN}-byte structure found: {overall_structures_found}.")
    
    lengths_map = {
        "BYTES_A": LEN_BYTES_A, "BYTES_B": LEN_BYTES_B, "BYTES_C": LEN_BYTES_C,
        "BYTES_D": LEN_BYTES_D, "BYTES_E": LEN_BYTES_E, "BYTES_F": LEN_BYTES_F,
        "BYTES_G": LEN_BYTES_G, "BYTES_H": LEN_BYTES_H, "BYTES_I": LEN_BYTES_I,
        "BYTES_J": LEN_BYTES_J
    }
    
    log_details_for_summary = [
        ("BYTES_A", "output_log_A", f"{LEN_BYTES_A}b after signature"),
        ("BYTES_B", "output_log_B", f"{LEN_BYTES_B}b after BYTES_A"),
        ("BYTES_C", "output_log_C", f"{LEN_BYTES_C}b after BYTES_B"),
        ("BYTES_D", "output_log_D", f"{LEN_BYTES_D}b after BYTES_C"),
        ("BYTES_E", "output_log_E", f"{LEN_BYTES_E}b after BYTES_D"),
        ("BYTES_F", "output_log_F", f"{LEN_BYTES_F}b after BYTES_E (texture name candidates)"),
        ("BYTES_G", "output_log_G", f"{LEN_BYTES_G}b after BYTES_F (texture name block)"),
        ("BYTES_H", "output_log_H", f"{LEN_BYTES_H}b after BYTES_G"),
        ("BYTES_I", "output_log_I", f"{LEN_BYTES_I}b after BYTES_H"),
        ("BYTES_J", "output_log_J", f"{LEN_BYTES_J}b after BYTES_I"),
    ]

    all_sets_empty = True
    for setName, log_arg_name, setDescription in log_details_for_summary:
        byte_set = master_unique_sets[setName]
        log_path = log_file_paths[log_arg_name]
        byte_len = lengths_map[setName]

        if byte_set:
            all_sets_empty = False
            print(Colours.GREEN, f"Found {len(byte_set)} unique {setName} sequences ({setDescription}).")
            try:
                os.makedirs(os.path.dirname(log_path), exist_ok=True) # Ensure directory exists
                with open(log_path, "w") as lf:
                    lf.write(f"# {len(byte_set)} unique {byte_len}-byte sequences ({setName}) found {setDescription.lower()}.\n")
                    lf.write(f"# Preceded by START_END_DATA_SEGMENT: {START_END_DATA_SEGMENT.hex()}" + (f" and prior byte sets." if setName != "BYTES_A" else ".") + "\n")
                    for seq in sorted(list(byte_set)): 
                        lf.write(f"{seq.hex()}\n")
                print(Colours.GREEN, f"Successfully wrote unique {setName} sequences to '{log_path}'.")
            except IOError as e:
                print(Colours.RED, f"Error writing to {setName} log file '{log_path}': {e}")
        else:
            print(Colours.YELLOW, f"No unique {setName} sequences were found.")
    
    if all_sets_empty and overall_structures_found == 0 :
        print(Colours.YELLOW, "No instances of the target structure were found in any file.")

if __name__ == '__main__':
    # This is a placeholder for the printer module if it's not found.
    # In a real scenario, ensure printer.py is in the same directory or PYTHONPATH.
    try:
        from printer import print, colours
    except ImportError:
        print("Warning: 'printer' module not found. Using standard print and dummy Colours.")
        class DummyColours:
            CYAN = ""
            RED = ""
            GREEN = ""
            YELLOW = ""
            BLUE = ""
        colours = DummyColours()
        # Redefine print to be the standard print if the custom one isn't available
        _print_backup = print 
        def print_custom(color, *args, **kwargs):
            _print_backup(*args, **kwargs)
        print = print_custom

    main()
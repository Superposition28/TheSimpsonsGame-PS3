#!/usr/bin/env python3
import struct
import os
import re
import argparse
import sys
import time

from printer import print, colours

# --- Signature Definitions ---
# The initial 4-byte sequence to search for
SEARCH_SIGNATURE_START = b'\x16\x00\x00\x00'

# The trailing 4-byte sequence that's part of the full 12-byte pattern
# Full pattern: SEARCH_SIGNATURE_START (4b) + Wildcard (4b) + EXPECTED_SIGNATURE_END (4b)
EXPECTED_SIGNATURE_END = b'\x2D\x00\x02\x1C'
OFFSET_OF_EXPECTED_END = 8  # (4 bytes for SEARCH_SIGNATURE_START + 4 wildcard bytes)
LENGTH_OF_EXPECTED_END = 4
FULL_PATTERN_LENGTH = 12 # Total length of "16000000XXXXXXXX2D00021C"

# String representation of the full 12-byte pattern for messages
FULL_PATTERN_STR = f"{SEARCH_SIGNATURE_START.hex()}........{EXPECTED_SIGNATURE_END.hex()}" # "16000000........2d00021c"

# LEN_START_END_DATA_SEGMENT: Length of any data *before* BYTES_A.
# Since the 12-byte pattern *is* the start of BYTES_A, this is 0.
LEN_START_END_DATA_SEGMENT = 0

# --- Component Length Definitions A-Z ---
LEN_BYTES_A = 20
LEN_BYTES_B = 8
LEN_BYTES_C = 4
LEN_BYTES_D = 4
LEN_BYTES_E = 8
LEN_BYTES_F = 4
LEN_BYTES_G = 8
LEN_BYTES_H = 4
LEN_BYTES_I = 66
LEN_BYTES_J = 5
LEN_BYTES_K = 1
LEN_BYTES_L = 12
LEN_BYTES_M = 256
LEN_BYTES_N = 8
LEN_BYTES_O = 8
LEN_BYTES_P = 4
LEN_BYTES_Q = 4
LEN_BYTES_R = 4
LEN_BYTES_S = 4
LEN_BYTES_T = 4
LEN_BYTES_U = 4
LEN_BYTES_V = 4
LEN_BYTES_W = 4
LEN_BYTES_X = 4
LEN_BYTES_Y = 4
LEN_BYTES_Z = 4

# Total length of components A-Z.
# Since LEN_START_END_DATA_SEGMENT is 0, TOTAL_STRUCTURE_LEN is effectively sum(LEN_BYTES_A to Z).
# This is the length of data expected *after* the 12-byte pattern has been identified (and is part of BYTES_A).
TOTAL_COMPONENTS_LEN = (
    LEN_BYTES_A + LEN_BYTES_B + LEN_BYTES_C + LEN_BYTES_D +
    LEN_BYTES_E + LEN_BYTES_F + LEN_BYTES_G + LEN_BYTES_H +
    LEN_BYTES_I + LEN_BYTES_J + LEN_BYTES_K +
    LEN_BYTES_L + LEN_BYTES_M + LEN_BYTES_N + LEN_BYTES_O +
    LEN_BYTES_P + LEN_BYTES_Q + LEN_BYTES_R + LEN_BYTES_S +
    LEN_BYTES_T + LEN_BYTES_U + LEN_BYTES_V + LEN_BYTES_W +
    LEN_BYTES_X + LEN_BYTES_Y + LEN_BYTES_Z
)
# TOTAL_STRUCTURE_LEN in the script's original context
TOTAL_STRUCTURE_LEN_VAR = LEN_START_END_DATA_SEGMENT + TOTAL_COMPONENTS_LEN


def extract_byte_sequences(txd_filepath,
                           unique_bytes_a_set, unique_bytes_b_set, unique_bytes_c_set,
                           unique_bytes_d_set, unique_bytes_e_set, unique_bytes_f_set,
                           unique_bytes_g_set, unique_bytes_h_set, unique_bytes_i_set,
                           unique_bytes_j_set, unique_bytes_k_set,
                           unique_bytes_l_set, unique_bytes_m_set, unique_bytes_n_set,
                           unique_bytes_o_set, unique_bytes_p_set, unique_bytes_q_set,
                           unique_bytes_r_set, unique_bytes_s_set, unique_bytes_t_set,
                           unique_bytes_u_set, unique_bytes_v_set, unique_bytes_w_set,
                           unique_bytes_x_set, unique_bytes_y_set, unique_bytes_z_set
                           ):
    """
    Scans the TXD file for the 12-byte pattern. If found, extracts subsequent
    byte sequences (BYTES_A to Z, where A starts with the pattern) and adds them to unique sets.
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
        # Find the initial 4-byte part of the 12-byte pattern
        found_idx = data.find(SEARCH_SIGNATURE_START, current_pos)
        if found_idx == -1:
            break # No more occurrences

        # Check if there's enough data for the full 12-byte pattern from found_idx
        if found_idx + FULL_PATTERN_LENGTH > len(data):
            current_pos = found_idx + 1 # Not enough data for the full pattern, advance search
            continue

        # Verify the trailing part of the 12-byte pattern
        actual_signature_end = data[found_idx + OFFSET_OF_EXPECTED_END : found_idx + OFFSET_OF_EXPECTED_END + LENGTH_OF_EXPECTED_END]
        if actual_signature_end != EXPECTED_SIGNATURE_END:
            current_pos = found_idx + 1 # Pattern's start found, but trailing part doesn't match. Advance search.
            continue

        # Full 12-byte pattern confirmed starting at found_idx.
        # Now check if there's enough data for all components A-Z, starting from found_idx.
        # TOTAL_STRUCTURE_LEN_VAR (which is sum(A-Z) because LEN_START_END_DATA_SEGMENT is 0)
        # determines the total length of components A-Z.
        if found_idx + TOTAL_COMPONENTS_LEN <= len(data):
            # BYTES_A starts at found_idx (since LEN_START_END_DATA_SEGMENT is 0)
            current_data_offset = found_idx + LEN_START_END_DATA_SEGMENT # This will be found_idx

            bytes_a = data[current_data_offset : current_data_offset + LEN_BYTES_A]; unique_bytes_a_set.add(bytes_a); current_data_offset += LEN_BYTES_A
            bytes_b = data[current_data_offset : current_data_offset + LEN_BYTES_B]; unique_bytes_b_set.add(bytes_b); current_data_offset += LEN_BYTES_B
            bytes_c = data[current_data_offset : current_data_offset + LEN_BYTES_C]; unique_bytes_c_set.add(bytes_c); current_data_offset += LEN_BYTES_C
            bytes_d = data[current_data_offset : current_data_offset + LEN_BYTES_D]; unique_bytes_d_set.add(bytes_d); current_data_offset += LEN_BYTES_D
            bytes_e = data[current_data_offset : current_data_offset + LEN_BYTES_E]; unique_bytes_e_set.add(bytes_e); current_data_offset += LEN_BYTES_E
            bytes_f = data[current_data_offset : current_data_offset + LEN_BYTES_F]; unique_bytes_f_set.add(bytes_f); current_data_offset += LEN_BYTES_F
            bytes_g = data[current_data_offset : current_data_offset + LEN_BYTES_G]; unique_bytes_g_set.add(bytes_g); current_data_offset += LEN_BYTES_G
            bytes_h = data[current_data_offset : current_data_offset + LEN_BYTES_H]; unique_bytes_h_set.add(bytes_h); current_data_offset += LEN_BYTES_H
            bytes_i = data[current_data_offset : current_data_offset + LEN_BYTES_I]; unique_bytes_i_set.add(bytes_i); current_data_offset += LEN_BYTES_I
            bytes_j = data[current_data_offset : current_data_offset + LEN_BYTES_J]; unique_bytes_j_set.add(bytes_j); current_data_offset += LEN_BYTES_J
            bytes_k = data[current_data_offset : current_data_offset + LEN_BYTES_K]; unique_bytes_k_set.add(bytes_k); current_data_offset += LEN_BYTES_K
            
            bytes_l = data[current_data_offset : current_data_offset + LEN_BYTES_L]; unique_bytes_l_set.add(bytes_l); current_data_offset += LEN_BYTES_L
            bytes_m = data[current_data_offset : current_data_offset + LEN_BYTES_M]; unique_bytes_m_set.add(bytes_m); current_data_offset += LEN_BYTES_M
            bytes_n = data[current_data_offset : current_data_offset + LEN_BYTES_N]; unique_bytes_n_set.add(bytes_n); current_data_offset += LEN_BYTES_N
            bytes_o = data[current_data_offset : current_data_offset + LEN_BYTES_O]; unique_bytes_o_set.add(bytes_o); current_data_offset += LEN_BYTES_O
            bytes_p = data[current_data_offset : current_data_offset + LEN_BYTES_P]; unique_bytes_p_set.add(bytes_p); current_data_offset += LEN_BYTES_P
            bytes_q = data[current_data_offset : current_data_offset + LEN_BYTES_Q]; unique_bytes_q_set.add(bytes_q); current_data_offset += LEN_BYTES_Q
            bytes_r = data[current_data_offset : current_data_offset + LEN_BYTES_R]; unique_bytes_r_set.add(bytes_r); current_data_offset += LEN_BYTES_R
            bytes_s = data[current_data_offset : current_data_offset + LEN_BYTES_S]; unique_bytes_s_set.add(bytes_s); current_data_offset += LEN_BYTES_S
            bytes_t = data[current_data_offset : current_data_offset + LEN_BYTES_T]; unique_bytes_t_set.add(bytes_t); current_data_offset += LEN_BYTES_T
            bytes_u = data[current_data_offset : current_data_offset + LEN_BYTES_U]; unique_bytes_u_set.add(bytes_u); current_data_offset += LEN_BYTES_U
            bytes_v = data[current_data_offset : current_data_offset + LEN_BYTES_V]; unique_bytes_v_set.add(bytes_v); current_data_offset += LEN_BYTES_V
            bytes_w = data[current_data_offset : current_data_offset + LEN_BYTES_W]; unique_bytes_w_set.add(bytes_w); current_data_offset += LEN_BYTES_W
            bytes_x = data[current_data_offset : current_data_offset + LEN_BYTES_X]; unique_bytes_x_set.add(bytes_x); current_data_offset += LEN_BYTES_X
            bytes_y = data[current_data_offset : current_data_offset + LEN_BYTES_Y]; unique_bytes_y_set.add(bytes_y); current_data_offset += LEN_BYTES_Y
            bytes_z = data[current_data_offset : current_data_offset + LEN_BYTES_Z]; unique_bytes_z_set.add(bytes_z); # current_data_offset += LEN_BYTES_Z (not needed for last one)
            
            structures_found_in_file += 1
        # else: Not enough data for all components A-Z following the pattern.
        
        current_pos = found_idx + 1 # Advance search position to find next potential pattern

    if structures_found_in_file > 0:
        print(Colours.GREEN, f"  Found and processed {structures_found_in_file} instance(s) of the {TOTAL_COMPONENTS_LEN}-byte data structure (A-Z) in '{os.path.basename(txd_filepath)}'.")
    else:
        print(Colours.BLUE, f"  No data structures matching the 12-byte pattern '{FULL_PATTERN_STR}' followed by all components A-Z were found in '{os.path.basename(txd_filepath)}'.")

    return structures_found_in_file

def main():
    description_text_lengths = (
        f"A:{LEN_BYTES_A}, B:{LEN_BYTES_B}, C:{LEN_BYTES_C}, D:{LEN_BYTES_D}, E:{LEN_BYTES_E}, "
        f"F:{LEN_BYTES_F}, G:{LEN_BYTES_G}, H:{LEN_BYTES_H}, I:{LEN_BYTES_I}, J:{LEN_BYTES_J}, K:{LEN_BYTES_K}, "
        f"L:{LEN_BYTES_L}, M:{LEN_BYTES_M}, N:{LEN_BYTES_N}, O:{LEN_BYTES_O}, P:{LEN_BYTES_P}, "
        f"Q:{LEN_BYTES_Q}, R:{LEN_BYTES_R}, S:{LEN_BYTES_S}, T:{LEN_BYTES_T}, U:{LEN_BYTES_U}, "
        f"V:{LEN_BYTES_V}, W:{LEN_BYTES_W}, X:{LEN_BYTES_X}, Y:{LEN_BYTES_Y}, Z:{LEN_BYTES_Z} bytes"
    )
    description_text = (
        f"Scans .txd files for structures starting with the specific {FULL_PATTERN_LENGTH}-byte signature ({FULL_PATTERN_STR}). "
        f"If the signature is found, it extracts twenty-six byte sequences (A-Z, where 'A' begins with the signature) "
        f"of lengths: {description_text_lengths}. "
        f"Logs unique sequences for each set (A-Z) to separate files."
    )
    parser = argparse.ArgumentParser(description=description_text)
    parser.add_argument("input_path", help="Path to a .txd file or a directory containing .txd files.")

    arg_configs = [
        ("o1", "output_log_A", f"reverse_engineering/Source/TODO/txd/unique_bytes_x16_A.log", f"BYTES_A ({LEN_BYTES_A} bytes)"),
        ("o2", "output_log_B", f"reverse_engineering/Source/TODO/txd/unique_bytes_x16_B.log", f"BYTES_B ({LEN_BYTES_B} bytes)"),
        # ... (rest of arg_configs are the same as original)
        ("o3", "output_log_C", f"reverse_engineering/Source/TODO/txd/unique_bytes_x16_C.log", f"BYTES_C ({LEN_BYTES_C} bytes)"),
        ("o4", "output_log_D", f"reverse_engineering/Source/TODO/txd/unique_bytes_x16_D.log", f"BYTES_D ({LEN_BYTES_D} bytes)"),
        ("o5", "output_log_E", f"reverse_engineering/Source/TODO/txd/unique_bytes_x16_E.log", f"BYTES_E ({LEN_BYTES_E} bytes)"),
        ("o6", "output_log_F", f"reverse_engineering/Source/TODO/txd/unique_bytes_x16_F.log", f"BYTES_F ({LEN_BYTES_F} bytes)"),
        ("o7", "output_log_G", f"reverse_engineering/Source/TODO/txd/unique_bytes_x16_G.log", f"BYTES_G ({LEN_BYTES_G} bytes)"),
        ("o8", "output_log_H", f"reverse_engineering/Source/TODO/txd/unique_bytes_x16_H.log", f"BYTES_H ({LEN_BYTES_H} bytes)"),
        ("o9", "output_log_I", f"reverse_engineering/Source/TODO/txd/unique_bytes_x16_I.log", f"BYTES_I ({LEN_BYTES_I} bytes)"),
        ("o10", "output_log_J", f"reverse_engineering/Source/TODO/txd/unique_bytes_x16_J.log", f"BYTES_J ({LEN_BYTES_J} bytes)"),
        ("o11", "output_log_K", f"reverse_engineering/Source/TODO/txd/unique_bytes_x16_K.log", f"BYTES_K ({LEN_BYTES_K} bytes)"),
        ("o12", "output_log_L", f"reverse_engineering/Source/TODO/txd/unique_bytes_x16_L.log", f"BYTES_L ({LEN_BYTES_L} bytes)"),
        ("o13", "output_log_M", f"reverse_engineering/Source/TODO/txd/unique_bytes_x16_M.log", f"BYTES_M ({LEN_BYTES_M} bytes)"),
        ("o14", "output_log_N", f"reverse_engineering/Source/TODO/txd/unique_bytes_x16_N.log", f"BYTES_N ({LEN_BYTES_N} bytes)"),
        ("o15", "output_log_O", f"reverse_engineering/Source/TODO/txd/unique_bytes_x16_O.log", f"BYTES_O ({LEN_BYTES_O} bytes)"),
        ("o16", "output_log_P", f"reverse_engineering/Source/TODO/txd/unique_bytes_x16_P.log", f"BYTES_P ({LEN_BYTES_P} bytes)"),
        ("o17", "output_log_Q", f"reverse_engineering/Source/TODO/txd/unique_bytes_x16_Q.log", f"BYTES_Q ({LEN_BYTES_Q} bytes)"),
        ("o18", "output_log_R", f"reverse_engineering/Source/TODO/txd/unique_bytes_x16_R.log", f"BYTES_R ({LEN_BYTES_R} bytes)"),
        ("o19", "output_log_S", f"reverse_engineering/Source/TODO/txd/unique_bytes_x16_S.log", f"BYTES_S ({LEN_BYTES_S} bytes)"),
        ("o20", "output_log_T", f"reverse_engineering/Source/TODO/txd/unique_bytes_x16_T.log", f"BYTES_T ({LEN_BYTES_T} bytes)"),
        ("o21", "output_log_U", f"reverse_engineering/Source/TODO/txd/unique_bytes_x16_U.log", f"BYTES_U ({LEN_BYTES_U} bytes)"),
        ("o22", "output_log_V", f"reverse_engineering/Source/TODO/txd/unique_bytes_x16_V.log", f"BYTES_V ({LEN_BYTES_V} bytes)"),
        ("o23", "output_log_W", f"reverse_engineering/Source/TODO/txd/unique_bytes_x16_W.log", f"BYTES_W ({LEN_BYTES_W} bytes)"),
        ("o24", "output_log_X", f"reverse_engineering/Source/TODO/txd/unique_bytes_x16_X.log", f"BYTES_X ({LEN_BYTES_X} bytes)"),
        ("o25", "output_log_Y", f"reverse_engineering/Source/TODO/txd/unique_bytes_x16_Y.log", f"BYTES_Y ({LEN_BYTES_Y} bytes)"),
        ("o26", "output_log_Z", f"reverse_engineering/Source/TODO/txd/unique_bytes_x16_Z.log", f"BYTES_Z ({LEN_BYTES_Z} bytes)"),
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
        "BYTES_I": set(), "BYTES_J": set(), "BYTES_K": set(),
        "BYTES_L": set(), "BYTES_M": set(), "BYTES_N": set(), "BYTES_O": set(),
        "BYTES_P": set(), "BYTES_Q": set(), "BYTES_R": set(), "BYTES_S": set(),
        "BYTES_T": set(), "BYTES_U": set(), "BYTES_V": set(), "BYTES_W": set(),
        "BYTES_X": set(), "BYTES_Y": set(), "BYTES_Z": set()
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
    print(Colours.CYAN, f"Searching for structures starting with the {FULL_PATTERN_LENGTH}-byte signature: {FULL_PATTERN_STR}")
    print(Colours.CYAN, f"If found, the following {TOTAL_COMPONENTS_LEN}-byte data components (A-Z) will be extracted.")


    for txd_file_path in txd_files_to_process:
        print(Colours.CYAN, f"\n--- Analyzing file: {os.path.basename(txd_file_path)} ---")
        structures_in_current_file = extract_byte_sequences(
            txd_file_path,
            master_unique_sets["BYTES_A"], master_unique_sets["BYTES_B"], master_unique_sets["BYTES_C"],
            master_unique_sets["BYTES_D"], master_unique_sets["BYTES_E"], master_unique_sets["BYTES_F"],
            master_unique_sets["BYTES_G"], master_unique_sets["BYTES_H"], master_unique_sets["BYTES_I"],
            master_unique_sets["BYTES_J"], master_unique_sets["BYTES_K"],
            master_unique_sets["BYTES_L"], master_unique_sets["BYTES_M"], master_unique_sets["BYTES_N"],
            master_unique_sets["BYTES_O"], master_unique_sets["BYTES_P"], master_unique_sets["BYTES_Q"],
            master_unique_sets["BYTES_R"], master_unique_sets["BYTES_S"], master_unique_sets["BYTES_T"],
            master_unique_sets["BYTES_U"], master_unique_sets["BYTES_V"], master_unique_sets["BYTES_W"],
            master_unique_sets["BYTES_X"], master_unique_sets["BYTES_Y"], master_unique_sets["BYTES_Z"]
        )

        if structures_in_current_file > 0:
            overall_structures_found += structures_in_current_file
        files_processed_count += 1

    print(Colours.CYAN, "\n--- Summary ---")
    print(Colours.CYAN, f"Attempted to process {len(txd_files_to_process)} .txd file(s).")
    print(Colours.CYAN, f"Files effectively scanned: {files_processed_count}.")
    print(Colours.CYAN, f"Total instances of the data structure (A-Z components) found following the signature: {overall_structures_found}.")
    
    lengths_map = {
        "BYTES_A": LEN_BYTES_A, "BYTES_B": LEN_BYTES_B, "BYTES_C": LEN_BYTES_C,
        "BYTES_D": LEN_BYTES_D, "BYTES_E": LEN_BYTES_E, "BYTES_F": LEN_BYTES_F,
        "BYTES_G": LEN_BYTES_G, "BYTES_H": LEN_BYTES_H, "BYTES_I": LEN_BYTES_I,
        "BYTES_J": LEN_BYTES_J, "BYTES_K": LEN_BYTES_K,
        "BYTES_L": LEN_BYTES_L, "BYTES_M": LEN_BYTES_M, "BYTES_N": LEN_BYTES_N,
        "BYTES_O": LEN_BYTES_O, "BYTES_P": LEN_BYTES_P, "BYTES_Q": LEN_BYTES_Q,
        "BYTES_R": LEN_BYTES_R, "BYTES_S": LEN_BYTES_S, "BYTES_T": LEN_BYTES_T,
        "BYTES_U": LEN_BYTES_U, "BYTES_V": LEN_BYTES_V, "BYTES_W": LEN_BYTES_W,
        "BYTES_X": LEN_BYTES_X, "BYTES_Y": LEN_BYTES_Y, "BYTES_Z": LEN_BYTES_Z
    }
    
    log_details_for_summary = [
        ("BYTES_A", "output_log_A", f"{LEN_BYTES_A}b, starts with the 12-byte signature"),
        ("BYTES_B", "output_log_B", f"{LEN_BYTES_B}b after BYTES_A"),
        ("BYTES_C", "output_log_C", f"{LEN_BYTES_C}b after BYTES_B"),
        # ... (Descriptions for D-Z can remain similar, e.g., "after BYTES_C", etc.)
        ("BYTES_D", "output_log_D", f"{LEN_BYTES_D}b after BYTES_C"),
        ("BYTES_E", "output_log_E", f"{LEN_BYTES_E}b after BYTES_D"),
        ("BYTES_F", "output_log_F", f"{LEN_BYTES_F}b after BYTES_E"),
        ("BYTES_G", "output_log_G", f"{LEN_BYTES_G}b after BYTES_F"),
        ("BYTES_H", "output_log_H", f"{LEN_BYTES_H}b after BYTES_G"),
        ("BYTES_I", "output_log_I", f"{LEN_BYTES_I}b after BYTES_H (texture name block)"),
        ("BYTES_J", "output_log_J", f"{LEN_BYTES_J}b after BYTES_I"),
        ("BYTES_K", "output_log_K", f"{LEN_BYTES_K}b after BYTES_J"),
        ("BYTES_L", "output_log_L", f"{LEN_BYTES_L}b after BYTES_K"),
        ("BYTES_M", "output_log_M", f"{LEN_BYTES_M}b after BYTES_L"),
        ("BYTES_N", "output_log_N", f"{LEN_BYTES_N}b after BYTES_M"),
        ("BYTES_O", "output_log_O", f"{LEN_BYTES_O}b after BYTES_N"),
        ("BYTES_P", "output_log_P", f"{LEN_BYTES_P}b after BYTES_O"),
        ("BYTES_Q", "output_log_Q", f"{LEN_BYTES_Q}b after BYTES_P"),
        ("BYTES_R", "output_log_R", f"{LEN_BYTES_R}b after BYTES_Q"),
        ("BYTES_S", "output_log_S", f"{LEN_BYTES_S}b after BYTES_R"),
        ("BYTES_T", "output_log_T", f"{LEN_BYTES_T}b after BYTES_S"),
        ("BYTES_U", "output_log_U", f"{LEN_BYTES_U}b after BYTES_T"),
        ("BYTES_V", "output_log_V", f"{LEN_BYTES_V}b after BYTES_U"),
        ("BYTES_W", "output_log_W", f"{LEN_BYTES_W}b after BYTES_V"),
        ("BYTES_X", "output_log_X", f"{LEN_BYTES_X}b after BYTES_W"),
        ("BYTES_Y", "output_log_Y", f"{LEN_BYTES_Y}b after BYTES_X"),
        ("BYTES_Z", "output_log_Z", f"{LEN_BYTES_Z}b after BYTES_Y"),
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
                    lf.write(f"# {len(byte_set)} unique {byte_len}-byte sequences for {setName} ({setDescription.lower()}).\n")
                    lf.write(f"# Extracted from structures identified by the leading {FULL_PATTERN_LENGTH}-byte pattern: {FULL_PATTERN_STR}.\n")
                    if setName == "BYTES_A":
                        lf.write(f"# {setName} itself starts with this {FULL_PATTERN_LENGTH}-byte pattern.\n")
                    else:
                        lf.write(f"# {setName} follows prior data components within such structures.\n")
                    for seq in sorted(list(byte_set)): 
                        lf.write(f"{seq.hex()}\n")
                print(Colours.GREEN, f"Successfully wrote unique {setName} sequences to '{log_path}'.")
            except IOError as e:
                print(Colours.RED, f"Error writing to {setName} log file '{log_path}': {e}")
        else:
            print(Colours.YELLOW, f"No unique {setName} sequences were found.")
    
    if all_sets_empty and overall_structures_found == 0 :
        print(Colours.YELLOW, f"No instances of structures starting with the pattern '{FULL_PATTERN_STR}' were found in any file.")

if __name__ == '__main__':
    main()
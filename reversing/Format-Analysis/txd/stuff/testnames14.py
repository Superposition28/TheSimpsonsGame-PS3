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


# 16 00 00 00 C4 54 15 00 2D 00 02 1C 01 00 00 00 04 00 00 00 2D 00 02 1C 01 00 0A 00 15 00 00 00 9C 54 15 00 2D 00 02 1C 01 00 00 00 70 54 15 00 2D 00 02 1C 00 00 00 0A 00 00 11 06 64 6F 64 5F 77 61 74 65 72 5F 6F 76 65 72 6C 61 79 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 80 00 18 28 01 86 02 00 02 00 20 06 04 01 00 00 10 00
# 14 00 00 00 2D 00 02 1C 2F EA 00 00 08 00 00 00 2D 00 02 1C 0D 58 C7 CC DD B3 32 66 15 00 00 00 98 54 05 00 2D 00 02 1C 01 00 00 00 6C 54 05 00 2D 00 02 1C 00 00 00 0A 00 00 11 06 64 6F 64 5F 77 61 74 65 72 5F 63 6F 6C 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 80 00 18 28 01 86 01 00 01 00 20 05 04 01 00 00 04 00

# Original component lengths A-K
LEN_BYTES_A = 20
LEN_BYTES_B = 8
LEN_BYTES_C = 4 # 15000000
LEN_BYTES_D = 4
LEN_BYTES_E = 8 # 2d00021c01000000
LEN_BYTES_F = 4
LEN_BYTES_G = 8 # 2d00021c0000000a
LEN_BYTES_H = 4 # indicates the four possible values before the name of the textures - 00001102 - 00001106 - 00003302 - 00003306
LEN_BYTES_I = 66 # this is the block of bytes that contains the name of the textures
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

# Total length of the full structure: START_END_DATA_SEGMENT + A + B + ... + Z
TOTAL_STRUCTURE_LEN = (LEN_START_END_DATA_SEGMENT +
                       LEN_BYTES_A + LEN_BYTES_B + LEN_BYTES_C + LEN_BYTES_D +
                       LEN_BYTES_E + LEN_BYTES_F + LEN_BYTES_G + LEN_BYTES_H +
                       LEN_BYTES_I + LEN_BYTES_J + LEN_BYTES_K +
                       LEN_BYTES_L + LEN_BYTES_M + LEN_BYTES_N + LEN_BYTES_O +
                       LEN_BYTES_P + LEN_BYTES_Q + LEN_BYTES_R + LEN_BYTES_S +
                       LEN_BYTES_T + LEN_BYTES_U + LEN_BYTES_V + LEN_BYTES_W +
                       LEN_BYTES_X + LEN_BYTES_Y + LEN_BYTES_Z)

def extract_byte_sequences(txd_filepath,
                           unique_bytes_a_set, unique_bytes_b_set, unique_bytes_c_set,
                           unique_bytes_d_set, unique_bytes_e_set, unique_bytes_f_set,
                           unique_bytes_g_set, unique_bytes_h_set, unique_bytes_i_set,
                           unique_bytes_j_set, unique_bytes_k_set,
                           # New sets for L-Z
                           unique_bytes_l_set, unique_bytes_m_set, unique_bytes_n_set,
                           unique_bytes_o_set, unique_bytes_p_set, unique_bytes_q_set,
                           unique_bytes_r_set, unique_bytes_s_set, unique_bytes_t_set,
                           unique_bytes_u_set, unique_bytes_v_set, unique_bytes_w_set,
                           unique_bytes_x_set, unique_bytes_y_set, unique_bytes_z_set
                           ):
    """
    Scans the entire TXD file for START_END_DATA_SEGMENT. If found, extracts subsequent
    byte sequences (BYTES_A to Z with specified lengths) and adds them to their respective unique sets.
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
            bytes_k = data[current_offset : current_offset + LEN_BYTES_K]; unique_bytes_k_set.add(bytes_k); current_offset += LEN_BYTES_K
            
            # Extracting new byte sequences L-Z
            bytes_l = data[current_offset : current_offset + LEN_BYTES_L]; unique_bytes_l_set.add(bytes_l); current_offset += LEN_BYTES_L
            bytes_m = data[current_offset : current_offset + LEN_BYTES_M]; unique_bytes_m_set.add(bytes_m); current_offset += LEN_BYTES_M
            bytes_n = data[current_offset : current_offset + LEN_BYTES_N]; unique_bytes_n_set.add(bytes_n); current_offset += LEN_BYTES_N
            bytes_o = data[current_offset : current_offset + LEN_BYTES_O]; unique_bytes_o_set.add(bytes_o); current_offset += LEN_BYTES_O
            bytes_p = data[current_offset : current_offset + LEN_BYTES_P]; unique_bytes_p_set.add(bytes_p); current_offset += LEN_BYTES_P
            bytes_q = data[current_offset : current_offset + LEN_BYTES_Q]; unique_bytes_q_set.add(bytes_q); current_offset += LEN_BYTES_Q
            bytes_r = data[current_offset : current_offset + LEN_BYTES_R]; unique_bytes_r_set.add(bytes_r); current_offset += LEN_BYTES_R
            bytes_s = data[current_offset : current_offset + LEN_BYTES_S]; unique_bytes_s_set.add(bytes_s); current_offset += LEN_BYTES_S
            bytes_t = data[current_offset : current_offset + LEN_BYTES_T]; unique_bytes_t_set.add(bytes_t); current_offset += LEN_BYTES_T
            bytes_u = data[current_offset : current_offset + LEN_BYTES_U]; unique_bytes_u_set.add(bytes_u); current_offset += LEN_BYTES_U
            bytes_v = data[current_offset : current_offset + LEN_BYTES_V]; unique_bytes_v_set.add(bytes_v); current_offset += LEN_BYTES_V
            bytes_w = data[current_offset : current_offset + LEN_BYTES_W]; unique_bytes_w_set.add(bytes_w); current_offset += LEN_BYTES_W
            bytes_x = data[current_offset : current_offset + LEN_BYTES_X]; unique_bytes_x_set.add(bytes_x); current_offset += LEN_BYTES_X
            bytes_y = data[current_offset : current_offset + LEN_BYTES_Y]; unique_bytes_y_set.add(bytes_y); current_offset += LEN_BYTES_Y
            bytes_z = data[current_offset : current_offset + LEN_BYTES_Z]; unique_bytes_z_set.add(bytes_z); current_offset += LEN_BYTES_Z
            
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
        f"F:{LEN_BYTES_F}, G:{LEN_BYTES_G}, H:{LEN_BYTES_H}, I:{LEN_BYTES_I}, J:{LEN_BYTES_J}, K:{LEN_BYTES_K}, "
        f"L:{LEN_BYTES_L}, M:{LEN_BYTES_M}, N:{LEN_BYTES_N}, O:{LEN_BYTES_O}, P:{LEN_BYTES_P}, "
        f"Q:{LEN_BYTES_Q}, R:{LEN_BYTES_R}, S:{LEN_BYTES_S}, T:{LEN_BYTES_T}, U:{LEN_BYTES_U}, "
        f"V:{LEN_BYTES_V}, W:{LEN_BYTES_W}, X:{LEN_BYTES_X}, Y:{LEN_BYTES_Y}, Z:{LEN_BYTES_Z} bytes"
    )
    description_text = (
        f"Scans .txd files for a specific {LEN_START_END_DATA_SEGMENT}-byte signature ({START_END_DATA_SEGMENT[:8].hex()}...), "
        f"then extracts twenty-six subsequent byte sequences (A-Z with varying lengths: "
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
        ("o11", "output_log_K", f"reverse_engineering/Source/TODO/txd/unique_bytes_K.log", f"BYTES_K ({LEN_BYTES_K} bytes) after BYTES_J"),
        ("o12", "output_log_L", f"reverse_engineering/Source/TODO/txd/unique_bytes_L.log", f"BYTES_L ({LEN_BYTES_L} bytes) after BYTES_K"),
        ("o13", "output_log_M", f"reverse_engineering/Source/TODO/txd/unique_bytes_M.log", f"BYTES_M ({LEN_BYTES_M} bytes) after BYTES_L"),
        ("o14", "output_log_N", f"reverse_engineering/Source/TODO/txd/unique_bytes_N.log", f"BYTES_N ({LEN_BYTES_N} bytes) after BYTES_M"),
        ("o15", "output_log_O", f"reverse_engineering/Source/TODO/txd/unique_bytes_O.log", f"BYTES_O ({LEN_BYTES_O} bytes) after BYTES_N"),
        ("o16", "output_log_P", f"reverse_engineering/Source/TODO/txd/unique_bytes_P.log", f"BYTES_P ({LEN_BYTES_P} bytes) after BYTES_O"),
        ("o17", "output_log_Q", f"reverse_engineering/Source/TODO/txd/unique_bytes_Q.log", f"BYTES_Q ({LEN_BYTES_Q} bytes) after BYTES_P"),
        ("o18", "output_log_R", f"reverse_engineering/Source/TODO/txd/unique_bytes_R.log", f"BYTES_R ({LEN_BYTES_R} bytes) after BYTES_Q"),
        ("o19", "output_log_S", f"reverse_engineering/Source/TODO/txd/unique_bytes_S.log", f"BYTES_S ({LEN_BYTES_S} bytes) after BYTES_R"),
        ("o20", "output_log_T", f"reverse_engineering/Source/TODO/txd/unique_bytes_T.log", f"BYTES_T ({LEN_BYTES_T} bytes) after BYTES_S"),
        ("o21", "output_log_U", f"reverse_engineering/Source/TODO/txd/unique_bytes_U.log", f"BYTES_U ({LEN_BYTES_U} bytes) after BYTES_T"),
        ("o22", "output_log_V", f"reverse_engineering/Source/TODO/txd/unique_bytes_V.log", f"BYTES_V ({LEN_BYTES_V} bytes) after BYTES_U"),
        ("o23", "output_log_W", f"reverse_engineering/Source/TODO/txd/unique_bytes_W.log", f"BYTES_W ({LEN_BYTES_W} bytes) after BYTES_V"),
        ("o24", "output_log_X", f"reverse_engineering/Source/TODO/txd/unique_bytes_X.log", f"BYTES_X ({LEN_BYTES_X} bytes) after BYTES_W"),
        ("o25", "output_log_Y", f"reverse_engineering/Source/TODO/txd/unique_bytes_Y.log", f"BYTES_Y ({LEN_BYTES_Y} bytes) after BYTES_X"),
        ("o26", "output_log_Z", f"reverse_engineering/Source/TODO/txd/unique_bytes_Z.log", f"BYTES_Z ({LEN_BYTES_Z} bytes) after BYTES_Y"),
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
        # New sets for L-Z
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
    print(Colours.CYAN, f"Searching for {TOTAL_STRUCTURE_LEN}-byte structures starting with signature: {START_END_DATA_SEGMENT.hex()}")

    for txd_file_path in txd_files_to_process:
        print(Colours.CYAN, f"\n--- Analyzing file: {os.path.basename(txd_file_path)} ---")
        structures_in_current_file = extract_byte_sequences(
            txd_file_path,
            master_unique_sets["BYTES_A"], master_unique_sets["BYTES_B"], master_unique_sets["BYTES_C"],
            master_unique_sets["BYTES_D"], master_unique_sets["BYTES_E"], master_unique_sets["BYTES_F"],
            master_unique_sets["BYTES_G"], master_unique_sets["BYTES_H"], master_unique_sets["BYTES_I"],
            master_unique_sets["BYTES_J"], master_unique_sets["BYTES_K"],
            # Pass new sets for L-Z
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
    print(Colours.CYAN, f"Files scanned: {files_processed_count}.")
    print(Colours.CYAN, f"Total instances of the full {TOTAL_STRUCTURE_LEN}-byte structure found: {overall_structures_found}.")
    
    lengths_map = {
        "BYTES_A": LEN_BYTES_A, "BYTES_B": LEN_BYTES_B, "BYTES_C": LEN_BYTES_C,
        "BYTES_D": LEN_BYTES_D, "BYTES_E": LEN_BYTES_E, "BYTES_F": LEN_BYTES_F,
        "BYTES_G": LEN_BYTES_G, "BYTES_H": LEN_BYTES_H, "BYTES_I": LEN_BYTES_I,
        "BYTES_J": LEN_BYTES_J, "BYTES_K": LEN_BYTES_K,
        # New lengths for L-Z
        "BYTES_L": LEN_BYTES_L, "BYTES_M": LEN_BYTES_M, "BYTES_N": LEN_BYTES_N,
        "BYTES_O": LEN_BYTES_O, "BYTES_P": LEN_BYTES_P, "BYTES_Q": LEN_BYTES_Q,
        "BYTES_R": LEN_BYTES_R, "BYTES_S": LEN_BYTES_S, "BYTES_T": LEN_BYTES_T,
        "BYTES_U": LEN_BYTES_U, "BYTES_V": LEN_BYTES_V, "BYTES_W": LEN_BYTES_W,
        "BYTES_X": LEN_BYTES_X, "BYTES_Y": LEN_BYTES_Y, "BYTES_Z": LEN_BYTES_Z
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
        ("BYTES_K", "output_log_K", f"{LEN_BYTES_K}b after BYTES_J"),
        # New log details for L-Z
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
    main()

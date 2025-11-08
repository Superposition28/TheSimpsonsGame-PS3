#!/usr/bin/env python3
import struct
import os
import re
import argparse
import sys
import time

from printer import print, colours


def extract_sequences_from_file(txd_filepath, unique_sequences_set):
    """
    Scans a TXD file for a specific signature and logs the subsequent 4 bytes.

    Args:
        txd_filepath (str): Path to the .txd file.
        unique_sequences_set (set): A set to store unique 4-byte sequences found.

    Returns:
        int: The number of times the signature was found in this file.
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

    texture_name_signature = b'\x16\x00\x00\x00'
    signature_len = len(texture_name_signature)

    bytes_to_extract = 12
    sequences_found_in_file = 0

    current_pos = 0
    while current_pos < 12:
        found_idx = data.find(texture_name_signature, current_pos)
        if found_idx == -1:
            break  # No more signatures found

        sequences_found_in_file += 1
        sequence_start_offset = found_idx

        if sequence_start_offset + bytes_to_extract <= len(data):
            four_byte_sequence = data[sequence_start_offset : sequence_start_offset + bytes_to_extract]
            unique_sequences_set.add(four_byte_sequence)
            # Optional: print(Colours.GREEN, f"  Found signature at 0x{found_idx:X}, next 4 bytes: {four_byte_sequence.hex()}")
        else:
            print(Colours.YELLOW, f"  Found signature at 0x{found_idx:X}, but not enough data for 4 subsequent bytes.")

        current_pos = found_idx + signature_len # Start search for next signature after the current one's data
                                                # Or use `found_idx + 1` if signatures can overlap

    if sequences_found_in_file > 0:
        print(Colours.GREEN, f"  Found {sequences_found_in_file} signature(s) in '{os.path.basename(txd_filepath)}'.")
    else:
        print(Colours.BLUE, f"  No '{texture_name_signature.hex()}' signatures found in '{os.path.basename(txd_filepath)}'.")

    return sequences_found_in_file

def main():
    parser = argparse.ArgumentParser(description="Extract unique 4-byte sequences following a specific signature in .txd files.")
    parser.add_argument("input_path", help="Path to a .txd file or a directory containing .txd files.")
    parser.add_argument("-l", "--log_file", default="unique_4byte_sequences.log",
                        help="File to log unique four-byte sequences found (default: unique_4byte_sequences.log).")

    # The -o argument is no longer used for outputting textures, so it's removed.
    # If you still need a general output directory for other purposes, you can add it back.
    # For this specific request, only the log file for sequences is needed.

    args = parser.parse_args()

    input_path_abs = os.path.abspath(args.input_path)
    log_file_path = args.log_file

    overall_signatures_found = 0
    files_processed_count = 0

    master_unique_sequences = set()

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
            for file in files:
                if file.lower().endswith(".txd"):
                    txd_files_to_process.append(os.path.join(root, file))
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

    for txd_file_path in txd_files_to_process:
        print(Colours.CYAN, f"\n--- Processing file: {os.path.basename(txd_file_path)} ---")
        signatures_in_current_file = extract_sequences_from_file(txd_file_path, master_unique_sequences)

        if signatures_in_current_file > 0 : # or some other condition to count a file as "processed"
            overall_signatures_found += signatures_in_current_file
        files_processed_count += 1

    print(Colours.CYAN, "\n--- Summary ---")
    print(Colours.CYAN, f"Attempted to process {len(txd_files_to_process)} .txd file(s).")
    print(Colours.CYAN, f"Files fully scanned: {files_processed_count}.")
    print(Colours.CYAN, f"Total instances of the signature found across all files: {overall_signatures_found}.")

    if master_unique_sequences:
        print(Colours.GREEN, f"Found {len(master_unique_sequences)} unique 4-byte sequences following the signature.")
        try:
            with open(log_file_path, "w") as lf:
                lf.write(f"# Unique {len(master_unique_sequences)} four-byte sequences found after signature {b'\\x2D\\x00\\x02\\x1C\\x00\\x00\\x00\\x0A'.hex()}:\n")
                for seq in sorted(list(master_unique_sequences)): # Sort for consistent output
                    lf.write(f"{seq.hex()}\n")
            print(Colours.GREEN, f"Successfully wrote unique sequences to '{log_file_path}'.")
        except IOError as e:
            print(Colours.RED, f"Error writing to log file '{log_file_path}': {e}")
    else:
        print(Colours.YELLOW, "No unique 4-byte sequences were found after the signature in any file.")

if __name__ == '__main__':
    main()
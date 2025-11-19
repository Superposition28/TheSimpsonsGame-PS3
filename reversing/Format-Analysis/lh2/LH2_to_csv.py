#!/usr/bin/env python3
# The Simpsons Game NewGen .LH2 parser to CSV

# Usage:
#   script.py "string_file.LH2"

# Output:
#   Generates "string_file.LH2.csv"

# Modified by samarixum from original script by Edness (v1.1)

import argparse
import os
import csv

def decode_lh2(path):
    def read_int():
        return int.from_bytes(file.read(0x4), "big")

    def read_str():
        # Reads byte by byte until null terminator, decodes as Windows-1252
        return "".join(iter(lambda: file.read(0x1).decode("1252"), "\x00"))

    if not os.path.exists(path):
        print(f"Error: File '{path}' not found.")
        return

    with open(path, "rb") as file:
        # Check Magic Number
        if file.read(0x4) != b"2HCL":
            print("Error: Not a valid .LH2 file!")
            return

        # Check File Size integrity
        if read_int() != os.path.getsize(path):
            print("Error: File size check failed!")
            return

        # Read Header Info
        file.seek(0x10)
        entries = read_int()
        tables = read_int()

        # Skip reserved/runtime pointers (8 bytes at 0x18)
        file.seek(0x20)

        # Read String IDs (Hashes)
        ids = [read_int() for x in range(entries)]

        # Read Offset Pointers
        # The pointers are arranged sequentially by table (language/column)
        ptr = [list() for x in range(tables)]
        for lst in ptr:
            lst.extend([read_int() for x in range(entries)])

        # Read Strings based on offsets
        txt = [list() for x in range(tables)]
        for i, lst in enumerate(ptr):
            for ofs in lst:
                file.seek(ofs)
                txt[i].append(read_str())

    # Prepare CSV Output
    output_path = f"{path}.csv"

    # Determine column structure
    # If there is more than 1 table, the last table is usually the internal String Label
    columns_count = tables - 1 if tables > 1 else tables

    with open(output_path, "w", encoding="UTF-8", newline='') as csvfile:
        writer = csv.writer(csvfile)

        # Create Header Row
        header = ["String ID"]
        if tables > 1:
            header.append("String Label")

        for x in range(columns_count):
            header.append(f"Language {x}")

        writer.writerow(header)

        # Write Data Rows
        for i, id_val in enumerate(ids):
            row = [f"{id_val:08X}"] # Format ID as Hex string

            if tables > 1:
                # If multiple tables, the last one is the label
                row.append(txt[-1][i])

            # Add the localized text columns
            for x in range(columns_count):
                row.append(txt[x][i])

            writer.writerow(row)

    print(f"Success: Output written to {output_path}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Converts The Simpsons Game (PS3/X360) .LH2 files to CSV.")
    parser.add_argument("path", type=str, help="Path to the .LH2 file to decode.")

    args = parser.parse_args()
    decode_lh2(args.path)
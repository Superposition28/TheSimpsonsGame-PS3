

import struct
import sys
import os

def parse_sfo_to_toml(file_path):
    with open(file_path, "rb") as f:
        # Read the 20-byte header
        header = f.read(20)
        if len(header) < 20:
            raise ValueError("File is too small to be a valid SFO.")

        # magic and version are Big Endian; the rest are Little Endian
        magic, version = struct.unpack(">4sI", header[:8])
        if magic != b"\x00PSF":
            raise ValueError("Invalid magic number. Not a PARAM.SFO file.")

        key_table_start, data_table_start, tables_entries = struct.unpack("<III", header[8:20])

        # Parse index table entries
        index_table = []
        for _ in range(tables_entries):
            entry_data = f.read(16)
            k_offs, d_fmt, d_len, d_max, d_offs = struct.unpack("<HHIII", entry_data)
            index_table.append({
                "key_offset": k_offs,
                "data_fmt": d_fmt,
                "data_len": d_len,
                "data_max_len": d_max,
                "data_offset": d_offs
            })

        parsed_data = {}

        # Extract keys and values mapped by the index table
        for entry in index_table:
            # 1. Extract Key
            f.seek(key_table_start + entry["key_offset"])
            key_bytes = bytearray()
            while True:
                b = f.read(1)
                # Keys are NULL terminated
                if not b or b == b'\x00':
                    break
                key_bytes.extend(b)
            key = key_bytes.decode('utf-8')

            # 2. Extract Data
            f.seek(data_table_start + entry["data_offset"])
            raw_data = f.read(entry["data_len"]) # Only read the used bytes

            # 3. Interpret Data based on data_fmt
            # fmt 04 04 -> int32 (Read as Little Endian 0x0404)
            if entry["data_fmt"] == 0x0404:
                value = struct.unpack("<I", raw_data[:4])[0]

            # fmt 04 02 -> utf8, NULL terminated (Read as Little Endian 0x0204)
            elif entry["data_fmt"] == 0x0204:
                value = raw_data.rstrip(b'\x00').decode('utf-8', errors='replace')

            # fmt 04 00 -> utf8-S, NOT NULL terminated / reserved binary (Read as Little Endian 0x0004)
            elif entry["data_fmt"] == 0x0004:
                try:
                    value = raw_data.decode('utf-8')
                    # Fallback if the payload has excessive unprintable characters (e.g. binary blob)
                    if sum(1 for c in value if not c.isprintable() and c not in '\n\r\t') > 5:
                        raise ValueError("Binary blob detected")
                except (UnicodeDecodeError, ValueError):
                    # Data that cannot be interpreted is dumped as raw hexadecimal
                    value = "RAW_HEX:" + raw_data.hex().upper()
            else:
                value = "RAW_HEX:" + raw_data.hex().upper()

            parsed_data[key] = value

    return parsed_data

def generate_toml(parsed_data):
    toml_lines = []
    for key, value in parsed_data.items():
        if isinstance(value, int):
            toml_lines.append(f'{key} = {value}')
        else:
            escaped_val = value.replace('\\', '\\\\').replace('"', '\\"')
            if '\n' in escaped_val:
                toml_lines.append(f'{key} = """\n{escaped_val}\n"""')
            else:
                toml_lines.append(f'{key} = "{escaped_val}"')
    return "\n".join(toml_lines)

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python sfo_parser.py <path_to_PARAM.SFO>")
        sys.exit(1)

    sfo_path = sys.argv[1]
    try:
        data = parse_sfo_to_toml(sfo_path)
        toml_output = generate_toml(data)

        output_path = sfo_path + ".toml"
        with open(output_path, "w", encoding="utf-8") as out_f:
            out_f.write(toml_output)

        print(f"Successfully converted {sfo_path} -> {output_path}")
    except Exception as e:
        print(f"Error parsing SFO: {e}")


import struct
import os
import sys
import json
import argparse
import glob

# --- CONFIGURATION ---
# Magic signature for validation (MMdl)
MAGIC_MMDL = b'MMdl'

def fix_corrupted_data(raw_data):
    """
    Attempts to fix specific corruption where 0x00 became 0x20 (space)
    and some bytes were UTF-8 encoded.
    """
    try:
        # First, try to reverse UTF-8 encoding artifacts
        decoded = raw_data.decode('utf-8', errors='replace')
        data = decoded.encode('latin-1', errors='ignore')
    except:
        data = raw_data

    # The specific corruption seen in your files: Null bytes (0x00) became Spaces (0x20)
    return data.replace(b'\x20', b'\x00')

def read_string(data, offset):
    """Reads a null-terminated string from the data buffer."""
    if offset < 0 or offset >= len(data):
        return ""
    end = data.find(b'\x00', offset)
    if end == -1:
        return ""
    try:
        return data[offset:end].decode('latin-1')
    except:
        return "<invalid_string>"

class MMdlParser:
    def __init__(self, filepath):
        self.filepath = filepath
        self.valid = False
        self.header = {}
        self.nodes = []
        self.assets = [] # Keep tracking assets for the JSON output
        self.raw_data = b''
        
        try:
            with open(filepath, 'rb') as f:
                self.raw_data = f.read()
                
            # Check magic
            if self.raw_data[0:4] != MAGIC_MMDL:
                # Try fixing corruption
                self.raw_data = fix_corrupted_data(self.raw_data)
            
            if self.raw_data[0:4] == MAGIC_MMDL:
                self.valid = True
                self.parse()
            else:
                pass
                
        except Exception as e:
            print(f"Error reading {filepath}: {e}")

    def parse(self):
        data = self.raw_data
        # 1. Header (Big Endian)
        self.header['version'] = struct.unpack('>I', data[4:8])[0]
        self.header['file_size'] = struct.unpack('>I', data[8:12])[0]
        self.header['bbox'] = struct.unpack('>6f', data[16:40])
        
        # 2. Offsets
        offsets = struct.unpack('>6I', data[44:68])
        
        node_start = offsets[1]
        attr_start = offsets[2]
        value_start = offsets[4]
        string_table_start = offsets[5] if offsets[5] > 0 else len(data) 

        # 3. Parse Nodes (Chunk 2)
        current = node_start
        while current < attr_start and current + 32 <= len(data):
            vals = struct.unpack('>8I', data[current:current+32])
            
            node_name = read_string(data, vals[1])
            inst_name = read_string(data, vals[2])
            
            node = {
                'type': node_name,
                'name': inst_name,
                'attributes': []
            }
            self.nodes.append(node)
            
            # Collect potential asset references from names
            if '.dff' in inst_name or '.glb' in inst_name:
                self.assets.append(inst_name)
                
            current += 32

        # 4. Parse Attributes (Chunk 3)
        current = attr_start
        while current < value_start and current + 16 <= len(data):
            vals = struct.unpack('>4I', data[current:current+16])
            attr_name = read_string(data, vals[0])
            if not attr_name: attr_name = read_string(data, vals[1]) # Fallback
            
            # If the Value field looks like a string pointer, try to read it
            val_str = ""
            if vals[1] > string_table_start and vals[1] < len(data):
                val_str = read_string(data, vals[1])
                if '.dff' in val_str or '.glb' in val_str:
                    self.assets.append(val_str)

            # If value looks like a float pointer
            val_float = 0.0
            if vals[1] >= value_start and vals[1] < string_table_start:
                try:
                    val_float = struct.unpack('>f', data[vals[1]:vals[1]+4])[0]
                except: pass

            if attr_name:
                if self.nodes:
                    self.nodes[-1]['attributes'].append({
                        'key': attr_name,
                        'val_int': vals[1],
                        'val_str': val_str,
                        'val_float': val_float
                    })
            
            current += 16

    def to_json(self):
        data = {
            "header": self.header,
            "nodes": self.nodes,
            "referenced_assets": list(set(self.assets)) # Included here since meta file is gone
        }
        return json.dumps(data, indent=4)

def process_path(path):
    if os.path.isfile(path):
        files = [path]
    elif os.path.isdir(path):
        files = glob.glob(os.path.join(path, '**', '*.meta.xml'), recursive=True)
    else:
        print(f"Invalid path: {path}")
        return

    print(f"Processing {len(files)} files...")

    count = 0
    for f_path in files:
        parser = MMdlParser(f_path)
        
        if parser.valid:
            base_name = f_path
            # Only output single JSON file
            json_path = base_name + ".json"
            
            with open(json_path, "w", encoding="utf-8") as f:
                f.write(parser.to_json())
            
            print(f"Converted: {json_path}")
            count += 1
        else:
            # Skip invalid files silently
            pass
            
    print(f"Done. Converted {count} files.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="The Simpsons Game (PS3) Meta Converter")
    parser.add_argument("input", help="Input file or directory path")
    args = parser.parse_args()
    
    process_path(args.input)
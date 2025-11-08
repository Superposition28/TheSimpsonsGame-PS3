import os
import struct
import math
from pathlib import Path
import collections

# --- Configuration ---
NODE_FORMAT = '>ffffffffiiiiiiii' # BE: 8 floats, 8 ints
NODE_SIZE = 64
LUMP_DIR_OFFSET = 0x10 # Start of the lump directory entries
LUMP_ENTRY_SIZE = 8    # Size of one lump directory entry (offset, length)
TARGET_LUMP_ID = 3     # The lump containing the nodes (0-based index)

# Output Limiting
MAX_NODES_TO_DETAIL = 15 # Max nodes to show full details for (start and end)
MAX_LEAVES_TO_DETAIL = 20 # Max leaves to show int fields for

# --- End Configuration ---

# Define field names based on the corrected structure
NODE_FIELD_NAMES = [
    'plane_nx', 'plane_ny', 'plane_nz', 'plane_d',
    'bbox_tx0', 'bbox_tx1', 'bbox_tx2', 'bbox_tx3', # BBox / Tex?
    'flags',    # Int 1
    'child_f',  # Int 2
    'child_b',  # Int 3
    'unk1',     # Int 4
    'unk2',     # Int 5
    'unk3',     # Int 6
    'unk4',     # Int 7
    'unk5'      # Int 8
]

def parse_node(data_chunk):
    """Unpacks a 64-byte chunk into a node dictionary."""
    if len(data_chunk) != NODE_SIZE:
        return None
    try:
        unpacked_data = struct.unpack(NODE_FORMAT, data_chunk)
        return dict(zip(NODE_FIELD_NAMES, unpacked_data))
    except struct.error:
        return None

def analyze_bsp_nodes(filepath):
    """Analyzes Lump 3 node structures in a BSP file."""
    print(f"\n--- Analyzing Node Structure: {filepath.name} ---")
    nodes = []
    lump_offset = -1
    lump_length = -1
    trailing_data = None
    num_nodes = 0

    try:
        with open(filepath, 'rb') as f:
            file_size = f.seek(0, os.SEEK_END)

            # 1. Find Lump 3 Offset/Length
            lump_entry_offset = LUMP_DIR_OFFSET + TARGET_LUMP_ID * LUMP_ENTRY_SIZE
            if lump_entry_offset + LUMP_ENTRY_SIZE > file_size:
                print("[!] Error: File too small for Lump 3 directory entry.")
                return

            f.seek(lump_entry_offset)
            lump_info = f.read(LUMP_ENTRY_SIZE)
            lump_offset, lump_length = struct.unpack('>II', lump_info)

            print(f"[*] Found Potential Lump {TARGET_LUMP_ID}: Offset=0x{lump_offset:X} ({lump_offset}), Length=0x{lump_length:X} ({lump_length})")

            # Basic validation
            if lump_offset + lump_length > file_size or lump_length < 0 or lump_offset < 0:
                 print(f"[!] Error: Lump {TARGET_LUMP_ID} offset/length invalid or out of bounds.")
                 print(f"    Lump Offset: {lump_offset}, Lump Length: {lump_length}, File Size: {file_size}")
                 # Attempt to provide more context if possible
                 if lump_offset + lump_length > file_size:
                      print("    Reason: Lump extends beyond file end.")
                 if lump_length == 0:
                     print("    Reason: Lump has zero length.")

                 # Check if previous lumps look okay to see if file is truncated
                 if TARGET_LUMP_ID > 0:
                     try:
                         prev_lump_entry_offset = LUMP_DIR_OFFSET + (TARGET_LUMP_ID - 1) * LUMP_ENTRY_SIZE
                         f.seek(prev_lump_entry_offset)
                         prev_lump_info = f.read(LUMP_ENTRY_SIZE)
                         prev_offset, prev_length = struct.unpack('>II', prev_lump_info)
                         print(f"[*] Previous Lump ({TARGET_LUMP_ID-1}): Offset=0x{prev_offset:X}, Length=0x{prev_length:X}")
                         if prev_offset + prev_length > file_size:
                              print("    [!] Previous lump also seems out of bounds - file might be truncated or lump dir corrupt.")
                     except Exception as e:
                         print(f"    Could not read previous lump info: {e}")

                 return # Stop analysis for this file if lump is invalid


            if lump_length == 0:
                 print(f"[*] Warning: Lump {TARGET_LUMP_ID} has zero length. No nodes to parse.")
                 return

            # 2. Read and Parse Nodes
            f.seek(lump_offset)
            lump_data = f.read(lump_length)

            num_nodes = lump_length // NODE_SIZE
            trailing_bytes_count = lump_length % NODE_SIZE
            print(f"[*] Expecting {num_nodes} nodes ({lump_length} bytes / {NODE_SIZE} bytes/node).")

            if trailing_bytes_count > 0:
                print(f"[!] Warning: Lump size ({lump_length}) is not a multiple of node size ({NODE_SIZE}).")
                print(f"    Found {trailing_bytes_count} trailing bytes after {num_nodes} full nodes.")
                trailing_data = lump_data[num_nodes * NODE_SIZE:]
                lump_data = lump_data[:num_nodes * NODE_SIZE] # Only parse full nodes

            for i in range(num_nodes):
                node_chunk = lump_data[i * NODE_SIZE : (i + 1) * NODE_SIZE]
                parsed = parse_node(node_chunk)
                if parsed:
                    nodes.append(parsed)
                else:
                    print(f"[!] Error parsing node index {i}.")
                    # Optionally break or continue based on preference
                    # break

            print(f"[*] Successfully parsed {len(nodes)} nodes.")

    except FileNotFoundError:
        print(f"[!] Error: File not found: {filepath}")
        return
    except Exception as e:
        print(f"[!] An error occurred during file reading/parsing: {e}")
        return

    if not nodes:
        print("[*] No nodes were parsed.")
        return

    # 3. Analyze Parsed Nodes
    print(f"\n--- Node Analysis (Showing first/last {MAX_NODES_TO_DETAIL // 2}, Leaves) ---")
    leaf_nodes_indices = []
    pointer_interpretations = collections.defaultdict(lambda: collections.defaultdict(int)) # interpretations[type][hypothesis] = count

    for i, node in enumerate(nodes):
        # --- Child Pointer Analysis ---
        child_f = node['child_f']
        child_b = node['child_b']
        is_leaf = False # Tentative flag

        # Check Front Child
        if child_f < 0:
            interpretation_f = f"Leaf? (~{child_f}={hex(~child_f)} or -({child_f}+1)={-(child_f+1)})"
            pointer_interpretations['Front']['Negative (Leaf?)'] += 1
        elif child_f == 0 and child_b == 0: # Special case like zone13 node 4?
            interpretation_f = "Zero (Leaf?)"
            pointer_interpretations['Front']['Zero (Leaf?)'] += 1
            is_leaf = True # Assume zero children means leaf for now
        else: # Positive child_f
            pointer_interpretations['Front']['Positive'] += 1
            hypotheses = []
            # H1: Byte offset from lump start? (Must be multiple of NODE_SIZE and within lump)
            if child_f % NODE_SIZE == 0 and 0 <= child_f < lump_length:
                hypotheses.append(f"Byte Offset (-> Node {child_f // NODE_SIZE}?)")
                pointer_interpretations['Front']['Hypothesis: Byte Offset'] += 1
            # H2: Node Index? (Must be valid index)
            if 0 <= child_f < num_nodes:
                hypotheses.append(f"Node Index?")
                pointer_interpretations['Front']['Hypothesis: Node Index'] += 1
            # H3: Maybe offset from current node start? (node_offset + child_f)
            # Requires node_offset, less direct to check here

            interpretation_f = f"Value={child_f}. Fits: {', '.join(hypotheses) if hypotheses else 'None?'}"

        # Check Back Child (similar logic)
        if child_b < 0:
            interpretation_b = f"Leaf? (~{child_b}={hex(~child_b)} or -({child_b}+1)={-(child_b+1)})"
            pointer_interpretations['Back']['Negative (Leaf?)'] += 1
            if child_f >= 0: is_leaf = False # If front is non-neg, likely not leaf even if back is neg? (Depends on format)
        elif child_f == 0 and child_b == 0:
             interpretation_b = "Zero (Leaf?)"
             pointer_interpretations['Back']['Zero (Leaf?)'] += 1
             # is_leaf already set True
        else: # Positive child_b
             pointer_interpretations['Back']['Positive'] += 1
             hypotheses = []
             if child_b % NODE_SIZE == 0 and 0 <= child_b < lump_length:
                 hypotheses.append(f"Byte Offset (-> Node {child_b // NODE_SIZE}?)")
                 pointer_interpretations['Back']['Hypothesis: Byte Offset'] += 1
             if 0 <= child_b < num_nodes:
                 hypotheses.append(f"Node Index?")
                 pointer_interpretations['Back']['Hypothesis: Node Index'] += 1
             interpretation_b = f"Value={child_b}. Fits: {', '.join(hypotheses) if hypotheses else 'None?'}"

        if child_f < 0 or child_b < 0: # If either pointer is negative, consider it potentially points to leaf info
            is_leaf = True

        if is_leaf:
            leaf_nodes_indices.append(i)

        # --- Reporting (Limited Detail) ---
        show_detail = (i < MAX_NODES_TO_DETAIL // 2) or (i >= num_nodes - MAX_NODES_TO_DETAIL // 2)

        if show_detail:
            print(f"\n--- Node {i} ---{' (Potential LEAF)' if is_leaf else ''}")

            # Plane Analysis
            nx, ny, nz, d = node['plane_nx'], node['plane_ny'], node['plane_nz'], node['plane_d']
            try:
                normal_mag = math.sqrt(nx*nx + ny*ny + nz*nz)
                norm_info = f"Normal Mag={normal_mag:.3f}{' (Normalized!)' if math.isclose(normal_mag, 1.0, abs_tol=1e-5) else ''}"
            except ValueError: # Handle potential negative values under sqrt if data is weird
                 norm_info = "Normal Mag=ERR"
            print(f"  Plane    : N=({nx:+.3f}, {ny:+.3f}, {nz:+.3f}), D={d:+.3f} | {norm_info}")

            # BBox/Tex Floats
            bbtx = [node['bbox_tx0'], node['bbox_tx1'], node['bbox_tx2'], node['bbox_tx3']]
            print(f"  BBox/Tex?: ({bbtx[0]:.3f}, {bbtx[1]:.3f}, {bbtx[2]:.3f}, {bbtx[3]:.3f})")

            # Children Pointers
            print(f"  Child F  : {interpretation_f}")
            print(f"  Child B  : {interpretation_b}")

            # Integers
            flags = node['flags']
            ints = [node['unk1'], node['unk2'], node['unk3'], node['unk4'], node['unk5']]
            print(f"  Ints     : Flags={flags}, Unk1-5={ints}")


    # --- Summarize Pointer Analysis ---
    print("\n--- Child Pointer Analysis Summary ---")
    for pointer_type in ['Front', 'Back']:
        print(f"[*] {pointer_type} Pointers:")
        if not pointer_interpretations[pointer_type]:
            print("    (None found or analyzed)")
            continue
        for category, count in pointer_interpretations[pointer_type].items():
             if not category.startswith('Hypothesis:'):
                 print(f"    - Type '{category}': {count} occurrences")
        # Print hypothesis counts separately
        hyp_counts = {k.replace('Hypothesis: ',''):v for k,v in pointer_interpretations[pointer_type].items() if k.startswith('Hypothesis:')}
        if hyp_counts:
            print(f"    - Positive Pointer Hypothesis Counts:")
            for hyp, count in hyp_counts.items():
                 print(f"        - Fits '{hyp}': {count} occurrences")


    # --- Leaf Node Analysis ---
    print("\n--- Leaf Node Analysis ---")
    print(f"[*] Found {len(leaf_nodes_indices)} potential leaf nodes (ChildF<=0 or ChildB<=0).")
    if leaf_nodes_indices:
        print(f"[*] Showing Integer fields for first {MAX_LEAVES_TO_DETAIL} potential leaves:")
        for idx in leaf_nodes_indices[:MAX_LEAVES_TO_DETAIL]:
            leaf_node = nodes[idx]
            flags = leaf_node['flags']
            child_f = leaf_node['child_f'] # Show child values for context
            child_b = leaf_node['child_b']
            ints = [leaf_node['unk1'], leaf_node['unk2'], leaf_node['unk3'], leaf_node['unk4'], leaf_node['unk5']]
            print(f"  - Leaf Node {idx:<4}: Children=({child_f}, {child_b}), Flags={flags}, Unk1-5={ints}")
        if len(leaf_nodes_indices) > MAX_LEAVES_TO_DETAIL:
            print(f"  ... ({len(leaf_nodes_indices) - MAX_LEAVES_TO_DETAIL} more potential leaves not detailed)")

    # --- Trailing Data ---
    if trailing_data:
        print("\n--- Trailing Data ---")
        print(f"[*] Found {len(trailing_data)} bytes after the last full node in Lump {TARGET_LUMP_ID}.")
        print(f"  Hex: {trailing_data.hex()}")


    # --- Optional: Tree Traversal ---
    # print("\n--- Basic Tree Traversal (from Node 0) ---")
    # traverse_bsp_tree(nodes, 0, lump_offset, num_nodes, lump_length) # Call traversal if implemented


# --- (Optional) Tree Traversal Function ---
# Placeholder - requires solid interpretation of child pointers first
# def traverse_bsp_tree(nodes, node_index, lump_start_offset, num_nodes, lump_length, visited=None, indent="", max_depth=10):
#     if visited is None: visited = set()
#     if node_index in visited or len(visited) > num_nodes * 2 or max_depth <= 0: # Basic cycle/limit checks
#         print(f"{indent}[!] Traversal limit reached or cycle detected at Node {node_index}")
#         return
#     if not (0 <= node_index < num_nodes):
#          print(f"{indent}[!] Invalid node index: {node_index}")
#          return

#     visited.add(node_index)
#     node = nodes[node_index]
#     print(f"{indent}Node {node_index}")

#     # Front Child
#     child_f = node['child_f']
#     print(f"{indent}  Front: {child_f}", end="")
#     if child_f < 0:
#         print(f" -> LEAF (~{child_f}={hex(~child_f)})")
#     elif child_f == 0 and node['child_b'] == 0:
#          print(" -> LEAF (Zero)")
#     # --- !!! Add logic here based on chosen pointer interpretation !!! ---
#     # Example if Byte Offset:
#     elif child_f % NODE_SIZE == 0 and 0 <= child_f < lump_length:
#          next_index_f = child_f // NODE_SIZE
#          print(f" -> Node {next_index_f}")
#          traverse_bsp_tree(nodes, next_index_f, lump_start_offset, num_nodes, lump_length, visited, indent + "    ", max_depth - 1)
#     else:
#          print(" -> ? (Unknown/Invalid)")


#     # Back Child (similar logic)
#     child_b = node['child_b']
#     print(f"{indent}  Back : {child_b}", end="")
#     if child_b < 0:
#         print(f" -> LEAF (~{child_b}={hex(~child_b)})")
#     elif child_b == 0 and node['child_f'] == 0:
#         print(" -> LEAF (Zero)")
#     # --- !!! Add logic here based on chosen pointer interpretation !!! ---
#     # Example if Byte Offset:
#     elif child_b % NODE_SIZE == 0 and 0 <= child_b < lump_length:
#          next_index_b = child_b // NODE_SIZE
#          print(f" -> Node {next_index_b}")
#          traverse_bsp_tree(nodes, next_index_b, lump_start_offset, num_nodes, lump_length, visited, indent + "    ", max_depth - 1)
#     else:
#          print(" -> ? (Unknown/Invalid)")


# --- Main Execution ---
def main():
    script_dir = Path(__file__).parent # Get the directory of the current script
    print(f"[*] Searching for .bsp files recursively in: {script_dir}")

    bsp_files = list(script_dir.rglob("*.bsp")) # Find all .bsp files recursively

    if not bsp_files:
        print("\n[!] No .bsp files found in the script's directory or subdirectories.")
        return

    print(f"[*] Found {len(bsp_files)} .bsp file(s).")

    found_files = 0
    for filepath in bsp_files: # Iterate through found files
        if filepath.is_file(): # Ensure it's actually a file
            found_files += 1
            analyze_bsp_nodes(filepath)
        # No need for an else here as rglob should only return files/dirs matching pattern

    if found_files == 0: # Should technically not happen if bsp_files list was not empty, but good practice
        print("\n[!] No valid .bsp files were processed (this might indicate an issue).")
    else:
        print("\n--- Analysis Complete ---")

if __name__ == "__main__":
    main()
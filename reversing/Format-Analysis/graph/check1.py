"""
graph_validator.py

A script to validate The Simpsons Game .graph files based on
reverse-engineered format rules.

It checks for:
1.  Expected static "magic" byte patterns at specific offsets.
2.  Structural integrity by comparing header counts (node_count)
    with header offsets (node_offset, node_end).
"""

from __future__ import annotations

import argparse
import os
import struct
import sys
from dataclasses import dataclass, field
from typing import Dict, Iterable, List, Optional, Tuple
from concurrent.futures import ProcessPoolExecutor, as_completed
from collections import Counter

# --- Configuration ---

# Target file extension
TARGET_SUFFIXES = (".graph",)

# Define the static patterns to search for.
# These are the "universal indicators" we expect in all files.
# pattern: hex string, wildcards `**` allowed.
# expected_offset: The exact byte offset where this pattern must start.
# required: If True, the file fails validation if this pattern is missing
#           or at the wrong offset.
@dataclass
class PatternDef:
    name: str
    pattern: str
    expected_offset: int
    required: bool = True
    note: str = ""

# These patterns are derived from your analysis and the hex dumps.
# All data is Big-Endian.
COMPILED_PATTERNS: List[PatternDef] = [
    PatternDef(
        name="Header Magic 1",
        pattern="00 00 00 10",
        expected_offset=0x08,
        note="Expected version/magic number",
    ),
    PatternDef(
        name="Header Node Offset (Standard)",
        pattern="00 00 00 94",
        expected_offset=0x20,
        required=False, # Set to False, we'll just warn if it's different
        note="Standard node data offset. Will warn if not 0x94.",
    ),
    PatternDef(
        name="Header Sentinel",
        pattern="FF FF 00 00",
        expected_offset=0x4C,
        note="Expected sentinel bytes",
    ),
    PatternDef(
        name="Header Magic 2",
        pattern="6D 00 00 00",
        expected_offset=0x78,
        note="Expected type/version magic",
    ),
]

# --- Core Logic ---

@dataclass
class FileResult:
    """Stores the analysis result for a single file."""
    path: str
    status: str = "PASS"  # PASS, WARN, FAIL
    patterns_found: List[Tuple[PatternDef, int]] = field(default_factory=list)
    patterns_missing: List[PatternDef] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)
    notes: List[str] = field(default_factory=list)

    def update_status(self, new_status: str):
        if new_status == "FAIL":
            self.status = "FAIL"
        elif new_status == "WARN" and self.status == "PASS":
            self.status = "WARN"

def find_pattern(content: bytes, pattern_hex: str) -> Iterable[int]:
    """Finds all occurrences of a hex pattern (with wildcards) in content."""
    pattern_bytes = []
    for part in pattern_hex.split():
        if part == "**":
            pattern_bytes.append(None)
        else:
            pattern_bytes.append(int(part, 16))
    
    scan_len = len(pattern_bytes)
    for i in range(len(content) - scan_len + 1):
        found = True
        for j in range(scan_len):
            if pattern_bytes[j] is not None and pattern_bytes[j] != content[i + j]:
                found = False
                break
        if found:
            yield i

def process_file(path: str) -> FileResult:
    """
    Analyzes a single file for pattern compliance and structural integrity.
    """
    res = FileResult(path=path)
    
    try:
        with open(path, "rb") as f:
            content = f.read()
    except IOError as e:
        res.update_status("FAIL")
        res.errors.append(f"IOError: {e}")
        return res

    if len(content) < 0x80: # Header size
        res.update_status("FAIL")
        res.errors.append(f"File too small. Size: {len(content)} bytes. Expected > 128 bytes.")
        return res

    # --- 1. Static Pattern Validation (from COMPILED_PATTERNS) ---
    found_patterns_map: Dict[str, List[int]] = {p.name: [] for p in COMPILED_PATTERNS}
    for p in COMPILED_PATTERNS:
        matches = list(find_pattern(content, p.pattern))
        if matches:
            for offset in matches:
                found_patterns_map[p.name].append(offset)
                if offset == p.expected_offset:
                    res.patterns_found.append((p, offset))
        
        # Check for failures
        if not matches:
            if p.required:
                res.update_status("FAIL")
                res.errors.append(f"Required pattern '{p.name}' ({p.pattern}) not found.")
                res.patterns_missing.append(p)
        elif p.expected_offset is not None and p.expected_offset not in matches:
            msg = f"Pattern '{p.name}' found, but not at expected offset 0x{p.expected_offset:X}. Found at: {[f'0x{m:X}' for m in matches]}"
            if p.required:
                res.update_status("FAIL")
                res.errors.append(msg)
            else:
                res.update_status("WARN")
                res.notes.append(msg)

    # --- 2. Structural Validation (Dynamic check for variance) ---
    try:
        # Read header fields (Big-Endian)
        # 0x0C: [u16 node_count] [u16 other_count]
        word_0c = struct.unpack_from('>I', content, 0x0C)[0]
        node_count = (word_0c >> 16) & 0xFFFF
        
        # 0x20: [u32 node_offset]
        node_offset = struct.unpack_from('>I', content, 0x20)[0]
        
        # 0x24: [u32 node_end]
        node_end = struct.unpack_from('>I', content, 0x24)[0]

        res.notes.append(f"Header OK: NodeCount={node_count}, NodeOffset=0x{node_offset:X}, NodeEnd=0x{node_end:X}")

        # Check for non-standard node offset
        if node_offset != 0x94 and "Header Node Offset (Standard)" in found_patterns_map:
            if not found_patterns_map["Header Node Offset (Standard)"]:
                res.update_status("WARN")
                res.notes.append(f"NodeOffset is 0x{node_offset:X} (not standard 0x94).")

        # The key variance check
        if node_count > 0:
            if node_end <= node_offset:
                res.update_status("FAIL")
                res.errors.append(f"Structural integrity FAIL: NodeEnd (0x{node_end:X}) is not after NodeOffset (0x{node_offset:X}).")
            else:
                bytes_in_node_array = node_end - node_offset
                expected_bytes = node_count * 32  # 32 bytes per node
                
                if bytes_in_node_array != expected_bytes:
                    res.update_status("FAIL")
                    res.errors.append(f"Structural integrity FAIL: Node array size mismatch.")
                    res.errors.append(f"  Header implies {node_count} nodes * 32 bytes/node = {expected_bytes} bytes.")
                    res.errors.append(f"  Offsets imply (0x{node_end:X} - 0x{node_offset:X}) = {bytes_in_node_array} bytes.")
                else:
                    res.notes.append(f"Structural integrity PASS: {node_count} nodes * 32 bytes = {expected_bytes} bytes.")

        elif node_count == 0:
            res.notes.append("File reports 0 nodes. Skipping structural size check.")
        
        if node_end > len(content):
            res.update_status("FAIL")
            res.errors.append(f"Structural integrity FAIL: NodeEnd offset 0x{node_end:X} is outside file bounds (0x{len(content):X}).")

    except struct.error as e:
        res.update_status("FAIL")
        res.errors.append(f"Structural integrity FAIL: Could not unpack header. File may be truncated. Error: {e}")
    except IndexError:
        # This can happen if file is too small for struct.unpack_from
        res.update_status("FAIL")
        res.errors.append(f"Structural integrity FAIL: File is too small to read header fields.")
        
    return res

def main():
    parser = argparse.ArgumentParser(description="Validate binary .graph files.")
    parser.add_argument("directory", help="Directory to scan for .graph files.")
    args = parser.parse_args()

    if not os.path.isdir(args.directory):
        print(f"Error: Not a directory: {args.directory}", file=sys.stderr)
        sys.exit(1)

    target_files = []
    for root, _, files in os.walk(args.directory):
        for file in files:
            if file.endswith(TARGET_SUFFIXES):
                target_files.append(os.path.join(root, file))

    if not target_files:
        print("No .graph files found in that directory.")
        sys.exit(0)

    print(f"Found {len(target_files)} files. Starting analysis...\n")

    results: List[FileResult] = []
    counts = Counter(PASS=0, WARN=0, FAIL=0)

    # Use ProcessPoolExecutor to run checks in parallel
    with ProcessPoolExecutor() as executor:
        futures = {executor.submit(process_file, path): path for path in target_files}
        for i, future in enumerate(as_completed(futures), 1):
            res = future.result()
            results.append(res)
            counts[res.status] += 1
            print(f"[{i}/{len(target_files)}] {res.status}: {os.path.basename(res.path)}")

    print("\n--- Validation Summary ---")
    print(f"PASS: {counts['PASS']}")
    print(f"WARN: {counts['WARN']}")
    print(f"FAIL: {counts['FAIL']}")

    if counts["FAIL"] > 0:
        print("\n--- FAILURES ---")
        for res in sorted(results, key=lambda x: x.path):
            if res.status == "FAIL":
                print(f"\n[FAIL] {res.path}")
                for err in res.errors:
                    print(f"  - {err}")

    if counts["WARN"] > 0:
        print("\n--- WARNINGS ---")
        for res in sorted(results, key=lambda x: x.path):
            if res.status == "WARN":
                print(f"\n[WARN] {res.path}")
                for note in res.notes:
                    if "FAIL" not in note: # Don't re-print structural passes
                        print(f"  - {note}")

if __name__ == "__main__":
    main()

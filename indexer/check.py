#!/usr/bin/env python3
import argparse
import hashlib
import os
import sqlite3
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple


# Hardcoded list of directory roots to compare.
# These are *relative to the script's location*.
VERSION_ROOTS = [
    r"EngineApps\Games\TheSimpsonsGame-PS3\GameFiles\STROUT-EU_Full-audio_og-notRenamed",
    r"EngineApps\Games\TheSimpsonsGame-PS3\GameFiles\STROUT-EU_Full-audio_reorg-isRenamed",
    r"EngineApps\Games\TheSimpsonsGame-PS3\GameFiles\STROUT-EU_Full-audio_reorg-notRenamed",
]

# Path to the rename mapping database
RENAME_MAP_DB = r"EngineApps\Games\TheSimpsonsGame-PS3\config\RenameMap.db"


def load_rename_mappings(script_dir: Path) -> Dict[str, str]:
    """Load the rename mappings from the SQLite database.
    Returns a dict mapping old_name -> new_name.
    """
    db_path = (script_dir / RENAME_MAP_DB).resolve()
    if not db_path.exists():
        return {}
    
    mappings = {}
    try:
        conn = sqlite3.connect(str(db_path))
        cursor = conn.cursor()
        cursor.execute("SELECT old_name, new_name FROM rename_mappings")
        for old_name, new_name in cursor.fetchall():
            mappings[old_name.lower()] = new_name
            # Also store reverse mapping for bidirectional lookup
            mappings[new_name.lower()] = old_name
        conn.close()
    except Exception as e:
        print(f"Warning: Could not load rename mappings: {e}")
    
    return mappings


def normalize_path(rel_path: Path, root_path: Path, rename_map: Dict[str, str]) -> Path:
    """Normalize a relative path by converting base folder names using the rename map.
    If the root is marked as 'isRenamed', convert new names to old names.
    Otherwise, keep the path as-is but enable matching with renamed versions.
    """
    parts = rel_path.parts
    if not parts:
        return rel_path
    
    # Check if this root uses renamed folders
    is_renamed_root = "-isRenamed" in str(root_path)
    
    # The first part is the base folder that might be renamed
    base_folder = parts[0].lower()
    
    if is_renamed_root:
        # Root uses new names, normalize to old names
        if base_folder in rename_map:
            normalized_base = rename_map[base_folder]
            return Path(normalized_base, *parts[1:])
    else:
        # Root uses old names, keep as-is (already normalized)
        pass
    
    return rel_path


def compute_hash(path: Path, algo: str = "sha256", chunk_size: int = 1024 * 1024) -> str:
    """Compute a hash of the file contents."""
    h = hashlib.new(algo)
    with path.open("rb") as f:
        while True:
            chunk = f.read(chunk_size)
            if not chunk:
                break
            h.update(chunk)
    return h.hexdigest()


def is_subpath(child: Path, parent: Path) -> bool:
    """Return True if 'child' is inside 'parent' (or equal)."""
    try:
        child.relative_to(parent)
        return True
    except ValueError:
        return False


def find_source_root(source: Path, roots: List[Path]) -> Optional[Path]:
    """
    Given the absolute path to the source file and a list of root directories,
    find which root contains the source file. If multiple, pick the deepest one.
    """
    containing_roots: List[Tuple[int, Path]] = []
    for root in roots:
        if is_subpath(source, root):
            # depth = how many parts the root has; deeper = more specific
            containing_roots.append((len(root.parts), root))
    if not containing_roots:
        return None
    # Pick the root with greatest depth
    containing_roots.sort(key=lambda t: t[0], reverse=True)
    return containing_roots[0][1]


def collect_files(root: Path) -> List[Path]:
    """Recursively collect all files under a root."""
    files: List[Path] = []
    for dirpath, _, filenames in os.walk(root):
        d = Path(dirpath)
        for name in filenames:
            files.append(d / name)
    return files


def analyze(
    source_file: Path,
    script_dir: Path,
    hash_algo: str = "sha256",
) -> List[Dict[str, Any]]:
    """
    Main comparison logic.

    Returns a list of dicts; each dict describes one candidate file and how it
    compares to the source file.
    """
    # Load rename mappings
    rename_map = load_rename_mappings(script_dir)
    
    # Resolve roots relative to the script directory
    abs_roots = [ (script_dir / r).resolve() for r in VERSION_ROOTS ]
    abs_roots = [r for r in abs_roots if r.exists() and r.is_dir()]

    if not abs_roots:
        raise RuntimeError("None of the VERSION_ROOTS directories exist. Please adjust VERSION_ROOTS.")

    source_file = source_file.resolve()

    if not source_file.is_file():
        raise FileNotFoundError(f"Source file does not exist or is not a file: {source_file}")

    # Determine which root contains the source file
    src_root = find_source_root(source_file, abs_roots)
    if src_root is None:
        raise RuntimeError(
            f"Source file {source_file} is not inside any of the configured roots:\n"
            + "\n".join(str(r) for r in abs_roots)
        )

    src_rel_from_root = source_file.relative_to(src_root)
    src_normalized_path = normalize_path(src_rel_from_root, src_root, rename_map)
    src_rel_parts = src_normalized_path.parts
    src_tail_3 = src_rel_parts[-3:] if len(src_rel_parts) >= 3 else src_rel_parts
    src_name = source_file.name
    src_size = source_file.stat().st_size
    src_mtime = source_file.stat().st_mtime
    src_hash = compute_hash(source_file, algo=hash_algo)

    results: List[Dict[str, Any]] = []

    for root in abs_roots:
        all_files = collect_files(root)
        for path in all_files:
            # Skip the file if it's literally the same path as the source
            if path == source_file:
                continue

            rel_from_root = path.relative_to(root)
            normalized_path = normalize_path(rel_from_root, root, rename_map)
            rel_parts = normalized_path.parts
            tail_3 = rel_parts[-3:] if len(rel_parts) >= 3 else rel_parts

            size = path.stat().st_size
            mtime = path.stat().st_mtime

            # Optional: only bother hashing files with the same size as the source.
            # (You can change this if you want to hash everything.)
            hash_val = None
            same_size = (size == src_size)
            if same_size:
                hash_val = compute_hash(path, algo=hash_algo)

            same_filename = (path.name == src_name)
            # Compare using normalized paths
            same_rel_path = (normalized_path == src_normalized_path)
            same_tail_3 = (tail_3 == src_tail_3)
            same_hash = (hash_val == src_hash) if hash_val is not None else False

            # --- NEW: skip files that have absolutely no similarity at all ---
            # Note: filename is not used as a match criterion (too generic)
            if not (same_rel_path or same_tail_3 or same_size or same_hash):
                continue

            candidate = {
                "root": str(root),
                "path": str(path),
                "rel_path": str(rel_from_root),
                "filename": path.name,
                "size": size,
                "mtime": mtime,
                "hash": hash_val,
                "same_filename": same_filename,
                "same_rel_path": same_rel_path,
                "same_tail_3": same_tail_3,
                "same_size": same_size,
                "same_hash": same_hash,
            }
            results.append(candidate)

    return results


def print_report(source_file: Path, results: List[Dict[str, Any]]):
    """Pretty-print the comparison results."""
    print(f"Source file: {source_file}")
    print("=" * 80)

    if not results:
        print("No other files found in the configured roots.")
        return

    # Get the source root and rel_path
    src_root = None
    src_rel_path = None
    src_hash = None
    for r in results:
        if Path(r['path']) == source_file:
            continue
    
    # Find source file info from first result (they all share the source comparison data)
    if results:
        # Extract source info by comparing with first result
        src_rel_path = results[0].get('rel_path') if results[0].get('same_rel_path') else None
        src_hash = results[0]['hash'] if results[0]['same_hash'] else None
        # Get hash from an exact match
        for r in results:
            if r['same_hash']:
                src_hash = r['hash']
                break
    
    # Group results by root
    by_root: Dict[str, List[Dict[str, Any]]] = {}
    for r in results:
        root = r['root']
        if root not in by_root:
            by_root[root] = []
        by_root[root].append(r)
    
    # Find duplicates in source root (same hash as source)
    source_root_files = [r for r in results if r['same_hash']]
    source_hash = source_root_files[0]['hash'] if source_root_files else None
    
    # Group source duplicates by hash
    duplicates_in_source: Dict[str, List[Dict[str, Any]]] = {}
    for r in source_root_files:
        h = r['hash']
        if h not in duplicates_in_source:
            duplicates_in_source[h] = []
        duplicates_in_source[h].append(r)
    
    print(f"\n{'='*80}")
    print(f"ANALYSIS BY VERSION ROOT")
    print(f"{'='*80}")
    
    for root_path, files in sorted(by_root.items()):
        root_name = Path(root_path).name
        print(f"\n{'─'*80}")
        print(f"Root: {root_name}")
        print(f"Path: {root_path}")
        print(f"{'─'*80}")
        
        # Separate by match type
        exact_path_match = [f for f in files if f['same_rel_path'] and f['same_hash']]
        exact_hash_diff_path = [f for f in files if f['same_hash'] and not f['same_rel_path']]
        similar_path_diff_hash = [f for f in files if f['same_rel_path'] and not f['same_hash']]
        other_matches = [f for f in files if not f['same_rel_path'] and not f['same_hash']]
        
        if exact_path_match:
            print(f"\n  ✓ EXACT MATCH (same path + same hash):")
            for f in exact_path_match:
                print(f"    → {f['rel_path']}")
                print(f"      Hash: {f['hash']}")
        
        if exact_hash_diff_path:
            print(f"\n  ⚠ DUPLICATES (same hash, different path):")
            for f in exact_hash_diff_path:
                print(f"    → {f['rel_path']}")
                print(f"      Hash: {f['hash']}")
        
        if similar_path_diff_hash:
            print(f"\n  ⚠ PATH MATCH (same path, different hash):")
            for f in similar_path_diff_hash:
                print(f"    → {f['rel_path']}")
                print(f"      Hash: {f['hash']}")
        
        if other_matches:
            print(f"\n  ≈ OTHER SIMILARITIES ({len(other_matches)} files):")
            for f in other_matches[:3]:  # Show first 3
                matches = []
                if f['same_tail_3']:
                    matches.append("tail_3")
                if f['same_size']:
                    matches.append("size")
                print(f"    → {f['rel_path']}")
                print(f"      Matches: {', '.join(matches)}")
            if len(other_matches) > 3:
                print(f"    ... and {len(other_matches) - 3} more")
    
    # Summary section
    print(f"\n{'='*80}")
    print(f"CROSS-ROOT SUMMARY")
    print(f"{'='*80}")
    
    exact_matches_by_root = {}
    for root_path, files in by_root.items():
        root_name = Path(root_path).name
        exact = [f for f in files if f['same_rel_path'] and f['same_hash']]
        if exact:
            exact_matches_by_root[root_name] = exact[0]['rel_path']
    
    if len(exact_matches_by_root) >= 2:
        print(f"\n✓ Found exact matches across {len(exact_matches_by_root)} roots:")
        for root_name, rel_path in sorted(exact_matches_by_root.items()):
            print(f"  • {root_name}: {rel_path}")
    else:
        print(f"\n⚠ Exact matches found in only {len(exact_matches_by_root)} root(s)")
    
    # Check for duplicates
    all_hashes = {}
    for r in results:
        if r['hash']:
            h = r['hash']
            if h not in all_hashes:
                all_hashes[h] = []
            all_hashes[h].append(r)
    
    duplicates = {h: files for h, files in all_hashes.items() if len(files) > 1}
    if duplicates:
        print(f"\n⚠ Found {len(duplicates)} hash groups with duplicates:")
        for h, files in sorted(duplicates.items(), key=lambda x: -len(x[1]))[:5]:
            print(f"\n  Hash: {h[:16]}...")
            print(f"  Found in {len(files)} locations:")
            for f in files:
                root_name = Path(f['root']).name
                print(f"    • [{root_name}] {f['rel_path']}")


def main():
    parser = argparse.ArgumentParser(
        description="Locate and compare instances of a file across multiple directory trees."
    )
    parser.add_argument(
        "file",
        help="Path to the source file (must be inside one of the configured VERSION_ROOTS).",
    )
    parser.add_argument(
        "--hash-algo",
        default="sha256",
        help="Hash algorithm (default: sha256). Any algo supported by hashlib is allowed.",
    )
    args = parser.parse_args()

    script_dir = Path(__file__).resolve().parent
    source_file = Path(args.file)

    results = analyze(source_file, script_dir, hash_algo=args.hash_algo)
    print_report(source_file.resolve(), results)


if __name__ == "__main__":
    main()

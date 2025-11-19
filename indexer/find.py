#!/usr/bin/env python3
"""
UID Finder for The Simpsons Game PS3 Remake Project Index

Searches the JSON index file for a given UID and lists all file instances,
checking if each file actually exists on disk.
"""

import argparse
import json
import os
from pathlib import Path
from typing import List, Dict, Any, Optional


# Base directories where file paths are relative to
GAME_FILES_ROOTS = [
    "STROUT-EU_Full-audio_og-notRenamed",
    "STROUT-EU_Full-audio_reorg-isRenamed",
    "STROUT-EU_Full-audio_reorg-notRenamed",
    "STROUT-US_Full-audio_og-isRenamed",
    "STROUT-US_Full-audio_og-notRenamed",
    "STROUT-US_Full-audio_reorg-isRenamed",
]


def load_index(index_path: Path) -> Dict[str, Any]:
    """Load the JSON index file"""
    if not index_path.exists():
        raise FileNotFoundError(f"Index file not found: {index_path}")
    
    with open(index_path, 'r', encoding='utf-8') as f:
        return json.load(f)


def find_uid_in_index(index_data: Dict[str, Any], uid: str) -> List[Dict[str, Any]]:
    """
    Search through the index structure to find all files with the given UID.
    Returns a list of file records.
    """
    results = []
    
    # Navigate the nested structure: index -> file_type -> stage -> extension -> uid -> [records]
    index_section = index_data.get('index', {})
    
    for file_type, stages in index_section.items():
        for stage, extensions in stages.items():
            for extension, uids in extensions.items():
                if uid in uids:
                    # Found the UID - add all records
                    records = uids[uid]
                    for record in records:
                        # Add context about where we found it
                        record_copy = record.copy()
                        record_copy['_file_type'] = file_type
                        record_copy['_stage'] = stage
                        record_copy['_extension'] = extension
                        results.append(record_copy)
    
    return results


def check_file_exists(rel_path: str, game_files_dir: Path) -> Optional[Path]:
    """
    Check if a file exists in any of the GAME_FILES_ROOTS directories.
    Returns the full path if found, None otherwise.
    """
    for root in GAME_FILES_ROOTS:
        full_path = game_files_dir / root / rel_path
        if full_path.exists():
            return full_path
    return None


def print_results(uid: str, records: List[Dict[str, Any]], game_files_dir: Path):
    """Pretty-print the search results"""
    if not records:
        print(f"No files found with UID: {uid}")
        return
    
    print(f"{'='*80}")
    print(f"Search Results for UID: {uid}")
    print(f"{'='*80}")
    print(f"Found {len(records)} file instance(s)\n")
    
    # Group by file type and stage
    by_type_stage = {}
    for record in records:
        file_type = record.get('_file_type', 'unknown')
        stage = record.get('_stage', 'unknown')
        key = f"{file_type}/{stage}"
        if key not in by_type_stage:
            by_type_stage[key] = []
        by_type_stage[key].append(record)
    
    for type_stage, files in sorted(by_type_stage.items()):
        print(f"\n{'-'*80}")
        print(f"Type/Stage: {type_stage}")
        print(f"{'-'*80}")
        
        for i, record in enumerate(files, 1):
            rel_path = record.get('rel_path', 'N/A')
            filename = record.get('filename', 'N/A')
            root_type = record.get('root_type', 'N/A')
            region = record.get('region', 'N/A')
            size = record.get('size', 0)
            file_hash = record.get('file_hash', 'N/A')
            extension = record.get('_extension', 'N/A')
            
            # Check if file exists
            full_path = check_file_exists(rel_path, game_files_dir)
            exists = full_path is not None
            status = "✓ EXISTS" if exists else "✗ MISSING"
            
            print(f"\n  [{i}] {status}")
            print(f"      Filename:  {filename}")
            print(f"      Extension: {extension}")
            print(f"      Region:    {region}")
            print(f"      Root Type: {root_type}")
            print(f"      Size:      {size:,} bytes")
            print(f"      Rel Path:  {rel_path}")
            if exists:
                print(f"      Full Path: {full_path}")
            print(f"      Hash:      {file_hash[:16]}..." if len(file_hash) > 16 else f"      Hash:      {file_hash}")
            
            # Show version flags if present
            version_flags = record.get('version_flags', {})
            if version_flags:
                print(f"      Flags:     {version_flags}")
    
    # Summary
    print(f"\n{'='*80}")
    print(f"SUMMARY")
    print(f"{'='*80}")
    
    existing = sum(1 for r in records if check_file_exists(r.get('rel_path', ''), game_files_dir) is not None)
    missing = len(records) - existing
    
    print(f"Total instances: {len(records)}")
    print(f"  ✓ Existing:    {existing}")
    print(f"  ✗ Missing:     {missing}")
    
    # Group by region
    by_region = {}
    for record in records:
        region = record.get('region', 'Unknown')
        by_region[region] = by_region.get(region, 0) + 1
    
    print(f"\nBy Region:")
    for region, count in sorted(by_region.items()):
        print(f"  {region}: {count}")
    
    # Group by root type
    by_root = {}
    for record in records:
        root_type = record.get('root_type', 'Unknown')
        by_root[root_type] = by_root.get(root_type, 0) + 1
    
    print(f"\nBy Root Type:")
    for root_type, count in sorted(by_root.items()):
        print(f"  {root_type}: {count}")


def main():
    parser = argparse.ArgumentParser(
        description="Find files by UID in The Simpsons Game PS3 index"
    )
    
    parser.add_argument(
        'uid',
        help='The UID to search for (6-char hex for most files, 7-8 char hex for audio)'
    )
    
    parser.add_argument(
        '--index',
        default='EngineApps/Games/TheSimpsonsGame-PS3/config/EU_index.json',
        help='Path to the JSON index file'
    )
    
    parser.add_argument(
        '--game-files',
        default='EngineApps/Games/TheSimpsonsGame-PS3/GameFiles',
        help='Path to the GameFiles directory containing the STROUT folders'
    )
    
    parser.add_argument(
        '--show-paths-only',
        action='store_true',
        help='Only show relative paths (one per line)'
    )
    
    args = parser.parse_args()
    
    # Resolve paths
    script_dir = Path(__file__).resolve().parent
    index_path = (script_dir.parent / args.index).resolve() if not Path(args.index).is_absolute() else Path(args.index)
    game_files_dir = (script_dir.parent / args.game_files).resolve() if not Path(args.game_files).is_absolute() else Path(args.game_files)
    
    # Validate inputs
    if not game_files_dir.exists():
        print(f"Error: GameFiles directory not found: {game_files_dir}")
        return 1
    
    # Load index
    try:
        index_data = load_index(index_path)
    except Exception as e:
        print(f"Error loading index: {e}")
        return 1
    
    # Search for UID
    uid = args.uid.lower()
    records = find_uid_in_index(index_data, uid)
    
    # Print results
    if args.show_paths_only:
        if not records:
            print(f"# No files found with UID: {uid}", file=sys.stderr)
        else:
            for record in records:
                rel_path = record.get('rel_path', '')
                full_path = check_file_exists(rel_path, game_files_dir)
                exists = "EXISTS" if full_path else "MISSING"
                print(f"{exists}\t{rel_path}")
    else:
        print_results(uid, records, game_files_dir)
    
    return 0


if __name__ == '__main__':
    import sys
    sys.exit(main())

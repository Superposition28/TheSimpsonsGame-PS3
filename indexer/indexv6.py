#!/usr/bin/env python3
"""
Universal File Indexer for The Simpsons Game PS3 Remake Project

Creates a deterministic index of all game files across transformations:
- Source files (STR archives, audio, video)
- Extracted files (from STR archives)
- Converted files (blend, glb, dds, png, wav, ogv)
- Multiple versions (EU/US, renamed/not-renamed, audio-reorg/og)

Each file gets:
- UUID: Unique per file instance (path_hash + file_hash)
- UID: Deterministic 6-char hex based on source origin (shared across transforms)
  - Audio files use their built-in UID from filename

Output: JSON file grouped by type and extension
"""

import argparse
import hashlib
import json
import os
import re
import sqlite3
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple
from dataclasses import dataclass, field, asdict
from tqdm import tqdm


# ============================================================================
# Configuration
# ============================================================================

# File type categories with their extensions (using FULL extensions)
FILE_TYPES = {
    'archive': ['.str'],
    'audio': {
        'source': ['.snu'],
        'converted': ['.wav']
    },
    'video': {
        'source': ['.vp6'],
        'converted': ['.ogv']
    },
    'model': {
        'extracted': ['.preinstanced', '.rws.ps3.preinstanced'],
        'blend': ['.blend', '.rws.ps3.blend'],
        'exported': ['.glb', '.rws.ps3.glb', '.fbx']
    },
    'texture': {
        'dict': ['.txd'],
        'extracted': ['.dds'],
        'converted': ['.png']
    },
    'metadata': ['.meta.xml', '.xml', '.inf', '.toc'],
    'other': []
}

# Audio filename pattern: d_as01_xxx_0003bb5.exa.wav
# UID is the hex part: 0003bb5
AUDIO_UID_PATTERN = re.compile(r'_([0-9a-fA-F]{7,8})\.(?:exa|exl|exp|mus)\.(?:wav|snu)')


# ============================================================================
# Data Classes
# ============================================================================

@dataclass
class FileRecord:
    """Represents a single file in the index"""
    uuid: str  # Unique per file instance
    uid: str  # Deterministic UID (shared across transforms)
    file_type: str  # Category (archive, audio, model, etc.)
    extension: str  # Full extension (.rws.ps3.preinstanced, not just .preinstanced)
    stage: str  # source, extracted, converted, etc.
    filename: str
    rel_path: str  # Relative to root
    abs_path: str
    file_hash: str
    path_hash: str
    size: int
    root_type: str  # source, strout-extract, strout-full
    region: str  # EU, US
    version_flags: Dict[str, str] = field(default_factory=dict)  # renamed, audio_state


@dataclass
class IndexState:
    """Maintains state during indexing"""
    # Organized by type -> stage -> extension -> uid -> list of records
    index: Dict[str, Dict[str, Dict[str, Dict[str, List[FileRecord]]]]] = field(default_factory=dict)

    # Quick lookups
    files_by_uuid: Dict[str, FileRecord] = field(default_factory=dict)
    files_by_uid: Dict[str, List[FileRecord]] = field(default_factory=dict)

    # Statistics
    total_files: int = 0
    files_by_type: Dict[str, int] = field(default_factory=dict)
    files_by_region: Dict[str, int] = field(default_factory=dict)


# ============================================================================
# Utility Functions
# ============================================================================

def get_full_extension(filename: str) -> str:
    """
    Get the FULL extension, not just the last part.
    Examples:
    - lodmodel1.rws.PS3.preinstanced -> .rws.ps3.preinstanced
    - file.meta.xml -> .meta.xml
    - simple.wav -> .wav
    """
    parts = filename.lower().split('.')
    if len(parts) <= 1:
        return ''

    # Common multi-part extensions
    if len(parts) >= 3:
        # Check for patterns like .rws.ps3.preinstanced
        if parts[-3] in ['rws', 'rwx'] and parts[-2] in ['ps3', 'pc']:
            return '.' + '.'.join(parts[-3:])
        # Check for .meta.xml
        if parts[-2] == 'meta' and parts[-1] == 'xml':
            return '.meta.xml'
        # Check for audio patterns like .exa.wav, .exl.snu
        if parts[-2] in ['exa', 'exl', 'exp', 'mus'] and parts[-1] in ['wav', 'snu']:
            return '.' + '.'.join(parts[-2:])

    # Default to last part
    return '.' + parts[-1]

def extract_audio_uid(filename: str) -> Optional[str]:
    """
    Extract the built-in UID from audio filenames.
    Example: d_as01_xxx_0003bb5.exa.wav -> 0003bb5
    """
    match = AUDIO_UID_PATTERN.search(filename)
    if match:
        return match.group(1).lower()
    return None


def get_file_type_and_stage(extension: str, root_type: str) -> Tuple[str, str]:
    """
    Determine file type category and transformation stage from extension.
    Returns: (file_type, stage)
    """
    ext_lower = extension.lower()

    # Check each type
    if ext_lower in FILE_TYPES['archive']:
        return 'archive', 'source'

    # Audio - check if ends with these extensions
    for audio_ext in FILE_TYPES['audio']['source']:
        if ext_lower.endswith(audio_ext):
            return 'audio', 'source'
    for audio_ext in FILE_TYPES['audio']['converted']:
        if ext_lower.endswith(audio_ext):
            return 'audio', 'converted'

    # Video
    for video_ext in FILE_TYPES['video']['source']:
        if ext_lower.endswith(video_ext):
            return 'video', 'source'
    for video_ext in FILE_TYPES['video']['converted']:
        if ext_lower.endswith(video_ext):
            return 'video', 'converted'

    # Model
    for model_ext in FILE_TYPES['model']['extracted']:
        if ext_lower.endswith(model_ext):
            return 'model', 'extracted'
    for model_ext in FILE_TYPES['model']['blend']:
        if ext_lower.endswith(model_ext):
            return 'model', 'blend'
    for model_ext in FILE_TYPES['model']['exported']:
        if ext_lower.endswith(model_ext):
            return 'model', 'exported'

    # Texture
    for tex_ext in FILE_TYPES['texture']['dict']:
        if ext_lower.endswith(tex_ext):
            return 'texture', 'dict'
    for tex_ext in FILE_TYPES['texture']['extracted']:
        if ext_lower.endswith(tex_ext):
            return 'texture', 'extracted'
    for tex_ext in FILE_TYPES['texture']['converted']:
        if ext_lower.endswith(tex_ext):
            return 'texture', 'converted'

    # Metadata
    for meta_ext in FILE_TYPES['metadata']:
        if ext_lower == meta_ext or ext_lower.endswith(meta_ext):
            return 'metadata', 'original'

    return 'other', 'unknown'
    """Compute hash of file contents"""
    h = hashlib.new(algo)
    with path.open("rb") as f:
        while chunk := f.read(1024 * 1024):
            h.update(chunk)
    return h.hexdigest()


def compute_file_hash(path: Path, algo: str = "sha256") -> str:
    """Compute hash of file contents"""
    h = hashlib.new(algo)
    with path.open("rb") as f:
        while chunk := f.read(1024 * 1024):
            h.update(chunk)
    return h.hexdigest()


def compute_path_hash(rel_path: str, algo: str = "md5") -> str:
    """Compute hash of relative path"""
    return hashlib.new(algo, rel_path.encode('utf-8')).hexdigest()


def make_uuid(file_hash: str, path_hash: str, root_hash: str = "") -> str:
    """Create unique UUID for file instance (includes root to distinguish versions)"""
    if root_hash:
        return f"{file_hash[:12]}_{path_hash[:12]}_{root_hash[:8]}"
    return f"{file_hash[:16]}_{path_hash[:16]}"


def make_deterministic_uid(source_path: str, file_type: str, filename: str) -> str:
    """
    Create deterministic 6-char hex UID based on source path and type.
    For audio files, extracts the built-in UID from the filename.
    For other files, generates from normalized path.
    """
    # Special handling for audio files
    if file_type == 'audio':
        audio_uid = extract_audio_uid(filename)
        if audio_uid:
            return audio_uid[:6]  # Ensure 6 chars

    # For other files, normalize path and generate UID
    normalized = source_path.lower()

    # Remove region-specific folders
    normalized = normalized.replace('/eu/', '/').replace('/us/', '/')
    normalized = normalized.replace('\\eu\\', '\\').replace('\\us\\', '\\')

    # Remove version-specific suffixes
    normalized = normalized.replace('_full-audio_og-notrenamed', '')
    normalized = normalized.replace('_full-audio_reorg-isrenamed', '')
    normalized = normalized.replace('_full-audio_reorg-notrenamed', '')
    normalized = normalized.replace('_full-audio_og-isrenamed', '')

    # Combine with file type for uniqueness
    uid_source = f"{normalized}:{file_type}"

    # Create 6-char hex from hash
    h = hashlib.sha256(uid_source.encode('utf-8')).hexdigest()
    return h[:6]


def parse_root_path(root_path: Path) -> Tuple[str, str, Dict[str, str]]:
    """
    Parse root path to extract type, region, and version flags.

    Examples:
    - Source/EU/PS3_GAME/USRDIR -> type='source', region='EU'
    - STROUT-EU-str_extract_only -> type='strout-extract', region='EU'
    - STROUT-EU_Full-audio_reorg-isRenamed -> type='strout-full', region='EU',
      flags={'audio_state': 'audio_reorg', 'renamed': 'isRenamed', 'type': 'Full'}
    """
    path_str = str(root_path).replace('\\', '/')

    # Detect source paths
    if '/Source/' in path_str:
        region = 'EU' if '/EU/' in path_str else 'US' if '/US/' in path_str else 'Unknown'
        return 'source', region, {}

    # Parse STROUT folder names
    folder_name = root_path.name

    if 'str_extract_only' in folder_name:
        region = 'EU' if folder_name.startswith('STROUT-EU') else 'US'
        return 'strout-extract', region, {'type': 'extract_only'}

    # Parse full STROUT format: STROUT-{REGION}_{Type}-{audio_state}-{renamed}
    if folder_name.startswith('STROUT-'):
        parts = folder_name.split('_', 1)
        region = parts[0].replace('STROUT-', '')

        if len(parts) > 1:
            flags_part = parts[1]
            flags = {}

            # Extract type
            if flags_part.startswith('Full'):
                flags['type'] = 'Full'
                flags_part = flags_part.replace('Full-', '').replace('Full_', '')
            elif flags_part.startswith('FullFlattened'):
                flags['type'] = 'FullFlattened'
                flags_part = flags_part.replace('FullFlattened-', '').replace('FullFlattened_', '')

            # Extract remaining flags
            sub_parts = flags_part.split('-')
            if len(sub_parts) >= 1:
                flags['audio_state'] = sub_parts[0] if 'audio' in sub_parts[0] else 'unknown'
            if len(sub_parts) >= 2:
                flags['renamed'] = sub_parts[1]

            return 'strout-full', region, flags

    return 'unknown', 'Unknown', {}


def normalize_rel_path(rel_path: Path, root_path: Path, rename_map: Dict[str, str]) -> Path:
    """
    Normalize relative path for UID generation by converting renamed folders to original names.
    """
    parts = rel_path.parts
    if not parts:
        return rel_path

    # Check if this root uses renamed folders
    is_renamed = 'isRenamed' in str(root_path)

    if is_renamed and len(parts) > 0:
        base_folder = parts[0].lower()
        if base_folder in rename_map:
            # Convert to original name
            original = rename_map[base_folder]
            return Path(original, *parts[1:])

    return rel_path


def load_rename_mappings(db_path: Path) -> Dict[str, str]:
    """Load rename mappings from database (new_name -> old_name)"""
    if not db_path.exists():
        return {}

    mappings = {}
    try:
        conn = sqlite3.connect(str(db_path))
        cursor = conn.cursor()
        cursor.execute("SELECT old_name, new_name FROM rename_mappings")
        for old_name, new_name in cursor.fetchall():
            mappings[new_name.lower()] = old_name
        conn.close()
    except Exception as e:
        print(f"Warning: Could not load rename mappings: {e}")

    return mappings


# ============================================================================
# Output Functions (JSON - Optional, SQLite - Default)
# ============================================================================

def save_index_to_json(state: IndexState, output_path: Path, pretty: bool = True):
    """Save the index to a JSON file"""
    # Convert to serializable format
    output = {
        'metadata': {
            'total_files': state.total_files,
            'files_by_type': state.files_by_type,
            'files_by_region': state.files_by_region,
            'unique_uids': len(state.files_by_uid)
        },
        'index': {}
    }

    # Convert dataclasses to dicts
    for file_type, stages in state.index.items():
        output['index'][file_type] = {}
        for stage, extensions in stages.items():
            output['index'][file_type][stage] = {}
            for extension, uids in extensions.items():
                output['index'][file_type][stage][extension] = {}
                for uid, records in uids.items():
                    output['index'][file_type][stage][extension][uid] = [
                        {k: v for k, v in asdict(r).items()}
                        for r in records
                    ]

    # Write to file
    with open(output_path, 'w', encoding='utf-8') as f:
        if pretty:
            json.dump(output, f, indent=2, ensure_ascii=False)
        else:
            json.dump(output, f, ensure_ascii=False)


def save_index_by_category(state: IndexState, output_dir: Path, prefix: str = '', pretty: bool = True):
    """
    Save separate JSON files for each file type category.
    Files will be named: {prefix}_{file_type}_index.json
    """
    output_dir.mkdir(parents=True, exist_ok=True)

    for file_type, stages in state.index.items():
        # Calculate category-specific metadata
        category_file_count = sum(
            len(records)
            for stage_data in stages.values()
            for ext_data in stage_data.values()
            for records in ext_data.values()
        )

        category_uid_count = len(set(
            uid
            for stage_data in stages.values()
            for ext_data in stage_data.values()
            for uid in ext_data.keys()
        ))

        # Build category-specific output
        category_output = {
            'metadata': {
                'file_type': file_type,
                'total_files': category_file_count,
                'unique_uids': category_uid_count,
                'stages': list(stages.keys())
            },
            'index': {}
        }

        # Convert dataclasses to dicts for this category
        for stage, extensions in stages.items():
            category_output['index'][stage] = {}
            for extension, uids in extensions.items():
                category_output['index'][stage][extension] = {}
                for uid, records in uids.items():
                    category_output['index'][stage][extension][uid] = [
                        {k: v for k, v in asdict(r).items()}
                        for r in records
                    ]

        # Write category file
        filename = f"{prefix}_{file_type}_index.json" if prefix else f"{file_type}_index.json"
        category_path = output_dir / filename

        with open(category_path, 'w', encoding='utf-8') as f:
            if pretty:
                json.dump(category_output, f, indent=2, ensure_ascii=False)
            else:
                json.dump(category_output, f, ensure_ascii=False)


def create_database_schema(conn: sqlite3.Connection):
    """
    Create SQLite database schema for file index.
    
    Tables:
    - files: Main file records
    - metadata: Statistics and summary information
    - version_flags: Key-value pairs for file version flags
    """
    cursor = conn.cursor()
    
    # Main files table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS files (
            uuid TEXT PRIMARY KEY,
            uid TEXT NOT NULL,
            file_type TEXT NOT NULL,
            extension TEXT NOT NULL,
            stage TEXT NOT NULL,
            filename TEXT NOT NULL,
            rel_path TEXT NOT NULL,
            abs_path TEXT NOT NULL,
            file_hash TEXT NOT NULL,
            path_hash TEXT NOT NULL,
            size INTEGER NOT NULL,
            root_type TEXT NOT NULL,
            region TEXT NOT NULL
        )
    ''')
    
    # Create indexes for common queries
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_uid ON files(uid)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_file_type ON files(file_type)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_extension ON files(extension)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_stage ON files(stage)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_file_hash ON files(file_hash)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_region ON files(region)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_type_stage_ext ON files(file_type, stage, extension)')
    
    # Version flags table (one-to-many relationship with files)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS version_flags (
            uuid TEXT NOT NULL,
            key TEXT NOT NULL,
            value TEXT NOT NULL,
            PRIMARY KEY (uuid, key),
            FOREIGN KEY (uuid) REFERENCES files(uuid)
        )
    ''')
    
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_vf_uuid ON version_flags(uuid)')
    
    # Metadata table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS metadata (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        )
    ''')
    
    conn.commit()


def save_index_to_sqlite(state: IndexState, output_path: Path, region: str = None):
    """
    Save the index to a SQLite database.
    
    Args:
        state: IndexState containing all file records
        output_path: Path to the .db file
        region: Optional region identifier for metadata
    """
    # Remove existing database
    if output_path.exists():
        output_path.unlink()
    
    # Create new database
    conn = sqlite3.connect(str(output_path))
    create_database_schema(conn)
    cursor = conn.cursor()
    
    # Insert all file records
    file_records = []
    version_flag_records = []
    
    for file_type, stages in state.index.items():
        for stage, extensions in stages.items():
            for extension, uids in extensions.items():
                for uid, records in uids.items():
                    for record in records:
                        # Main file record
                        file_records.append((
                            record.uuid,
                            record.uid,
                            record.file_type,
                            record.extension,
                            record.stage,
                            record.filename,
                            record.rel_path,
                            record.abs_path,
                            record.file_hash,
                            record.path_hash,
                            record.size,
                            record.root_type,
                            record.region
                        ))
                        
                        # Version flags
                        for key, value in record.version_flags.items():
                            version_flag_records.append((
                                record.uuid,
                                key,
                                value
                            ))
    
    # Batch insert files
    cursor.executemany('''
        INSERT INTO files (uuid, uid, file_type, extension, stage, filename, 
                          rel_path, abs_path, file_hash, path_hash, size, 
                          root_type, region)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', file_records)
    
    # Batch insert version flags
    if version_flag_records:
        cursor.executemany('''
            INSERT INTO version_flags (uuid, key, value)
            VALUES (?, ?, ?)
        ''', version_flag_records)
    
    # Insert metadata
    metadata = {
        'total_files': str(state.total_files),
        'unique_uids': str(len(state.files_by_uid)),
        'region': region or 'unknown'
    }
    
    # Add file type counts
    for file_type, count in state.files_by_type.items():
        metadata[f'count_{file_type}'] = str(count)
    
    # Add region counts
    for region_name, count in state.files_by_region.items():
        metadata[f'region_{region_name}'] = str(count)
    
    cursor.executemany(
        'INSERT INTO metadata (key, value) VALUES (?, ?)',
        list(metadata.items())
    )
    
    conn.commit()
    conn.close()


# ============================================================================
# Indexing Logic
# ============================================================================

def add_to_index(state: IndexState, record: FileRecord):
    """Add a file record to the index structure"""
    # Ensure hierarchy exists
    if record.file_type not in state.index:
        state.index[record.file_type] = {}
    if record.stage not in state.index[record.file_type]:
        state.index[record.file_type][record.stage] = {}
    if record.extension not in state.index[record.file_type][record.stage]:
        state.index[record.file_type][record.stage][record.extension] = {}
    if record.uid not in state.index[record.file_type][record.stage][record.extension]:
        state.index[record.file_type][record.stage][record.extension][record.uid] = []

    # Add record
    state.index[record.file_type][record.stage][record.extension][record.uid].append(record)

    # Update quick lookups
    state.files_by_uuid[record.uuid] = record
    if record.uid not in state.files_by_uid:
        state.files_by_uid[record.uid] = []
    state.files_by_uid[record.uid].append(record)

    # Update statistics
    state.total_files += 1
    state.files_by_type[record.file_type] = state.files_by_type.get(record.file_type, 0) + 1
    state.files_by_region[record.region] = state.files_by_region.get(record.region, 0) + 1

def count_files_in_directory(root_path: Path) -> int:
    """Count total files in directory for progress bar."""
    total = 0
    for _, _, filenames in os.walk(root_path):
        total += len(filenames)
    return total


def walk_and_index_directory(
    root_path: Path,
    state: IndexState,
    rename_map: Dict[str, str],
    verbose: bool = False,
    show_progress: bool = True
):
    """
    Walk directory tree and index all files.
    """
    root_type, region, version_flags = parse_root_path(root_path)

    print(f"\nIndexing: {root_path}")
    print(f"  Type: {root_type}, Region: {region}, Flags: {version_flags}")

    # Count files first for progress bar
    if show_progress:
        print("  Counting files...")
        total_files = count_files_in_directory(root_path)
        print(f"  Found {total_files:,} files to index")
        pbar = tqdm(total=total_files, unit='file', desc=f"  Indexing", 
                   bar_format='{desc}: {percentage:3.0f}%|{bar}| {n_fmt}/{total_fmt} [{elapsed}<{remaining}, {rate_fmt}]')
    else:
        pbar = None

    file_count = 0

    # Compute root hash once for UUID generation
    root_hash = hashlib.md5(str(root_path).encode('utf-8')).hexdigest()

    for dirpath, _, filenames in os.walk(root_path):
        for filename in filenames:
            abs_path = Path(dirpath) / filename
            rel_path = abs_path.relative_to(root_path)

            # Get FULL extension
            extension = get_full_extension(filename)
            file_type, stage = get_file_type_and_stage(extension, root_type)
            size = abs_path.stat().st_size

            # Compute hashes
            file_hash = compute_file_hash(abs_path)
            path_hash = compute_path_hash(str(rel_path))
            uuid = make_uuid(file_hash, path_hash, root_hash)

            # Normalize path for UID generation
            normalized_rel = normalize_rel_path(rel_path, root_path, rename_map)

            # Generate deterministic UID
            uid_source = str(normalized_rel)
            uid = make_deterministic_uid(uid_source, file_type, filename)

            # Create record
            record = FileRecord(
                uuid=uuid,
                uid=uid,
                file_type=file_type,
                extension=extension,
                stage=stage,
                filename=filename,
                rel_path=str(rel_path),
                abs_path=str(abs_path),
                file_hash=file_hash,
                path_hash=path_hash,
                size=size,
                root_type=root_type,
                region=region,
                version_flags=version_flags
            )

            # Add to index
            add_to_index(state, record)

            file_count += 1

            # Update progress bar
            if pbar:
                pbar.update(1)
            elif verbose and file_count % 1000 == 0:
                print(f"  Indexed {file_count} files...")

    if pbar:
        pbar.close()
        print(f"  Completed: {file_count:,} files indexed")
    elif verbose:
        print(f"  Total: {file_count} files")


# ============================================================================
# Main
# ============================================================================

def main():
    parser = argparse.ArgumentParser(
        description="Universal File Indexer for The Simpsons Game PS3 Remake"
    )

    parser.add_argument(
        '--game-root',
        default='EngineApps/Games/TheSimpsonsGame-PS3',
        help='Root directory of the game module'
    )

    parser.add_argument(
        '--output-dir',
        default='EngineApps/Games/TheSimpsonsGame-PS3/config/index',
        help='Directory for output JSON files (will create {Region}_index.json for each region)'
    )

    parser.add_argument(
        '--regions',
        nargs='+',
        default=['EU', 'US'],
        help='Regions to index (creates separate index for each)'
    )

    parser.add_argument(
        '--roots',
        nargs='+',
        help='Specific root directories to index (optional, overrides auto-discovery)'
    )

    parser.add_argument(
        '--verbose',
        action='store_true',
        help='Enable verbose output'
    )

    parser.add_argument(
        '--compact',
        action='store_true',
        help='Output compact JSON (no pretty printing, only used with --json)'
    )

    parser.add_argument(
        '--json',
        action='store_true',
        help='Also export to JSON format (in addition to SQLite)'
    )

    parser.add_argument(
        '--no-progress',
        action='store_true',
        help='Disable progress bar'
    )

    args = parser.parse_args()

    # Resolve paths
    game_root = Path(args.game_root).resolve()
    output_dir = Path(args.output_dir).resolve()
    rename_map_db = game_root / 'config' / 'RenameMap.db'

    # Load rename mappings
    rename_map = load_rename_mappings(rename_map_db)

    # Ensure output directory exists
    output_dir.mkdir(parents=True, exist_ok=True)

    # Process each region separately
    if args.roots:
        # Custom roots mode - single index
        print("Custom roots mode - creating single combined database")
        roots = [Path(r).resolve() for r in args.roots]
        state = IndexState()

        for root in roots:
            if root.exists():
                walk_and_index_directory(root, state, rename_map, args.verbose, show_progress=not args.no_progress)
            else:
                print(f"Warning: Root does not exist: {root}")

        # Save to SQLite (always)
        output_path = output_dir / 'custom_index.db'
        print(f"\nSaving index to SQLite database...")
        save_index_to_sqlite(state, output_path, region='custom')

        # Save to JSON (optional)
        if args.json:
            json_output_path = output_dir / 'custom_index.json'
            print(f"Saving index to JSON...")
            save_index_to_json(state, json_output_path, pretty=not args.compact)
            
            print(f"Saving category-specific JSON files...")
            save_index_by_category(state, output_dir, prefix='custom', pretty=not args.compact)

        print(f"\n{'='*60}")
        print("Indexing Complete - Custom Roots")
        print(f"{'='*60}")
        print(f"Total files: {state.total_files}")
        print(f"Unique UIDs: {len(state.files_by_uid)}")
        print(f"Output: {output_path}")
        if args.json:
            print(f"JSON Output: {json_output_path}")
            print(f"\nCategory files:")
            for file_type in state.index.keys():
                print(f"  - custom_{file_type}_index.json")
        print(f"\nFiles by type:")
        for file_type, count in sorted(state.files_by_type.items(), key=lambda x: -x[1]):
            print(f"  {file_type:20s}: {count:6d}")
    else:
        # Auto-discover mode - separate index per region
        for region in args.regions:
            print(f"\n{'='*80}")
            print(f"Processing Region: {region}")
            print(f"{'='*80}")

            # Initialize state for this region
            state = IndexState()
            roots = []

            # Source directory
            source_root = game_root / 'Source' / region / 'PS3_GAME' / 'USRDIR'
            if source_root.exists():
                roots.append(source_root)
            else:
                print(f"Warning: Source directory not found: {source_root}")
                continue

            # STROUT directories for this region (exclude str_extract_only)
            gamefiles_root = game_root / 'GameFiles'
            if gamefiles_root.exists():
                for item in gamefiles_root.iterdir():
                    if item.is_dir() and item.name.startswith(f'STROUT-{region}'):
                        # Skip the str_extract_only directories
                        if 'str_extract_only' not in item.name:
                            roots.append(item)

            if not roots:
                print(f"No roots found for region {region}, skipping...")
                continue

            # Index all roots for this region
            print(f"\nIndexing {len(roots)} directories for {region}...")
            print(f"Roots:")
            for root in roots:
                print(f"  - {root}")
            for root in roots:
                walk_and_index_directory(root, state, rename_map, args.verbose, show_progress=not args.no_progress)

            # Save to SQLite (always)
            output_path = output_dir / f'{region}_index.db'
            print(f"\nSaving {region} index to SQLite database...")
            save_index_to_sqlite(state, output_path, region=region)

            # Save to JSON (optional)
            if args.json:
                json_output_path = output_dir / f'{region}_index.json'
                print(f"Saving {region} index to JSON...")
                save_index_to_json(state, json_output_path, pretty=not args.compact)
                
                print(f"Saving {region} category-specific JSON files...")
                save_index_by_category(state, output_dir, prefix=region, pretty=not args.compact)

            # Print statistics
            print(f"\n{'-'*60}")
            print(f"{region} Indexing Complete")
            print(f"{'-'*60}")
            print(f"Total files: {state.total_files}")
            print(f"Unique UIDs: {len(state.files_by_uid)}")
            print(f"\nFiles by type:")
            for file_type, count in sorted(state.files_by_type.items(), key=lambda x: -x[1]):
                print(f"  {file_type:20s}: {count:6d}")
            print(f"\nOutput: {output_path}")
            if args.json:
                print(f"JSON Output: {json_output_path}")
                print(f"Category files:")
                for file_type in state.index.keys():
                    print(f"  - {region}_{file_type}_index.json")

        print(f"\n{'='*80}")
        print("All Regions Complete")
        print(f"{'='*80}")


if __name__ == '__main__':
    main()

import os
import sys
import argparse
import sqlite3
import hashlib
import time
import json
import glob
from typing import Dict, Tuple, Iterable, Optional


# --------------------
# CLI and Configuration
# --------------------

# Base folder rename mapping (original -> renamed)
RENAME_MAP = {
    "audiostreams": "Assets_1_Audio_Streams",
    "movies": "Assets_1_Video_Movies",
    "frontend": "Assets_2_Frontend",
    "simpsons_chars": "Assets_2_Characters_Simpsons",
    "spr_hub": "Map_3-00_SprHub",
    "loc": "Map_3-01_LandOfChocolate",
    "brt": "Map_3-02_BartmanBegins",
    "eighty_bites": "Map_3-03_HungryHungryHomer",
    "tree_hugger": "Map_3-04_TreeHugger",
    "mob_rules": "Map_3-05_MobRules",
    "cheater": "Map_3-06_EnterTheCheatrix",
    "dayofthedolphins": "Map_3-07_DayOfTheDolphin",
    "colossaldonut": "Map_3-08_TheColossalDonut",
    "dayspringfieldstoodstill": "Map_3-09_Invasion",
    "bargainbin": "Map_3-10_BargainBin",
    "gamehub": "Map_3-00_GameHub",
    "neverquest": "Map_3-11_NeverQuest",
    "grand_theft_scratchy": "Map_3-12_GrandTheftScratchy",
    "medal_of_homer": "Map_3-13_MedalOfHomer",
    "bigsuperhappy": "Map_3-14_BigSuperHappy",
    "rhymes": "Map_3-15_Rhymes",
    "meetthyplayer": "Map_3-16_MeetThyPlayer",
}

ORIGINAL_BASES = list(RENAME_MAP.keys())
RENAMED_BASES = list(RENAME_MAP.values())


def parse_args():
    parser = argparse.ArgumentParser(
        description="New Simpsons Game File Indexer (relationships + file catalogs)"
    )

    parser.add_argument(
        '--input-dir',
        default=r"A:\\RemakeEngine\\EngineApps\\Games\\TheSimpsonsGame-PS3\\Source\\USRDIR",
        help='Custom input directory for source files'
    )

    parser.add_argument(
        '--output-dir',
        default=r"A:\\RemakeEngine\\EngineApps\\Games\\TheSimpsonsGame-PS3\\GameFiles\\STROUT",
        help='Custom output directory for extracted files'
    )

    # Detailed selection flags
    parser.add_argument(
        '--region', choices=['EU', 'US'], required=True,
        help="Region selector ('EU' or 'US')"
    )

    parser.add_argument(
        '--Type', dest='index_type', choices=['Full', 'FullFlattened', 'SourceOnly'], required=True,
        help="Index Type: 'Full'|'FullFlattened'|'SourceOnly'"
    )

    parser.add_argument(
        '--renamedBaseDirs', dest='renamed_base_dirs', choices=['isRenamed', 'notRenamed'], required=True,
        help="Whether base dirs were renamed: 'isRenamed'|'notRenamed'"
    )

    parser.add_argument(
        '--AudioReorg', dest='audio_reorg', choices=['audio_reorg', 'audio_og'], required=True,
        help="Audio reorg status: 'audio_reorg'|'audio_og'"
    )

    parser.add_argument( ## changed logic of extraction tools, so the blend files are actually being placed in the STROUT folder instead of TEMP_BLEND for easier access
        '--blend-dir', dest='blend_dir', default=r"A:\RemakeEngine\EngineApps\Games\TheSimpsonsGame-PS3\GameFiles\STROUT",
        help='Optional TEMP_BLEND directory (mirror layout of STROUT for .blend)'
    )

    parser.add_argument(
        '--flatten-map-dir', dest='flatten_map_dir', default=None,
        help='Directory containing flatten_map_*.json files (required for FullFlattened type)'
    )

    return parser.parse_args()


# --------------------
# Utility helpers
# --------------------

def norm_rel(path: str) -> str:
    return path.replace('\\', '/').lstrip('/')


def sha256_file(path: str) -> str:
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()


def md5_string(s: str) -> str:
    return hashlib.md5(s.encode('utf-8')).hexdigest()


def make_uuid(file_hash: str, rel_path: str) -> str:
    ph = file_hash[:16]
    rh = md5_string(rel_path)[:16]
    return f"{ph}_{rh}"


def ensure_dir(path: str):
    os.makedirs(path, exist_ok=True)


def discover_blend_dir(output_dir: str, provided: str | None) -> str:
    if provided:
        return provided
    candidate = os.path.normpath(os.path.join(os.path.dirname(output_dir), 'TEMP_BLEND'))
    return candidate


def get_base_names(selected_renamed: str) -> Iterable[str]:
    return RENAMED_BASES if selected_renamed == 'isRenamed' else ORIGINAL_BASES


def validate_base_folders(root_dir: str, expected_bases: Iterable[str], label: str, require_all: bool = True):
    """Validate that base folders exist in the root directory.
    
    Args:
        root_dir: Root directory to check
        expected_bases: List of expected base folder names
        label: Label for error messages
        require_all: If True, all folders must exist. If False, at least one must exist.
    """
    missing = []
    found = []
    for base in expected_bases:
        sub = os.path.join(root_dir, base)
        if not os.path.isdir(sub):
            missing.append(sub)
        else:
            found.append(sub)
    
    if require_all and missing:
        lines = "\n  ".join(missing)
        raise RuntimeError(f"Missing required base folders in {label}:\n  {lines}")
    elif not require_all and not found:
        raise RuntimeError(f"No base folders found in {label}. Expected at least one of: {expected_bases}")


# --------------------
# SQLite schema helpers
# --------------------

EXT_TO_TABLE = {
    '.str': 'str_index',
    '.preinstanced': 'preinstanced_index',
    '.blend': 'blend_index',
    '.glb': 'glb_index',
    '.txd': 'txd_index',
    '.vp6': 'video_index',
    '.ogv': 'video_ogv_index',
    '.snu': 'snu_index',
    '.wav': 'audio_wav_index',
    '.mus': 'mus_index',
    '.dds': 'dds_index',
    '.png': 'png_index',
}


GENERIC_TABLES = set(EXT_TO_TABLE.values()) | {"other_files_index"}


def init_schema(conn: sqlite3.Connection):
    cur = conn.cursor()

    # Generic file tables
    for table in GENERIC_TABLES:
        cur.execute(f"""
            CREATE TABLE IF NOT EXISTS {table} (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                uuid TEXT UNIQUE NOT NULL,
                source_file_name TEXT,
                source_path TEXT UNIQUE NOT NULL,
                original_path TEXT,
                file_hash TEXT,
                path_hash TEXT,
                group_name TEXT,
                first_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        cur.execute(f"""
            CREATE TRIGGER IF NOT EXISTS update_{table}_last_updated
            AFTER UPDATE ON {table}
            FOR EACH ROW
            BEGIN
                UPDATE {table} SET last_updated = CURRENT_TIMESTAMP WHERE id = OLD.id;
            END;
        """)

    # Relationships
    cur.execute("""
        CREATE TABLE IF NOT EXISTS str_content_relationship (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            str_uuid TEXT NOT NULL,
            content_file_uuid TEXT NOT NULL,
            content_file_table TEXT NOT NULL,
            UNIQUE (str_uuid, content_file_uuid, content_file_table)
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS txd_dds_relationship (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            txd_uuid TEXT NOT NULL,
            dds_uuid TEXT NOT NULL,
            UNIQUE (txd_uuid, dds_uuid)
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS dds_png_relationship (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            dds_uuid TEXT NOT NULL,
            png_uuid TEXT NOT NULL,
            UNIQUE (dds_uuid, png_uuid)
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS preinstanced_blend_relationship (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            preinstanced_uuid TEXT NOT NULL,
            blend_uuid TEXT NOT NULL,
            UNIQUE (preinstanced_uuid, blend_uuid)
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS glb_blend_relationship (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            glb_uuid TEXT NOT NULL,
            blend_uuid TEXT NOT NULL,
            UNIQUE (glb_uuid, blend_uuid)
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS preinstanced_blend_glb_relationship (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            preinstanced_uuid TEXT NOT NULL,
            blend_uuid TEXT NOT NULL,
            glb_uuid TEXT NOT NULL,
            UNIQUE (preinstanced_uuid, blend_uuid, glb_uuid)
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS snu_wav_relationship (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            snu_uuid TEXT NOT NULL,
            wav_uuid TEXT NOT NULL,
            UNIQUE (snu_uuid, wav_uuid)
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS vp6_ogv_relationship (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            vp6_uuid TEXT NOT NULL,
            ogv_uuid TEXT NOT NULL,
            UNIQUE (vp6_uuid, ogv_uuid)
        )
    """)

    conn.commit()


def table_for_ext(ext: str) -> str:
    return EXT_TO_TABLE.get(ext.lower(), 'other_files_index')


def upsert_file(conn: sqlite3.Connection, table: str, full_path: str, rel_path: str, group_name: str, 
                original_path: Optional[str] = None) -> str:
    """Insert or update a file record in the database.
    
    Args:
        conn: Database connection
        table: Table name to insert into
        full_path: Absolute file path on disk
        rel_path: Relative path (flattened if in FullFlattened mode)
        group_name: Grouping/category name
        original_path: Original hierarchical path (for FullFlattened mode)
    
    Returns:
        UUID of the file record
    """
    file_hash = sha256_file(full_path)
    path_hash = md5_string(rel_path)
    uuid = make_uuid(file_hash, rel_path)

    cur = conn.cursor()
    cur.execute(
        f"""
        INSERT OR IGNORE INTO {table} (uuid, source_file_name, source_path, original_path, file_hash, path_hash, group_name)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (uuid, os.path.basename(full_path), rel_path, original_path, file_hash, path_hash, group_name)
    )
    if cur.rowcount == 0:
        # Ensure we can retrieve UUID of existing row (by source_path)
        cur.execute(f"SELECT uuid FROM {table} WHERE source_path = ?", (rel_path,))
        row = cur.fetchone()
        if row:
            uuid = row[0]
            # Update original_path if provided and not already set
            if original_path:
                cur.execute(f"UPDATE {table} SET original_path = ? WHERE uuid = ? AND original_path IS NULL", 
                           (original_path, uuid))
    conn.commit()
    return uuid


# --------------------
# Indexing passes
# --------------------

class FlattenMapLoader:
    """Loads and manages flatten map JSON files for FullFlattened indexing."""
    
    def __init__(self, flatten_map_dir: str):
        self.flatten_map_dir = flatten_map_dir
        # Maps: new_path -> original_path
        self.new_to_original: Dict[str, str] = {}
        # Maps: original_path -> new_path
        self.original_to_new: Dict[str, str] = {}
        self._load_maps()
    
    def _load_maps(self):
        """Load all flatten_map_*.json files from the directory."""
        if not os.path.isdir(self.flatten_map_dir):
            raise RuntimeError(f"Flatten map directory does not exist: {self.flatten_map_dir}")
        
        pattern = os.path.join(self.flatten_map_dir, "flatten_map_*.json")
        map_files = glob.glob(pattern)
        
        # Exclude the monolithic flatten_map.json if it exists
        map_files = [f for f in map_files if not f.endswith("flatten_map.json") 
                     and not f.endswith("flatten_map_summary.json")]
        
        if not map_files:
            raise RuntimeError(f"No flatten_map_*.json files found in {self.flatten_map_dir}")
        
        print(f"Loading {len(map_files)} flatten map files...")
        for map_file in map_files:
            try:
                with open(map_file, 'r', encoding='utf-8') as f:
                    entries = json.load(f)
                    for entry in entries:
                        orig = norm_rel(entry['original_path'])
                        new = norm_rel(entry['new_path'])
                        self.new_to_original[new] = orig
                        self.original_to_new[orig] = new
            except Exception as e:
                print(f"WARN: Failed to load {map_file}: {e}", file=sys.stderr)
        
        print(f"Loaded {len(self.new_to_original)} path mappings from flatten maps")
    
    def get_original_path(self, new_path: str) -> Optional[str]:
        """Get the original path for a flattened path."""
        return self.new_to_original.get(norm_rel(new_path))
    
    def get_new_path(self, original_path: str) -> Optional[str]:
        """Get the flattened path for an original path."""
        return self.original_to_new.get(norm_rel(original_path))


class IndexState:
    def __init__(self):
        # per-extension map: rel_path -> uuid
        self.by_ext: Dict[str, Dict[str, str]] = {}

    def add(self, ext: str, rel_path: str, uuid: str):
        ext = ext.lower()
        if ext not in self.by_ext:
            self.by_ext[ext] = {}
        self.by_ext[ext][rel_path] = uuid

    def get(self, ext: str, rel_path: str) -> str | None:
        ext = ext.lower()
        return self.by_ext.get(ext, {}).get(rel_path)


def infer_original_path(flattened_path: str, ext: str, flatten_map: FlattenMapLoader) -> Optional[str]:
    """Infer what the original path would have been for a generated file.
    
    For files not in the flatten map (generated after flattening like .blend, .glb, .wav, .ogv, .png),
    infer their original path based on their relationship to source files that ARE in the map.
    
    Args:
        flattened_path: The current flattened path
        ext: File extension
        flatten_map: The flatten map loader
    
    Returns:
        Inferred original path, or None if cannot infer
    """
    ext = ext.lower()
    
    # Generated files that follow extension-swap pattern
    ext_swap_map = {
        '.blend': '.preinstanced',
        '.glb': '.preinstanced',
        '.wav': '.snu',
        '.ogv': '.vp6',
        '.png': '.dds',
    }
    
    if ext in ext_swap_map:
        # Try to find the source file in the map
        source_ext = ext_swap_map[ext]
        source_path = flattened_path[:-len(ext)] + source_ext
        original_source = flatten_map.get_original_path(source_path)
        
        if original_source:
            # Infer the original target path by swapping extension
            return original_source[:-len(source_ext)] + ext
    
    # For files extracted from archives (in _str or _txd directories)
    # Try to find parent archive in map
    if '_str/' in flattened_path or '_txd/' in flattened_path:
        # Extract archive name
        if '_str/' in flattened_path:
            archive_sep = '_str/'
            archive_ext = '.str'
        else:
            archive_sep = '_txd/'
            archive_ext = '.txd'
        
        parts = flattened_path.split(archive_sep)
        if len(parts) == 2:
            archive_path = parts[0] + archive_ext
            content_rel = parts[1]
            
            original_archive = flatten_map.get_original_path(archive_path)
            if original_archive:
                # Reconstruct original extraction path
                original_archive_no_ext = original_archive[:-len(archive_ext)]
                return f"{original_archive_no_ext}{archive_sep}{content_rel}"
    
    return None


def walk_files(base_dir: str, allow_exts: set[str] | None = None) -> Iterable[Tuple[str, str, str]]:
    for root, _, files in os.walk(base_dir):
        for fn in files:
            ext = os.path.splitext(fn)[1].lower()
            if allow_exts is not None and ext not in allow_exts:
                continue
            full = os.path.join(root, fn)
            rel = norm_rel(os.path.relpath(full, base_dir))
            yield full, rel, ext


def index_root_dir(conn: sqlite3.Connection, base_dir: str, ext_filter: set[str] | None, state: IndexState,
                  flatten_map: Optional[FlattenMapLoader] = None):
    """Index all files in a directory tree.
    
    Args:
        conn: Database connection
        base_dir: Root directory to index
        ext_filter: If provided, only index files with these extensions
        state: Index state tracker
        flatten_map: Optional flatten map for determining original paths
    """
    for full, rel, ext in walk_files(base_dir, ext_filter):
        tbl = table_for_ext(ext)
        grp = ext  # simple grouping by extension string
        
        # Determine original path if flatten map is available
        original_path = None
        if flatten_map:
            original_path = flatten_map.get_original_path(rel)
            # If not in map, try to infer original path based on file type and relationships
            if not original_path:
                original_path = infer_original_path(rel, ext, flatten_map)
        
        try:
            uuid = upsert_file(conn, tbl, full, rel, grp, original_path)
            state.add(ext, rel, uuid)
        except Exception as e:
            print(f"ERROR indexing {full}: {e}", file=sys.stderr)


def relate_str_contents(conn: sqlite3.Connection, input_dir: str, output_dir: str, state: IndexState, 
                       flatten_map: Optional[FlattenMapLoader] = None):
    cur = conn.cursor()
    str_map = state.by_ext.get('.str', {})
    for rel_str_path, str_uuid in str_map.items():
        # Determine the original path if using flatten map
        original_str_path = rel_str_path
        if flatten_map:
            original = flatten_map.get_original_path(rel_str_path)
            if original:
                original_str_path = original
        
        # Remove .str extension
        rel_no_ext = original_str_path[:-4] if original_str_path.lower().endswith('.str') else original_str_path
        extraction_rel_dir = f"{rel_no_ext}_str"
        extraction_abs_dir = os.path.join(output_dir, extraction_rel_dir)
        
        # In FullFlattened mode, content may be in flattened locations
        if not os.path.isdir(extraction_abs_dir):
            # Try the flattened path extraction dir as fallback
            rel_no_ext_flat = rel_str_path[:-4] if rel_str_path.lower().endswith('.str') else rel_str_path
            extraction_rel_dir = f"{rel_no_ext_flat}_str"
            extraction_abs_dir = os.path.join(output_dir, extraction_rel_dir)
        
        if not os.path.isdir(extraction_abs_dir):
            # It's valid for some STRs not to be extracted yet
            continue
        
        for root, _, files in os.walk(extraction_abs_dir):
            for fn in files:
                fext = os.path.splitext(fn)[1].lower()
                full = os.path.join(root, fn)
                rel = norm_rel(os.path.relpath(full, output_dir))
                content_tbl = table_for_ext(fext)
                content_uuid = state.get(fext, rel)
                if content_uuid is None:
                    # If not indexed yet (e.g., filtered), index on-the-fly
                    # Infer original path for content files
                    original_content_path = None
                    if flatten_map:
                        original_content_path = flatten_map.get_original_path(rel)
                        if not original_content_path:
                            original_content_path = infer_original_path(rel, fext, flatten_map)
                    try:
                        content_uuid = upsert_file(conn, content_tbl, full, rel, fext, original_content_path)
                        state.add(fext, rel, content_uuid)
                    except Exception as e:
                        print(f"WARN: could not index STR content {full}: {e}", file=sys.stderr)
                        continue
                try:
                    cur.execute(
                        """
                        INSERT OR IGNORE INTO str_content_relationship (str_uuid, content_file_uuid, content_file_table)
                        VALUES (?, ?, ?)
                        """,
                        (str_uuid, content_uuid, content_tbl)
                    )
                except Exception as e:
                    print(f"WARN: relation STR->content failed for {rel} : {e}", file=sys.stderr)
    conn.commit()


def relate_txd_dds(conn: sqlite3.Connection, roots: Iterable[str], state: IndexState, 
                  flatten_map: Optional[FlattenMapLoader] = None):
    cur = conn.cursor()
    # Build a quick lookup of dds rel paths
    for base in roots:
        for full, rel, ext in walk_files(base, {'.txd'}):
            # Get original path if using flatten map
            original_rel = rel
            if flatten_map:
                original = flatten_map.get_original_path(rel)
                if original:
                    original_rel = original
            
            parent_dir = os.path.dirname(full)
            base_no_ext = os.path.splitext(os.path.basename(full))[0]
            dds_dir = os.path.join(parent_dir, base_no_ext + "_txd")
            
            txd_uuid = state.get('.txd', rel)
            if txd_uuid is None:
                try:
                    txd_uuid = upsert_file(conn, table_for_ext('.txd'), full, rel, '.txd', original_rel)
                    state.add('.txd', rel, txd_uuid)
                except Exception as e:
                    print(f"WARN: could not index TXD {full} for relationships: {e}", file=sys.stderr)
                    continue
            if not os.path.isdir(dds_dir):
                continue
            for droot, _, files in os.walk(dds_dir):
                for fn in files:
                    if not fn.lower().endswith('.dds'):
                        continue
                    dfull = os.path.join(droot, fn)
                    drel = norm_rel(os.path.relpath(dfull, base))
                    d_uuid = state.get('.dds', drel)
                    if d_uuid is None:
                        # Infer original DDS path
                        original_dds_path = None
                        if flatten_map:
                            original_dds_path = flatten_map.get_original_path(drel)
                            if not original_dds_path:
                                original_dds_path = infer_original_path(drel, '.dds', flatten_map)
                        try:
                            d_uuid = upsert_file(conn, table_for_ext('.dds'), dfull, drel, '.dds', original_dds_path)
                            state.add('.dds', drel, d_uuid)
                        except Exception as e:
                            print(f"WARN: could not index DDS {dfull}: {e}", file=sys.stderr)
                            continue
                    try:
                        cur.execute(
                            "INSERT OR IGNORE INTO txd_dds_relationship (txd_uuid, dds_uuid) VALUES (?, ?)",
                            (txd_uuid, d_uuid)
                        )
                    except Exception as e:
                        print(f"WARN: TXD-DDS relation failed for {rel} -> {drel}: {e}", file=sys.stderr)
    conn.commit()


def relate_ext_swap(conn: sqlite3.Connection, state: IndexState, from_ext: str, to_ext: str,
                    table_rel: str, from_col: str, to_col: str, 
                    flatten_map: Optional[FlattenMapLoader] = None):
    cur = conn.cursor()
    src_map = dict(state.by_ext.get(from_ext, {}))
    dst_map = dict(state.by_ext.get(to_ext, {}))
    
    for rel_from, uuid_from in src_map.items():
        if not rel_from.lower().endswith(from_ext):
            continue
        
        # Calculate the target path - try multiple strategies
        rel_to = rel_from[:-len(from_ext)] + to_ext
        
        # In FullFlattened mode, try to use flatten map, but fall back if not mapped
        if flatten_map:
            original_from = flatten_map.get_original_path(rel_from)
            if original_from:
                # Calculate what the original "to" path would be
                original_to = original_from[:-len(from_ext)] + to_ext
                # Try to find the flattened version in the map
                flattened_to = flatten_map.get_new_path(original_to)
                if flattened_to:
                    rel_to = flattened_to
                # else: target file not in map (e.g., generated files like WAV/OGV)
                #       fall back to simple extension swap on the flattened source path
        
        uuid_to = dst_map.get(rel_to)
        if not uuid_to:
            continue
        try:
            cur.execute(
                f"INSERT OR IGNORE INTO {table_rel} ({from_col}, {to_col}) VALUES (?, ?)",
                (uuid_from, uuid_to)
            )
        except Exception as e:
            print(f"WARN: relation {from_ext}->{to_ext} failed for {rel_from}: {e}", file=sys.stderr)
    conn.commit()


def relate_models_chain(conn: sqlite3.Connection, state: IndexState, 
                       flatten_map: Optional[FlattenMapLoader] = None):
    cur = conn.cursor()
    pre_map = dict(state.by_ext.get('.preinstanced', {}))
    blend_map = dict(state.by_ext.get('.blend', {}))
    glb_map = dict(state.by_ext.get('.glb', {}))

    for rel_pre, uuid_pre in pre_map.items():
        if not rel_pre.lower().endswith('.preinstanced'):
            continue
        
        # Calculate related paths
        # Strategy: In FullFlattened mode, blend/glb are generated in the same directory
        # as the flattened preinstanced file, so we use the flattened path as base
        rel_common = rel_pre[:-len('.preinstanced')]
        rel_blend = rel_common + '.blend'
        rel_glb = rel_common + '.glb'
        
        # In FullFlattened mode with flatten map:
        # - Preinstanced is in the map (because it was in STROUT before flattening)
        # - Blend/GLB are NOT in map (generated after flattening)
        # - But they ARE in the same flattened directory structure
        # So we use the flattened preinstanced location to find them
        # (The code above already does this correctly - no changes needed!)
        
        uuid_blend = blend_map.get(rel_blend)
        uuid_glb = glb_map.get(rel_glb)
        
        if uuid_blend:
            try:
                cur.execute(
                    "INSERT OR IGNORE INTO preinstanced_blend_relationship (preinstanced_uuid, blend_uuid) VALUES (?, ?)",
                    (uuid_pre, uuid_blend)
                )
            except Exception as e:
                print(f"WARN: preinstanced->blend relation failed for {rel_pre}: {e}", file=sys.stderr)
        if uuid_glb and uuid_blend:
            try:
                cur.execute(
                    "INSERT OR IGNORE INTO glb_blend_relationship (glb_uuid, blend_uuid) VALUES (?, ?)",
                    (uuid_glb, uuid_blend)
                )
                cur.execute(
                    "INSERT OR IGNORE INTO preinstanced_blend_glb_relationship (preinstanced_uuid, blend_uuid, glb_uuid) VALUES (?, ?, ?)",
                    (uuid_pre, uuid_blend, uuid_glb)
                )
            except Exception as e:
                print(f"WARN: model chain relation failed for {rel_pre}: {e}", file=sys.stderr)
    conn.commit()


# --------------------
# Main
# --------------------

def main():
    args = parse_args()

    selected_region = args.region
    selected_index_type = args.index_type
    selected_renamed = args.renamed_base_dirs
    selected_audio = args.audio_reorg

    input_dir = args.input_dir
    output_dir = args.output_dir
    blend_dir = discover_blend_dir(output_dir, args.blend_dir)

    # Load flatten map if using FullFlattened mode
    flatten_map = None
    if selected_index_type == 'FullFlattened':
        flatten_map_dir = args.flatten_map_dir
        if not flatten_map_dir:
            # Auto-detect flatten map directory
            # Assume it's in the output_dir or a sibling directory
            if output_dir.endswith('STROUT'):
                flatten_map_dir = output_dir.replace('STROUT', 'STROUT_Normalized')
            else:
                flatten_map_dir = output_dir
        
        print(f"FullFlattened mode: Loading flatten maps from {flatten_map_dir}")
        try:
            flatten_map = FlattenMapLoader(flatten_map_dir)
        except Exception as e:
            print(f"FATAL: Failed to load flatten maps: {e}", file=sys.stderr)
            sys.exit(3)
        
        # In FullFlattened mode, use the flatten_map_dir as output_dir if different
        if flatten_map_dir != output_dir and os.path.isdir(flatten_map_dir):
            print(f"FullFlattened mode: Using flatten map directory as output directory: {flatten_map_dir}")
            output_dir = flatten_map_dir
            # Update blend_dir to match
            blend_dir = flatten_map_dir

    # Validate base folder names exist in Source, STROUT, TEMP_BLEND
    expected_bases = list(get_base_names(selected_renamed))
    try:
        # Source directory should have all base folders
        validate_base_folders(input_dir, expected_bases, 'Source (input-dir)', require_all=True)
        
        # Output and blend directories: in FullFlattened mode, not all folders may exist
        # (some may be empty and excluded from the flattened structure)
        require_all_output = (selected_index_type != 'FullFlattened')
        validate_base_folders(output_dir, expected_bases, 'STROUT (output-dir)', require_all=require_all_output)
        validate_base_folders(blend_dir, expected_bases, 'TEMP_BLEND (blend-dir)', require_all=require_all_output)
    except RuntimeError as e:
        print(f"FATAL: {e}", file=sys.stderr)
        sys.exit(2)

    # Compute DB path by pattern
    dbpath = rf"A:\\RemakeEngine\\EngineApps\\Games\\TheSimpsonsGame-PS3\\config\\GameFilesIndex_{selected_region}_{selected_index_type}-{selected_audio}-{selected_renamed}.db"

    # Ensure DB directory exists
    ensure_dir(os.path.dirname(dbpath))

    # Open DB and create schema
    conn = sqlite3.connect(dbpath)
    conn.execute("PRAGMA foreign_keys = ON;")
    conn.execute("PRAGMA journal_mode = WAL;")
    init_schema(conn)

    state = IndexState()

    # Select scanning strategy by Type
    # - SourceOnly: only index input_dir
    # - Full/FullFlattened: index input_dir, output_dir, and blend_dir
    try:
        if selected_index_type == 'SourceOnly':
            index_root_dir(conn, input_dir, None, state, None)
        else:
            # Index input dir (no flatten map for source files)
            index_root_dir(conn, input_dir, None, state, None)
            # Index output dir (with flatten map in FullFlattened mode)
            index_root_dir(conn, output_dir, None, state, flatten_map)
            # Blend dir may not exist for all projects; skip if missing
            if os.path.isdir(blend_dir):
                index_root_dir(conn, blend_dir, {'.blend'}, state, flatten_map)

        # Relationships
        if selected_index_type != 'SourceOnly':
            relate_str_contents(conn, input_dir, output_dir, state, flatten_map)

            # TXD -> DDS from both roots
            relate_txd_dds(conn, [input_dir, output_dir], state, flatten_map)

            # SNU -> WAV (by same rel path and extension swap) across input->output
            relate_ext_swap(conn, state, '.snu', '.wav', 'snu_wav_relationship', 'snu_uuid', 'wav_uuid', flatten_map)

            # VP6 -> OGV across input->output
            relate_ext_swap(conn, state, '.vp6', '.ogv', 'vp6_ogv_relationship', 'vp6_uuid', 'ogv_uuid', flatten_map)

            # DDS -> PNG within output
            relate_ext_swap(conn, state, '.dds', '.png', 'dds_png_relationship', 'dds_uuid', 'png_uuid', flatten_map)

            # Model relationships using STROUT (.preinstanced, .glb) and TEMP_BLEND (.blend)
            relate_models_chain(conn, state, flatten_map)

        print(f"Index complete. SQLite written to: {dbpath}")
    finally:
        conn.close()


if __name__ == '__main__':
    main()


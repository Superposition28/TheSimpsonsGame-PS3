"""

"""
import os
import sqlite3
import hashlib
import re
import subprocess
import json
import sys
import argparse
from pathlib import Path
from typing import List, Dict, Tuple
import tomllib

# ============================================================================
# CONFIGURATION
# ============================================================================

# Paths
SCRIPT_DIR = Path(__file__).resolve().parent
GAME_ROOT = SCRIPT_DIR.parent
PROJECT_ROOT = GAME_ROOT.parent.parent.parent
GAME_FILES_DIR = GAME_ROOT / "GameFiles"
CONFIG_DB_PATH = GAME_ROOT / "config" / "UniversalIndex.db"
RENAME_MAP_PATH = GAME_ROOT / "config" / "RenameMap.db"
OPS_TOML_PATH = GAME_ROOT / "operations.toml"

# Engine Execution
DOTNET_CMD = ["dotnet", "run", "-c", "Release", "--project", str(PROJECT_ROOT / "EngineNet"), "--framework", "net9.0", "--"]
GAME_MODULE_ARG = ["--game_module", str(GAME_ROOT)]

# Indexing Rules
IGNORE_DIRS = {'.git', '__pycache__'}
AUDIO_STRIP_DIRS = {'en', 'global'}
NORMALIZED_UID_PATTERN = re.compile(r'_([0-9a-fA-F]{6})(\.[a-zA-Z0-9]+)+$')

# Extension to table mapping - organizes files by type
EXT_TO_TABLE = {
    '.str': 'archives',
    '.preinstanced': 'models_preinstanced',
    '.rws.ps3.preinstanced': 'models_preinstanced',
    '.blend': 'models_blend',
    '.rws.ps3.blend': 'models_blend',
    '.glb': 'models_glb',
    '.rws.ps3.glb': 'models_glb',
    '.fbx': 'models_fbx',
    '.txd': 'textures_txd',
    '.dds': 'textures_dds',
    '.png': 'textures_png',
    '.vp6': 'videos_source',
    '.ogv': 'videos_converted',
    '.snu': 'audio_source',
    '.wav': 'audio_converted',
    '.mus': 'audio_music',
}

# ============================================================================
# PERMUTATION DEFINITIONS
# ============================================================================

PERMUTATIONS = [
    # --- EU VARIANTS ---
    {
        "name": "EU_Full_audio_og_notRenamed",
        "config": {
            "Region": "EU",
            "Type": "Full",
            "audio_state": "audio_og",
            "isRenamed": "notRenamed",
            "STROUT": "STROUT",
            "MainSourcePath": str(GAME_ROOT / "Source" / "EU" / "PS3_GAME" / "USRDIR"),
            "SourcePath": str(GAME_ROOT / "Source"),
            "PostSourcePath": "PS3_GAME\\USRDIR"
        },
        # Extract(6), Convert Vid(12), Convert Aud(13), Extract Tex(8), Convert Tex(9), Convert Model(11)
        "ops": [6, 12, 13, 8, 9, 11]
    },
    {
        "name": "EU_Full_audio_og_isRenamed",
        "config": {
            "Region": "EU",
            "Type": "Full",
            "audio_state": "audio_og",
            "isRenamed": "isRenamed",
            "STROUT": "STROUT",
            "MainSourcePath": str(GAME_ROOT / "Source" / "EU" / "PS3_GAME" / "USRDIR"),
            "SourcePath": str(GAME_ROOT / "Source"),
            "PostSourcePath": "PS3_GAME\\USRDIR"
        },
        # + Rename(3)
        "ops": [6, 12, 13, 8, 9, 11, 3]
    },
    {
        "name": "EU_Full_audio_reorg_isRenamed",
        "config": {
            "Region": "EU",
            "Type": "Full",
            "audio_state": "audio_reorg",
            "isRenamed": "isRenamed",
            "STROUT": "STROUT",
            "MainSourcePath": str(GAME_ROOT / "Source" / "EU" / "PS3_GAME" / "USRDIR"),
            "SourcePath": str(GAME_ROOT / "Source"),
            "PostSourcePath": "PS3_GAME\\USRDIR"
        },
        # + Reorg Audio(4) - Note: Audio Reorg usually runs AFTER Rename
        "ops": [6, 12, 13, 8, 9, 11, 3, 4]
    },
    # --- NORMALIZED VARIANTS ---
    {
        "name": "EU_FullFlattened_audio_reorg_isRenamed",
        "config": {
            "Region": "EU",
            "Type": "FullFlattened",
            "audio_state": "audio_reorg",
            "isRenamed": "isRenamed",
            "STROUT": "STROUT_Normalized",
            "MainSourcePath": str(GAME_ROOT / "Source" / "EU" / "PS3_GAME" / "USRDIR"),
            "SourcePath": str(GAME_ROOT / "Source"),
            "PostSourcePath": "PS3_GAME\\USRDIR"
        },
        # + Normalize(7) - Runs on the result of the previous steps
        "ops": [6, 12, 13, 8, 9, 11, 3, 4, 7]
    }
]

# ============================================================================
# DATABASE MANAGER
# ============================================================================

def compute_file_hash(path: Path) -> str:
    """Compute SHA256 hash of file contents"""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(1024 * 1024):
            h.update(chunk)
    return h.hexdigest()

def compute_path_hash(rel_path: str) -> str:
    """
    Compute MD5 hash of path after first folder, without extension.
    Example: "folder1/folder2/file.ext" -> hash("folder2/file")
    """
    parts = Path(rel_path).parts
    if len(parts) <= 1:
        # Just filename, no folders
        stem = Path(rel_path).stem
        return hashlib.md5(stem.encode('utf-8')).hexdigest()

    # Skip first folder, exclude extension
    path_without_first = "/".join(parts[1:])
    path_without_ext = str(Path(path_without_first).with_suffix(''))
    return hashlib.md5(path_without_ext.encode('utf-8')).hexdigest()

def make_uuid(file_hash: str, path_hash: str) -> str:
    """Create UUID from file hash + path hash"""
    return f"{file_hash[:16]}_{path_hash[:16]}"

def get_file_extension(filename: str) -> str:
    """
    Get full extension for multi-part extensions.
    Examples:
    - file.rws.ps3.preinstanced -> .rws.ps3.preinstanced
    - file.blend -> .blend
    """
    parts = filename.lower().split('.')
    if len(parts) <= 1:
        return ''

    # Check for multi-part extensions
    if len(parts) >= 3:
        if parts[-3] in ['rws', 'rwx'] and parts[-2] in ['ps3', 'pc']:
            return '.' + '.'.join(parts[-3:])

    return '.' + parts[-1]

def table_for_extension(ext: str) -> str:
    """Map file extension to database table name"""
    ext_lower = ext.lower()
    return EXT_TO_TABLE.get(ext_lower, 'other_files')

def init_db(db_path: Path):
    """Initialize database with improved schema organized by file type"""
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    c = conn.cursor()

    # Permutations table (unchanged)
    c.execute('''CREATE TABLE IF NOT EXISTS permutations (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT UNIQUE,
        region TEXT,
        build_type TEXT,
        audio_state TEXT,
        renamed_state TEXT,
        normalized INTEGER
    )''')

    # Assets table with enhanced metadata
    c.execute('''CREATE TABLE IF NOT EXISTS assets (
        uid TEXT PRIMARY KEY,
        canonical_stem TEXT,
        simple_name TEXT,
        file_type TEXT,
        base_extension TEXT
    )''')

    # File type specific tables - Archives (STR files)
    c.execute('''CREATE TABLE IF NOT EXISTS archives (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        uuid TEXT UNIQUE NOT NULL,
        asset_uid TEXT NOT NULL,
        perm_id INTEGER NOT NULL,
        filename TEXT NOT NULL,
        rel_path TEXT NOT NULL,
        full_path TEXT NOT NULL,
        extension TEXT NOT NULL,
        file_hash TEXT NOT NULL,
        path_hash TEXT NOT NULL,
        size_bytes INTEGER NOT NULL,
        first_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY(asset_uid) REFERENCES assets(uid),
        FOREIGN KEY(perm_id) REFERENCES permutations(id)
    )''')

    # Models - Preinstanced
    c.execute('''CREATE TABLE IF NOT EXISTS models_preinstanced (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        uuid TEXT UNIQUE NOT NULL,
        asset_uid TEXT NOT NULL,
        perm_id INTEGER NOT NULL,
        filename TEXT NOT NULL,
        rel_path TEXT NOT NULL,
        full_path TEXT NOT NULL,
        extension TEXT NOT NULL,
        file_hash TEXT NOT NULL,
        path_hash TEXT NOT NULL,
        size_bytes INTEGER NOT NULL,
        parent_archive_uid TEXT,
        first_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY(asset_uid) REFERENCES assets(uid),
        FOREIGN KEY(perm_id) REFERENCES permutations(id)
    )''')

    # Models - Blend
    c.execute('''CREATE TABLE IF NOT EXISTS models_blend (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        uuid TEXT UNIQUE NOT NULL,
        asset_uid TEXT NOT NULL,
        perm_id INTEGER NOT NULL,
        filename TEXT NOT NULL,
        rel_path TEXT NOT NULL,
        full_path TEXT NOT NULL,
        extension TEXT NOT NULL,
        file_hash TEXT NOT NULL,
        path_hash TEXT NOT NULL,
        size_bytes INTEGER NOT NULL,
        source_preinstanced_uid TEXT,
        first_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY(asset_uid) REFERENCES assets(uid),
        FOREIGN KEY(perm_id) REFERENCES permutations(id)
    )''')

    # Models - GLB
    c.execute('''CREATE TABLE IF NOT EXISTS models_glb (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        uuid TEXT UNIQUE NOT NULL,
        asset_uid TEXT NOT NULL,
        perm_id INTEGER NOT NULL,
        filename TEXT NOT NULL,
        rel_path TEXT NOT NULL,
        full_path TEXT NOT NULL,
        extension TEXT NOT NULL,
        file_hash TEXT NOT NULL,
        path_hash TEXT NOT NULL,
        size_bytes INTEGER NOT NULL,
        source_blend_uid TEXT,
        source_preinstanced_uid TEXT,
        first_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY(asset_uid) REFERENCES assets(uid),
        FOREIGN KEY(perm_id) REFERENCES permutations(id)
    )''')

    # Models - FBX
    c.execute('''CREATE TABLE IF NOT EXISTS models_fbx (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        uuid TEXT UNIQUE NOT NULL,
        asset_uid TEXT NOT NULL,
        perm_id INTEGER NOT NULL,
        filename TEXT NOT NULL,
        rel_path TEXT NOT NULL,
        full_path TEXT NOT NULL,
        extension TEXT NOT NULL,
        file_hash TEXT NOT NULL,
        path_hash TEXT NOT NULL,
        size_bytes INTEGER NOT NULL,
        first_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY(asset_uid) REFERENCES assets(uid),
        FOREIGN KEY(perm_id) REFERENCES permutations(id)
    )''')

    # Textures - TXD
    c.execute('''CREATE TABLE IF NOT EXISTS textures_txd (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        uuid TEXT UNIQUE NOT NULL,
        asset_uid TEXT NOT NULL,
        perm_id INTEGER NOT NULL,
        filename TEXT NOT NULL,
        rel_path TEXT NOT NULL,
        full_path TEXT NOT NULL,
        extension TEXT NOT NULL,
        file_hash TEXT NOT NULL,
        path_hash TEXT NOT NULL,
        size_bytes INTEGER NOT NULL,
        parent_archive_uid TEXT,
        first_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY(asset_uid) REFERENCES assets(uid),
        FOREIGN KEY(perm_id) REFERENCES permutations(id)
    )''')

    # Textures - DDS
    c.execute('''CREATE TABLE IF NOT EXISTS textures_dds (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        uuid TEXT UNIQUE NOT NULL,
        asset_uid TEXT NOT NULL,
        perm_id INTEGER NOT NULL,
        filename TEXT NOT NULL,
        rel_path TEXT NOT NULL,
        full_path TEXT NOT NULL,
        extension TEXT NOT NULL,
        file_hash TEXT NOT NULL,
        path_hash TEXT NOT NULL,
        size_bytes INTEGER NOT NULL,
        parent_txd_uid TEXT,
        first_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY(asset_uid) REFERENCES assets(uid),
        FOREIGN KEY(perm_id) REFERENCES permutations(id)
    )''')

    # Textures - PNG
    c.execute('''CREATE TABLE IF NOT EXISTS textures_png (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        uuid TEXT UNIQUE NOT NULL,
        asset_uid TEXT NOT NULL,
        perm_id INTEGER NOT NULL,
        filename TEXT NOT NULL,
        rel_path TEXT NOT NULL,
        full_path TEXT NOT NULL,
        extension TEXT NOT NULL,
        file_hash TEXT NOT NULL,
        path_hash TEXT NOT NULL,
        size_bytes INTEGER NOT NULL,
        source_dds_uid TEXT,
        first_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY(asset_uid) REFERENCES assets(uid),
        FOREIGN KEY(perm_id) REFERENCES permutations(id)
    )''')

    # Videos - Source (VP6)
    c.execute('''CREATE TABLE IF NOT EXISTS videos_source (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        uuid TEXT UNIQUE NOT NULL,
        asset_uid TEXT NOT NULL,
        perm_id INTEGER NOT NULL,
        filename TEXT NOT NULL,
        rel_path TEXT NOT NULL,
        full_path TEXT NOT NULL,
        extension TEXT NOT NULL,
        file_hash TEXT NOT NULL,
        path_hash TEXT NOT NULL,
        size_bytes INTEGER NOT NULL,
        first_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY(asset_uid) REFERENCES assets(uid),
        FOREIGN KEY(perm_id) REFERENCES permutations(id)
    )''')

    # Videos - Converted (OGV)
    c.execute('''CREATE TABLE IF NOT EXISTS videos_converted (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        uuid TEXT UNIQUE NOT NULL,
        asset_uid TEXT NOT NULL,
        perm_id INTEGER NOT NULL,
        filename TEXT NOT NULL,
        rel_path TEXT NOT NULL,
        full_path TEXT NOT NULL,
        extension TEXT NOT NULL,
        file_hash TEXT NOT NULL,
        path_hash TEXT NOT NULL,
        size_bytes INTEGER NOT NULL,
        source_video_uid TEXT,
        first_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY(asset_uid) REFERENCES assets(uid),
        FOREIGN KEY(perm_id) REFERENCES permutations(id)
    )''')

    # Audio - Source (SNU)
    c.execute('''CREATE TABLE IF NOT EXISTS audio_source (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        uuid TEXT UNIQUE NOT NULL,
        asset_uid TEXT NOT NULL,
        perm_id INTEGER NOT NULL,
        filename TEXT NOT NULL,
        rel_path TEXT NOT NULL,
        full_path TEXT NOT NULL,
        extension TEXT NOT NULL,
        file_hash TEXT NOT NULL,
        path_hash TEXT NOT NULL,
        size_bytes INTEGER NOT NULL,
        first_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY(asset_uid) REFERENCES assets(uid),
        FOREIGN KEY(perm_id) REFERENCES permutations(id)
    )''')

    # Audio - Converted (WAV)
    c.execute('''CREATE TABLE IF NOT EXISTS audio_converted (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        uuid TEXT UNIQUE NOT NULL,
        asset_uid TEXT NOT NULL,
        perm_id INTEGER NOT NULL,
        filename TEXT NOT NULL,
        rel_path TEXT NOT NULL,
        full_path TEXT NOT NULL,
        extension TEXT NOT NULL,
        file_hash TEXT NOT NULL,
        path_hash TEXT NOT NULL,
        size_bytes INTEGER NOT NULL,
        source_audio_uid TEXT,
        first_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY(asset_uid) REFERENCES assets(uid),
        FOREIGN KEY(perm_id) REFERENCES permutations(id)
    )''')

    # Audio - Music (MUS)
    c.execute('''CREATE TABLE IF NOT EXISTS audio_music (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        uuid TEXT UNIQUE NOT NULL,
        asset_uid TEXT NOT NULL,
        perm_id INTEGER NOT NULL,
        filename TEXT NOT NULL,
        rel_path TEXT NOT NULL,
        full_path TEXT NOT NULL,
        extension TEXT NOT NULL,
        file_hash TEXT NOT NULL,
        path_hash TEXT NOT NULL,
        size_bytes INTEGER NOT NULL,
        first_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY(asset_uid) REFERENCES assets(uid),
        FOREIGN KEY(perm_id) REFERENCES permutations(id)
    )''')

    # Other files (fallback)
    c.execute('''CREATE TABLE IF NOT EXISTS other_files (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        uuid TEXT UNIQUE NOT NULL,
        asset_uid TEXT NOT NULL,
        perm_id INTEGER NOT NULL,
        filename TEXT NOT NULL,
        rel_path TEXT NOT NULL,
        full_path TEXT NOT NULL,
        extension TEXT NOT NULL,
        file_hash TEXT NOT NULL,
        path_hash TEXT NOT NULL,
        size_bytes INTEGER NOT NULL,
        first_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY(asset_uid) REFERENCES assets(uid),
        FOREIGN KEY(perm_id) REFERENCES permutations(id)
    )''')

    # Create indexes for efficient lookups
    tables = [
        'archives', 'models_preinstanced', 'models_blend', 'models_glb', 'models_fbx',
        'textures_txd', 'textures_dds', 'textures_png',
        'videos_source', 'videos_converted',
        'audio_source', 'audio_converted', 'audio_music',
        'other_files'
    ]

    for table in tables:
        c.execute(f'CREATE INDEX IF NOT EXISTS idx_{table}_asset_uid ON {table}(asset_uid)')
        c.execute(f'CREATE INDEX IF NOT EXISTS idx_{table}_perm_id ON {table}(perm_id)')
        c.execute(f'CREATE INDEX IF NOT EXISTS idx_{table}_file_hash ON {table}(file_hash)')
        c.execute(f'CREATE INDEX IF NOT EXISTS idx_{table}_path_hash ON {table}(path_hash)')
        c.execute(f'CREATE INDEX IF NOT EXISTS idx_{table}_lookup ON {table}(perm_id, asset_uid)')

    # Create triggers for automatic last_updated
    for table in tables:
        c.execute(f'''
            CREATE TRIGGER IF NOT EXISTS update_{table}_timestamp
            AFTER UPDATE ON {table}
            FOR EACH ROW
            BEGIN
                UPDATE {table} SET last_updated = CURRENT_TIMESTAMP WHERE id = OLD.id;
            END
        ''')

    conn.commit()
    return conn

# ============================================================================
# OPERATIONS MANAGER
# ============================================================================

class OperationsManager:
    def __init__(self, toml_path: Path):
        if not toml_path.exists():
            raise FileNotFoundError(f"operations.toml not found at {toml_path}")

        with open(toml_path, "rb") as f:
            data = tomllib.load(f)

        # Create lookup map by ID
        self.ops = {}
        raw_ops = data.get('operation', [])
        for op in raw_ops:
            self.ops[op['id']] = op

    def get_execution_params(self, op_id: int) -> Tuple[str, str, List[str]]:
        """
        Returns (script_type, script_path, additional_args_list)
        For BMS operations, returns --set arguments for input/output/extension.
        For other operations with 'args', returns the args list.
        """
        op = self.ops.get(op_id)
        if not op:
            raise ValueError(f"Operation ID {op_id} not found in toml")

        s_type = op.get('script_type', 'lua')
        script = op.get('script', '')
        additional_args = []

        # 1. Handle BMS case - pass input/output/extension as operation fields
        if s_type == 'bms':
            if 'input' in op:
                additional_args.extend(['--set', f'input={op["input"]}'])
            if 'output' in op:
                additional_args.extend(['--set', f'output={op["output"]}'])
            if 'extension' in op:
                additional_args.extend(['--set', f'extension={op["extension"]}'])

        # 2. Handle Standard 'args' list + Prompts
        else:
            script_args = op.get('args', []).copy()

            # Process prompts for default values
            prompts = op.get('prompts', [])
            prompt_values = {}

            for prompt in prompts:
                name = prompt.get('Name')
                default_val = prompt.get('default')

                if name:
                    prompt_values[name] = default_val

                # Check condition
                condition = prompt.get('condition')
                if condition and condition in prompt_values and not prompt_values[condition]:
                    continue

                if default_val is None:
                    continue

                p_type = prompt.get('type')
                if p_type == 'confirm' and default_val is True and 'cli_arg' in prompt:
                    script_args.append(prompt['cli_arg'])
                elif p_type == 'checkbox' and 'cli_prefix' in prompt and isinstance(default_val, list):
                    for v in default_val:
                        script_args.append(prompt['cli_prefix'])
                        script_args.append(str(v))
                elif p_type == 'select' and 'cli_prefix' in prompt:
                    script_args.append(prompt['cli_prefix'])
                    script_args.append(str(default_val))

            if script_args:
                additional_args.extend(['--args', json.dumps(script_args)])

        return s_type, script, additional_args

# ============================================================================
# ENGINE CONTROLLER
# ============================================================================

class EngineController:
    def __init__(self, ops_manager: OperationsManager):
        self.ops = ops_manager

    def update_config(self, key_values: Dict[str, str]):
        """Calls config.lua to update placeholders in config.toml"""
        for key, val in key_values.items():
            cmd = DOTNET_CMD + GAME_MODULE_ARG + [
                "--script_type", "lua",
                "--script", "{{Game_Root}}/config.lua",
                "--args", json.dumps(["--group", "placeholders", "--set", f"{key}={val}:string"])
            ]
            subprocess.run(cmd, check=True, capture_output=True)

    def run_operation(self, op_id: int):
        """Runs a specific operation by reading TOML and executing via CLI"""
        print(f"  [Engine] Running Op {op_id}...")

        try:
            s_type, script, additional_args = self.ops.get_execution_params(op_id)

            cmd = DOTNET_CMD + GAME_MODULE_ARG + [
                "--script_type", s_type,
                "--script", script
            ] + additional_args

            # Execute
            subprocess.run(cmd, check=True, capture_output=False)

        except Exception as e:
            print(f"!! Error running Operation {op_id}: {e}")
            raise e

# ============================================================================
# SCANNER LOGIC
# ============================================================================

class Scanner:
    def __init__(self, rename_db: Path):
        self.rename_map = {}
        if rename_db.exists():
            c = sqlite3.connect(rename_db)
            try:
                for old, new in c.execute("SELECT old_name, new_name FROM rename_mappings"):
                    if new: self.rename_map[new.lower()] = old
            except sqlite3.OperationalError:
                pass
            c.close()

    def generate_uid(self, rel_path: str, is_norm: bool, is_renamed: bool) -> Tuple[str, str, str]:
        path = Path(rel_path)
        filename = path.name

        # 1. Try Filename Extraction (Fastest for Normalized)
        if is_norm:
            match = NORMALIZED_UID_PATTERN.search(filename)
            if match:
                return match.group(1), filename, filename.split('.')[0]

        # 2. Calculate from Canonical Path
        parts = list(path.parts)
        clean_parts = []

        for p in parts[:-1]:
            pl = p.lower()
            # Reverse Rename if needed (New -> Old)
            if is_renamed and pl in self.rename_map:
                clean_parts.append(self.rename_map[pl])
            # Strip Audio Reorg folders
            elif pl in AUDIO_STRIP_DIRS:
                continue
            else:
                clean_parts.append(p)

        # Add filename stem (no ext)
        simple_name = filename.split('.')[0]
        clean_parts.append(simple_name)

        canonical_stem = "/".join(clean_parts).replace("\\", "/").lower()
        uid = hashlib.md5(canonical_stem.encode('utf-8')).hexdigest()[:6]

        return uid, canonical_stem, simple_name

# ============================================================================
# JSON EXPORT
# ============================================================================

def export_to_json(db_path: Path, json_path: Path, pretty: bool = True):
    """
    Export the SQLite database to JSON format.
    """
    print(f"\n  [JSON Export] Reading from database: {db_path}")

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    # 1. Export Permutations (mirrors: permutations table)
    cursor.execute("SELECT id, name, region, build_type, audio_state, renamed_state, normalized FROM permutations")
    permutations = []
    for row in cursor.fetchall():
        permutations.append({
            "id": row["id"],
            "name": row["name"],
            "region": row["region"],
            "build_type": row["build_type"],
            "audio_state": row["audio_state"],
            "renamed_state": row["renamed_state"],
            "normalized": bool(row["normalized"])
        })

    # 2. Export Assets with their files from all tables
    cursor.execute("SELECT uid, canonical_stem, simple_name, file_type, base_extension FROM assets")
    assets = []

    # All file tables to query
    file_tables = [
        'archives', 'models_preinstanced', 'models_blend', 'models_glb', 'models_fbx',
        'textures_txd', 'textures_dds', 'textures_png',
        'videos_source', 'videos_converted',
        'audio_source', 'audio_converted', 'audio_music',
        'other_files'
    ]

    total_files = 0
    files_by_table = {}

    for row in cursor.fetchall():
        asset_uid = row["uid"]

        # Get files from each table for this asset
        files_data = {}
        for table in file_tables:
            cursor.execute(f"""
                SELECT id, uuid, perm_id, filename, rel_path, full_path, extension,
                       file_hash, path_hash, size_bytes, first_seen, last_updated
                FROM {table}
                WHERE asset_uid = ?
                ORDER BY perm_id, rel_path
            """, (asset_uid,))

            table_files = []
            for file_row in cursor.fetchall():
                table_files.append({
                    "id": file_row["id"],
                    "uuid": file_row["uuid"],
                    "perm_id": file_row["perm_id"],
                    "filename": file_row["filename"],
                    "rel_path": file_row["rel_path"],
                    "full_path": file_row["full_path"],
                    "extension": file_row["extension"],
                    "file_hash": file_row["file_hash"],
                    "path_hash": file_row["path_hash"],
                    "size_bytes": file_row["size_bytes"],
                    "first_seen": file_row["first_seen"],
                    "last_updated": file_row["last_updated"]
                })

            if table_files:
                files_data[table] = table_files
                total_files += len(table_files)
                files_by_table[table] = files_by_table.get(table, 0) + len(table_files)

        if files_data:  # Only add asset if it has files
            assets.append({
                "uid": row["uid"],
                "canonical_stem": row["canonical_stem"],
                "simple_name": row["simple_name"],
                "file_type": row["file_type"],
                "base_extension": row["base_extension"],
                "files": files_data
            })

    # 3. Generate Metadata
    metadata = {
        "total_permutations": len(permutations),
        "total_assets": len(assets),
        "total_files": total_files,
        "files_by_table": files_by_table
    }

    conn.close()

    # 4. Build final JSON structure
    output = {
        "permutations": permutations,
        "assets": assets,
        "metadata": metadata
    }

    # 5. Write to file
    print(f"  [JSON Export] Writing to: {json_path}")
    with open(json_path, 'w', encoding='utf-8') as f:
        if pretty:
            json.dump(output, f, indent=2, ensure_ascii=False)
        else:
            json.dump(output, f, ensure_ascii=False)

    print(f"  [JSON Export] Complete - {metadata['total_assets']} assets, {metadata['total_files']} files")

# ============================================================================
# MAIN LOOP
# ============================================================================

def main():
    # Parse command-line arguments
    parser = argparse.ArgumentParser(
        description="Universal Permutation Indexer v10 - Builds and indexes all game file permutations with source file support"
    )
    parser.add_argument(
        '--generate',
        action='store_true',
        help='Run engine operations to generate output files (default: skip and just index existing files)'
    )
    parser.add_argument(
        '--json',
        action='store_true',
        help='Export the database to JSON format after indexing'
    )
    parser.add_argument(
        '--json-output',
        default=None,
        help='Path for JSON output file (default: same as db but .json extension)'
    )
    parser.add_argument(
        '--compact',
        action='store_true',
        help='Output compact JSON (no pretty printing)'
    )

    args = parser.parse_args()

    print("--- Universal Permutation Indexer v10 ---")
    if args.generate:
        print("Mode: Generation + Indexing")
    else:
        print("Mode: Indexing Only (Existing Files)")

    # 1. Setup
    conn = init_db(CONFIG_DB_PATH)
    cursor = conn.cursor()
    ops_mgr = OperationsManager(OPS_TOML_PATH)
    engine = EngineController(ops_mgr)

    # 2. Build & Index Loop
    for perm in PERMUTATIONS:
        print(f"\n>>> Processing Permutation: {perm['name']}")

        cfg = perm['config']

        # A. Generation (Optional)
        if args.generate:
            # Update config used by engine
            engine.update_config(cfg)

            # Run Operations
            try:
                for op_id in perm['ops']:
                    engine.run_operation(op_id)
            except Exception as e:
                print(f"Skipping index for {perm['name']} due to build error. {e}")
                continue
        else:
            print("  [Engine] Skipping operations (Generation disabled)")

        # B. Define Directories to Scan
        # 1. Output Directory (GameFiles/STROUT-...)
        dir_name = f"{cfg.get('STROUT')}-{cfg['Region']}_{cfg['Type']}-{cfg['audio_state']}-{cfg['isRenamed']}"
        target_dir = GAME_FILES_DIR / dir_name

        # 2. Source Directory (Source/EU/PS3_GAME/USRDIR)
        source_dir = Path(cfg['MainSourcePath'])

        dirs_to_scan = [
            (target_dir, "Output"),
            (source_dir, "Source")
        ]

        # C. Register Permutation
        is_norm = (cfg.get('STROUT') == 'STROUT_Normalized')
        is_renamed = (cfg.get('isRenamed') == 'isRenamed')

        cursor.execute("INSERT OR IGNORE INTO permutations (name, region, build_type, audio_state, renamed_state, normalized) VALUES (?,?,?,?,?,?)",
            (perm['name'], cfg['Region'], cfg['Type'], cfg['audio_state'], cfg['isRenamed'], 1 if is_norm else 0))
        cursor.execute("SELECT id FROM permutations WHERE name=?", (perm['name'],))
        perm_id = cursor.fetchone()[0]

        # D. Index Files
        # Reload scanner to ensure fresh RenameMap is loaded
        scanner = Scanner(RENAME_MAP_PATH)
        batch_by_table = {}

        for root_path, tag in dirs_to_scan:
            if not root_path.exists():
                print(f"  [Indexer] Warning: {tag} directory not found: {root_path}")
                continue

            print(f"  [Indexer] Scanning {tag}: {root_path.name}...")

            for root, dirs, files in os.walk(root_path):
                # Filter out ignored directories
                dirs[:] = [d for d in dirs if d not in IGNORE_DIRS]

                for file in files:
                    abs_path = Path(root) / file

                    # Calculate relative path based on the specific root we are currently scanning
                    # This ensures source files are relative to SourcePath, and output files relative to TargetDir
                    rel_path = str(abs_path.relative_to(root_path)).replace("\\", "/")

                    # Generate UID and metadata
                    uid, canon, simple = scanner.generate_uid(rel_path, is_norm, is_renamed)

                    # Compute file hashes
                    file_hash = compute_file_hash(abs_path)
                    path_hash = compute_path_hash(rel_path)
                    uuid = make_uuid(file_hash, path_hash)

                    # Determine file type and table
                    extension = get_file_extension(file)
                    table_name = table_for_extension(extension)
                    file_type = table_name.split('_')[0] if '_' in table_name else table_name

                    # Register Asset with enhanced metadata
                    cursor.execute(
                        "INSERT OR IGNORE INTO assets (uid, canonical_stem, simple_name, file_type, base_extension) VALUES (?,?,?,?,?)",
                        (uid, canon, simple, file_type, extension)
                    )

                    # Prepare file record for batch insert
                    if table_name not in batch_by_table:
                        batch_by_table[table_name] = []

                    batch_by_table[table_name].append((
                        uuid, uid, perm_id, file, rel_path, str(abs_path),
                        extension, file_hash, path_hash, abs_path.stat().st_size
                    ))

                    # Batch commit per table
                    if len(batch_by_table[table_name]) > 5000:
                        cursor.executemany(
                            f"INSERT OR IGNORE INTO {table_name} (uuid, asset_uid, perm_id, filename, rel_path, full_path, extension, file_hash, path_hash, size_bytes) VALUES (?,?,?,?,?,?,?,?,?,?)",
                            batch_by_table[table_name]
                        )
                        batch_by_table[table_name] = []
                        conn.commit()

        # Final batch inserts
        for table_name, batch in batch_by_table.items():
            if batch:
                cursor.executemany(
                    f"INSERT OR IGNORE INTO {table_name} (uuid, asset_uid, perm_id, filename, rel_path, full_path, extension, file_hash, path_hash, size_bytes) VALUES (?,?,?,?,?,?,?,?,?,?)",
                    batch
                )
                conn.commit()

        print(f"  [Indexer] Complete.")

    conn.close()
    print("\nAll permutations indexed successfully.")

    # 3. Export to JSON (if requested)
    if args.json:
        print("\n--- JSON Export ---")
        json_output = args.json_output
        if json_output is None:
            json_output = CONFIG_DB_PATH.with_suffix('.json')
        else:
            json_output = Path(json_output)

        export_to_json(CONFIG_DB_PATH, json_output, pretty=not args.compact)
        print(f"JSON export saved to: {json_output}")

if __name__ == "__main__":
    main()

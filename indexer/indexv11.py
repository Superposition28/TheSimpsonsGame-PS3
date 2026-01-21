"""

"""

import os
import sqlite3
import hashlib
import re
import subprocess
import json
import argparse
import multiprocessing
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
DOTNET_CMD = ["dotnet", "run", "-c", "Release", "--no-build", "--project", str(PROJECT_ROOT / "EngineNet"), "--framework", "net9.0", "--"]
GAME_MODULE_ARG = ["--game_module", str(GAME_ROOT)]

# Indexing Rules
IGNORE_DIRS = {'.git', '__pycache__', 'text', 'A1_Video', 'A1_Audio'}
AUDIO_STRIP_DIRS = {'en', 'global', 'us', 'eu'}
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
        "ops": [6, 12, 13, 8, 9, 11, 3, 4, 7]
    }
]

# ============================================================================
# UTILITY FUNCTIONS
# ============================================================================

def compute_file_hash(path: Path) -> str:
    """Compute SHA256 hash of file contents"""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(1024 * 1024):
            h.update(chunk)
    return h.hexdigest()

def compute_path_hash(rel_path: str) -> str:
    """Compute MD5 hash of path after first folder, without extension."""
    parts = Path(rel_path).parts
    if len(parts) <= 1:
        stem = Path(rel_path).stem
        return hashlib.md5(stem.encode('utf-8')).hexdigest()

    path_without_first = "/".join(parts[1:])
    path_without_ext = str(Path(path_without_first).with_suffix(''))
    return hashlib.md5(path_without_ext.encode('utf-8')).hexdigest()

def make_uuid(file_hash: str, path_hash: str) -> str:
    """Create UUID from file hash + path hash"""
    return f"{file_hash[:16]}_{path_hash[:16]}"

def get_file_extension(filename: str) -> str:
    """Get full extension for multi-part extensions."""
    parts = filename.lower().split('.')
    if len(parts) <= 1: return ''
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

    # WAL Mode for better concurrency during multiprocessing
    conn.execute("PRAGMA journal_mode=WAL;")

    c = conn.cursor()

    # Permutations table
    c.execute('''CREATE TABLE IF NOT EXISTS permutations (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT UNIQUE,
        region TEXT,
        build_type TEXT,
        audio_state TEXT,
        renamed_state TEXT,
        normalized INTEGER
    )''')

    # Assets table
    c.execute('''CREATE TABLE IF NOT EXISTS assets (
        uid TEXT PRIMARY KEY,
        canonical_stem TEXT,
        simple_name TEXT,
        file_type TEXT,
        base_extension TEXT
    )''')

    # File type specific tables
    tables = list(set(EXT_TO_TABLE.values())) + ['other_files']

    for table in tables:
        c.execute(f'''CREATE TABLE IF NOT EXISTS {table} (
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
            source_uid TEXT,
            first_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(asset_uid) REFERENCES assets(uid),
            FOREIGN KEY(perm_id) REFERENCES permutations(id)
        )''')

    # Indexes
    for table in tables:
        c.execute(f'CREATE INDEX IF NOT EXISTS idx_{table}_asset_uid ON {table}(asset_uid)')
        c.execute(f'CREATE INDEX IF NOT EXISTS idx_{table}_perm_id ON {table}(perm_id)')
        c.execute(f'CREATE INDEX IF NOT EXISTS idx_{table}_lookup ON {table}(perm_id, asset_uid)')

    # Triggers
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
    conn.close()

# ============================================================================
# CLASSES (Ops, Engine, Scanner)
# ============================================================================

class OperationsManager:
    def __init__(self, toml_path: Path):
        if not toml_path.exists():
            raise FileNotFoundError(f"operations.toml not found at {toml_path}")
        with open(toml_path, "rb") as f:
            data = tomllib.load(f)
        self.ops = {}
        for op in data.get('operation', []):
            self.ops[op['id']] = op

    def get_execution_params(self, op_id: int) -> Tuple[str, str, List[str]]:
        op = self.ops.get(op_id)
        if not op: raise ValueError(f"Operation ID {op_id} not found")
        s_type = op.get('script_type', 'lua')
        script = op.get('script', '')
        additional_args = []
        if s_type == 'bms':
            if 'input' in op: additional_args.extend(['--set', f'input={op["input"]}'])
            if 'output' in op: additional_args.extend(['--set', f'output={op["output"]}'])
            if 'extension' in op: additional_args.extend(['--set', f'extension={op["extension"]}'])
        else:
            script_args = op.get('args', []).copy()
            prompts = op.get('prompts', [])
            prompt_values = {}
            for prompt in prompts:
                name = prompt.get('Name')
                default_val = prompt.get('default')
                if name: prompt_values[name] = default_val

                condition = prompt.get('condition')
                if condition and condition in prompt_values and not prompt_values[condition]:
                    continue

                if default_val is None: continue

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

class EngineController:
    def __init__(self, ops_manager: OperationsManager):
        self.ops = ops_manager

    def run_operation(self, op_id: int, config_overrides: Dict[str, str] = None):
        print(f"  [Engine] Running Op {op_id}...")
        try:
            s_type, script, additional_args = self.ops.get_execution_params(op_id)
            override_args = []
            if config_overrides:
                for k, v in config_overrides.items():
                    override_args.extend(['--set', f'{k}={v}'])
            cmd = DOTNET_CMD + GAME_MODULE_ARG + ["--script_type", s_type, "--script", script] + additional_args + override_args
            subprocess.run(cmd, check=True, capture_output=False)
        except Exception as e:
            print(f"!! Error running Operation {op_id}: {e}")
            raise e

class Scanner:
    def __init__(self, rename_db: Path):
        self.rename_map = {}
        if rename_db.exists():
            try:
                c = sqlite3.connect(rename_db)
                for old, new in c.execute("SELECT old_name, new_name FROM rename_mappings"):
                    if new: self.rename_map[new.lower()] = old
                c.close()
            except: pass

    def generate_uid(self, rel_path: str, is_norm: bool, is_renamed: bool) -> Tuple[str, str, str]:
        path = Path(rel_path)
        filename = path.name
        if is_norm:
            match = NORMALIZED_UID_PATTERN.search(filename)
            if match: return match.group(1), filename, filename.split('.')[0]

        parts = list(path.parts)
        clean_parts = []
        for p in parts[:-1]:
            pl = p.lower()
            if is_renamed and pl in self.rename_map: clean_parts.append(self.rename_map[pl])
            elif pl in AUDIO_STRIP_DIRS: continue
            else: clean_parts.append(p)

        simple_name = filename.split('.')[0]
        clean_parts.append(simple_name)
        canonical_stem = "/".join(clean_parts).replace("\\", "/").lower()
        uid = hashlib.md5(canonical_stem.encode('utf-8')).hexdigest()[:6]
        return uid, canonical_stem, simple_name

# ============================================================================
# WORKER PROCESS
# ============================================================================

def process_permutation_worker(task_data):
    """
    Worker function to handle a single permutation.
    task_data: (perm_def, perm_id, generate_flag)
    """
    perm_def, perm_id, generate_flag = task_data
    perm_name = perm_def['name']
    cfg = perm_def['config']

    prefix = f"[{perm_name}]"
    print(f"{prefix} Starting processing...")

    # 1. Initialize Local Controllers
    ops_mgr = OperationsManager(OPS_TOML_PATH)
    engine = EngineController(ops_mgr)

    # 2. Run Generation (Optional)
    if generate_flag:
        print(f"{prefix} Running engine operations...")
        try:
            for op_id in perm_def['ops']:
                engine.run_operation(op_id, config_overrides=cfg)
        except Exception as e:
            print(f"{prefix} !! FAILED during generation: {e}")
            return
    else:
        print(f"{prefix} Skipping generation (Index Only)")

    # 3. Indexing
    # Connect to DB (Worker gets its own connection)
    conn = sqlite3.connect(CONFIG_DB_PATH, timeout=60.0) # High timeout for concurrency
    cursor = conn.cursor()

    # Reload scanner per worker
    scanner = Scanner(RENAME_MAP_PATH)

    # Identify directories
    dir_name = f"{cfg.get('STROUT')}-{cfg['Region']}_{cfg['Type']}-{cfg['audio_state']}-{cfg['isRenamed']}"
    target_dir = GAME_FILES_DIR / dir_name
    source_dir = Path(cfg['MainSourcePath'])

    dirs_to_scan = [(target_dir, "Output"), (source_dir, "Source")]

    batch_by_table = {}
    is_norm = (cfg.get('STROUT') == 'STROUT_Normalized')
    is_renamed = (cfg.get('isRenamed') == 'isRenamed')

    for root_path, tag in dirs_to_scan:
        if not root_path.exists():
            print(f"{prefix} Warning: {tag} dir not found: {root_path}")
            continue

        print(f"{prefix} Scanning {tag}...")

        for root, dirs, files in os.walk(root_path):
            dirs[:] = [d for d in dirs if d not in IGNORE_DIRS]
            for file in files:
                abs_path = Path(root) / file
                rel_path = str(abs_path.relative_to(root_path)).replace("\\", "/")

                # Calculation
                uid, canon, simple = scanner.generate_uid(rel_path, is_norm, is_renamed)
                file_hash = compute_file_hash(abs_path)
                path_hash = compute_path_hash(rel_path)
                uuid = make_uuid(file_hash, path_hash)

                extension = get_file_extension(file)
                table_name = table_for_extension(extension)
                file_type = table_name.split('_')[0] if '_' in table_name else table_name

                # Insert Asset (Ignore if exists)
                cursor.execute(
                    "INSERT OR IGNORE INTO assets (uid, canonical_stem, simple_name, file_type, base_extension) VALUES (?,?,?,?,?)",
                    (uid, canon, simple, file_type, extension)
                )

                # Buffer Instance
                if table_name not in batch_by_table: batch_by_table[table_name] = []
                batch_by_table[table_name].append((
                    uuid, uid, perm_id, file, rel_path, str(abs_path),
                    extension, file_hash, path_hash, abs_path.stat().st_size
                ))

                # Flush Buffer
                if len(batch_by_table[table_name]) > 2000:
                    cursor.executemany(
                        f"INSERT OR IGNORE INTO {table_name} (uuid, asset_uid, perm_id, filename, rel_path, full_path, extension, file_hash, path_hash, size_bytes) VALUES (?,?,?,?,?,?,?,?,?,?)",
                        batch_by_table[table_name]
                    )
                    batch_by_table[table_name] = []
                    conn.commit()

    # Final Flush
    for table_name, batch in batch_by_table.items():
        if batch:
            cursor.executemany(
                f"INSERT OR IGNORE INTO {table_name} (uuid, asset_uid, perm_id, filename, rel_path, full_path, extension, file_hash, path_hash, size_bytes) VALUES (?,?,?,?,?,?,?,?,?,?)",
                batch
            )
            conn.commit()

    conn.close()
    print(f"{prefix} Finished.")

# ============================================================================
# MAIN LOOP
# ============================================================================

def main():
    parser = argparse.ArgumentParser(description="Universal Permutation Indexer v11 - Multiprocessing Enabled")
    parser.add_argument('--generate', action='store_true', help='Run engine operations')
    parser.add_argument('--json', action='store_true', help='Export to JSON after')
    parser.add_argument('--compact', action='store_true', help='Compact JSON output')
    parser.add_argument('-j', '--jobs', type=int, default=1, help='Number of parallel processes (Default: 1)')
    args = parser.parse_args()

    print(f"--- Universal Permutation Indexer v11 ---")
    print(f"Mode: {'GENERATE + INDEX' if args.generate else 'INDEX ONLY'}")
    print(f"Parallel Jobs: {args.jobs}")

    # 0. Build Engine (Once) to prevent race conditions
    if args.generate:
        print("Building Engine...")
        subprocess.run(["dotnet", "build", "-c", "Release", str(PROJECT_ROOT / "EngineNet")], check=True)

    # 1. Initialization (Main Process)
    init_db(CONFIG_DB_PATH)

    # 2. Pre-register Permutations to get IDs (Prevents race conditions)
    conn = sqlite3.connect(CONFIG_DB_PATH)
    c = conn.cursor()
    tasks = []

    print("\nPreparing tasks...")
    for perm in PERMUTATIONS:
        cfg = perm['config']
        is_norm = (cfg.get('STROUT') == 'STROUT_Normalized')
        c.execute(
            "INSERT OR IGNORE INTO permutations (name, region, build_type, audio_state, renamed_state, normalized) VALUES (?,?,?,?,?,?)",
            (perm['name'], cfg['Region'], cfg['Type'], cfg['audio_state'], cfg['isRenamed'], 1 if is_norm else 0)
        )
        # Get ID
        c.execute("SELECT id FROM permutations WHERE name=?", (perm['name'],))
        perm_id = c.fetchone()[0]

        # Create task tuple
        tasks.append((perm, perm_id, args.generate))

    conn.commit()
    conn.close()

    # 3. Parallel Processing
    if args.jobs > 1:
        print(f"\nStarting Pool with {args.jobs} workers...")
        with multiprocessing.Pool(processes=args.jobs) as pool:
            pool.map(process_permutation_worker, tasks)
    else:
        print("\nRunning sequentially...")
        for task in tasks:
            process_permutation_worker(task)

    print("\nAll processing complete.")

    # 4. Export (Optional)
    if args.json:
        # ... (Same JSON export logic as before, kept brief for file limit)
        print("\n--- Exporting JSON ---")
        json_path = CONFIG_DB_PATH.with_suffix('.json')
        export_to_json(CONFIG_DB_PATH, json_path, not args.compact)

def export_to_json(db_path, json_path, pretty):
    # Simplified export logic re-used from v10
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()

    c.execute("SELECT * FROM permutations")
    perms = [dict(r) for r in c.fetchall()]

    c.execute("SELECT uid, canonical_stem, simple_name, file_type, base_extension FROM assets")
    assets = []
    file_tables = list(set(EXT_TO_TABLE.values())) + ['other_files']

    # Optimizing export: Fetch all files first?
    # For brevity in v11 file, standard export:
    for row in c.fetchall():
        asset = dict(row)
        asset['files'] = {}
        has_files = False
        for tbl in file_tables:
            c.execute(f"SELECT * FROM {tbl} WHERE asset_uid=?", (asset['uid'],))
            files = [dict(r) for r in c.fetchall()]
            if files:
                asset['files'][tbl] = files
                has_files = True
        if has_files: assets.append(asset)

    with open(json_path, 'w', encoding='utf-8') as f:
        json.dump({'permutations': perms, 'assets': assets}, f, indent=2 if pretty else None)
    print(f"Exported to {json_path}")

if __name__ == "__main__":
    multiprocessing.freeze_support() # For Windows support
    main()


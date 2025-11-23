import os
import sqlite3
import hashlib
import re
import subprocess
import json
import sys
import argparse
from pathlib import Path
from typing import List, Dict, Tuple, Set, Any

# Try to import TOML parser (Standard in 3.11+, or 'tomli' for older)
try:
    import tomllib
except ImportError:
    try:
        import tomli as tomllib
    except ImportError:
        print("CRITICAL: Python 3.11+ or 'tomli' library required to parse operations.toml")
        print("pip install tomli")
        sys.exit(1)

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
IGNORE_DIRS = {'.git', '__pycache__', 'text', 'movies', 'audiostreams', 'A1_Video', 'A1_Audio'}
AUDIO_STRIP_DIRS = {'en', 'global', 'us', 'eu'}
NORMALIZED_UID_PATTERN = re.compile(r'_([0-9a-fA-F]{6})(\.[a-zA-Z0-9]+)+$')

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

def init_db(db_path: Path):
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    c = conn.cursor()

    c.execute('''CREATE TABLE IF NOT EXISTS permutations (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT UNIQUE,
        region TEXT,
        build_type TEXT,
        audio_state TEXT,
        renamed_state TEXT,
        normalized INTEGER
    )''')

    c.execute('''CREATE TABLE IF NOT EXISTS assets (
        uid TEXT PRIMARY KEY,
        canonical_stem TEXT,
        simple_name TEXT
    )''')

    c.execute('''CREATE TABLE IF NOT EXISTS instances (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        asset_uid TEXT,
        perm_id INTEGER,
        rel_path TEXT,
        full_path TEXT,
        extension TEXT,
        size_bytes INTEGER,
        FOREIGN KEY(asset_uid) REFERENCES assets(uid),
        FOREIGN KEY(perm_id) REFERENCES permutations(id)
    )''')
    
    c.execute('CREATE INDEX IF NOT EXISTS idx_lookup ON instances(perm_id, asset_uid)')
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
            
        # 2. Handle Standard 'args' list
        elif 'args' in op:
            # Pass args as JSON string
            additional_args.extend(['--args', json.dumps(op['args'])])

        return s_type, script, additional_args

# ============================================================================
# ENGINE CONTROLLER
# ============================================================================

class EngineController:
    def __init__(self, ops_manager: OperationsManager):
        self.ops = ops_manager

    def update_config(self, key_values: Dict[str, str]):
        """Calls config.lua to update placeholders in config.toml"""
        # print(f"  [Config] Setting: {key_values}") # Verbose
        for key, val in key_values.items():
            # We use the operations.toml lookup for the config script too, 
            # but here we construct it manually because we are changing the config that drives operations.
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
            result = subprocess.run(cmd, check=True, capture_output=False) # Let output flow to console
            
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
            # Check table existence just in case
            try:
                for old, new in c.execute("SELECT old_name, new_name FROM rename_mappings"):
                    if new: self.rename_map[new.lower()] = old
            except sqlite3.OperationalError:
                pass # Table might not exist yet if Op 3 hasn't run
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
    
    The JSON structure mirrors the database schema:
    {
        "permutations": [
            {
                // Mirrors: permutations table
                "id": int,
                "name": str,
                "region": str,
                "build_type": str,
                "audio_state": str,
                "renamed_state": str,
                "normalized": bool
            }
        ],
        "assets": [
            {
                // Mirrors: assets table
                "uid": str,
                "canonical_stem": str,
                "simple_name": str,
                "instances": [
                    {
                        // Mirrors: instances table (joined with asset_uid)
                        "id": int,
                        "perm_id": int,
                        "rel_path": str,
                        "full_path": str,
                        "extension": str,
                        "size_bytes": int
                    }
                ]
            }
        ],
        "metadata": {
            "total_permutations": int,
            "total_assets": int,
            "total_instances": int
        }
    }
    """
    print(f"\n  [JSON Export] Reading from database: {db_path}")
    
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row  # Enable column access by name
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
    
    # 2. Export Assets with their Instances (mirrors: assets + instances tables)
    cursor.execute("SELECT uid, canonical_stem, simple_name FROM assets")
    assets = []
    for row in cursor.fetchall():
        asset_uid = row["uid"]
        
        # Get all instances for this asset (mirrors: instances table)
        cursor.execute("""
            SELECT id, perm_id, rel_path, full_path, extension, size_bytes 
            FROM instances 
            WHERE asset_uid = ?
            ORDER BY perm_id, rel_path
        """, (asset_uid,))
        
        instances = []
        for inst_row in cursor.fetchall():
            instances.append({
                "id": inst_row["id"],
                "perm_id": inst_row["perm_id"],
                "rel_path": inst_row["rel_path"],
                "full_path": inst_row["full_path"],
                "extension": inst_row["extension"],
                "size_bytes": inst_row["size_bytes"]
            })
        
        assets.append({
            "uid": row["uid"],
            "canonical_stem": row["canonical_stem"],
            "simple_name": row["simple_name"],
            "instances": instances
        })
    
    # 3. Generate Metadata
    metadata = {
        "total_permutations": len(permutations),
        "total_assets": len(assets),
        "total_instances": sum(len(asset["instances"]) for asset in assets)
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
    
    print(f"  [JSON Export] Complete - {metadata['total_assets']} assets, {metadata['total_instances']} instances")

# ============================================================================
# MAIN LOOP
# ============================================================================

def main():
    # Parse command-line arguments
    parser = argparse.ArgumentParser(
        description="Universal Permutation Indexer v7 - Builds and indexes all game file permutations"
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
    
    print("--- Universal Permutation Indexer v7 ---")
    
    # 1. Setup
    conn = init_db(CONFIG_DB_PATH)
    cursor = conn.cursor()
    ops_mgr = OperationsManager(OPS_TOML_PATH)
    engine = EngineController(ops_mgr)
    
    # 2. Build & Index Loop
    for perm in PERMUTATIONS:
        print(f"\n>>> Processing Permutation: {perm['name']}")
        
        # A. Configure Engine (Update config.toml)
        engine.update_config(perm['config'])
        
        # B. Run Operations
        try:
            for op_id in perm['ops']:
                engine.run_operation(op_id)
        except Exception as e:
            print(f"Skipping index for {perm['name']} due to build error.")
            continue

        # C. Locate Target Directory
        # We reconstruct the dir name based on the config we just set
        cfg = perm['config']
        dir_name = f"{cfg.get('STROUT')}-{cfg['Region']}_{cfg['Type']}-{cfg['audio_state']}-{cfg['isRenamed']}"
        target_dir = GAME_FILES_DIR / dir_name
        
        if not target_dir.exists():
            print(f"!! Error: Expected output directory {target_dir} does not exist.")
            continue

        # D. Register Permutation
        is_norm = (cfg.get('STROUT') == 'STROUT_Normalized')
        is_renamed = (cfg.get('isRenamed') == 'isRenamed')
        
        cursor.execute("INSERT OR IGNORE INTO permutations (name, region, build_type, audio_state, renamed_state, normalized) VALUES (?,?,?,?,?,?)",
            (perm['name'], cfg['Region'], cfg['Type'], cfg['audio_state'], cfg['isRenamed'], 1 if is_norm else 0))
        cursor.execute("SELECT id FROM permutations WHERE name=?", (perm['name'],))
        perm_id = cursor.fetchone()[0]

        # E. Index Files
        print(f"  [Indexer] Scanning {dir_name}...")
        
        # Reload scanner to ensure fresh RenameMap is loaded (if Op 3 just ran)
        scanner = Scanner(RENAME_MAP_PATH)
        
        batch = []
        
        for root, dirs, files in os.walk(target_dir):
            dirs[:] = [d for d in dirs if d not in IGNORE_DIRS]
            for file in files:
                abs_path = Path(root) / file
                rel_path = str(abs_path.relative_to(target_dir)).replace("\\", "/")
                
                uid, canon, simple = scanner.generate_uid(rel_path, is_norm, is_renamed)
                
                # Register Asset
                cursor.execute("INSERT OR IGNORE INTO assets (uid, canonical_stem, simple_name) VALUES (?,?,?)", (uid, canon, simple))
                
                # Register Instance
                batch.append((uid, perm_id, rel_path, str(abs_path), "".join(abs_path.suffixes), abs_path.stat().st_size))
                
                if len(batch) > 5000:
                    cursor.executemany("INSERT INTO instances (asset_uid, perm_id, rel_path, full_path, extension, size_bytes) VALUES (?,?,?,?,?,?)", batch)
                    batch = []
                    conn.commit()
                    
        if batch:
            cursor.executemany("INSERT INTO instances (asset_uid, perm_id, rel_path, full_path, extension, size_bytes) VALUES (?,?,?,?,?,?)", batch)
            conn.commit()
            
        print(f"  [Indexer] Complete.")

        # F. Cleanup (Optional)
        # import shutil
        # shutil.rmtree(target_dir) 

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
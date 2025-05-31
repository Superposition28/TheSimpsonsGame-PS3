import os
import sqlite3
import hashlib
import subprocess
import time
import sys
import re # Import re for path manipulation

from PIL import Image, UnidentifiedImageError
import imagehash

# --- Configuration Paths & Constants ---
# IMPORTANT: Adjust these paths to your actual environment
STR_INPUT_DIR = r"Source\USRDIR"
OUTPUT_BASE_DIR = r"GameFiles\STROUT"
DB_PATH = r"RemakeRegistry\Games\TheSimpsonsGame\GameFilesIndex2.db" # Renamed or keep same if overwriting

QUICKBMS_EXE = r"Tools\QuickBMS\exe\quickbms.exe"
BMS_SCRIPT = r"RemakeRegistry\Games\TheSimpsonsGame\Scripts\simpsons_str.bms"

# Updated EXT_GROUPS to include the new types
EXT_GROUPS = {
    ".str": "audio_root",
    ".preinstanced": "models",
    ".blend": "models_blend", # blender file table, each related to a preinstanced file, of the same name and file path
    ".glb": "models_glb", # glb file table
    ".fbx": "models_fbx", # fbx file table
    ".txd": "textures",
    ".vp6": "videos",
    ".snu": "audio",
    ".mus": "audio_other",
    ".lua": "other",
    ".bin": "other",
    ".txt": "other",
    ".dds": "textures_dds"  # located in TXD folders adjacent to TXD files in extraction
}

# Hashing and SSIM parameters (adjust as needed)
PHASH_IMG_SIZE = 8
DHASH_IMG_SIZE = 8
AHASH_IMG_SIZE = 8

MAX_DB_RETRIES = 5
RETRY_DELAY_SEC = 1

# --- Hashing Utilities ---
def sha256_file(path):
    h = hashlib.sha256()
    try:
        with open(path, "rb") as f:
            for chunk in iter(lambda: f.read(8192), b""):
                h.update(chunk)
            return h.hexdigest()
    except IOError as e:
        print(f"Error reading file for hashing {path}: {e}", file=sys.stderr)
        return None

def md5_string(s):
    return hashlib.md5(s.encode('utf-8')).hexdigest()

# --- Extraction Logic (Using QuickBMS) ---
def extract_str_file(file_path: str):
    if not file_path.endswith('.str'):
        return False

    try:
        abs_str_input_dir = os.path.abspath(STR_INPUT_DIR)
        abs_file_path = os.path.abspath(file_path)

        if not abs_file_path.startswith(abs_str_input_dir):
            print(f"ERROR: File {file_path} is not under STR_INPUT_DIR {STR_INPUT_DIR}. Cannot determine relative path for extraction output.", file=sys.stderr)
            return False

        relative_path = os.path.relpath(abs_file_path, start=abs_str_input_dir)
        # QuickBMS often creates a directory based on the input filename without extension
        output_dir = os.path.join(OUTPUT_BASE_DIR, os.path.splitext(relative_path)[0] + "_str")
        os.makedirs(output_dir, exist_ok=True)
    except Exception as e:
        print(f"Error preparing output directory for {file_path}: {e}", file=sys.stderr)
        return False

    print(f"    Extracting {file_path} to {output_dir}...")
    try:
        process_result = subprocess.run(
            [QUICKBMS_EXE, "-o", BMS_SCRIPT, file_path, output_dir],
            check=True, capture_output=False, text=True # Not capturing output directly to console
        )
        print(f"    Successfully extracted: {file_path}")
        return True
    except subprocess.CalledProcessError as e:
        print(f"ERROR: Extraction failed for {file_path} using QuickBMS.", file=sys.stderr)
        print(f"    Return code: {e.returncode}", file=sys.stderr)
        print(f"    Command: {' '.join(e.cmd)}", file=sys.stderr)
        # Capture output if it exists, otherwise note the lack of output
        # This is now handled by capture_output=True but suppressed printing,
        # so we'd need to re-enable capture_output=True and print it here if needed for debugging.
        # Keeping capture_output=False as it's less memory intensive for large output.
        # You might see QuickBMS output directly in the console this way.
        return False
    except FileNotFoundError:
        print(f"ERROR: QuickBMS executable not found at {QUICKBMS_EXE} or BMS script at {BMS_SCRIPT}.", file=sys.stderr)
        print(f"        Please check QUICKBMS_EXE and BMS_SCRIPT paths.", file=sys.stderr)
        return False
    except Exception as e:
        print(f"An unexpected error occurred during extraction of {file_path}: {e}", file=sys.stderr)
        return False

# --- Database Initialization and Table Management ---
def get_table_name_for_ext(ext):
    sanitized_ext = ext.lstrip('.').lower()
    # Define specific mappings for the new tables based on group names in EXT_GROUPS
    specific_mappings = {
        "models_blend": "blend_index",
        "models_glb": "glb_index",
        "models_fbx": "fbx_index",
        "textures_dds": "dds_index",
        "audio_root": "str_index", # .str files
        "unknown": "unknown_files_index" # Catch-all
    }

    group_name = EXT_GROUPS.get(ext.lower(), "unknown")

    # Use specific mapping if available, otherwise fall back to generic ext_index
    return specific_mappings.get(group_name, f"{sanitized_ext}_index")

def init_db():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("PRAGMA foreign_keys = ON;")

    # Table for .str archives
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS str_index (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            uuid TEXT UNIQUE NOT NULL,
            source_file_name TEXT,
            source_path TEXT UNIQUE NOT NULL,
            file_hash TEXT,
            path_hash TEXT
        )
    """)

    # Create tables for each group type based on EXT_GROUPS, except .str and .dds
    created_tables = set()
    for ext, group in EXT_GROUPS.items():
        if ext.lower() == ".str": continue # Handled by str_index
        if ext.lower() == ".dds": continue # Handled separately

        table_name = get_table_name_for_ext(ext)

        # Ensure 'preinstanced' uses 'preinstanced_index' table
        if ext.lower() == ".preinstanced":
             table_name = "preinstanced_index"

        if table_name not in created_tables and table_name != "str_index" and table_name != "dds_index" and table_name != "unknown_files_index":
            cursor.execute(f"""
                CREATE TABLE IF NOT EXISTS {table_name} (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    uuid TEXT UNIQUE NOT NULL,
                    source_file_name TEXT,
                    source_path TEXT UNIQUE NOT NULL, -- Source path should be unique within its table
                    file_hash TEXT,
                    path_hash TEXT,
                    group_name TEXT
                )
            """)
            created_tables.add(table_name)
            # print(f"Created table: {table_name}") # Debug print

    # --- DDS Table Creation/Alteration (includes image hashes) ---
    dds_table_name = get_table_name_for_ext(".dds")
    cursor.execute(f"""
        CREATE TABLE IF NOT EXISTS {dds_table_name} (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            uuid TEXT UNIQUE NOT NULL,
            source_file_name TEXT,
            source_path TEXT UNIQUE NOT NULL, -- Source path should be unique within its table
            file_hash TEXT,
            path_hash TEXT,
            group_name TEXT DEFAULT 'textures_dds',
            phash TEXT,
            dhash TEXT,
            ahash TEXT,
            color_phash TEXT,
            color_dhash TEXT,
            color_ahash TEXT
        )
    """)
    created_tables.add(dds_table_name)

    # Add new color hash columns if the table already exists without them
    try:
        cursor.execute(f"ALTER TABLE {dds_table_name} ADD COLUMN color_phash TEXT")
        # print(f"Added color_phash column to {dds_table_name}") # Debug print
    except sqlite3.OperationalError: pass # Column already exists
    try:
        cursor.execute(f"ALTER TABLE {dds_table_name} ADD COLUMN color_dhash TEXT")
        # print(f"Added color_dhash column to {dds_table_name}") # Debug print
    except sqlite3.OperationalError: pass # Column already exists
    try:
        cursor.execute(f"ALTER TABLE {dds_table_name} ADD COLUMN color_ahash TEXT")
        # print(f"Added color_ahash column to {dds_table_name}") # Debug print
    except sqlite3.OperationalError: pass # Column already exists
    # --- End DDS Table Alteration ---

    # --- Unknown Files Table ---
    unknown_table_name = get_table_name_for_ext("unknown")
    if unknown_table_name not in created_tables:
        cursor.execute(f"""
            CREATE TABLE IF NOT EXISTS {unknown_table_name} (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                uuid TEXT UNIQUE NOT NULL,
                source_file_name TEXT,
                source_path TEXT UNIQUE NOT NULL, -- Source path should be unique within its table
                file_hash TEXT,
                path_hash TEXT,
                group_name TEXT DEFAULT 'unknown'
            )
        """)
        created_tables.add(unknown_table_name)
        # print(f"Created table: {unknown_table_name}") # Debug print

    # --- Relationship Tables ---

    # Relationship between STR archives and their extracted content
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS str_content_relationship (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            str_uuid TEXT NOT NULL,
            content_file_uuid TEXT NOT NULL,
            content_file_table TEXT NOT NULL, -- Store the table name of the content file
            FOREIGN KEY (str_uuid) REFERENCES str_index(uuid) ON DELETE CASCADE,
            UNIQUE (str_uuid, content_file_uuid, content_file_table)
        )
    """)
    # Relationship between TXD files and their extracted DDS files
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS txd_dds_relationship (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            txd_uuid TEXT NOT NULL,
            dds_uuid TEXT NOT NULL,
            -- No strict foreign keys here as UUIDs can point to different content tables
            UNIQUE (txd_uuid, dds_uuid)
        )
    """)

    # Relationship between extracted .blend and their source .preinstanced
    # Assumes the related preinstanced file exists in the preinstanced_index table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS blend_preinstanced_relationship (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            blend_uuid TEXT NOT NULL,
            preinstanced_uuid TEXT NOT NULL,
            -- No strict foreign keys here
            UNIQUE (blend_uuid, preinstanced_uuid)
        )
    """)

    # Relationship between extracted .glb/.fbx and their source .blend files
    # content_uuid refers to either glb_uuid or fbx_uuid
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS glb_fbx_blend_relationship (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            glb_fbx_uuid TEXT NOT NULL,
            glb_fbx_table TEXT NOT NULL, -- 'glb_index' or 'fbx_index'
            blend_uuid TEXT NOT NULL,
            -- No strict foreign keys here
            UNIQUE (glb_fbx_uuid, blend_uuid)
        )
    """)


    conn.commit()
    return conn

def insert_relationship(conn, table_name, values):
    """Helper to insert into relationship tables with retry and integrity handling."""
    cursor = conn.cursor()
    cols = ", ".join(values.keys())
    placeholders = ", ".join("?" * len(values))
    sql = f"INSERT INTO {table_name} ({cols}) VALUES ({placeholders})"

    for attempt in range(MAX_DB_RETRIES):
        try:
            cursor.execute(sql, list(values.values()))
            conn.commit()
            return True
        except sqlite3.OperationalError as e:
            if "database is locked" in str(e):
                time.sleep(RETRY_DELAY_SEC)
                if attempt == MAX_DB_RETRIES - 1:
                    print(f"ERROR: Failed to insert into {table_name} due to persistent lock: {e}", file=sys.stderr)
                    conn.rollback()
                    return False
                continue
            print(f"ERROR: Operational error inserting into {table_name}: {e}", file=sys.stderr)
            conn.rollback()
            return False
        except sqlite3.IntegrityError:
            # print(f"    INFO: Relationship already exists in {table_name} for values {list(values.values())}") # Too verbose
            conn.rollback() # Rollback the failed insert attempt
            return False # Relationship already exists, not an error
        except Exception as e:
            print(f"An unexpected error occurred inserting into {table_name}: {e}", file=sys.stderr)
            conn.rollback()
            return False
    return False # Should not reach here if retries are handled

# --- Indexing Functions ---
# index_generic_file remains largely the same, now using updated get_table_name_for_ext
def index_generic_file(conn, file_path, rel_path, group_name, file_ext_for_table):
    table_name = get_table_name_for_ext(file_ext_for_table)
    # Explicitly handle DDS and STR, which have dedicated indexers
    if table_name == get_table_name_for_ext(".dds"):
         print(f"    WARNING: Called index_generic_file for a DDS file: {file_path}. Use index_dds_file instead.", file=sys.stderr)
         return None
    if table_name == get_table_name_for_ext(".str"):
         print(f"    WARNING: Called index_generic_file for an STR file: {file_path}. Use index_str_archive instead.", file=sys.stderr)
         return None
    # Ensure preinstanced uses its specific table name if not covered by get_table_name_for_ext default
    if file_ext_for_table.lower() == ".preinstanced":
        table_name = "preinstanced_index"


    file_hash = sha256_file(file_path)
    if file_hash is None:
        print(f"    Failed to get SHA256 hash for generic file: {file_path}", file=sys.stderr)
        return None

    path_hash = md5_string(rel_path)
    uuid = f"{file_hash[:16]}_{path_hash[:16]}" # Simple combined hash for UUID

    cursor = conn.cursor()
    for attempt in range(MAX_DB_RETRIES):
        try:
            cursor.execute(f"""
                INSERT INTO {table_name} (
                    uuid, source_file_name, source_path,
                    file_hash, path_hash, group_name
                ) VALUES (?, ?, ?, ?, ?, ?)
            """, (
                uuid, os.path.basename(file_path), rel_path.replace("\\", "/"),
                file_hash, path_hash, group_name
            ))
            conn.commit()
            # print(f"    Indexed: {rel_path} into {table_name}") # Too verbose during large scans
            return uuid
        except sqlite3.OperationalError as e:
            if "database is locked" in str(e):
                 # print(f"Database locked for {file_path} in {table_name}. Retrying ({attempt+1}/{MAX_DB_RETRIES})...", file=sys.stderr)
                 time.sleep(RETRY_DELAY_SEC)
                 if attempt == MAX_DB_RETRIES - 1:
                     print(f"ERROR: Failed to insert {file_path} into {table_name} due to persistent lock.", file=sys.stderr)
                     # conn.rollback() # Decide if rollback is needed on final failure
                     raise # Re-raise to signal critical failure
                 continue
            print(f"ERROR: Operational error for {file_path} in {table_name}: {e}", file=sys.stderr)
            # conn.rollback()
            raise # Re-raise other operational errors
        except sqlite3.IntegrityError:
            # Check if the row exists by path first (most common conflict)
            cursor.execute(f"SELECT uuid FROM {table_name} WHERE source_path = ?", (rel_path.replace("\\", "/"),))
            existing_row = cursor.fetchone()
            if existing_row:
                 # print(f"    INFO: File already indexed: {rel_path} in {table_name}")
                 conn.rollback() # Rollback the failed insert attempt
                 return existing_row[0] # Return existing UUID

            # If not by path, check by UUID (less common, but possible hash collision)
            cursor.execute(f"SELECT uuid FROM {table_name} WHERE uuid = ?", (uuid,))
            existing_uuid_row = cursor.fetchone()
            if existing_uuid_row:
                # print(f"    INFO: UUID collision detected for {rel_path} in {table_name}, UUID {uuid} already exists.")
                conn.rollback() # Rollback the failed insert attempt
                return existing_uuid_row[0] # Return existing UUID

            print(f"ERROR: Integrity error for {file_path} in {table_name} but could not fetch existing row (uuid: {uuid}, path: {rel_path}).", file=sys.stderr)
            conn.rollback()
            return None # Indicate insertion failure
        except Exception as e:
            print(f"An unexpected error occurred during indexing of {file_path} in {table_name}: {e}", file=sys.stderr)
            conn.rollback()
            return None # Indicate insertion failure

    print(f"ERROR: Could not index {file_path} into {table_name} after {MAX_DB_RETRIES} retries (locked).", file=sys.stderr)
    conn.rollback()
    return None

# index_dds_file remains the same, it already includes color hashing
def index_dds_file(conn, file_path, rel_path):
    table_name = get_table_name_for_ext(".dds")
    group_name = EXT_GROUPS.get(".dds", "textures_dds")

    file_hash = sha256_file(file_path)
    if file_hash is None:
        print(f"    Failed to get SHA256 hash for DDS: {file_path}", file=sys.stderr)
        return None

    path_hash = md5_string(rel_path)
    uuid = f"{file_hash[:16]}_{path_hash[:16]}"

    phash_val = None
    dhash_val = None
    ahash_val = None
    color_phash_val = None
    color_dhash_val = None
    color_ahash_val = None


    try:
        # PIL/Pillow might need specific loaders for DDS, install `pillow-wave` if needed
        # e.g., pip install Pillow-Wave
        # Standard Pillow supports some DDS formats.
        img = Image.open(file_path)

        # --- Calculate Grayscale Hashes ---
        if img.mode != 'L':
            try:
                img_gray = img.convert('L')
            except ValueError as e:
                 print(f"    WARNING: Could not convert DDS image {file_path} to grayscale for hashing: {e}", file=sys.stderr)
                 img_gray = None # Cannot do grayscale hashing
        else:
            img_gray = img

        if img_gray:
             phash_val = str(imagehash.phash(img_gray, hash_size=PHASH_IMG_SIZE))
             dhash_val = str(imagehash.dhash(img_gray, hash_size=DHASH_IMG_SIZE))
             ahash_val = str(imagehash.average_hash(img_gray, hash_size=AHASH_IMG_SIZE))

        # --- Calculate Color Hashes ---
        if img.mode not in ('RGB', 'RGBA'): # Allow RGBA as it can be converted to RGB
            try:
                img_rgb = img.convert('RGB')
            except ValueError as e:
                 print(f"    WARNING: Could not convert DDS image {file_path} to RGB for color hashing: {e}", file=sys.stderr)
                 img_rgb = None # Cannot do color hashing
        else:
            img_rgb = img.convert('RGB') # Ensure it's strictly RGB if it was RGBA

        if img_rgb:
            try:
                color_ahash_val = str(imagehash.average_hash(img_rgb, hash_size=AHASH_IMG_SIZE))
                color_dhash_val = str(imagehash.dhash(img_rgb, hash_size=DHASH_IMG_SIZE))

                # Perceptual hash needs manual channel processing if include_color is not supported or desired for phash
                try:
                    phash_r = imagehash.phash(img_rgb.getchannel('R'), hash_size=PHASH_IMG_SIZE)
                    phash_g = imagehash.phash(img_rgb.getchannel('G'), hash_size=PHASH_IMG_SIZE)
                    phash_b = imagehash.phash(img_rgb.getchannel('B'), hash_size=PHASH_IMG_SIZE)
                    # Concatenate or combine hex strings - simple concatenation might be less useful for distance
                    # A better approach might be to store them separately or use a combined hash algorithm if imagehash supports one.
                    # For now, let's concatenate as requested.
                    color_phash_val = str(phash_r) + str(phash_g) + str(phash_b)
                except Exception as e:
                    print(f"    WARNING: Failed to calculate individual channel pHash for DDS {file_path}: {e}", file=sys.stderr)
                    color_phash_val = None

            except Exception as e:
                print(f"    ERROR calculating color hashes (ahash/dhash) for DDS {file_path}: {e}", file=sys.stderr)
                color_dhash_val = None
                color_ahash_val = None

        img.close()

    except FileNotFoundError:
        print(f"    ERROR: DDS file not found for hashing: {file_path}", file=sys.stderr)
        return None
    except UnidentifiedImageError:
        print(f"    WARNING: Could not identify/load DDS file for hashing (potentially corrupted or unsupported format): {file_path}", file=sys.stderr)
        # Index the file anyway with just file_hash/path_hash if image hashing fails
        # Continue to the database insertion block
    except Exception as e:
        print(f"    ERROR processing DDS file {file_path} for hashing: {e}", file=sys.stderr)
        # Index the file anyway with just file_hash/path_hash if image hashing fails
        # Continue to the database insertion block


    # --- Database Insertion ---
    cursor = conn.cursor()
    for attempt in range(MAX_DB_RETRIES):
        try:
            cursor.execute(f"""
                INSERT INTO {table_name} (
                    uuid, source_file_name, source_path,
                    file_hash, path_hash, group_name,
                    phash, dhash, ahash,
                    color_phash, color_dhash, color_ahash
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                uuid, os.path.basename(file_path), rel_path.replace("\\", "/"),
                file_hash, path_hash, group_name,
                phash_val, dhash_val, ahash_val,
                color_phash_val, color_dhash_val, color_ahash_val
            ))
            conn.commit()
            print(f"    Indexed DDS: {rel_path}") # Keep this feedback, DDS are important textures
            return uuid
        except sqlite3.OperationalError as e:
            if "database is locked" in str(e):
                # print(f"Database locked for {file_path} in {table_name}. Retrying ({attempt+1}/{MAX_DB_RETRIES})...", file=sys.stderr)
                time.sleep(RETRY_DELAY_SEC)
                if attempt == MAX_DB_RETRIES - 1:
                    print(f"ERROR: Failed to insert {file_path} into {table_name} due to persistent lock after retries.", file=sys.stderr)
                    conn.rollback()
                    raise # Re-raise to signal failure up the call stack
                continue
            print(f"ERROR: Operational error for DDS {file_path} in {table_name}: {e}", file=sys.stderr)
            conn.rollback()
            raise
        except sqlite3.IntegrityError:
            cursor.execute(f"SELECT uuid FROM {table_name} WHERE source_path = ?", (rel_path.replace("\\", "/"),))
            existing_row = cursor.fetchone()
            if existing_row:
                # print(f"    INFO: DDS file already indexed: {rel_path}")
                conn.rollback()
                return existing_row[0]

            cursor.execute(f"SELECT uuid FROM {table_name} WHERE uuid = ?", (uuid,))
            existing_uuid_row = cursor.fetchone()
            if existing_uuid_row:
                # print(f"    INFO: DDS UUID collision detected for {rel_path}, UUID {uuid} already exists.")
                conn.rollback()
                return existing_uuid_row[0]

            print(f"ERROR: Integrity error for DDS {file_path} in {table_name} but could not fetch existing row (uuid: {uuid}, path: {rel_path}).", file=sys.stderr)
            conn.rollback()
            return None
        except Exception as e:
            print(f"An unexpected error occurred during indexing of DDS {file_path} in {table_name}: {e}", file=sys.stderr)
            conn.rollback()
            return None

    print(f"ERROR: Could not index DDS {file_path} after {MAX_DB_RETRIES} retries (locked).", file=sys.stderr)
    conn.rollback()
    return None

def index_str_archive(conn, str_file_full_path, str_file_rel_path):
    table_name = get_table_name_for_ext(".str") # Should be str_index
    file_hash = sha256_file(str_file_full_path)
    if file_hash is None:
        print(f"    Failed to get SHA256 hash for .str: {str_file_full_path}", file=sys.stderr)
        return None

    path_hash = md5_string(str_file_rel_path)
    uuid = f"{file_hash[:16]}_{path_hash[:16]}"

    cursor = conn.cursor()
    for attempt in range(MAX_DB_RETRIES):
        try:
            cursor.execute(f"""
                INSERT INTO {table_name} (uuid, source_file_name, source_path, file_hash, path_hash)
                VALUES (?, ?, ?, ?, ?)
            """, (
                uuid, os.path.basename(str_file_full_path), str_file_rel_path.replace("\\", "/"),
                file_hash, path_hash
            ))
            conn.commit()
            return uuid
        except sqlite3.OperationalError as e:
            if "database is locked" in str(e): time.sleep(RETRY_DELAY_SEC); continue
            print(f"ERROR: Operational error for .str {str_file_full_path} in {table_name}: {e}", file=sys.stderr)
            conn.rollback()
            raise
        except sqlite3.IntegrityError:
            cursor.execute(f"SELECT uuid FROM {table_name} WHERE source_path = ?", (str_file_rel_path.replace("\\", "/"),))
            existing = cursor.fetchone()
            if existing:
                 conn.rollback()
                 return existing[0]

            cursor.execute(f"SELECT uuid FROM {table_name} WHERE uuid = ?", (uuid,))
            existing_uuid = cursor.fetchone()
            if existing_uuid:
                 conn.rollback()
                 return existing_uuid[0]

            print(f"ERROR: Integrity error for .str {str_file_full_path} but could not fetch existing UUID.", file=sys.stderr)
            conn.rollback()
            return None
        except Exception as e:
             print(f"An unexpected error occurred during indexing of .str {str_file_full_path} in {table_name}: {e}", file=sys.stderr)
             conn.rollback()
             return None
    print(f"ERROR: Could not index .str {str_file_full_path} after {MAX_DB_RETRIES} retries.", file=sys.stderr)
    conn.rollback()
    return None

# This function is only called for TXD files found during scanning (Pass 1 or Pass 2)
def process_txd_related_dds(conn, txd_file_uuid, txd_file_full_path, dds_files_base_dir_for_relpath):
    """Processes DDS files found in the generated _txd folders next to TXD files."""
    txd_filename_no_ext = os.path.splitext(os.path.basename(txd_file_full_path))[0]
    txd_dir = os.path.dirname(txd_file_full_path)
    dds_folder_name = txd_filename_no_ext + "_txd" # This is the expected folder name from quickbms/script
    dds_folder_full_path = os.path.join(txd_dir, dds_folder_name)

    if not os.path.isdir(dds_folder_full_path):
        # print(f"    INFO: DDS folder not found for {os.path.basename(txd_file_full_path)}: {dds_folder_full_path}")
        return

    print(f"    Processing DDS files in: {dds_folder_full_path}")
    dds_table_name = get_table_name_for_ext(".dds")

    for dds_root, _, dds_filenames in os.walk(dds_folder_full_path):
        for dds_filename in dds_filenames:
            if dds_filename.lower().endswith(".dds"):
                full_dds_file_path = os.path.join(dds_root, dds_filename)

                try:
                    # Calculate relative path from the base directory where the TXD/DDS pair was found
                    # This base directory can be STR_INPUT_DIR (Pass 1) or an extracted _str dir (Pass 2)
                    abs_dds_base_dir = os.path.abspath(dds_files_base_dir_for_relpath)
                    abs_full_dds_file_path = os.path.abspath(full_dds_file_path)

                    if not abs_full_dds_file_path.startswith(abs_dds_base_dir):
                         # Fallback to absolute path if relative calculation fails - less ideal for uniqueness
                         print(f"    WARNING: DDS file {abs_full_dds_file_path} is not under the expected base {abs_dds_base_dir}. Using full path relative to C: as fallback for rel_path.", file=sys.stderr)
                         dds_relative_path = abs_full_dds_file_path
                    else:
                        dds_relative_path = os.path.relpath(abs_full_dds_file_path, start=abs_dds_base_dir)

                except ValueError as e:
                    print(f"    WARNING: Could not make DDS path {full_dds_file_path} relative to {dds_files_base_dir_for_relpath}. Error: {e}. Skipping DDS file.", file=sys.stderr)
                    continue

                # Calls the updated index_dds_file
                dds_file_uuid = index_dds_file(conn, full_dds_file_path, dds_relative_path)

                if dds_file_uuid:
                    insert_relationship(conn, "txd_dds_relationship", {
                        "txd_uuid": txd_file_uuid,
                        "dds_uuid": dds_file_uuid
                    })
                # else:
                    # print(f"    Skipping TXD-DDS relationship for extracted DDS file {full_dds_file_path} due to indexing failure.") # Too verbose

def index_extracted_content(conn, parent_str_uuid, extracted_files_base_dir):
    """
    Indexes files extracted from a single STR archive and establishes relationships.
    Collects relevant files first, then creates relationships.
    """
    if not parent_str_uuid:
        print(f"ERROR: Cannot index extracted content without a valid parent_str_uuid.", file=sys.stderr)
        return

    files_found_in_extraction = 0
    indexed_extraction_files = {
        'preinstanced': {}, # rel_path_in_extraction -> uuid
        'blend': {},
        'glb': {},
        'fbx': {},
        'txd': {} # Need TXD UUIDs for TXD-DDS relationship processing
    }

    print(f"    Scanning extracted directory for indexing: {extracted_files_base_dir}")

    for root, _, files in os.walk(extracted_files_base_dir):
        # print(f"    Scanning subdirectory: {root}") # Too verbose

        for file_name in files:
            files_found_in_extraction += 1
            full_file_path = os.path.join(root, file_name)

            # Calculate relative path from the extraction base directory (e.g., Output/game/path/file_str)
            # This path is used for finding related files later (same path, different extension)
            rel_path_in_extraction = os.path.relpath(full_file_path, start=extracted_files_base_dir)

            # Calculate relative path from the main OUTPUT_BASE_DIR for database storage
            abs_output_base_dir = os.path.abspath(OUTPUT_BASE_DIR)
            abs_full_file_path = os.path.abspath(full_file_path)
            if not abs_full_file_path.startswith(abs_output_base_dir):
                 # Fallback to absolute path if relative calculation fails
                 print(f"    WARNING: Extracted file {abs_full_file_path} is not under OUTPUT_BASE_DIR {abs_output_base_dir}. Using full path relative to C: as fallback rel_path for DB.", file=sys.stderr)
                 rel_file_path_for_db = abs_full_file_path
            else:
                rel_file_path_for_db = os.path.relpath(abs_full_file_path, start=abs_output_base_dir)

            file_ext = os.path.splitext(file_name)[1].lower()
            group = EXT_GROUPS.get(file_ext, "unknown")
            table_lookup_ext = file_ext if group != "unknown" and file_ext not in ['.str', '.dds'] else group # Use group name for table lookup if not specific ext

            content_file_uuid = None
            content_table_name = None

            if file_ext == ".dds":
                 # print(f"    Indexing extracted DDS: {rel_file_path_for_db}") # Feedback handled by index_dds_file
                 content_file_uuid = index_dds_file(conn, full_file_path, rel_file_path_for_db)
                 content_table_name = get_table_name_for_ext(".dds")

            elif file_ext == ".txd":
                 # print(f"    Indexing extracted TXD: {rel_file_path_for_db}") # Feedback handled by index_generic_file
                 content_file_uuid = index_generic_file(conn, full_file_path, rel_file_path_for_db, group, file_ext)
                 content_table_name = get_table_name_for_ext(file_ext)
                 # Note: TXD-DDS relationship processed *after* initial scan for this extraction

            # Handle new file types and preinstanced
            elif file_ext in ['.blend', '.glb', '.fbx', '.preinstanced']:
                 # print(f"    Indexing extracted {file_ext.upper()}: {rel_file_path_for_db} (Group: {group})") # Too verbose
                 content_file_uuid = index_generic_file(conn, full_file_path, rel_file_path_for_db, group, file_ext)
                 content_table_name = get_table_name_for_ext(file_ext)

                 # Store for relationship processing after the scan
                 if content_file_uuid:
                     if file_ext == '.preinstanced':
                         indexed_extraction_files['preinstanced'][rel_path_in_extraction] = content_file_uuid
                     elif file_ext == '.blend':
                          indexed_extraction_files['blend'][rel_path_in_extraction] = content_file_uuid
                     elif file_ext == '.glb':
                          indexed_extraction_files['glb'][rel_path_in_extraction] = content_file_uuid
                     elif file_ext == '.fbx':
                          indexed_extraction_files['fbx'][rel_path_in_extraction] = content_file_uuid


            else: # Other generic files
                 # print(f"    Indexing extracted file: {rel_file_path_for_db} (Group: {group})") # Too verbose
                 content_file_uuid = index_generic_file(conn, full_file_path, rel_file_path_for_db, group, table_lookup_ext)
                 content_table_name = get_table_name_for_ext(table_lookup_ext)

            # Add STR-Content relationship for any successfully indexed file
            if content_file_uuid and content_table_name:
                insert_relationship(conn, "str_content_relationship", {
                    "str_uuid": parent_str_uuid,
                    "content_file_uuid": content_file_uuid,
                    "content_file_table": content_table_name
                })
            # else:
                # print(f"    Skipped STR relationship for extracted file {full_file_path} due to indexing failure.") # Too verbose

    if files_found_in_extraction == 0:
        print(f"    Warning: No files found to index in extracted directory: {extracted_files_base_dir}", file=sys.stderr)
        return # Nothing to process for relationships

    # --- Post-scan Relationship Processing for this Extraction ---
    print(f"    Processing relationships for extracted content in: {extracted_files_base_dir}")

    # 1. Blend to Preinstanced Relationship
    print(f"    Checking for Blend -> Preinstanced relationships...")
    blends_processed_for_rel = 0
    blends_with_match = 0
    for blend_rel_path_in_extraction, blend_uuid in indexed_extraction_files['blend'].items():
        blends_processed_for_rel += 1
        preinstanced_rel_path_in_extraction = os.path.splitext(blend_rel_path_in_extraction)[0] + ".preinstanced"

        if preinstanced_rel_path_in_extraction in indexed_extraction_files['preinstanced']:
            preinstanced_uuid = indexed_extraction_files['preinstanced'][preinstanced_rel_path_in_extraction]
            # Insert relationship
            if insert_relationship(conn, "blend_preinstanced_relationship", {
                "blend_uuid": blend_uuid,
                "preinstanced_uuid": preinstanced_uuid
            }):
                blends_with_match += 1
                # print(f"    Created Blend-Preinstanced relationship for {blend_rel_path_in_extraction}") # Too verbose
        # else:
             # print(f"    No matching .preinstanced found for {blend_rel_path_in_extraction} within this extraction.") # Too verbose
    print(f"    Processed {blends_processed_for_rel} .blend files for relationship check. Found {blends_with_match} matches.")


    # 2. Glb/Fbx to Blend Relationship
    print(f"    Checking for Glb/Fbx -> Blend relationships...")
    glb_fbx_processed_for_rel = 0
    glb_fbx_with_match = 0

    # Process GLB files
    for glb_rel_path_in_extraction, glb_uuid in indexed_extraction_files['glb'].items():
        glb_fbx_processed_for_rel += 1
        blend_rel_path_in_extraction = os.path.splitext(glb_rel_path_in_extraction)[0] + ".blend"

        if blend_rel_path_in_extraction in indexed_extraction_files['blend']:
            blend_uuid = indexed_extraction_files['blend'][blend_rel_path_in_extraction]
            # Insert relationship
            if insert_relationship(conn, "glb_fbx_blend_relationship", {
                "glb_fbx_uuid": glb_uuid,
                "glb_fbx_table": get_table_name_for_ext(".glb"),
                "blend_uuid": blend_uuid
            }):
                glb_fbx_with_match += 1
                # print(f"    Created Glb-Blend relationship for {glb_rel_path_in_extraction}") # Too verbose
        # else:
             # print(f"    No matching .blend found for {glb_rel_path_in_extraction} within this extraction.") # Too verbose

    # Process FBX files
    for fbx_rel_path_in_extraction, fbx_uuid in indexed_extraction_files['fbx'].items():
        glb_fbx_processed_for_rel += 1
        blend_rel_path_in_extraction = os.path.splitext(fbx_rel_path_in_extraction)[0] + ".blend"

        if blend_rel_path_in_extraction in indexed_extraction_files['blend']:
            blend_uuid = indexed_extraction_files['blend'][blend_rel_path_in_extraction]
            # Insert relationship
            if insert_relationship(conn, "glb_fbx_blend_relationship", {
                "glb_fbx_uuid": fbx_uuid,
                "glb_fbx_table": get_table_name_for_ext(".fbx"),
                "blend_uuid": blend_uuid
            }):
                glb_fbx_with_match += 1
                # print(f"    Created Fbx-Blend relationship for {fbx_rel_path_in_extraction}") # Too verbose
        # else:
             # print(f"    No matching .blend found for {fbx_rel_path_in_extraction} within this extraction.") # Too verbose
    print(f"    Processed {glb_fbx_processed_for_rel} .glb and .fbx files for relationship check. Found {glb_fbx_with_match} matches.")

    # 3. Process TXD-DDS relationships from this extraction
    print(f"    Checking for TXD -> DDS relationships...")
    txds_processed_for_rel = 0
    for txd_rel_path_in_extraction, txd_uuid in indexed_extraction_files['txd'].items():
        txds_processed_for_rel += 1
        # Reconstruct the full path relative to the *extraction base* needed by process_txd_related_dds
        # This is a bit clunky - ideally process_txd_related_dds would work off relative paths within the extraction too.
        # For now, convert back to full path relative to where the TXD was found during the os.walk
        full_txd_path_for_dds_scan = os.path.join(extracted_files_base_dir, txd_rel_path_in_extraction)
        # process_txd_related_dds requires the base dir to calculate the DDS relative path for DB storage
        process_txd_related_dds(conn, txd_uuid, full_txd_path_for_dds_scan, OUTPUT_BASE_DIR) # Pass OUTPUT_BASE_DIR as the base for DDS rel_path
    print(f"    Processed {txds_processed_for_rel} .txd files for relationship check.")

# --- Main Processing Logic ---
def main():
    if not os.path.isdir(STR_INPUT_DIR):
        print(f"ERROR: STR_INPUT_DIR does not exist: {STR_INPUT_DIR}", file=sys.stderr)
        return
    os.makedirs(OUTPUT_BASE_DIR, exist_ok=True)
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)

    print(f"Initializing database at: {DB_PATH}")
    try:
        conn = init_db()
    except Exception as e:
        print(f"FATAL ERROR: Could not initialize database: {e}", file=sys.stderr)
        sys.exit(1)

    print("\n--- Pass 1: Indexing Root-Level Files (excluding .str) ---")
    print(f"Starting scan of source directory: {STR_INPUT_DIR}")
    root_files_processed = 0
    for root_dir, _, dir_files in os.walk(STR_INPUT_DIR):
        print(f"Scanning directory: {root_dir}")

        # Skip the output directory itself to avoid infinite loops if OUTPUT_BASE_DIR is inside STR_INPUT_DIR
        if os.path.abspath(root_dir).startswith(os.path.abspath(OUTPUT_BASE_DIR)):
            print(f"    INFO: Skipping directory within OUTPUT_BASE_DIR: {root_dir}", file=sys.stderr)
            continue

        for file_item_name in dir_files:
            full_file_path = os.path.join(root_dir, file_item_name)
            file_ext = os.path.splitext(file_item_name)[1].lower()

            if file_ext == ".str":
                continue # Handle .str files in Pass 2

            root_files_processed += 1 # Count non-str root files

            abs_str_input_dir = os.path.abspath(STR_INPUT_DIR)
            abs_full_file_path = os.path.abspath(full_file_path)

            if not abs_full_file_path.startswith(abs_str_input_dir):
                print(f"    WARNING: Root file {abs_full_file_path} is not under STR_INPUT_DIR {abs_str_input_dir}. Using full path relative to C: as fallback rel_path. This may impact uniqueness.", file=sys.stderr)
                rel_file_path = abs_full_file_path # Fallback relative path
            else:
                rel_file_path = os.path.relpath(abs_full_file_path, start=abs_str_input_dir)

            group_name = EXT_GROUPS.get(file_ext, "unknown")
            table_lookup_ext = file_ext if group_name != "unknown" else "unknown" # Use file_ext for lookup if known type, 'unknown' otherwise

            file_uuid = None # Initialize uuid

            if file_ext == ".dds":
                # Index root-level DDS files (will now include color hashes)
                # print(f"    Indexing root DDS: {rel_file_path} (Group: {group_name})") # Feedback handled by index_dds_file
                file_uuid = index_dds_file(conn, full_file_path, rel_file_path)

            elif file_ext == ".txd":
				# print(f"    Indexing root TXD: {rel_file_path} (Group: {group_name})") # Feedback handled by index_generic_file
				file_uuid = index_generic_file(conn, full_file_path, rel_file_path, group_name, table_lookup_ext)

				# Process any related DDS files located next to this root TXD
				if file_uuid:
					process_txd_related_dds(conn, file_uuid, full_file_path, STR_INPUT_DIR) # Pass STR_INPUT_DIR as base for DDS rel_path

            else:
                file_uuid = index_generic_file(conn, full_file_path, rel_file_path, group_name, table_lookup_ext)

    print(f"\n--- Pass 2: Processing .str Archives and Extracted Contents ---")
    print(f"Starting scan for .str files in source directory: {STR_INPUT_DIR}")
    str_files_processed = 0
    for root_dir, _, dir_files in os.walk(STR_INPUT_DIR):
        # print(f"Scanning directory: {root_dir}") # Too verbose for outer loop here

        # Skip the output directory itself
        if os.path.abspath(root_dir).startswith(os.path.abspath(OUTPUT_BASE_DIR)):
            continue

        for file_item_name in dir_files:
            if file_item_name.endswith(".str"):
                str_files_processed += 1
                full_str_file_path = os.path.join(root_dir, file_item_name)

                abs_str_input_dir = os.path.abspath(STR_INPUT_DIR)
                abs_full_str_file_path = os.path.abspath(full_str_file_path)
                if not abs_full_str_file_path.startswith(abs_str_input_dir):
                    print(f"    WARNING: .str file {abs_full_str_file_path} is not under STR_INPUT_DIR {abs_str_input_dir}. Using full path relative to C: as fallback rel_path for STR indexing.", file=sys.stderr)
                    rel_str_file_path = abs_full_str_file_path
                else:
                    rel_str_file_path = os.path.relpath(abs_full_str_file_path, start=abs_str_input_dir)

                print(f"\nProcessing .str archive: {rel_str_file_path}")

                # Index the STR archive itself
                parent_str_uuid = index_str_archive(conn, full_str_file_path, rel_str_file_path)
                if not parent_str_uuid:
                    print(f"    Failed to index or retrieve UUID for .str: {rel_str_file_path}. Skipping content extraction and indexing.", file=sys.stderr)
                    continue
                print(f"    .str indexed/found with UUID: {parent_str_uuid}")

                # Define the expected extraction directory based on the relative path of the STR
                expected_extraction_dir_rel = os.path.splitext(rel_str_file_path)[0] + "_str"
                expected_extraction_dir = os.path.join(OUTPUT_BASE_DIR, expected_extraction_dir_rel)

                # Decide whether to extract or just index if already extracted
                # Simple check: if the expected directory exists and isn't empty, assume already extracted
                if os.path.isdir(expected_extraction_dir) and any(os.scandir(expected_extraction_dir)):
                    print(f"    Extraction directory already exists and is not empty: {expected_extraction_dir}. Skipping extraction.")
                    extraction_successful = True # Assume successful prior extraction
                else:
                    extraction_successful = extract_str_file(full_str_file_path)


                if extraction_successful:
                    if os.path.isdir(expected_extraction_dir):
                        # Index extracted content and build relationships within this extraction
                        index_extracted_content(conn, parent_str_uuid, expected_extraction_dir)
                    else:
                        print(f"    WARNING: Extraction reported success for {rel_str_file_path}, but directory not found: {expected_extraction_dir}", file=sys.stderr)
                else:
                    print(f"    Skipping content indexing for {rel_str_file_path} due to extraction failure.", file=sys.stderr)

    conn.close()
    print("\n✅ Full Indexing, Extraction, and Relationship Processing complete.")
    print(f"Scanned {root_files_processed} root files (excluding .str) and processed {str_files_processed} .str archives.")

if __name__ == "__main__":
    quickbms_ok = os.path.isfile(QUICKBMS_EXE) and os.access(QUICKBMS_EXE, os.X_OK)
    bms_script_ok = os.path.isfile(BMS_SCRIPT)

    if not quickbms_ok:
        print(f"ERROR: QuickBMS executable not found or not executable at: {QUICKBMS_EXE}", file=sys.stderr)
    if not bms_script_ok:
        print(f"ERROR: BMS script not found at: {BMS_SCRIPT}", file=sys.stderr)

    if quickbms_ok and bms_script_ok:
        main()
    else:
        print("Please fix the tool paths and permissions before running.", file=sys.stderr)

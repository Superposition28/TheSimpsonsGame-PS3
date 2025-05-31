import os
import sqlite3
import hashlib
import subprocess # Added for QuickBMS execution
import time

# --- Configuration Paths & Constants ---
# Paths for file indexing and database
STR_INPUT_DIR = r"Source\USRDIR"
OUTPUT_BASE_DIR = r"GameFiles\STROUT"
DB_PATH = r"RemakeRegistry\Games\TheSimpsonsGame\str_index_refactored.db"

# QuickBMS specific paths (from your example)
QUICKBMS_EXE = r"Tools\QuickBMS\exe\quickbms.exe"
BMS_SCRIPT = r"RemakeRegistry\Games\TheSimpsonsGame\Scripts\simpsons_str.bms"

EXT_GROUPS = {
    ".str": "audio_root", # Special type for .str archives
    ".preinstanced": "models",
    ".txd": "textures",
    ".vp6": "videos",
    ".snu": "audio",
    ".mus": "other",
    ".lua": "other",
    ".bin": "other",
    ".txt": "other"
}

# retry on "database is locked"
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
        print(f"Error reading file for hashing {path}: {e}")
        return None

def md5_string(s):
    return hashlib.md5(s.encode('utf-8')).hexdigest()

# --- Extraction Logic (Using QuickBMS) ---
def extract_str_file(file_path: str):
    """
    Extracts a .str file using QuickBMS.
    The STR_INPUT_DIR and OUTPUT_BASE_DIR constants are used to determine paths.
    """
    if not file_path.endswith('.str'):
        # This check is a bit redundant if called only for .str files,
        # but good for a standalone utility.
        # print(f"Skipping non-.str file: {file_path}")
        return False # Indicate not processed or failure

    # Create output directory for this str file
    # This logic must match how expected_extraction_dir is calculated in main()
    try:
        relative_path = os.path.relpath(file_path, start=STR_INPUT_DIR)
        output_dir = os.path.join(OUTPUT_BASE_DIR, os.path.splitext(relative_path)[0] + "_str")
        os.makedirs(output_dir, exist_ok=True)
    except Exception as e:
        print(f"Error preparing output directory for {file_path}: {e}")
        return False

    print(f"  Extracting {file_path} to {output_dir}...")

    try:
        # Command: quickbms.exe -k <script.bms> <archive.str> <output_folder>
        # Using "-k" to keep the paths as stored in the archive, if applicable.
        # Adjust QuickBMS options if needed (e.g., removing -k or adding others).
        process_result = subprocess.run(
            [QUICKBMS_EXE, "-o", BMS_SCRIPT, file_path, output_dir],
            check=True,
            capture_output=False, # Capture stdout/stderr
            text=True # Decode stdout/stderr as text
        )
        # print(f"    QuickBMS STDOUT for {file_path}:\n{process_result.stdout}") # Optional: log output
        #if process_result.stderr:
        #    print(f"    QuickBMS STDERR for {file_path}:\n{process_result.stderr}")
        print(f"  Successfully extracted: {file_path}")
        return True
    except subprocess.CalledProcessError as e:
        print(f"ERROR: Extraction failed for {file_path} using QuickBMS.")
        print(f"  Return code: {e.returncode}")
        print(f"  Command: {' '.join(e.cmd)}")
        if e.stdout:
            print(f"  QuickBMS STDOUT:\n{e.stdout}")
        if e.stderr:
            print(f"  QuickBMS STDERR:\n{e.stderr}")
        return False
    except FileNotFoundError:
        print(f"ERROR: QuickBMS executable not found at {QUICKBMS_EXE} or BMS script at {BMS_SCRIPT}.")
        print(f"       Please check QUICKBMS_EXE and BMS_SCRIPT paths.")
        return False
    except Exception as e:
        print(f"An unexpected error occurred during extraction of {file_path}: {e}")
        return False

# --- Database Initialization and Table Management ---
def get_table_name_for_ext(ext):
    sanitized_ext = ext.lstrip('.').lower()
    if not sanitized_ext:
        return "unknown_files_index"
    return f"{sanitized_ext}_index"

def init_db():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("PRAGMA foreign_keys = ON;") # Enforce foreign key constraints

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

    created_tables = set()
    for ext_key, group_name in EXT_GROUPS.items():
        if ext_key == ".str":
            continue
        table_name = get_table_name_for_ext(ext_key)
        if table_name not in created_tables:
            cursor.execute(f"""
                CREATE TABLE IF NOT EXISTS {table_name} (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    uuid TEXT UNIQUE NOT NULL,
                    source_file_name TEXT,
                    source_path TEXT NOT NULL,
                    file_hash TEXT,
                    path_hash TEXT,
                    group_name TEXT
                )
            """)
            created_tables.add(table_name)

    unknown_table_name = get_table_name_for_ext("unknown")
    if unknown_table_name not in created_tables:
        cursor.execute(f"""
            CREATE TABLE IF NOT EXISTS {unknown_table_name} (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                uuid TEXT UNIQUE NOT NULL,
                source_file_name TEXT,
                source_path TEXT NOT NULL,
                file_hash TEXT,
                path_hash TEXT,
                group_name TEXT DEFAULT 'unknown'
            )
        """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS str_content_relationship (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            str_uuid TEXT NOT NULL,
            content_file_uuid TEXT NOT NULL,
            content_file_table TEXT NOT NULL,
            FOREIGN KEY (str_uuid) REFERENCES str_index(uuid) ON DELETE CASCADE,
            UNIQUE (str_uuid, content_file_uuid, content_file_table)
        )
    """)
    conn.commit()
    return conn

# --- Indexing Functions ---
def index_generic_file(conn, file_path, rel_path, group_name, file_ext_for_table):
    table_name = get_table_name_for_ext(file_ext_for_table)
    file_hash = sha256_file(file_path)
    if file_hash is None: return None
        
    path_hash = md5_string(rel_path)
    uuid = f"{file_hash[:16]}_{path_hash[:16]}"
    
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
            return uuid
        except sqlite3.OperationalError as e:
            if "database is locked" in str(e):
                time.sleep(RETRY_DELAY_SEC)
                continue
            raise
        except sqlite3.IntegrityError:
            cursor.execute(f"SELECT uuid FROM {table_name} WHERE uuid = ?", (uuid,))
            existing_uuid_row = cursor.fetchone()
            if existing_uuid_row: return existing_uuid_row[0]
            else:
                print(f"ERROR: Integrity error for {file_path} in {table_name} but could not fetch existing UUID by uuid.")
                # Fallback: Try fetching by content and path hash combination, as UUID is derived from these
                cursor.execute(f"SELECT uuid FROM {table_name} WHERE file_hash = ? AND path_hash = ?", (file_hash, path_hash))
                existing_uuid_row_fallback = cursor.fetchone()
                if existing_uuid_row_fallback: return existing_uuid_row_fallback[0]
                print(f"ERROR: Still could not fetch existing UUID for {file_path} in {table_name} by content.")
                return None
    print(f"ERROR: Could not insert {file_path} into {table_name} after {MAX_DB_RETRIES} retries.")
    return None

def index_str_archive(conn, str_file_full_path, str_file_rel_path):
    file_hash = sha256_file(str_file_full_path)
    if file_hash is None:
        return None

    path_hash = md5_string(str_file_rel_path)
    uuid = f"{file_hash[:16]}_{path_hash[:16]}"

    cursor = conn.cursor()
    for attempt in range(MAX_DB_RETRIES):
        try:
            cursor.execute("""
                INSERT INTO str_index (uuid, source_file_name, source_path, file_hash, path_hash)
                VALUES (?, ?, ?, ?, ?)
            """, (
                uuid, os.path.basename(str_file_full_path), str_file_rel_path.replace("\\", "/"),
                file_hash, path_hash
            ))
            conn.commit()
            return uuid
        except sqlite3.OperationalError as e:
            if "database is locked" in str(e):
                time.sleep(RETRY_DELAY_SEC)
                continue
            raise
        except sqlite3.IntegrityError:
            # Prioritize source_path for lookup as it's unique for .str files
            cursor.execute("SELECT uuid FROM str_index WHERE source_path = ?", (str_file_rel_path.replace("\\", "/"),))
            existing = cursor.fetchone()
            if existing:
                return existing[0]
            cursor.execute("SELECT uuid FROM str_index WHERE uuid = ?", (uuid,)) # Fallback to UUID
            existing = cursor.fetchone()
            if existing:
                return existing[0]

            print(f"ERROR: Integrity error for .str {str_file_full_path} but could not fetch existing UUID.")
            return None
    print(f"ERROR: Could not index .str {str_file_full_path} after {MAX_DB_RETRIES} retries.")
    return None

def index_extracted_content(conn, parent_str_uuid, extracted_files_base_dir):
    if not parent_str_uuid:
        print(f"ERROR: Cannot index extracted content without a valid parent_str_uuid.")
        return

    cursor = conn.cursor()
    files_found_in_extraction = 0
    for root, _, files in os.walk(extracted_files_base_dir):
        for file_name in files:
            files_found_in_extraction += 1
            full_file_path = os.path.join(root, file_name)
            rel_file_path = os.path.relpath(full_file_path, start=OUTPUT_BASE_DIR)
            
            file_ext = os.path.splitext(file_name)[1].lower()
            group = EXT_GROUPS.get(file_ext, "unknown")
            table_lookup_ext = file_ext if group != "unknown" else "unknown"

            content_file_uuid = index_generic_file(conn, full_file_path, rel_file_path, group, table_lookup_ext)
            
            if content_file_uuid:
                content_table_name = get_table_name_for_ext(table_lookup_ext)
                try:
                    cursor.execute("""
                        INSERT INTO str_content_relationship (str_uuid, content_file_uuid, content_file_table)
                        VALUES (?, ?, ?)
                    """, (parent_str_uuid, content_file_uuid, content_table_name))
                    conn.commit()
                except sqlite3.IntegrityError:
                    pass # Relationship likely already exists
                except Exception as e:
                    print(f"Error adding relationship for {full_file_path}: {e}")
            else:
                print(f"  Skipped relationship for extracted file {full_file_path} due to previous indexing failure.")
    if files_found_in_extraction == 0:
        print(f"  Warning: No files found to index in extracted directory: {extracted_files_base_dir}")


# --- Main Processing Logic ---
def main():
    conn = init_db()
    print("--- Pass 1: Indexing Other Root-Level Files ---")
    for root_dir, _, dir_files in os.walk(STR_INPUT_DIR):
        for file_item_name in dir_files:
            file_ext = os.path.splitext(file_item_name)[1].lower()
            if file_ext in [".str"]:
                continue # Skip .str (Pass 2) and assumed extraction-only types

            group_name = EXT_GROUPS.get(file_ext)
            if group_name:
                full_file_path = os.path.join(root_dir, file_item_name)
                rel_file_path = os.path.relpath(full_file_path, start=STR_INPUT_DIR)
                print(f"Indexing root file: {file_item_name} (Group: {group_name})")
                index_generic_file(conn, full_file_path, rel_file_path, group_name, file_ext)


    print("\n--- Pass 2: Processing .str Archives and Extracted Contents ---")
    for root_dir, _, dir_files in os.walk(STR_INPUT_DIR):
        for file_item_name in dir_files:
            if file_item_name.endswith(".str"):
                full_str_file_path = os.path.join(root_dir, file_item_name)
                rel_str_file_path = os.path.relpath(full_str_file_path, start=STR_INPUT_DIR)
                
                print(f"\nProcessing .str archive: {rel_str_file_path}")

                parent_str_uuid = index_str_archive(conn, full_str_file_path, rel_str_file_path)
                if not parent_str_uuid:
                    print(f"  Failed to index or retrieve UUID for .str: {rel_str_file_path}. Skipping contents.")
                    continue
                print(f"  .str indexed/found with UUID: {parent_str_uuid}")

                # Call the integrated extraction function
                extraction_successful = extract_str_file(full_str_file_path)
                
                if extraction_successful:
                    expected_extraction_dir = os.path.join(OUTPUT_BASE_DIR, os.path.splitext(rel_str_file_path)[0] + "_str")
                    if os.path.isdir(expected_extraction_dir):
                        print(f"  Indexing extracted contents from: {expected_extraction_dir}")
                        index_extracted_content(conn, parent_str_uuid, expected_extraction_dir)
                    else:
                        print(f"  WARNING: Extraction reported success, but directory not found: {expected_extraction_dir}")
                else:
                    print(f"  Skipping content indexing for {rel_str_file_path} due to extraction failure.")


    conn.close()
    print("\n✅ Full Indexing and Extraction complete.")

if __name__ == "__main__":
    # Ensure the directories STR_INPUT_DIR and OUTPUT_BASE_DIR exist before running.
    # Also ensure QUICKBMS_EXE and BMS_SCRIPT paths are correct and QuickBMS is functional.
    if not os.path.isdir(STR_INPUT_DIR):
        print(f"ERROR: STR_INPUT_DIR does not exist: {STR_INPUT_DIR}")
    elif not os.path.isdir(OUTPUT_BASE_DIR):
        print(f"INFO: OUTPUT_BASE_DIR does not exist: {OUTPUT_BASE_DIR}. Will be created by extraction.")
        # os.makedirs(OUTPUT_BASE_DIR, exist_ok=True) # Or create it here if preferred
    else:
        main()
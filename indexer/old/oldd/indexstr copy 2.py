import os
import sqlite3
import hashlib
import subprocess
import time

# --- Configuration Paths & Constants ---
# IMPORTANT: Adjust these paths to your actual environment
STR_INPUT_DIR = r"Source\USRDIR"
OUTPUT_BASE_DIR = r"GameFiles\STROUT"
DB_PATH = r"RemakeRegistry\Games\TheSimpsonsGame\str_index_refactored_with_dds.db"

QUICKBMS_EXE = r"Tools\QuickBMS\exe\quickbms.exe"
BMS_SCRIPT = r"RemakeRegistry\Games\TheSimpsonsGame\Scripts\simpsons_str.bms"

EXT_GROUPS = {
    ".str": "audio_root",
    ".preinstanced": "models",
    ".txd": "textures",
    ".vp6": "videos",
    ".snu": "audio",
    ".mus": "other",
    ".lua": "other",
    ".bin": "other",
    ".txt": "other",
    ".dds": "textures_dds"  # located in TXD folders adjacent to TXD files in
}

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
    if not file_path.endswith('.str'):
        return False

    try:
        # Ensure STR_INPUT_DIR is an absolute path for relpath if file_path is absolute
        abs_str_input_dir = os.path.abspath(STR_INPUT_DIR)
        abs_file_path = os.path.abspath(file_path)
        
        if not abs_file_path.startswith(abs_str_input_dir):
            print(f"ERROR: File {file_path} is not under STR_INPUT_DIR {STR_INPUT_DIR}. Cannot determine relative path for extraction output.")
            return False
            
        relative_path = os.path.relpath(abs_file_path, start=abs_str_input_dir)
        output_dir = os.path.join(OUTPUT_BASE_DIR, os.path.splitext(relative_path)[0] + "_str")
        os.makedirs(output_dir, exist_ok=True)
    except Exception as e:
        print(f"Error preparing output directory for {file_path}: {e}")
        return False

    print(f"  Extracting {file_path} to {output_dir}...")
    try:
        process_result = subprocess.run(
            [QUICKBMS_EXE, "-o", BMS_SCRIPT, file_path, output_dir], # Added -o for overwrite
            check=True, capture_output=False, text=True # Not capturing output directly to console
        )
        print(f"  Successfully extracted: {file_path}")
        return True
    except subprocess.CalledProcessError as e:
        print(f"ERROR: Extraction failed for {file_path} using QuickBMS.")
        print(f"  Return code: {e.returncode}")
        print(f"  Command: {' '.join(e.cmd)}")
        # QuickBMS often outputs to stdout even on errors with some scripts
        if e.stdout: print(f"  QuickBMS STDOUT:\n{e.stdout}")
        if e.stderr: print(f"  QuickBMS STDERR:\n{e.stderr}")
        return False
    except FileNotFoundError:
        print(f"ERROR: QuickBMS executable not found at {QUICKBMS_EXE} or BMS script at {BMS_SCRIPT}.")
        print(f"         Please check QUICKBMS_EXE and BMS_SCRIPT paths.")
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
    cursor.execute("PRAGMA foreign_keys = ON;")

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

    txd_table_name = get_table_name_for_ext('.txd')
    dds_table_name = get_table_name_for_ext('.dds')
    cursor.execute(f"""
        CREATE TABLE IF NOT EXISTS txd_dds_relationship (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            txd_uuid TEXT NOT NULL,
            dds_uuid TEXT NOT NULL,
            FOREIGN KEY (txd_uuid) REFERENCES {txd_table_name}(uuid) ON DELETE CASCADE,
            FOREIGN KEY (dds_uuid) REFERENCES {dds_table_name}(uuid) ON DELETE CASCADE,
            UNIQUE (txd_uuid, dds_uuid)
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
                # print(f"Database locked for {file_path} in {table_name}. Retrying ({attempt+1}/{MAX_DB_RETRIES})...")
                time.sleep(RETRY_DELAY_SEC)
                if attempt == MAX_DB_RETRIES - 1:
                    print(f"ERROR: Failed to insert {file_path} into {table_name} due to persistent lock.")
                    raise # Or return None if you prefer to continue
                continue
            print(f"ERROR: Operational error for {file_path} in {table_name}: {e}")
            raise # Re-raise other operational errors
        except sqlite3.IntegrityError:
            # This means UUID (derived from file_hash and path_hash) already exists.
            # Fetch the existing UUID.
            cursor.execute(f"SELECT uuid FROM {table_name} WHERE uuid = ?", (uuid,))
            existing_uuid_row = cursor.fetchone()
            if existing_uuid_row:
                return existing_uuid_row[0]
            else:
                # This case should ideally not be reached if UUID is truly unique and derived correctly.
                # Fallback, though less likely to be needed given UUID structure.
                cursor.execute(f"SELECT uuid FROM {table_name} WHERE file_hash = ? AND path_hash = ?", (file_hash, path_hash))
                existing_uuid_row_fallback = cursor.fetchone()
                if existing_uuid_row_fallback:
                    return existing_uuid_row_fallback[0]
                print(f"ERROR: Integrity error for {file_path} in {table_name} but could not fetch existing UUID (uuid: {uuid}).")
                return None
    # This part is reached if all retries for "database is locked" fail
    print(f"ERROR: Could not insert {file_path} into {table_name} after {MAX_DB_RETRIES} retries (locked).")
    return None

def index_str_archive(conn, str_file_full_path, str_file_rel_path):
    file_hash = sha256_file(str_file_full_path)
    if file_hash is None: return None

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
            if "database is locked" in str(e): time.sleep(RETRY_DELAY_SEC); continue
            raise
        except sqlite3.IntegrityError:
            # source_path is UNIQUE in str_index, so try fetching by that first.
            cursor.execute("SELECT uuid FROM str_index WHERE source_path = ?", (str_file_rel_path.replace("\\", "/"),))
            existing = cursor.fetchone()
            if existing: return existing[0]
            # Fallback to UUID if source_path somehow wasn't the cause (e.g., direct UUID collision)
            cursor.execute("SELECT uuid FROM str_index WHERE uuid = ?", (uuid,))
            existing_uuid = cursor.fetchone()
            if existing_uuid: return existing_uuid[0]
            
            print(f"ERROR: Integrity error for .str {str_file_full_path} but could not fetch existing UUID.")
            return None # Should not happen if source_path or uuid is unique
    print(f"ERROR: Could not index .str {str_file_full_path} after {MAX_DB_RETRIES} retries.")
    return None

# --- New function to process DDS files related to a TXD ---
def process_txd_related_dds(conn, txd_file_uuid, txd_file_full_path, dds_files_base_dir_for_relpath):
    txd_filename_no_ext = os.path.splitext(os.path.basename(txd_file_full_path))[0]
    txd_dir = os.path.dirname(txd_file_full_path)
    dds_folder_name = txd_filename_no_ext + "_txd"
    dds_folder_full_path = os.path.join(txd_dir, dds_folder_name)

    if not os.path.isdir(dds_folder_full_path):
        # print(f"  INFO: DDS folder not found for {os.path.basename(txd_file_full_path)}: {dds_folder_full_path}")
        return

    print(f"  Processing DDS files in: {dds_folder_full_path}")
    cursor = conn.cursor()
    dds_group_name = EXT_GROUPS.get(".dds", "textures_dds") # Default if not in EXT_GROUPS for some reason

    for dds_root, _, dds_filenames in os.walk(dds_folder_full_path):
        for dds_filename in dds_filenames:
            if dds_filename.lower().endswith(".dds"):
                full_dds_file_path = os.path.join(dds_root, dds_filename)
                
                try:
                    # Ensure dds_files_base_dir_for_relpath is absolute for robust relpath calculation
                    abs_dds_base_dir = os.path.abspath(dds_files_base_dir_for_relpath)
                    abs_full_dds_file_path = os.path.abspath(full_dds_file_path)

                    if not abs_full_dds_file_path.startswith(abs_dds_base_dir):
                         print(f"  WARNING: DDS file {abs_full_dds_file_path} is not under the expected base {abs_dds_base_dir}. Using filename as fallback for rel_path. This may impact uniqueness if paths are complex.")
                         dds_relative_path = dds_filename # Fallback, less ideal
                    else:
                        dds_relative_path = os.path.relpath(abs_full_dds_file_path, start=abs_dds_base_dir)

                except ValueError as e:
                    print(f"  WARNING: Could not make DDS path {full_dds_file_path} relative to {dds_files_base_dir_for_relpath}. Error: {e}. Using filename as fallback. Skipping DDS file.")
                    continue # Skip this DDS if pathing is problematic
                
                dds_file_uuid = index_generic_file(conn,
                                                 full_dds_file_path,
                                                 dds_relative_path,
                                                 dds_group_name,
                                                 ".dds")

                if dds_file_uuid:
                    try:
                        cursor.execute("""
                            INSERT INTO txd_dds_relationship (txd_uuid, dds_uuid)
                            VALUES (?, ?)
                        """, (txd_file_uuid, dds_file_uuid))
                        conn.commit()
                    except sqlite3.IntegrityError:
                        pass # Relationship already exists
                    except Exception as e:
                        print(f"    Error creating TXD-DDS relationship for {dds_filename} ({dds_file_uuid}) with TXD ({txd_file_uuid}): {e}")
                else:
                    print(f"    Failed to index DDS file: {full_dds_file_path}")

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
            
            # rel_file_path for extracted content is relative to OUTPUT_BASE_DIR
            abs_output_base_dir = os.path.abspath(OUTPUT_BASE_DIR)
            abs_full_file_path = os.path.abspath(full_file_path)
            if not abs_full_file_path.startswith(abs_output_base_dir):
                print(f"  WARNING: Extracted file {abs_full_file_path} is not under OUTPUT_BASE_DIR {abs_output_base_dir}. Using filename as fallback rel_path.")
                rel_file_path = file_name # Fallback
            else:
                rel_file_path = os.path.relpath(abs_full_file_path, start=abs_output_base_dir)
            
            file_ext = os.path.splitext(file_name)[1].lower()
            group = EXT_GROUPS.get(file_ext, "unknown")
            table_lookup_ext = file_ext if group != "unknown" else "unknown"

            content_file_uuid = index_generic_file(conn, full_file_path, rel_file_path, group, table_lookup_ext)
            
            if content_file_uuid:
                if file_ext == ".txd":
                    process_txd_related_dds(conn, content_file_uuid, full_file_path, OUTPUT_BASE_DIR)

                content_table_name = get_table_name_for_ext(table_lookup_ext)
                try:
                    cursor.execute("""
                        INSERT INTO str_content_relationship (str_uuid, content_file_uuid, content_file_table)
                        VALUES (?, ?, ?)
                    """, (parent_str_uuid, content_file_uuid, content_table_name))
                    conn.commit()
                except sqlite3.IntegrityError:
                    pass 
                except Exception as e:
                    print(f"Error adding STR relationship for {full_file_path}: {e}")
            else:
                print(f"  Skipped STR relationship for extracted file {full_file_path} due to indexing failure.")
    if files_found_in_extraction == 0:
        print(f"  Warning: No files found to index in extracted directory: {extracted_files_base_dir}")

# --- Main Processing Logic ---
def main():
    if not os.path.isdir(STR_INPUT_DIR):
        print(f"ERROR: STR_INPUT_DIR does not exist: {STR_INPUT_DIR}")
        return
    os.makedirs(OUTPUT_BASE_DIR, exist_ok=True)

    conn = init_db()
    
    print("--- Pass 1: Indexing Root-Level Files (excluding .str) ---")
    for root_dir, _, dir_files in os.walk(STR_INPUT_DIR):
        for file_item_name in dir_files:
            file_ext = os.path.splitext(file_item_name)[1].lower()
            if file_ext == ".str":
                continue

            full_file_path = os.path.join(root_dir, file_item_name)
            
            abs_str_input_dir = os.path.abspath(STR_INPUT_DIR)
            abs_full_file_path = os.path.abspath(full_file_path)
            if not abs_full_file_path.startswith(abs_str_input_dir):
                 print(f"  WARNING: Root file {abs_full_file_path} is not under STR_INPUT_DIR {abs_str_input_dir}. Using filename as fallback rel_path.")
                 rel_file_path = file_item_name
            else:
                rel_file_path = os.path.relpath(abs_full_file_path, start=abs_str_input_dir)

            group_name = EXT_GROUPS.get(file_ext, "unknown")
            table_lookup_ext_for_generic = file_ext if group_name != "unknown" else "unknown"

            print(f"Indexing root file: {rel_file_path} (Group: {group_name})")
            file_uuid = index_generic_file(conn, full_file_path, rel_file_path, group_name, table_lookup_ext_for_generic)

            if file_uuid and file_ext == ".txd":
                process_txd_related_dds(conn, file_uuid, full_file_path, STR_INPUT_DIR)

    print("\n--- Pass 2: Processing .str Archives and Extracted Contents ---")
    for root_dir, _, dir_files in os.walk(STR_INPUT_DIR):
        for file_item_name in dir_files:
            if file_item_name.endswith(".str"):
                full_str_file_path = os.path.join(root_dir, file_item_name)
                
                abs_str_input_dir = os.path.abspath(STR_INPUT_DIR)
                abs_full_str_file_path = os.path.abspath(full_str_file_path)
                if not abs_full_str_file_path.startswith(abs_str_input_dir):
                    print(f"  WARNING: .str file {abs_full_str_file_path} is not under STR_INPUT_DIR {abs_str_input_dir}. Using filename as fallback rel_path for STR indexing.")
                    rel_str_file_path = file_item_name
                else:
                    rel_str_file_path = os.path.relpath(abs_full_str_file_path, start=abs_str_input_dir)
                
                print(f"\nProcessing .str archive: {rel_str_file_path}")

                parent_str_uuid = index_str_archive(conn, full_str_file_path, rel_str_file_path)
                if not parent_str_uuid:
                    print(f"  Failed to index or retrieve UUID for .str: {rel_str_file_path}. Skipping contents.")
                    continue
                print(f"  .str indexed/found with UUID: {parent_str_uuid}")

                extraction_successful = extract_str_file(full_str_file_path) # file_path needs to be full path here
                
                if extraction_successful:
                    expected_extraction_dir = os.path.join(OUTPUT_BASE_DIR, os.path.splitext(rel_str_file_path)[0] + "_str")
                    if os.path.isdir(expected_extraction_dir):
                        print(f"  Indexing extracted contents from: {expected_extraction_dir}")
                        index_extracted_content(conn, parent_str_uuid, expected_extraction_dir)
                    else:
                        print(f"  WARNING: Extraction reported success for {rel_str_file_path}, but directory not found: {expected_extraction_dir}")
                else:
                    print(f"  Skipping content indexing for {rel_str_file_path} due to extraction failure.")
    conn.close()
    print("\n✅ Full Indexing, Extraction, and DDS Processing complete.")

if __name__ == "__main__":
    if not os.path.isfile(QUICKBMS_EXE) or not os.access(QUICKBMS_EXE, os.X_OK):
        print(f"ERROR: QuickBMS executable not found or not executable at: {QUICKBMS_EXE}")
    elif not os.path.isfile(BMS_SCRIPT):
        print(f"ERROR: BMS script not found at: {BMS_SCRIPT}")
    else:
        main()
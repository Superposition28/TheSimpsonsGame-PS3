import os
import sqlite3
import hashlib
import subprocess
import time
import sys

# Add the directory containing Pillow-WavefrontDDS plugin to the path if needed
# Depending on installation method, Pillow might find it automatically.
# You might need to adjust this path or skip if Pillow finds the plugin.
# from PIL import Image, ImageFile
# dds_plugin_path = r"C:\Python3x\Lib\site-packages\Pillow_WavefrontDDS.libs" # Example path
# if os.path.exists(dds_plugin_path):
#     ImageFile.LOADER_LOGGER.debug(f"Adding plugin directory: {dds_plugin_path}")
#     sys.path.append(dds_plugin_path)
# else:
#     ImageFile.LOADER_LOGGER.debug(f"DDS plugin directory not found: {dds_plugin_path}")

from PIL import Image, UnidentifiedImageError # Import Image and specific error
import imagehash # Import imagehash library

# --- Configuration Paths & Constants ---
# IMPORTANT: Adjust these paths to your actual environment
STR_INPUT_DIR = r"Source\USRDIR"
OUTPUT_BASE_DIR = r"GameFiles\STROUT"
DB_PATH = r"RemakeRegistry\Games\TheSimpsonsGame\str_index_refactored_with_dds.db" # Renamed or keep same if overwriting

QUICKBMS_EXE = r"Tools\QuickBMS\exe\quickbms.exe"
BMS_SCRIPT = r"RemakeRegistry\Games\TheSimpsonsGame\Scripts\simpsons_str.bms"

EXT_GROUPS = {
    ".str": "audio_root",
    ".preinstanced": "models",
    ".txd": "textures",
    ".vp6": "videos",
    ".snu": "audio",
    ".mus": "audio", # Corrected mus group if it's audio
    ".lua": "other",
    ".bin": "other",
    ".txt": "other",
    ".dds": "textures_dds"  # located in TXD folders adjacent to TXD files in extraction
}

# Hashing and SSIM parameters (adjust as needed)
# For perceptual hashes, typically an image size like 8x8 is used internally
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
        print(f"Error reading file for hashing {path}: {e}")
        return None

def md5_string(s):
    return hashlib.md5(s.encode('utf-8')).hexdigest()

# --- Extraction Logic (Using QuickBMS) ---
# (Keep extract_str_file as is)
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
        # Added -o for overwrite in case previous runs left partial extractions
        process_result = subprocess.run(
            [QUICKBMS_EXE, "-o", BMS_SCRIPT, file_path, output_dir],
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
    if not sanitized_ext or sanitized_ext not in [e.lstrip('.') for e in EXT_GROUPS] + ["unknown", "dds"]: # Ensure 'dds' is handled even if not explicit key
         return "unknown_files_index"

    # Specific table name for dds
    if sanitized_ext == "dds":
        return "dds_index"

    return f"{sanitized_ext}_index"


def init_db():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("PRAGMA foreign_keys = ON;")

    # str_index table (remains the same)
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

    # Generic index tables (exclude .str and .dds)
    created_tables = set()
    for ext, group in EXT_GROUPS.items():
        if ext == ".str" or ext == ".dds": # Skip .str and .dds here
            continue
        table_name = get_table_name_for_ext(ext)
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

    # DDS index table (New table with perceptual hashes)
    dds_table_name = get_table_name_for_ext(".dds")
    cursor.execute(f"""
        CREATE TABLE IF NOT EXISTS {dds_table_name} (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            uuid TEXT UNIQUE NOT NULL,
            source_file_name TEXT,
            source_path TEXT NOT NULL,
            file_hash TEXT, -- SHA256 of the file content
            path_hash TEXT, -- MD5 of the source_path
            group_name TEXT DEFAULT 'textures_dds',
            phash TEXT,     -- Perceptual Hash (pHash)
            dhash TEXT,     -- Difference Hash (dHash)
            ahash TEXT      -- Average Hash (aHash)
            -- Add more hash types here if needed
        )
    """)

    # Unknown files index table
    unknown_table_name = get_table_name_for_ext("unknown")
    if unknown_table_name not in created_tables: # Check again in case 'unknown' group was in EXT_GROUPS somehow
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


    # str_content_relationship table (remains the same, links STR to any content table)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS str_content_relationship (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            str_uuid TEXT NOT NULL,
            content_file_uuid TEXT NOT NULL,
            content_file_table TEXT NOT NULL, -- Stores the name of the table the content file is in (e.g., 'dds_index')
            FOREIGN KEY (str_uuid) REFERENCES str_index(uuid) ON DELETE CASCADE,
            UNIQUE (str_uuid, content_file_uuid, content_file_table)
        )
    """)

    # txd_dds_relationship table (Remains the same, links TXD to DDS)
    txd_table_name = get_table_name_for_ext('.txd')
    dds_table_name = get_table_name_for_ext('.dds') # Ensure this gets the correct 'dds_index' table name
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
    if table_name == "dds_index":
         print(f"  WARNING: Calling index_generic_file for a DDS file: {file_path}. Use index_dds_file instead.")
         return None # Avoid processing DDS with the generic function

    file_hash = sha256_file(file_path)
    if file_hash is None: return None

    path_hash = md5_string(rel_path)
    # UUID based on content hash (file_hash) and location hash (path_hash)
    uuid = f"{file_hash[:16]}_{path_hash[:16]}" # Example UUID format

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
                    # Consider rolling back the transaction here if not automatically handled
                    # conn.rollback() # Add rollback if needed
                    raise # Re-raise after max retries
                continue
            print(f"ERROR: Operational error for {file_path} in {table_name}: {e}")
            # conn.rollback() # Add rollback if needed
            raise # Re-raise other operational errors
        except sqlite3.IntegrityError:
            # This means UUID (derived from file_hash and path_hash) already exists,
            # OR source_path is unique and this is a duplicate insertion attempt.
            # Fetch the existing UUID based on source_path first (more reliable for files).
            cursor.execute(f"SELECT uuid FROM {table_name} WHERE source_path = ?", (rel_path.replace("\\", "/"),))
            existing_row = cursor.fetchone()
            if existing_row:
                 # print(f"  INFO: File already indexed: {rel_path}")
                 return existing_row[0]

            # Fallback: check by UUID if source_path didn't match (less likely but safer)
            cursor.execute(f"SELECT uuid FROM {table_name} WHERE uuid = ?", (uuid,))
            existing_uuid_row = cursor.fetchone()
            if existing_uuid_row:
                # This case should ideally not be reached if source_path handling is correct,
                # but handles theoretical UUID collision with a different path (highly improbable).
                 # print(f"  INFO: UUID collision detected for {rel_path}, UUID {uuid} already exists.")
                 return existing_uuid_row[0]

            # If we reach here, an integrity error occurred but we couldn't find the existing row.
            # This indicates a deeper issue or race condition.
            print(f"ERROR: Integrity error for {file_path} in {table_name} but could not fetch existing row (uuid: {uuid}, path: {rel_path}).")
            # conn.rollback() # Add rollback if needed
            return None # Indicate failure
        except Exception as e:
            print(f"An unexpected error occurred during indexing of {file_path} in {table_name}: {e}")
            # conn.rollback() # Add rollback if needed
            return None # Indicate failure

    # This part is reached if all retries for "database is locked" fail
    print(f"ERROR: Could not insert {file_path} into {table_name} after {MAX_DB_RETRIES} retries (locked).")
    # conn.rollback() # Add rollback if needed
    return None


def index_dds_file(conn, file_path, rel_path):
    table_name = get_table_name_for_ext(".dds")
    group_name = EXT_GROUPS.get(".dds", "textures_dds")

    file_hash = sha256_file(file_path)
    if file_hash is None:
        print(f"  Failed to get SHA256 hash for DDS: {file_path}")
        return None

    path_hash = md5_string(rel_path)
    uuid = f"{file_hash[:16]}_{path_hash[:16]}"

    phash_val = None
    dhash_val = None
    ahash_val = None

    try:
        # Ensure Pillow can load DDS via plugin
        # Image.registered_extensions() # Can check if .dds is listed after importing plugin
        img = Image.open(file_path)

        # Calculate perceptual hashes (convert to grayscale first as is common)
        # Handle different image modes (e.g., 'RGBA', 'RGB', 'L')
        if img.mode != 'L':
             img_gray = img.convert('L')
        else:
             img_gray = img

        # Calculate hashes, resizing internally is handled by imagehash
        phash_val = str(imagehash.phash(img_gray, hash_size=PHASH_IMG_SIZE))
        dhash_val = str(imagehash.dhash(img_gray, hash_size=DHASH_IMG_SIZE))
        ahash_val = str(imagehash.average_hash(img_gray, hash_size=AHASH_IMG_SIZE))

        img.close() # Close the image file

    except FileNotFoundError:
        print(f"  ERROR: DDS file not found: {file_path}")
        return None
    except UnidentifiedImageError:
        print(f"  WARNING: Could not identify/load DDS file (potentially corrupted or unsupported format): {file_path}")
        return None
    except Exception as e:
        print(f"  ERROR calculating perceptual hashes for DDS {file_path}: {e}")
        return None # Still try to index with file/path hash if perceptual hashing fails? Or skip? Skipping for now.

    # If any hash calculation failed, we might choose to skip indexing,
    # or index with None hashes. Let's skip if hashes couldn't be calculated.
    if phash_val is None or dhash_val is None or ahash_val is None:
        print(f"  Skipping DDS indexing due to hashing failure: {file_path}")
        return None


    cursor = conn.cursor()
    for attempt in range(MAX_DB_RETRIES):
        try:
            cursor.execute(f"""
                INSERT INTO {table_name} (
                    uuid, source_file_name, source_path,
                    file_hash, path_hash, group_name,
                    phash, dhash, ahash
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                uuid, os.path.basename(file_path), rel_path.replace("\\", "/"),
                file_hash, path_hash, group_name,
                phash_val, dhash_val, ahash_val
            ))
            conn.commit()
            print(f"  Indexed DDS: {rel_path} (UUID: {uuid}, Hashes: p={phash_val}, d={dhash_val}, a={ahash_val})")
            return uuid
        except sqlite3.OperationalError as e:
            if "database is locked" in str(e):
                 # print(f"Database locked for {file_path} in {table_name}. Retrying ({attempt+1}/{MAX_DB_RETRIES})...")
                 time.sleep(RETRY_DELAY_SEC)
                 if attempt == MAX_DB_RETRIES - 1:
                    print(f"ERROR: Failed to insert {file_path} into {table_name} due to persistent lock after retries.")
                    # conn.rollback()
                    raise
                 continue
            print(f"ERROR: Operational error for DDS {file_path} in {table_name}: {e}")
            # conn.rollback()
            raise
        except sqlite3.IntegrityError:
            # Check by source_path first
            cursor.execute(f"SELECT uuid FROM {table_name} WHERE source_path = ?", (rel_path.replace("\\", "/"),))
            existing_row = cursor.fetchone()
            if existing_row:
                 # print(f"  INFO: DDS file already indexed: {rel_path}")
                 return existing_row[0]

            # Fallback: check by UUID
            cursor.execute(f"SELECT uuid FROM {table_name} WHERE uuid = ?", (uuid,))
            existing_uuid_row = cursor.fetchone()
            if existing_uuid_row:
                 # print(f"  INFO: DDS UUID collision detected for {rel_path}, UUID {uuid} already exists.")
                 return existing_uuid_row[0]

            print(f"ERROR: Integrity error for DDS {file_path} in {table_name} but could not fetch existing row (uuid: {uuid}, path: {rel_path}).")
            # conn.rollback()
            return None
        except Exception as e:
            print(f"An unexpected error occurred during indexing of DDS {file_path} in {table_name}: {e}")
            # conn.rollback()
            return None

    print(f"ERROR: Could not index DDS {file_path} after {MAX_DB_RETRIES} retries (locked).")
    # conn.rollback()
    return None


def index_str_archive(conn, str_file_full_path, str_file_rel_path):
    # (Keep index_str_archive as is)
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
            print(f"ERROR: Operational error for .str {str_file_full_path} in str_index: {e}")
            # conn.rollback()
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
            # conn.rollback()
            return None # Should not happen if source_path or uuid is unique
        except Exception as e:
             print(f"An unexpected error occurred during indexing of .str {str_file_full_path} in str_index: {e}")
             # conn.rollback()
             return None
    print(f"ERROR: Could not index .str {str_file_full_path} after {MAX_DB_RETRIES} retries.")
    # conn.rollback()
    return None


# --- New function to process DDS files related to a TXD ---
# This function finds DDS files next to a TXD and indexes them
def process_txd_related_dds(conn, txd_file_uuid, txd_file_full_path, dds_files_base_dir_for_relpath):
    txd_filename_no_ext = os.path.splitext(os.path.basename(txd_file_full_path))[0]
    txd_dir = os.path.dirname(txd_file_full_path)
    dds_folder_name = txd_filename_no_ext + "_txd" # This matches QuickBMS output structure
    dds_folder_full_path = os.path.join(txd_dir, dds_folder_name)

    if not os.path.isdir(dds_folder_full_path):
        # print(f"  INFO: DDS folder not found for {os.path.basename(txd_file_full_path)}: {dds_folder_full_path}")
        return

    print(f"  Processing DDS files in: {dds_folder_full_path}")
    cursor = conn.cursor()
    dds_table_name = get_table_name_for_ext(".dds")

    for dds_root, _, dds_filenames in os.walk(dds_folder_full_path):
        for dds_filename in dds_filenames:
            if dds_filename.lower().endswith(".dds"):
                full_dds_file_path = os.path.join(dds_root, dds_filename)

                try:
                    # Ensure dds_files_base_dir_for_relpath is absolute for robust relpath calculation
                    abs_dds_base_dir = os.path.abspath(dds_files_base_dir_for_relpath)
                    abs_full_dds_file_path = os.path.abspath(full_dds_file_path)

                    # rel_path for DDS next to TXD should be relative to the base extraction dir (OUTPUT_BASE_DIR)
                    # or the base source dir (STR_INPUT_DIR) depending on whether the TXD was extracted or not.
                    # The dds_files_base_dir_for_relpath argument is designed to handle this.
                    if not abs_full_dds_file_path.startswith(abs_dds_base_dir):
                         print(f"  WARNING: DDS file {abs_full_dds_file_path} is not under the expected base {abs_dds_base_dir}. Using full path relative to C: as fallback for rel_path. This may impact uniqueness if paths are complex.")
                         # Fallback: Relative to root or just filename. Using full path for better uniqueness.
                         dds_relative_path = os.path.abspath(full_dds_file_path) # Use full path as rel_path if base fails
                    else:
                        dds_relative_path = os.path.relpath(abs_full_dds_file_path, start=abs_dds_base_dir)


                except ValueError as e:
                    print(f"  WARNING: Could not make DDS path {full_dds_file_path} relative to {dds_files_base_dir_for_relpath}. Error: {e}. Skipping DDS file.")
                    continue # Skip this DDS if pathing is problematic


                # Use the dedicated index_dds_file function
                dds_file_uuid = index_dds_file(conn, full_dds_file_path, dds_relative_path)

                if dds_file_uuid:
                    try:
                        # Insert into the TXD-DDS relationship table
                        cursor.execute("""
                            INSERT INTO txd_dds_relationship (txd_uuid, dds_uuid)
                            VALUES (?, ?)
                        """, (txd_file_uuid, dds_file_uuid))
                        conn.commit()
                        # print(f"    Created TXD-DDS relationship: TXD({txd_file_uuid}) -> DDS({dds_file_uuid})")
                    except sqlite3.IntegrityError:
                        # print(f"    TXD-DDS relationship already exists: TXD({txd_file_uuid}) -> DDS({dds_file_uuid})")
                        pass # Relationship already exists
                    except sqlite3.OperationalError as e:
                        if "database is locked" in str(e):
                            print(f"    Database locked creating TXD-DDS relationship. Skipping for now.")
                            # Could implement retry logic here too if needed frequently
                            conn.rollback() # Rollback pending changes for this file
                            continue
                        print(f"    Operational Error creating TXD-DDS relationship for {dds_filename}: {e}")
                        conn.rollback()
                        continue
                    except Exception as e:
                        print(f"    Error creating TXD-DDS relationship for {dds_filename} ({dds_file_uuid}) with TXD ({txd_file_uuid}): {e}")
                        conn.rollback()
                        continue
                else:
                    print(f"    Skipping TXD-DDS relationship for extracted DDS file {full_dds_file_path} due to indexing failure.")


# --- Index Extracted Content Function ---
def index_extracted_content(conn, parent_str_uuid, extracted_files_base_dir):
    if not parent_str_uuid:
        print(f"ERROR: Cannot index extracted content without a valid parent_str_uuid.")
        return

    cursor = conn.cursor()
    files_found_in_extraction = 0
    print(f"  Scanning extracted directory for indexing: {extracted_files_base_dir}")
    indexed_uuids = {} # Cache UUIDs indexed in this pass to avoid redundant DB lookups if needed

    for root, _, files in os.walk(extracted_files_base_dir):
        for file_name in files:
            files_found_in_extraction += 1
            full_file_path = os.path.join(root, file_name)

            # rel_file_path for extracted content is relative to OUTPUT_BASE_DIR
            abs_output_base_dir = os.path.abspath(OUTPUT_BASE_DIR)
            abs_full_file_path = os.path.abspath(full_file_path)
            if not abs_full_file_path.startswith(abs_output_base_dir):
                print(f"  WARNING: Extracted file {abs_full_file_path} is not under OUTPUT_BASE_DIR {abs_output_base_dir}. Using full path relative to C: as fallback rel_path.")
                # Fallback: Relative to root or just filename. Using full path for better uniqueness.
                rel_file_path = os.path.abspath(full_file_path) # Use full path as rel_path if base fails
            else:
                rel_file_path = os.path.relpath(abs_full_file_path, start=abs_output_base_dir)

            file_ext = os.path.splitext(file_name)[1].lower()
            group = EXT_GROUPS.get(file_ext, "unknown")

            content_file_uuid = None
            content_table_name = None

            if file_ext == ".dds":
                # Use the specific DDS indexing function
                print(f"  Indexing extracted DDS: {rel_file_path}")
                content_file_uuid = index_dds_file(conn, full_file_path, rel_file_path)
                content_table_name = get_table_name_for_ext(".dds") # Should be 'dds_index'

            elif file_ext == ".txd":
                 # Index TXD first generically
                print(f"  Indexing extracted TXD: {rel_file_path}")
                content_file_uuid = index_generic_file(conn, full_file_path, rel_file_path, group, file_ext)
                content_table_name = get_table_name_for_ext(file_ext) # Should be 'txd_index'

                # Then process any related DDS files
                if content_file_uuid:
                    # Pass OUTPUT_BASE_DIR as the base for calculating relative paths for DDS files found here
                    process_txd_related_dds(conn, content_file_uuid, full_file_path, OUTPUT_BASE_DIR)


            else:
                # Index all other file types generically
                # print(f"  Indexing extracted file: {rel_file_path} (Group: {group})")
                table_lookup_ext_for_generic = file_ext if group != "unknown" else "unknown"
                content_file_uuid = index_generic_file(conn, full_file_path, rel_file_path, group, table_lookup_ext_for_generic)
                content_table_name = get_table_name_for_ext(table_lookup_ext_for_generic)


            # If the file was successfully indexed (or already existed), create the relationship
            if content_file_uuid and content_table_name:
                 try:
                    # Ensure the UUID is not already linked to this STR and table in this run
                    # This avoids redundant INSERT IGNORE attempts if the same file path appears multiple times (unlikely in STR extraction)
                    # but is a good practice. A simple set check is faster than a DB query if the UUID was just added.
                    # For robustness, we'll rely on the UNIQUE constraint in the DB, but acknowledge the possibility of checking here first.
                    # The DB constraint is the ultimate source of truth.

                    cursor.execute("""
                        INSERT INTO str_content_relationship (str_uuid, content_file_uuid, content_file_table)
                        VALUES (?, ?, ?)
                    """, (parent_str_uuid, content_file_uuid, content_table_name))
                    conn.commit()
                    # print(f"    Created STR-Content relationship: STR({parent_str_uuid}) -> {content_table_name}({content_file_uuid})")

                 except sqlite3.IntegrityError:
                     # Relationship already exists. This is common if rerunning the script.
                     pass
                     # print(f"    STR-Content relationship already exists: STR({parent_str_uuid}) -> {content_table_name}({content_file_uuid})")
                 except sqlite3.OperationalError as e:
                     if "database is locked" in str(e):
                         print(f"    Database locked creating STR-Content relationship. Skipping for now.")
                         conn.rollback()
                         continue
                     print(f"    Operational Error creating STR-Content relationship for {rel_file_path}: {e}")
                     conn.rollback()
                     continue
                 except Exception as e:
                    print(f"Error adding STR relationship for extracted file {full_file_path}: {e}")
                    conn.rollback()
                    continue
            else:
                if file_ext != ".dds" and file_ext != ".txd": # Avoid double-printing for DDS/TXD handled above
                   print(f"  Skipped STR relationship for extracted file {full_file_path} due to indexing failure.")

    if files_found_in_extraction == 0:
        print(f"  Warning: No files found to index in extracted directory: {extracted_files_base_dir}")

# --- Main Processing Logic ---
def main():
    if not os.path.isdir(STR_INPUT_DIR):
        print(f"ERROR: STR_INPUT_DIR does not exist: {STR_INPUT_DIR}")
        return
    os.makedirs(OUTPUT_BASE_DIR, exist_ok=True)
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True) # Ensure DB directory exists

    print(f"Initializing database at: {DB_PATH}")
    conn = init_db()

    print("\n--- Pass 1: Indexing Root-Level Files (excluding .str) ---")
    print(f"Scanning directory: {STR_INPUT_DIR}")
    root_files_processed = 0
    for root_dir, _, dir_files in os.walk(STR_INPUT_DIR):
        # Avoid processing extracted files if they happen to be placed under STR_INPUT_DIR (shouldn't happen with default setup)
        if os.path.abspath(root_dir).startswith(os.path.abspath(OUTPUT_BASE_DIR)):
             print(f"  INFO: Skipping directory within OUTPUT_BASE_DIR: {root_dir}")
             continue

        for file_item_name in dir_files:
            root_files_processed += 1
            full_file_path = os.path.join(root_dir, file_item_name)
            file_ext = os.path.splitext(file_item_name)[1].lower()

            if file_ext == ".str":
                continue # .str files are handled in Pass 2

            abs_str_input_dir = os.path.abspath(STR_INPUT_DIR)
            abs_full_file_path = os.path.abspath(full_file_path)

            # Calculate relative path to STR_INPUT_DIR for indexing
            if not abs_full_file_path.startswith(abs_str_input_dir):
                 print(f"  WARNING: Root file {abs_full_file_path} is not under STR_INPUT_DIR {abs_str_input_dir}. Using full path relative to C: as fallback rel_path.")
                 rel_file_path = os.path.abspath(full_file_path) # Fallback rel_path
            else:
                rel_file_path = os.path.relpath(abs_full_file_path, start=abs_str_input_dir)


            group_name = EXT_GROUPS.get(file_ext, "unknown")
            table_lookup_ext_for_generic = file_ext if group_name != "unknown" else "unknown"

            # Handle DDS differently
            if file_ext == ".dds":
                 print(f"  Indexing root DDS: {rel_file_path} (Group: {group_name})")
                 file_uuid = index_dds_file(conn, full_file_path, rel_file_path)
                 # Note: Root DDS found like this are not currently linked to any STR or TXD
                 # unless they are processed as part of a TXD's sibling folder later.
                 # The current logic in process_txd_related_dds handles DDS *next to* TXD in either source or output dir.
                 # Standalone root DDS will be indexed in dds_index but won't have relationships established here.

            elif file_ext == ".txd":
                print(f"  Indexing root TXD: {rel_file_path} (Group: {group_name})")
                file_uuid = index_generic_file(conn, full_file_path, rel_file_path, group_name, table_lookup_ext_for_generic)

                # Process any related DDS files that might be in a sibling _txd folder in the source directory
                if file_uuid:
                    # Pass STR_INPUT_DIR as the base for calculating relative paths for DDS files found here
                    process_txd_related_dds(conn, file_uuid, full_file_path, STR_INPUT_DIR)

            else:
                # Index all other generic root files
                # print(f"  Indexing root file: {rel_file_path} (Group: {group_name})")
                file_uuid = index_generic_file(conn, full_file_path, rel_file_path, group_name, table_lookup_ext_for_generic)
                # No relationships are created for these root files by default here.


    print(f"\n--- Pass 2: Processing .str Archives and Extracted Contents ---")
    print(f"Scanning directory: {STR_INPUT_DIR}")
    str_files_processed = 0
    for root_dir, _, dir_files in os.walk(STR_INPUT_DIR):
         # Avoid processing extracted files if they happen to be placed under STR_INPUT_DIR (shouldn't happen)
        if os.path.abspath(root_dir).startswith(os.path.abspath(OUTPUT_BASE_DIR)):
             continue

        for file_item_name in dir_files:
            if file_item_name.endswith(".str"):
                str_files_processed += 1
                full_str_file_path = os.path.join(root_dir, file_item_name)

                abs_str_input_dir = os.path.abspath(STR_INPUT_DIR)
                abs_full_str_file_path = os.path.abspath(full_str_file_path)
                if not abs_full_str_file_path.startswith(abs_str_input_dir):
                    print(f"  WARNING: .str file {abs_full_str_file_path} is not under STR_INPUT_DIR {abs_str_input_dir}. Using full path relative to C: as fallback rel_path for STR indexing.")
                    rel_str_file_path = os.path.abspath(full_str_file_path) # Fallback rel_path
                else:
                    rel_str_file_path = os.path.relpath(abs_full_str_file_path, start=abs_str_input_dir)


                print(f"\nProcessing .str archive: {rel_str_file_path}")

                # Index or retrieve the UUID for the .str archive itself
                parent_str_uuid = index_str_archive(conn, full_str_file_path, rel_str_file_path)
                if not parent_str_uuid:
                    print(f"  Failed to index or retrieve UUID for .str: {rel_str_file_path}. Skipping contents.")
                    continue
                print(f"  .str indexed/found with UUID: {parent_str_uuid}")

                # Extract the contents of the .str file
                extraction_successful = extract_str_file(full_str_file_path)

                # If extraction was successful, index the contents
                if extraction_successful:
                    # The expected extraction directory is relative to OUTPUT_BASE_DIR
                    expected_extraction_dir = os.path.join(OUTPUT_BASE_DIR, os.path.splitext(rel_str_file_path)[0] + "_str")
                    if os.path.isdir(expected_extraction_dir):
                        print(f"  Indexing extracted contents from: {expected_extraction_dir}")
                        # Index extracted contents and create relationships to the parent STR UUID
                        index_extracted_content(conn, parent_str_uuid, expected_extraction_dir)
                    else:
                        print(f"  WARNING: Extraction reported success for {rel_str_file_path}, but directory not found: {expected_extraction_dir}")
                else:
                    print(f"  Skipping content indexing for {rel_str_file_path} due to extraction failure.")


    conn.close()
    print("\n✅ Full Indexing, Extraction, and DDS Processing complete.")
    print(f"Indexed {root_files_processed} root files and processed {str_files_processed} .str archives.")


if __name__ == "__main__":
    # Basic checks for external tools
    quickbms_ok = os.path.isfile(QUICKBMS_EXE) and os.access(QUICKBMS_EXE, os.X_OK)
    bms_script_ok = os.path.isfile(BMS_SCRIPT)

    if not quickbms_ok:
        print(f"ERROR: QuickBMS executable not found or not executable at: {QUICKBMS_EXE}")
    if not bms_script_ok:
        print(f"ERROR: BMS script not found at: {BMS_SCRIPT}")

    if quickbms_ok and bms_script_ok:
        main()
    else:
        print("Please fix the tool paths and permissions before running.")
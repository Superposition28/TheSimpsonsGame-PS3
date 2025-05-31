#!/usr/bin/env python3
import sqlite3
import os
import questionary
from pathlib import Path
import hashlib # For potential future input validation if needed
import sys # For sys.executable
import subprocess # For calling external script

# --- Configuration ---
DB_PATH_DEFAULT = r"A:\Dev\Games\TheSimpsonsGame\PAL\RemakeRegistry\Games\TheSimpsonsGame\str_index_refactored.db"

EXT_GROUPS = {
    ".str": "audio_root",
    ".preinstanced": "models",
    ".txd": "textures",
    ".vp6": "videos",
    ".snu": "audio",
    ".mus": "other",
    ".lua": "other",
    ".bin": "other",
    ".txt": "other"
}
UNKNOWN_FILES_TABLE = "unknown_files_index" # As per your indexing script

# --- Configuration for Extraction ---
PYTHON_EXECUTABLE = sys.executable  # Path to current python interpreter

# Path to the extraction script, relative to this script's location or project root
# More robustly determined in main() if needed
_EXTRACT_SCRIPT_NAME = "Modules/Extract/bms_extract.py"

# This is the base directory where the original .str files are located.
# It MUST match the STR_INPUT_DIR that bms_extract.py uses for its relpath logic.
STR_INPUT_DIR_FOR_EXTRACTION = r"A:\Dev\Games\TheSimpsonsGame\PAL\Source\USRDIR"


# --- Database Utilities ---
def get_db_connection(db_path_str):
    db_file = Path(db_path_str)
    if not db_file.exists() or not db_file.is_file():
        print(f"Error: Database file not found at '{db_file}'.")
        print("Please ensure the path is correct and the indexing script has been run.")
        return None
    try:
        conn = sqlite3.connect(f"file:{db_file}?mode=ro", uri=True)  # Read-only
        conn.row_factory = sqlite3.Row
        return conn
    except sqlite3.Error as e:
        print(f"Database connection error: {e}")
        return None

def get_table_name_for_ext(ext):
    sanitized_ext = ext.lstrip('.').lower()
    if not sanitized_ext:
        return UNKNOWN_FILES_TABLE
    return f"{sanitized_ext}_index"

def get_all_content_tables(conn):
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
    except sqlite3.Error as e:
        print(f"Error fetching table list from DB: {e}")
        return []
        
    all_tables = [row[0] for row in cursor.fetchall()]
    known_content_tables = set()
    for ext_key in EXT_GROUPS:
        if ext_key == ".str":
            continue
        known_content_tables.add(get_table_name_for_ext(ext_key))
    known_content_tables.add(UNKNOWN_FILES_TABLE)

    actual_content_tables = [tbl for tbl in all_tables if tbl in known_content_tables]
    
    # Heuristic for other potential content tables
    for tbl in all_tables:
        if tbl.endswith("_index") and tbl not in ["str_index"] and tbl not in actual_content_tables:
            actual_content_tables.append(tbl)
            
    return list(set(actual_content_tables))


# --- Search Functions --- (Largely unchanged, ensure they return necessary details)
def find_str_archives_from_content(conn, search_value, search_field, content_tables):
    cursor = conn.cursor()
    found_str_archive_details = []
    processed_content_uuids = set()

    for table_name in content_tables:
        query_value = search_value
        sql_query = f"SELECT uuid, source_file_name, source_path FROM {table_name} WHERE {search_field} = ?"

        if search_field == 'source_path':
            try:
                cursor.execute(sql_query, (query_value,))
                rows = cursor.fetchall()
                if not rows and os.path.basename(query_value) != query_value : # Avoid re-querying if basename is same as full
                    base_name_query = f"SELECT uuid, source_file_name, source_path FROM {table_name} WHERE source_file_name = ?"
                    cursor.execute(base_name_query, (os.path.basename(query_value),))
                    rows = cursor.fetchall()
            except sqlite3.Error: continue
        else:
            try:
                cursor.execute(sql_query, (query_value,))
                rows = cursor.fetchall()
            except sqlite3.Error: continue

        for row in rows:
            content_uuid = row['uuid']
            if content_uuid in processed_content_uuids: continue
            processed_content_uuids.add(content_uuid)
            try:
                cursor.execute("SELECT str_uuid FROM str_content_relationship WHERE content_file_uuid = ?", (content_uuid,))
                relationship_rows = cursor.fetchall()
                for rel_row in relationship_rows:
                    str_uuid = rel_row['str_uuid']
                    cursor.execute("SELECT source_file_name, source_path, uuid FROM str_index WHERE uuid = ?", (str_uuid,))
                    str_archive_row = cursor.fetchone()
                    if str_archive_row:
                        found_str_archive_details.append({
                            'str_name': str_archive_row['source_file_name'],
                            'str_path': str_archive_row['source_path'],
                            'str_uuid': str_archive_row['uuid'],
                            'found_via_content_name': row['source_file_name'],
                            'found_via_content_path': row['source_path']
                        })
            except sqlite3.Error as e:
                print(f"Error querying relationships or str_index for content UUID {content_uuid}: {e}")
    return found_str_archive_details

def find_str_archives_directly(conn, search_value, search_field):
    cursor = conn.cursor()
    direct_found_archives = []
    sql_query = f"SELECT source_file_name, source_path, uuid FROM str_index WHERE {search_field} = ?"
    query_value = search_value

    if search_field == 'source_path':
        try:
            cursor.execute(sql_query, (query_value,))
            rows = cursor.fetchall()
            if not rows and os.path.basename(query_value) != query_value:
                base_name_query = f"SELECT source_file_name, source_path, uuid FROM str_index WHERE source_file_name = ?"
                cursor.execute(base_name_query, (os.path.basename(query_value),))
                rows = cursor.fetchall()
        except sqlite3.Error: return []
    else:
        try:
            cursor.execute(sql_query, (query_value,))
            rows = cursor.fetchall()
        except sqlite3.Error: return []

    for row in rows:
        direct_found_archives.append({
            'str_name': row['source_file_name'],
            'str_path': row['source_path'],
            'str_uuid': row['uuid'],
            'found_via_content_name': None,
            'found_via_content_path': None
        })
    return direct_found_archives

# --- Main Application Logic ---
def main():
    print("--- Granular STR Archive Finder ---")
    
    # Determine script's own directory for robust relative path to bms_extract.py
    script_dir = Path(__file__).resolve().parent
    extract_script_full_path = script_dir / _EXTRACT_SCRIPT_NAME

    db_path_input = questionary.text(
        "Enter the path to your 'str_index_refactored.db' database:",
        default=DB_PATH_DEFAULT
    ).ask()

    if not db_path_input:
        print("No database path provided. Exiting.")
        return

    conn = get_db_connection(db_path_input)
    if not conn: return

    content_tables = get_all_content_tables(conn)
    if not content_tables:
        print("Warning: Could not determine content tables. Searches for content files might be incomplete.")

    try:
        while True:
            search_term_raw = questionary.text(
                "Enter file name/path, UUID, or hash (or type 'exit' to quit):",
                validate=lambda text: True if len(text.strip()) > 0 else "Input cannot be empty."
            ).ask()

            if search_term_raw is None or search_term_raw.lower() == 'exit':
                print("Exiting...")
                break

            search_term = search_term_raw.strip()
            search_term_path_normalized = search_term.replace("\\", "/")

            print(f"\nSearching for: '{search_term}'...")
            all_results = []
            
            print("  Checking as content file detail...")
            for field in ['uuid', 'file_hash']:
                all_results.extend(find_str_archives_from_content(conn, search_term, field, content_tables))
            all_results.extend(find_str_archives_from_content(conn, search_term_path_normalized, 'source_path', content_tables))

            print("  Checking as .STR archive detail...")
            for field in ['uuid', 'file_hash']:
                all_results.extend(find_str_archives_directly(conn, search_term, field))
            all_results.extend(find_str_archives_directly(conn, search_term_path_normalized, 'source_path'))
            
            unique_displayed_items = []
            displayed_results_tracker = set()

            if all_results:
                for res_item in all_results:
                    result_key = (res_item['str_uuid'], res_item['str_path'])
                    if result_key not in displayed_results_tracker:
                        unique_displayed_items.append(res_item)
                        displayed_results_tracker.add(result_key)
                
                if unique_displayed_items:
                    print("\n--- Found Matching STR Archive(s) ---")
                    for item in unique_displayed_items:
                        print(f"  STR Archive Name: {item['str_name']}")
                        print(f"  STR Archive Path (relative to source input dir): {item['str_path']}")
                        print(f"  STR Archive UUID: {item['str_uuid']}")
                        if item['found_via_content_name']:
                            print(f"    Found because it contains: {item['found_via_content_name']}")
                            print(f"    Content Path (relative to QuickBMS output dir): {item['found_via_content_path']}")
                        print("-" * 20)
                else: # Should only happen if all_results had items but somehow none were unique
                     print(f"\nNo unique .str archive found related to '{search_term}'.")

            else:
                print(f"\nNo .str archive found related to '{search_term}'.")
                # (Tips for searching - can be re-added if desired)

            # --- Extraction Step ---
            if unique_displayed_items:
                archives_to_extract_paths = []
                if len(unique_displayed_items) == 1:
                    res = unique_displayed_items[0]
                    # Construct full absolute path to the .str file
                    full_str_path_to_extract = Path(STR_INPUT_DIR_FOR_EXTRACTION) / res['str_path']
                    if questionary.confirm(
                        f"Extract the found archive: {res['str_name']} ({res['str_path']})?", default=False
                    ).ask():
                        archives_to_extract_paths = [str(full_str_path_to_extract)]
                else:
                    choices_for_q = [
                        {
                            "name": f"{item['str_name']} ({item['str_path']})",
                            # Store the full absolute path for easy use later
                            "value": str(Path(STR_INPUT_DIR_FOR_EXTRACTION) / item['str_path']),
                            "checked": False
                        }
                        for item in unique_displayed_items
                    ]
                    selected_full_paths = questionary.checkbox(
                        "Select STR archives to extract (files must exist at the specified source path):",
                        choices=choices_for_q
                    ).ask()
                    archives_to_extract_paths = selected_full_paths or []

                if archives_to_extract_paths:
                    print("\n--- Attempting Extraction ---")
                    if not extract_script_full_path.is_file():
                        print(f"ERROR: Extraction script not found at '{extract_script_full_path}'. Cannot proceed.")
                    else:
                        for str_file_full_path_str in archives_to_extract_paths:
                            str_file_to_extract = Path(str_file_full_path_str)
                            if not str_file_to_extract.is_file():
                                print(f"  ERROR: STR file not found for extraction: {str_file_to_extract}")
                                print(f"         (Expected under: {STR_INPUT_DIR_FOR_EXTRACTION})")
                                continue

                            print(f"  Requesting extraction for: {str_file_to_extract}")
                            cmd = [
                                PYTHON_EXECUTABLE, 
                                str(extract_script_full_path),
                                str(str_file_to_extract) # Pass the full path to the .str file
                            ]
                            print(f"    Executing: {' '.join(cmd)}")
                            try:
                                # Using Popen to stream output
                                process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, encoding='utf-8', errors='replace')
                                if process.stdout:
                                    for line in iter(process.stdout.readline, ''):
                                        print(f"    [bms_extract.py] {line.strip()}")
                                    process.stdout.close()
                                return_code = process.wait()

                                if return_code == 0:
                                    print(f"    Extraction process completed for: {str_file_to_extract}")
                                else:
                                    print(f"    ERROR: Extraction process for {str_file_to_extract} failed with return code {return_code}.")
                            except FileNotFoundError:
                                print(f"    ERROR: Could not find Python ('{PYTHON_EXECUTABLE}') or the script ('{extract_script_full_path}').")
                            except Exception as e:
                                print(f"    ERROR: An unexpected error occurred during extraction of {str_file_to_extract}: {e}")
            
            print("\n" + "="*50 + "\n")

    except (KeyboardInterrupt, EOFError):
        print("\nSearch cancelled by user. Exiting.")
    except Exception as e:
        print(f"An unexpected error occurred in the main loop: {e}")
        import traceback
        traceback.print_exc()
    finally:
        if conn:
            conn.close()

if __name__ == "__main__":
    main()
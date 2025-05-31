import sqlite3
import json
import os

# Paths - IMPORTANT: Update DB_PATH to the refactored database name
DB_PATH = r"A:\Dev\Games\TheSimpsonsGame\PAL\RemakeRegistry\Games\TheSimpsonsGame\str_index_refactored.db"
OUTPUT_JSON = r"A:\Dev\Games\TheSimpsonsGame\PAL\RemakeRegistry\Games\TheSimpsonsGame\str_index_export_refactored.json"

# EXT_GROUPS definition from the main indexing script
# Needed to correctly assign group for .str files
EXT_GROUPS = {
    ".preinstanced": "models",
    ".txd": "textures",
    ".vp6": "videos",
    ".snu": "audio",
    ".str": "Archive", # Group for .str archives
    ".mus": "mus",
    ".lua": "lua",
    ".bin": "bin",
    ".txt": "txt"
}

def get_all_file_related_tables(conn):
    """Gets all tables that look like file indexes (e.g., str_index, txd_index, unknown_files_index)."""
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name LIKE '%_index'")
    tables = [row[0] for row in cursor.fetchall()]
    return tables

def create_json_entry(uuid, source_file_name, source_path, file_hash, path_hash):
    """Helper to create the basic JSON structure for a file entry, matching the old format."""
    file_ext = os.path.splitext(source_file_name)[1].lower()
    if not file_ext: # Handle files with no extension if they occur
        file_ext = ".noext"

    entry = {
        "uuid": uuid,
        "sourceFileName": source_file_name,
        "sourcePath": source_path, # Consumer needs context for path relativity
        "fileHash": file_hash,
        "pathNameHashMD5": path_hash, # Corresponds to path_hash from DB
        "stages": {
            file_ext: { # The file's own extension is the "stage"
                "path": source_path # The path to this file
            }
        },
        "children": [] # Populated later for .str archives
    }
    return entry

def export_to_json():
    if not os.path.exists(DB_PATH):
        print(f"ERROR: Database not found at {DB_PATH}")
        return

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row # Access columns by name, e.g., row['uuid']
    cursor = conn.cursor()

    uuid_map = {} # Stores all file entries (both .str and others) by their UUID

    # 1. Process .str files (from str_index table)
    str_archive_group_name = EXT_GROUPS.get(".str", "archives") # Default if somehow not in EXT_GROUPS
    try:
        cursor.execute("SELECT uuid, source_file_name, source_path, file_hash, path_hash FROM str_index")
        for row in cursor.fetchall():
            entry = create_json_entry(row["uuid"], row["source_file_name"], row["source_path"],
                                      row["file_hash"], row["path_hash"])
            entry["_is_str_archive"] = True # Temporary flag to identify .str archives
            entry["_group_name_for_json"] = str_archive_group_name # Temporary storage for its group
            uuid_map[row["uuid"]] = entry
    except sqlite3.OperationalError as e:
        print(f"Error querying str_index: {e}. Make sure the table exists and schema is correct.")
        conn.close()
        return

    # 2. Process files from all other extension-specific and unknown_files_index tables
    all_other_file_tables = get_all_file_related_tables(conn)
    for table_name in all_other_file_tables:
        if table_name == "str_index":
            continue # Already processed

        try:
            # These tables should have a 'group_name' column
            cursor.execute(f"SELECT uuid, source_file_name, source_path, file_hash, path_hash, group_name FROM {table_name}")
            for row in cursor.fetchall():
                if row["uuid"] in uuid_map:
                    print(f"Warning: Duplicate UUID {row['uuid']} encountered when processing {table_name}. This entry will be skipped.")
                    continue
                
                entry = create_json_entry(row["uuid"], row["source_file_name"], row["source_path"],
                                          row["file_hash"], row["path_hash"])
                entry["_group_name_for_json"] = row["group_name"] # Temporary storage for its group
                uuid_map[row["uuid"]] = entry
        except sqlite3.OperationalError as e:
            print(f"Error querying table {table_name}: {e}. Skipping this table.")
            continue

    # 3. Fetch relationships and establish parent-child links
    child_uuids_with_parents = set() # Keep track of UUIDs that are children
    try:
        cursor.execute("SELECT str_uuid, content_file_uuid FROM str_content_relationship")
        relationships = cursor.fetchall()
    except sqlite3.OperationalError as e:
        print(f"Error querying str_content_relationship: {e}. Hierarchy may be incomplete.")
        relationships = []
    
    conn.close() # Done with DB operations

    for rel_row in relationships:
        parent_str_uuid = rel_row["str_uuid"]
        child_content_uuid = rel_row["content_file_uuid"]

        parent_entry = uuid_map.get(parent_str_uuid)
        child_entry = uuid_map.get(child_content_uuid)

        if parent_entry and child_entry:
            parent_entry["children"].append(child_entry)
            child_uuids_with_parents.add(child_content_uuid) # Mark this child as having a parent
        else:
            if not parent_entry:
                print(f"Warning: Parent .str archive UUID '{parent_str_uuid}' from relationship not found in map.")
            if not child_entry:
                 print(f"Warning: Child content UUID '{child_content_uuid}' from relationship not found in map.")

    # 4. Assemble the final grouped_data for JSON output
    final_grouped_json = {}
    for uuid_key, file_entry_value in uuid_map.items():
        # Retrieve and remove the temporary group name storage
        group_name = file_entry_value.pop("_group_name_for_json", "unknown_group")

        is_str_archive = file_entry_value.pop("_is_str_archive", False) # Get and remove temp flag

        # A file is top-level if it's a .str archive OR if it's any other file type that is NOT a child
        if is_str_archive or (uuid_key not in child_uuids_with_parents):
            if group_name not in final_grouped_json:
                final_grouped_json[group_name] = []
            final_grouped_json[group_name].append(file_entry_value)
    
    # Optional: Sort entries within each group by sourceFileName for consistent output
    for group_key in final_grouped_json:
        final_grouped_json[group_key].sort(key=lambda x: x.get("sourceFileName", "").lower())

    # 5. Write the JSON file
    output_dir = os.path.dirname(OUTPUT_JSON)
    if output_dir and not os.path.exists(output_dir): # Ensure output directory exists
        try:
            os.makedirs(output_dir)
        except OSError as e:
            print(f"Error creating output directory {output_dir}: {e}")
            return


    try:
        with open(OUTPUT_JSON, 'w', encoding='utf-8') as f:
            json.dump(final_grouped_json, f, indent=4, ensure_ascii=False)
        print(f"✅ Exported database (refactored schema) to JSON: {OUTPUT_JSON}")
    except IOError as e:
        print(f"Error writing JSON file to {OUTPUT_JSON}: {e}")


if __name__ == "__main__":
    export_to_json()
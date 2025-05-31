import sqlite3
import sys
import config

def get_table_name_for_ext(ext: str) -> str:
    """
    Determines the database table name for a given file extension.
    Uses EXT_GROUPS for specific mappings, otherwise generates a name.
    """
    sanitized_ext = ext.lstrip('.').lower()
    group_name = config.EXT_GROUPS.get(ext.lower())

    # Specific mappings based on group names in EXT_GROUPS or direct extension
    specific_mappings = {
        "Archive_root": "str_index",        # .str files (archives)
        "models_source": "preinstanced_index",   # .preinstanced files
        "models_blend": "blend_index",    # .blend files
        "models_glb": "glb_index",        # .glb files
        "models_fbx": "fbx_index",        # .fbx files
        "textures_dds": "dds_index",      # .dds files (extracted textures)
        "texture_dictionary": "txd_index",          # .txd files (texture dictionaries)
        "video_source": "video_index",          # .vp6 files
        "audio_source": "snu_index",             # .snu files
        "audio_other": "mus_index",       # .mus files
        "other": "other_files_index",     # Default for .lua, .bin, .txt etc.
        "unknown": "unknown_files_index",  # Catch-all for unmapped extensions
		"audio_wav": "audio_wav_index", # .wav files
		"video_ogv": "video_ogv_index" # .ogv files
    }

    if group_name and group_name in specific_mappings:
        return specific_mappings[group_name]
    elif sanitized_ext in specific_mappings: # Direct mapping for extension if not via group
        return specific_mappings[sanitized_ext]
    elif group_name == "other":
        return specific_mappings["other"]
    elif sanitized_ext: # Fallback for known extensions not explicitly mapped
        #print(f"WARNING: Extension '{ext}' not specifically mapped, using 'other_files_index'. Consider adding to EXT_GROUPS or specific_mappings.", file=sys.stderr)
        return specific_mappings["unknown"]
    else: # Should not happen if ext is valid
        return specific_mappings["unknown"]


def create_generic_file_table(cursor: sqlite3.Cursor, table_name: str):
    """Creates a generic file index table if it doesn't exist."""
    if table_name == get_table_name_for_ext(".dds"): # DDS has its own creator
        return
    cursor.execute(f"""
        CREATE TABLE IF NOT EXISTS {table_name} (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            uuid TEXT UNIQUE NOT NULL,
            source_file_name TEXT,
            source_path TEXT UNIQUE NOT NULL, -- Relative path, should be unique within its context
            file_hash TEXT, -- SHA256
            path_hash TEXT, -- MD5 of source_path
            group_name TEXT, -- From EXT_GROUPS
            first_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    # Add triggers for last_updated
    cursor.execute(f"""
        CREATE TRIGGER IF NOT EXISTS update_{table_name}_last_updated
        AFTER UPDATE ON {table_name}
        FOR EACH ROW
        BEGIN
            UPDATE {table_name} SET last_updated = CURRENT_TIMESTAMP WHERE id = OLD.id;
        END;
    """)

def create_dds_table(cursor: sqlite3.Cursor):
    """Creates or alters the DDS index table with image hash columns."""
    table_name = get_table_name_for_ext(".dds")
    cursor.execute(f"""
        CREATE TABLE IF NOT EXISTS {table_name} (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            uuid TEXT UNIQUE NOT NULL,
            source_file_name TEXT,
            source_path TEXT UNIQUE NOT NULL,
            file_hash TEXT,
            path_hash TEXT,
            group_name TEXT DEFAULT 'textures_dds',
            phash TEXT,
            dhash TEXT,
            ahash TEXT,
            color_phash TEXT,
            color_dhash TEXT,
            color_ahash TEXT,
            first_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    # Add triggers for last_updated
    cursor.execute(f"""
        CREATE TRIGGER IF NOT EXISTS update_{table_name}_last_updated
        AFTER UPDATE ON {table_name}
        FOR EACH ROW
        BEGIN
            UPDATE {table_name} SET last_updated = CURRENT_TIMESTAMP WHERE id = OLD.id;
        END;
    """)

    # Add columns if they don't exist (for backward compatibility if schema changes)
    columns_to_add = {
        "phash": "TEXT", "dhash": "TEXT", "ahash": "TEXT",
        "color_phash": "TEXT", "color_dhash": "TEXT", "color_ahash": "TEXT",
        "first_seen": "TIMESTAMP", "last_updated": "TIMESTAMP" # Ensure these are also checked
    }
    cursor.execute(f"PRAGMA table_info({table_name})")
    existing_columns = [row[1] for row in cursor.fetchall()]

    for col, col_type in columns_to_add.items():
        if col not in existing_columns:
            try:
                cursor.execute(f"ALTER TABLE {table_name} ADD COLUMN {col} {col_type}")
                if "TIMESTAMP" in col_type: # Add default for new timestamp columns
                     cursor.execute(f"UPDATE {table_name} SET {col} = CURRENT_TIMESTAMP WHERE {col} IS NULL")
                print(f"Added column '{col}' to table '{table_name}'.")
            except sqlite3.OperationalError as e:
                # This might happen if run concurrently, but should be rare with exist_ok
                print(f"Warning: Could not add column {col} to {table_name} (might already exist or other issue): {e}", file=sys.stderr)


def create_relationship_tables(cursor: sqlite3.Cursor):
    """Creates all relationship tables."""
    # STR archives to their extracted content
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS str_content_relationship (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            str_uuid TEXT NOT NULL,      -- UUID from str_index
            content_file_uuid TEXT NOT NULL, -- UUID from another file table
            content_file_table TEXT NOT NULL, -- Name of the table content_file_uuid is in
            FOREIGN KEY (str_uuid) REFERENCES str_index(uuid) ON DELETE CASCADE,
            -- Cannot have direct FOREIGN KEY to content_file_uuid due to dynamic table
            UNIQUE (str_uuid, content_file_uuid, content_file_table)
        )
    """)

    # TXD files to their extracted DDS files
    # Assumes txd_uuid is from txd_index and dds_uuid is from dds_index
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS txd_dds_relationship (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            txd_uuid TEXT NOT NULL,
            dds_uuid TEXT NOT NULL,
            FOREIGN KEY (txd_uuid) REFERENCES txd_index(uuid) ON DELETE CASCADE,
            FOREIGN KEY (dds_uuid) REFERENCES dds_index(uuid) ON DELETE CASCADE,
            UNIQUE (txd_uuid, dds_uuid)
        )
    """)

    # .blend files to their source .preinstanced files
    # Assumes blend_uuid is from blend_index and preinstanced_uuid is from preinstanced_index
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS blend_preinstanced_relationship (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            blend_uuid TEXT NOT NULL,
            preinstanced_uuid TEXT NOT NULL,
            FOREIGN KEY (blend_uuid) REFERENCES blend_index(uuid) ON DELETE CASCADE,
            FOREIGN KEY (preinstanced_uuid) REFERENCES preinstanced_index(uuid) ON DELETE CASCADE,
            UNIQUE (blend_uuid, preinstanced_uuid)
        )
    """)

    # .glb/.fbx files to their source .blend files
    # Assumes glb_fbx_uuid is from glb_index or fbx_index, blend_uuid from blend_index
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS model_export_blend_relationship (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            exported_model_uuid TEXT NOT NULL, -- UUID from glb_index or fbx_index
            exported_model_table TEXT NOT NULL, -- 'glb_index' or 'fbx_index'
            blend_uuid TEXT NOT NULL,          -- UUID from blend_index
            FOREIGN KEY (blend_uuid) REFERENCES blend_index(uuid) ON DELETE CASCADE,
            -- Cannot have direct FOREIGN KEY to exported_model_uuid due to dynamic table
            UNIQUE (exported_model_uuid, blend_uuid)
        )
    """)

    # Add other relationship tables here as needed
    # Example: "variant_of_relationship"
    # cursor.execute("""
    #     CREATE TABLE IF NOT EXISTS variant_of_relationship (
    #         id INTEGER PRIMARY KEY AUTOINCREMENT,
    #         file_uuid TEXT NOT NULL,
    #         variant_of_uuid TEXT NOT NULL,
    #         variant_type TEXT, -- e.g., "color_corrected", "resized"
    #         UNIQUE (file_uuid, variant_of_uuid, variant_type)
    #     )
    # """)

def initialize_database(conn: sqlite3.Connection):
    """Initializes all necessary tables in the database."""
    cursor = conn.cursor()
    print("Initializing database schema...")

    # Create tables for each distinct table name derived from EXT_GROUPS
    created_table_names = set()
    for ext_key in config.EXT_GROUPS.keys():
        table_name = get_table_name_for_ext(ext_key)
        if table_name not in created_table_names:
            if table_name == get_table_name_for_ext(".dds"): # Special handling for DDS
                create_dds_table(cursor)
            else:
                create_generic_file_table(cursor, table_name)
            created_table_names.add(table_name)
            print(f"Ensured table: {table_name}")

    # Ensure 'unknown_files_index' is created if not covered by EXT_GROUPS iteration
    unknown_table = get_table_name_for_ext("unknown_ext_placeholder_for_table_name_logic") # Use logic to get the name
    if unknown_table not in created_table_names:
        create_generic_file_table(cursor, unknown_table)
        print(f"Ensured table: {unknown_table}")


    # Create all relationship tables
    create_relationship_tables(cursor)
    print("Ensured all relationship tables.")

    try:
        conn.commit()
        print("Database schema initialization complete.")
    except sqlite3.Error as e:
        print(f"ERROR: Failed to commit schema changes: {e}", file=sys.stderr)
        conn.rollback()
        raise
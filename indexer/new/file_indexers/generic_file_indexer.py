import os
import sys
import config
from core_utils import sha256_file, md5_string, generate_uuid, get_relative_path
from db import operations as db_ops
from db.schema import get_table_name_for_ext

def index_generic_file(conn,
                       full_file_path: str,
                       rel_path_for_db: str, # This is the path used for DB uniqueness and identification
                       file_ext_for_table_lookup: str, # The extension to determine the target table
                       group_name: str) -> str | None:
    """
    Indexes a generic file into the appropriate database table.

    Args:
        conn: Active SQLite database connection.
        full_file_path: The absolute path to the file on disk.
        rel_path_for_db: The relative path string to be stored in the database for this file.
                         This path should be unique within its context (e.g., relative to STR_INPUT_DIR or OUTPUT_BASE_DIR).
        file_ext_for_table_lookup: The file extension (e.g., ".txt", ".blend") used to find the target table.
        group_name: The group name for the file type (e.g., "other", "models_blend").

    Returns:
        The UUID of the indexed file, or None if indexing failed.
    """
    table_name = get_table_name_for_ext(file_ext_for_table_lookup)

    # Sanity checks - DDS and STR should use their specific indexers
    if table_name == get_table_name_for_ext(".dds"):
        print(f"    WARNING: index_generic_file called for a DDS file: {full_file_path}. Use dds_file_indexer.index_dds_file.", file=sys.stderr)
        # Delegate to dds_indexer if desired, or simply return None to enforce specific usage
        from .dds_file_indexer import index_dds_file # Local import to avoid circularity at module level
        return index_dds_file(conn, full_file_path, rel_path_for_db)

    if table_name == get_table_name_for_ext(".str"):
        print(f"    WARNING: index_generic_file called for an STR file: {full_file_path}. Use str_archive_indexer.index_str_archive.", file=sys.stderr)
        # Delegate or return None
        from .str_archive_indexer import index_str_archive # Local import
        return index_str_archive(conn, full_file_path, rel_path_for_db)


    file_hash = sha256_file(full_file_path)
    if file_hash is None:
        print(f"    Failed to get SHA256 hash for generic file: {full_file_path}", file=sys.stderr)
        return None

    path_hash_content = rel_path_for_db # Use the provided relative path for path hashing
    path_hash = md5_string(path_hash_content)
    file_uuid = generate_uuid(file_hash, path_hash)

    data_to_insert = {
        "uuid": file_uuid,
        "source_file_name": os.path.basename(full_file_path),
        "source_path": rel_path_for_db, # Storing the carefully constructed relative path
        "file_hash": file_hash,
        "path_hash": path_hash,
        "group_name": group_name
    }

    inserted_uuid = db_ops.insert_file_entry(conn, table_name, data_to_insert)

    if inserted_uuid == file_uuid : # Successfully inserted this new one
        print(f"    Indexed generic: {rel_path_for_db} (UUID: {file_uuid}) into {table_name}")
    elif inserted_uuid: # Entry already existed
        print(f"    Found existing generic: {rel_path_for_db} (UUID: {inserted_uuid}) in {table_name}")
    else: # Failed to insert and not found
        print(f"    Failed to index/find generic: {rel_path_for_db} in {table_name}", file=sys.stderr)
        return None
        
    return inserted_uuid # Return the UUID, whether new or existing
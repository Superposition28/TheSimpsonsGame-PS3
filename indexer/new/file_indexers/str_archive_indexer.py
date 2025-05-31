import os
import sys
import config
from core_utils import sha256_file, md5_string, generate_uuid
from db import operations as db_ops
from db.schema import get_table_name_for_ext

def index_str_archive(conn,
                      full_file_path: str,
                      rel_path_for_db: str) -> str | None:
    """
    Indexes a .str archive file itself (not its content).

    Args:
        conn: Active SQLite database connection.
        full_file_path: The absolute path to the .str file on disk.
        rel_path_for_db: The relative path string to be stored in the database.

    Returns:
        The UUID of the indexed .str archive, or None if indexing failed.
    """
    table_name = get_table_name_for_ext(".str") # Should resolve to 'str_index'
    group_name = config.EXT_GROUPS.get(".str", "audio_root")


    file_hash = sha256_file(full_file_path)
    if file_hash is None:
        print(f"    Failed to get SHA256 hash for .str archive: {full_file_path}", file=sys.stderr)
        return None

    path_hash_content = rel_path_for_db
    path_hash = md5_string(path_hash_content)
    file_uuid = generate_uuid(file_hash, path_hash)

    data_to_insert = {
        "uuid": file_uuid,
        "source_file_name": os.path.basename(full_file_path),
        "source_path": rel_path_for_db,
        "file_hash": file_hash,
        "path_hash": path_hash,
        "group_name": group_name # Store group for STR files too
    }

    inserted_uuid = db_ops.insert_file_entry(conn, table_name, data_to_insert)

    if inserted_uuid == file_uuid:
        print(f"    Indexed .str archive: {rel_path_for_db} (UUID: {file_uuid})")
    elif inserted_uuid: # Already exists
        print(f"    Found existing .str archive: {rel_path_for_db} (UUID: {inserted_uuid})")
    else:
        print(f"    Failed to index/find .str archive: {rel_path_for_db}", file=sys.stderr)
        return None
        
    return inserted_uuid
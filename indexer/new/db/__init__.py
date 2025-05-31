# This can be empty or used to expose parts of the submodules
from .connection import get_db_connection, close_db_connection
from .schema import initialize_database, get_table_name_for_ext
from .operations import (
    insert_file_entry,
    get_file_uuid_by_path,
    get_file_uuid_by_hash_and_path, # More specific if needed
    insert_relationship_entry
)
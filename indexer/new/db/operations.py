import sqlite3
import time
import sys
import config # Use .. for relative import from parent package
from db.schema import get_table_name_for_ext # To determine target table

def _execute_with_retry(conn: sqlite3.Connection, sql: str, params: tuple = (), commit: bool = False, fetch_one: bool = False, fetch_all: bool = False):
    """Helper to execute SQL with retry logic for locked database."""
    cursor = conn.cursor()
    for attempt in range(config.MAX_DB_RETRIES):
        try:
            cursor.execute(sql, params)
            if commit:
                conn.commit()
            
            if fetch_one:
                return cursor.fetchone()
            if fetch_all:
                return cursor.fetchall()
            return cursor # Or True if commit and no fetch
        except sqlite3.OperationalError as e:
            if "database is locked" in str(e):
                if attempt < config.MAX_DB_RETRIES - 1:
                    # print(f"DB locked. Retrying query ({sql[:30]}...) attempt {attempt+1}", file=sys.stderr)
                    time.sleep(config.RETRY_DELAY_SEC * (attempt + 1)) # Exponential backoff
                    continue
                else:
                    print(f"ERROR: DB query failed due to persistent lock: {sql[:100]}... - {e}", file=sys.stderr)
                    conn.rollback() # Rollback if a transaction was implicitly started by DML
                    raise
            else: # Other operational errors
                print(f"ERROR: Operational error executing SQL: {sql[:100]}... - {e}", file=sys.stderr)
                conn.rollback()
                raise
        except sqlite3.IntegrityError as e:
             # For INSERTs, this is often expected (e.g., UNIQUE constraint violation)
             # Let the calling function handle this by checking return values or catching it.
            conn.rollback()
            raise # Re-raise to be handled by caller
        except Exception as e:
            print(f"ERROR: Unexpected error executing SQL: {sql[:100]}... - {e}", file=sys.stderr)
            conn.rollback()
            raise
    return None # Should be unreachable if retries fail and raise

def get_file_uuid_by_path(conn: sqlite3.Connection, table_name: str, source_path: str) -> str | None:
    """Fetches a file's UUID from a given table by its source_path."""
    sql = f"SELECT uuid FROM {table_name} WHERE source_path = ?"
    try:
        row = _execute_with_retry(conn, sql, (source_path,), fetch_one=True)
        return row['uuid'] if row else None
    except sqlite3.Error as e: # Catch errors from _execute_with_retry if they weren't re-raised as critical
        print(f"INFO: Could not fetch UUID by path for {source_path} in {table_name} (may not exist): {e}", file=sys.stderr)
        return None

def get_file_uuid_by_hash_and_path(conn: sqlite3.Connection, table_name: str, file_hash: str, path_hash: str) -> str | None:
    """Fetches a file's UUID by its file_hash and path_hash (more specific than just path)."""
    # This assumes UUID is constructed from these or they are otherwise queryable for this purpose.
    # If UUID is the primary way, this might not be needed or UUID generation should be consistent.
    # For now, let's assume we might query by file_hash and path_hash if they are indexed.
    sql = f"SELECT uuid FROM {table_name} WHERE file_hash = ? AND path_hash = ?"
    try:
        row = _execute_with_retry(conn, sql, (file_hash, path_hash), fetch_one=True)
        return row['uuid'] if row else None
    except sqlite3.Error:
        return None


def insert_file_entry(conn: sqlite3.Connection, table_name: str, data: dict) -> str | None:
    """
    Inserts a file entry into the specified table.
    Handles IntegrityError if the entry (based on source_path or uuid) already exists.
    Returns the UUID of the inserted or existing record.
    'data' dict should contain keys matching table columns (e.g., uuid, source_file_name, source_path, etc.).
    """
    # Ensure required fields are present, especially for fetching existing
    if 'source_path' not in data or 'uuid' not in data:
        print(f"ERROR: 'source_path' and 'uuid' are required in data for insert_file_entry into {table_name}.", file=sys.stderr)
        return None

    cols = ', '.join(data.keys())
    placeholders = ', '.join(['?'] * len(data))
    sql = f"INSERT INTO {table_name} ({cols}) VALUES ({placeholders})"

    try:
        _execute_with_retry(conn, sql, tuple(data.values()), commit=True)
        # print(f"    Indexed: {data.get('source_path', data.get('uuid'))} into {table_name}")
        return data['uuid']
    except sqlite3.IntegrityError:
        # Entry likely already exists. Try to fetch its UUID.
        # Prefer fetching by source_path as it's usually the UNIQUE constraint violated first for files.
        existing_uuid = get_file_uuid_by_path(conn, table_name, data['source_path'])
        if existing_uuid:
            # print(f"    Info: File already indexed (by path): {data['source_path']} in {table_name}. UUID: {existing_uuid}")
            return existing_uuid
        
        # If not found by path, but UUID was the conflict (less common if path is also unique)
        # This path implies a hash collision leading to same UUID for different paths,
        # OR, data['source_path'] was different but data['uuid'] was the same.
        # The schema usually has UNIQUE on source_path AND UNIQUE on uuid.
        try:
            cursor = conn.cursor()
            cursor.execute(f"SELECT source_path FROM {table_name} WHERE uuid = ?", (data['uuid'],))
            row = cursor.fetchone()
            if row:
                # print(f"    Info: File UUID {data['uuid']} already exists in {table_name} (path: {row['source_path']}).")
                return data['uuid'] # Return the conflicting UUID
        except sqlite3.Error:
            pass # Fall through if this secondary check fails

        print(f"WARNING: IntegrityError for {data.get('source_path')} in {table_name}, but could not retrieve existing UUID.", file=sys.stderr)
        return None # Indicate an issue
    except sqlite3.Error as e: # Catch other errors from _execute_with_retry
        print(f"ERROR: Failed to insert file entry into {table_name} for {data.get('source_path')}: {e}", file=sys.stderr)
        return None


def insert_relationship_entry(conn: sqlite3.Connection, relationship_table_name: str, data: dict) -> bool:
    """
    Inserts an entry into a relationship table.
    Handles IntegrityError if the relationship already exists.
    Returns True if inserted or already existed, False on other errors.
    """
    cols = ', '.join(data.keys())
    placeholders = ', '.join(['?'] * len(data))
    sql = f"INSERT INTO {relationship_table_name} ({cols}) VALUES ({placeholders})"

    try:
        _execute_with_retry(conn, sql, tuple(data.values()), commit=True)
        # print(f"    Created relationship in {relationship_table_name}: {data}")
        return True
    except sqlite3.IntegrityError:
        # print(f"    Info: Relationship already exists in {relationship_table_name} for {data}.")
        return True # Relationship already exists, considered success for this function's purpose
    except sqlite3.Error as e: # Catch other errors
        print(f"ERROR: Failed to insert relationship into {relationship_table_name} for {data}: {e}", file=sys.stderr)
        return False
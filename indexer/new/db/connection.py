import sqlite3
import sys
import config # Use .. to go up one level to the main package directory

_connection = None

def get_db_connection(db_path: str = config.DB_PATH, max_retries: int = config.MAX_DB_RETRIES, retry_delay: int = config.RETRY_DELAY_SEC):
    """Establishes and returns a SQLite database connection."""
    global _connection
    if _connection is None:
        for attempt in range(max_retries):
            try:
                _connection = sqlite3.connect(db_path, timeout=10) # Increased timeout
                _connection.execute("PRAGMA foreign_keys = ON;")
                _connection.execute("PRAGMA journal_mode = WAL;") # Write-Ahead Logging for better concurrency
                _connection.row_factory = sqlite3.Row # Access columns by name
                print(f"Database connection established to: {db_path}")
                return _connection
            except sqlite3.OperationalError as e:
                if "database is locked" in str(e):
                    if attempt < max_retries - 1:
                        print(f"Database locked. Retrying ({attempt + 1}/{max_retries})...", file=sys.stderr)
                        time.sleep(retry_delay)
                    else:
                        print(f"FATAL: Could not connect to database {db_path} after {max_retries} retries: {e}", file=sys.stderr)
                        raise
                else:
                    print(f"FATAL: sqlite3.OperationalError connecting to {db_path}: {e}", file=sys.stderr)
                    raise
            except Exception as e:
                print(f"FATAL: Unexpected error connecting to database {db_path}: {e}", file=sys.stderr)
                raise
    return _connection


def close_db_connection():
    """Closes the existing SQLite database connection."""
    global _connection
    if _connection:
        _connection.close()
        _connection = None
        print("Database connection closed.")
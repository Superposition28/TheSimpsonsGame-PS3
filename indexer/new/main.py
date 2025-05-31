import os
import sys
import time

import config
from core_utils import ensure_dir_exists
from db import connection as db_conn, schema as db_schema
from processing_orchestrator import run_processing_passes


def initial_checks():
    """Performs initial checks for directories and tools."""
    print("Performing initial checks...")
    valid = True
    if not os.path.isdir(config.STR_INPUT_DIR):
        print(f"ERROR: Source input directory STR_INPUT_DIR does not exist: {config.STR_INPUT_DIR}", file=sys.stderr)
        valid = False

    ensure_dir_exists(config.OUTPUT_BASE_DIR) # Create output base if not exists
    ensure_dir_exists(os.path.dirname(config.DB_PATH)) # Create DB directory if not exists

    if not os.path.isfile(config.QUICKBMS_EXE) or not os.access(config.QUICKBMS_EXE, os.X_OK):
        print(f"ERROR: QuickBMS executable not found or not executable: {config.QUICKBMS_EXE}", file=sys.stderr)
        valid = False
    if not os.path.isfile(config.BMS_SCRIPT):
        print(f"ERROR: BMS script not found: {config.BMS_SCRIPT}", file=sys.stderr)
        valid = False

    if not valid:
        print("Initial checks failed. Please correct the paths in config.py and ensure tools are available.", file=sys.stderr)
        sys.exit(1)
    print("Initial checks passed.")


def main():
    start_time = time.time()
    print("Starting Simpsons Game File Processor...")

    initial_checks()

    conn = None
    try:
        # Establish and initialize database
        conn = db_conn.get_db_connection()
        if not conn: # Should have raised in get_db_connection if failed
            print("FATAL: Could not establish database connection.", file=sys.stderr)
            sys.exit(1)

        db_schema.initialize_database(conn)

        # Run the main processing logic
        run_processing_passes(conn)

    except sqlite3.Error as e:
        print(f"FATAL DATABASE ERROR: {e}", file=sys.stderr)
        # Potentially log detailed error
    except Exception as e:
        print(f"AN UNEXPECTED FATAL ERROR OCCURRED: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
    finally:
        if conn:
            db_conn.close_db_connection()

    end_time = time.time()
    print(f"\n✅ Simpsons Game File Processor finished in {end_time - start_time:.2f} seconds.")

if __name__ == "__main__":
    main()

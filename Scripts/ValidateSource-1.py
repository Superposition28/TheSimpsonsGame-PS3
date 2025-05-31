import os
import sqlite3
import argparse

import os
import sys
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..', '..', 'Utils')))
from printer import printerprint as print
from printer import Colours, print_error, print_verbose, print_debug, printc


# --- Configuration ---
USRDIR_DIRS = [
    "Assets_1_Audio_Streams", "Assets_1_Video_Movies", "Assets_2_Characters_Simpsons",
    "Assets_2_Frontend", "Map_3-00_GameHub", "Map_3-00_SprHub", "Map_3-01_LandOfChocolate",
    "Map_3-02_BartmanBegins", "Map_3-03_HungryHungryHomer", "Map_3-04_TreeHugger",
    "Map_3-05_MobRules", "Map_3-06_EnterTheCheatrix", "Map_3-07_DayOfTheDolphin",
    "Map_3-08_TheColossalDonut", "Map_3-09_Invasion", "Map_3-10_BargainBin",
    "Map_3-11_NeverQuest", "Map_3-12_GrandTheftScratchy", "Map_3-13_MedalOfHomer",
    "Map_3-14_BigSuperHappy", "Map_3-15_Rhymes", "Map_3-16_MeetThyPlayer",
]

def check_required_directories(base_folder: str, required_dirs: list) -> bool:
    """
    Checks if all required subdirectories exist within the base_folder.
    This check is non-fatal; it reports missing directories but returns
    whether all were found.

    Args:
        base_folder (str): The parent folder to check within.
        required_dirs (list): A list of subdirectory names that must exist.

    Returns:
        bool: True if all required directories are found, False otherwise.
    """
    print(prefix="Validate", msg=f"--- Checking for Required Subdirectories in: {base_folder} ---")
    all_found = True
    missing_dirs = []
    found_dirs_count = 0

    for dir_name in required_dirs:
        expected_dir_path = os.path.join(base_folder, dir_name)
        if not os.path.isdir(expected_dir_path):
            missing_dirs.append(dir_name)
            all_found = False
        else:
            found_dirs_count += 1

    if not all_found:
        print(colour="yellow", prefix="Validate", msg="WARNING: The following required subdirectories were NOT found:")
        for m_dir in missing_dirs:
            print(colour="yellow", prefix="Validate", msg=f"  - {m_dir}")
        print(colour="yellow", prefix="Validate", msg=f"Found {found_dirs_count}/{len(required_dirs)} required subdirectories.")
        print(colour="yellow", prefix="Validate", msg="Continuing with database file checks, but results might be affected by missing base directories.")
    else:
        print(colour=Colours.GREEN, prefix="Validate", msg=f"✅ All {len(required_dirs)} required subdirectories found.")
    print(prefix="Validate", msg="-" * 20)
    return all_found

def check_file_existence(db_path: str, base_check_folder: str):
    """
    Connects to the SQLite database, reads specified index tables,
    and checks if the files listed exist in the base_check_folder.
    It also performs a non-fatal check for required subdirectories.

    Args:
        db_path (str): Path to the SQLite database file.
        base_check_folder (str): The base folder path to check for files.
    """
    if not os.path.isfile(db_path):
        print(prefix="Validate", msg=f"ERROR: Database file not found at {db_path}")
        return

    if not os.path.isdir(base_check_folder):
        print(prefix="Validate", msg=f"ERROR: Check folder not found or is not a directory: {base_check_folder}")
        return

    # --- Preliminary Check for Required Directories (Non-Fatal) ---
    # Store the result for potential context later, but don't stop.
    required_dirs_all_present = check_required_directories(base_check_folder, USRDIR_DIRS)

    conn = None
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        tables_to_check = {
            "str_index": "source_path",
            "video_index": "source_path",
            "mus_index": "source_path",
            "snu_index": "source_path"
        }

        overall_db_files_all_found = True
        total_db_files_checked = 0
        total_db_files_missing = 0

        print(prefix="Validate", msg=f"\n--- Starting Database File Existence Check ---")
        print(prefix="Validate", msg=f"Database: {db_path}")
        print(prefix="Validate", msg=f"Checking against base folder: {base_check_folder}\n")

        for table_name, path_column_name in tables_to_check.items():
            print(prefix="Validate", msg=f"Checking table: {table_name}...")
            try:
                cursor.execute(f"SELECT {path_column_name} FROM {table_name}")
                rows = cursor.fetchall()
            except sqlite3.OperationalError as e:
                print(prefix="Validate", msg=f"  WARNING: Could not query table {table_name}. Error: {e}")
                print(prefix="Validate", msg=f"  Skipping this table.")
                print(prefix="Validate", msg="-" * 20)
                continue

            if not rows:
                print(colour="red", prefix="Validate", msg=f"  No entries found in {table_name}.")
                print(prefix="Validate", msg="-" * 20)
                continue

            table_missing_count = 0
            table_checked_count = 0
            for row_index, row in enumerate(rows):
                relative_path = row[0]
                if relative_path is None:
                    print(prefix="Validate", msg=f"  WARNING: Row {row_index + 1} in {table_name} has a NULL {path_column_name}. Skipping.")
                    continue

                table_checked_count += 1
                normalized_relative_path = os.path.normpath(relative_path)
                full_expected_path = os.path.join(base_check_folder, normalized_relative_path)
                
                if not os.path.isfile(full_expected_path):
                    #print(prefix="Validate", msg=f"  MISSING (DB): {full_expected_path} (from {table_name})")
                    overall_db_files_all_found = False
                    total_db_files_missing += 1
                    table_missing_count +=1
                # else:
                #     print(prefix="Validate", msg=f"  FOUND (DB): {full_expected_path}") # Optional: for verbose output
            
            total_db_files_checked += table_checked_count

            if table_checked_count > 0: # Only print summary if files were expected
                if table_missing_count == 0:
                    print(prefix="Validate", msg=f"  All {table_checked_count} files from {table_name} (as per DB) found.")
                else:
                    print(prefix="Validate", msg=f"  {table_missing_count} file(s) MISSING from {table_name} (out of {table_checked_count} expected in this table).")
            else:
                print(prefix="Validate", msg=f"  No valid file paths to check in {table_name}.")
            print(prefix="Validate", msg="-" * 20)

        print(prefix="Validate", msg="\n--- Overall Summary ---")
        if not required_dirs_all_present:
            print(prefix="Validate", msg="NOTE: Some required base subdirectories were missing. This might affect the accuracy of the database file checks.")
        
        if total_db_files_checked == 0:
            print(prefix="Validate", msg="No files were checked from the database. Ensure tables exist, contain data, and paths are valid.")
        elif overall_db_files_all_found:
            print(prefix="Validate", msg=f"✅ All {total_db_files_checked} files checked from the database were found in {base_check_folder}.")
        else:
            print(prefix="Validate", msg=f"❌ {total_db_files_missing} out of {total_db_files_checked} files checked from the database are MISSING.")

    except sqlite3.Error as e:
        print(prefix="Validate", msg=f"SQLite error: {e}")
    except Exception as e:
        print(prefix="Validate", msg=f"An unexpected error occurred: {e}")
    finally:
        if conn:
            conn.close()

def main():
    parser = argparse.ArgumentParser(
        description="Checks for required subdirectories and then if file paths from SQLite database tables exist in a given folder."
    )
    parser.add_argument(
        "db_path",
        type=str,
        help="Path to the SQLite database file (e.g., RemakeRegistry/Games/TheSimpsonsGame/str_index_refactored_with_dds.db)"
    )
    parser.add_argument(
        "check_folder",
        type=str,
        help="The base folder path to check for required subdirectories and the existence of files listed in the database."
    )

    args = parser.parse_args()

    abs_db_path = os.path.abspath(args.db_path)
    abs_check_folder = os.path.abspath(args.check_folder)

    check_file_existence(abs_db_path, abs_check_folder)

if __name__ == "__main__":
    main()
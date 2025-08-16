"""
This module initializes the configuration and validates the source directory for the RemakeEngine.
"""
import builtins
import json
import shutil # Import shutil for file operations

import os
import sys
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..', '..', 'Utils')))
from printer import print, Colours, print_error, print_verbose, print_debug, printc


# --- Constants for Directory Lists ---
USRDIR_DIRS = [
    "Assets_1_Audio_Streams", "Assets_1_Video_Movies", "Assets_2_Characters_Simpsons",
    "Assets_2_Frontend", "Map_3-00_GameHub", "Map_3-00_SprHub", "Map_3-01_LandOfChocolate",
    "Map_3-02_BartmanBegins", "Map_3-03_HungryHungryHomer", "Map_3-04_TreeHugger",
    "Map_3-05_MobRules", "Map_3-06_EnterTheCheatrix", "Map_3-07_DayOfTheDolphin",
    "Map_3-08_TheColossalDonut", "Map_3-09_Invasion", "Map_3-10_BargainBin",
    "Map_3-11_NeverQuest", "Map_3-12_GrandTheftScratchy", "Map_3-13_MedalOfHomer",
    "Map_3-14_BigSuperHappy", "Map_3-15_Rhymes", "Map_3-16_MeetThyPlayer",
]
USRDIR_DIRS_ORIGINAL = [
    "audiostreams", "bargainbin", "bigsuperhappy", "brt", "cheater", "colossaldonut",
    "dayofthedolphins", "dayspringfieldstoodstill", "eighty_bites", "frontend", "gamehub",
    "grand_theft_scratchy", "loc", "medal_of_homer", "meetthyplayer", "mob_rules",
    "movies", "neverquest", "rhymes", "simpsons_chars", "spr_hub", "text", "tree_hugger",
]

# --- Status Codes for Clarity ---
CREATED = "CREATED"
EXISTS_VALID = "EXISTS_VALID"
EXISTS_MISSING_SOURCEPATH = "EXISTS_MISSING_SOURCEPATH"
EXISTS_INVALID_SUBDIRS = "EXISTS_INVALID_SUBDIRS"
ERROR_CREATE = "ERROR_CREATE"
ERROR_READ = "ERROR_READ"
ERROR_CONFIG_UPDATE = "ERROR_CONFIG_UPDATE"
ERROR_INVALID_SOURCEPATH_DIR = "ERROR_INVALID_SOURCEPATH_DIR"
USER_PROVIDED_PATH_INVALID = "USER_PROVIDED_PATH_INVALID"
ERROR_FILE_OPERATION = "ERROR_FILE_OPERATION" # New status for copy/move errors

# --- Helper Function: check_dirs_exist (Unchanged) ---
def check_dirs_exist(base_path, required_dirs, list_name=""):
    # (Keep the implementation of check_dirs_exist as it was)
    if not os.path.isdir(base_path):
        print(Colours.RED, f"  Error: The base path '{base_path}' provided for checking subdirs is not a valid directory.")
        return False
    missing = []
    print(Colours.CYAN, f"  Checking against list '{list_name}':") if list_name else print(Colours.CYAN, "  Checking against list:")
    for dir_name in required_dirs:
        full_path = os.path.join(base_path, dir_name)
        if not os.path.isdir(full_path):
            missing.append(dir_name)
    if not missing:
        print(Colours.DARK_GREEN, f"    Success: All {len(required_dirs)} directories from this list found in '{base_path}'.")
        return True
    else:
        # print(Colours.YELLOW, f"    Info: Missing {len(missing)} subdirectories in '{base_path}': {', '.join(missing)}")
        return False

# --- Modified check_or_create_config Function ---
def check_or_create_config(filename):
    """
    Checks/creates JSON config, validates SourcePath (prompting if needed).
    Asks user how to handle the validated source path (copy, move, use directly).
    Performs file operations if requested.
    Validates subdirs in the *effective* source path (original, copied, or moved location).
    Updates config for USRDIR if found within the effective path.

    Args:
        filename (str): The name of the configuration file (e.g., "project.json").

    Returns:
        tuple: (status_code, path_value or None)
                status_code (str): Outcome status.
                path_value (str or None): Effective path used/validated, or None on errors.
    """
    config_file_path = os.path.abspath(filename)
    project_base_dir = os.path.dirname(config_file_path)
    local_data_path = os.path.join(project_base_dir, "Source\\GameFiles\\SimpGamePS3")
	# path to this file
    this_file_path = os.path.abspath(__file__)
    # path to module parent dir of this files dir
    path_to_module = os.path.dirname(os.path.dirname(this_file_path))

    default_data = {
        "RemakeEngine": {
            "Config": { "project_path": project_base_dir, "module_path": path_to_module },
            "Directories": { "SourcePath": "" },
            "Tools": {}
        }
    }

    # --- Check 1: File Existence ---
    if not os.path.exists(config_file_path):
        print(Colours.YELLOW, f"File '{config_file_path}' not found. Creating it...")
        try:
            with open(config_file_path, 'w', encoding='utf-8') as f:
                json.dump(default_data, f, indent=4, ensure_ascii=False)
            print(Colours.GREEN, f"File '{config_file_path}' created successfully.")
            #print(Colours.RED, "  Action Required: The 'SourcePath' is empty. Run again to provide it.")
            return CREATED, None
        except Exception as e:
            print(Colours.RED, f"Error creating file '{config_file_path}': {e}")
            return ERROR_CREATE, None

    # --- File Exists: Load and Validate ---
    else:
        print(Colours.BLUE, f"File '{config_file_path}' exists. Verifying content...")
        config_data = None
        try:
            with open(config_file_path, 'r', encoding='utf-8') as f:
                config_data = json.load(f)
        except Exception as e:
            print(Colours.RED, f"Error reading or parsing '{config_file_path}': {e}")
            return ERROR_READ, None

        # --- Check 2: SourcePath key existence and validity ---
        path_from_config = None # This will hold the path confirmed to be a directory
        source_path_valid_in_file = False
        try:
            path_from_config = config_data.get("RemakeEngine", {}).get("Directories", {}).get("SourcePath")
            if path_from_config and isinstance(path_from_config, str) and path_from_config.strip():
                if os.path.isdir(path_from_config):
                    effective_source_path = path_from_config

                    potential_usrdir_path = os.path.join(effective_source_path, "USRDIR")
                    path_to_validate = effective_source_path # Start with the effective path

                    if os.path.isdir(potential_usrdir_path):
                        print(Colours.BLUE, f"  Info: Found 'USRDIR' subdirectory within effective path.")
                        print(Colours.BLUE, f"  Info: Will check for required subdirectories inside: '{potential_usrdir_path}'")
                        path_to_validate = potential_usrdir_path # Update path for subdir check

                        print(Colours.BLUE, f"  Info: Using '{path_to_validate}' for subdirectory validation due to found USRDIR.")

                    print(Colours.CYAN, f"  Found SourcePath in config: '{path_from_config}'")
                    print(Colours.CYAN, f"  Validating subdirectories in '{path_to_validate}'...")
                    found_original = check_dirs_exist(path_to_validate, USRDIR_DIRS_ORIGINAL, "USRDIR_DIRS_ORIGINAL")

                    found_usrdir = False
                    if not found_original:
                        print(Colours.YELLOW, f"  Info: Did not find all directories from the 'ORIGINAL' list. Checking second list ('USRDIR_DIRS')...")
                        found_usrdir = check_dirs_exist(path_to_validate, USRDIR_DIRS, "USRDIR_DIRS")

                    # Final validation result
                    if found_usrdir or found_original:
                        source_path_valid_in_file = True
                    else:
                        print(Colours.RED, f"  Error: Validation failed. Could not find all required subdirectories from *either* list within '{path_to_validate}'.")

                else:
                    print(Colours.YELLOW, f"  Warning: Configured SourcePath '{path_from_config}' is not currently a valid directory.")
        except AttributeError:
            pass

        # --- Interactive Prompt if SourcePath is Invalid/Missing ---
        if not source_path_valid_in_file:
            print(Colours.YELLOW, f"Warning: 'RemakeEngine.Directories.SourcePath' in '{filename}' is missing, empty, or invalid.")
            while True:
                print(Colours.CYAN, "Please enter the full path to the source directory:")
                user_input_path = input("> ").strip()
                if not user_input_path:
                    print(Colours.YELLOW, "Path cannot be empty. Please try again.")
                    continue
                if os.path.isdir(user_input_path):
                    print(Colours.DARK_GREEN, f"  Path '{user_input_path}' is a valid directory.")
                    path_from_config = user_input_path
                    print(Colours.YELLOW, f"  Attempting to update '{filename}' with user input path...")
                    try:
                        if "RemakeEngine" not in config_data: config_data["RemakeEngine"] = {}
                        if "Directories" not in config_data["RemakeEngine"]: config_data["RemakeEngine"]["Directories"] = {}
                        config_data["RemakeEngine"]["Directories"]["MainSourcePath"] = path_from_config
                        with open(config_file_path, 'w', encoding='utf-8') as f:
                            json.dump(config_data, f, indent=4, ensure_ascii=False)
                        print(Colours.GREEN, f"  Success: Config file '{filename}' updated.")
                    except Exception as e:
                        print(Colours.RED, f"  Error updating config file '{filename}': {e}")
                        print(Colours.YELLOW, "  Warning: Proceeding with the provided path, but config file was not saved.")
                    break # Exit loop after getting valid path
                else:
                    print(Colours.RED, f"  Error: The path '{user_input_path}' is not a valid directory. Please try again.")
            # Check if loop somehow exited without valid path (shouldn't happen)
            if not path_from_config:
                print(Colours.RED, "Could not obtain a valid SourcePath. Exiting.")
                return USER_PROVIDED_PATH_INVALID, None

        # --- Check 3: User choice for handling the source path ---
        print(Colours.MAGENTA, "\n--- Source Path Handling ---")
        print(Colours.CYAN, f"Validated source path: '{path_from_config}'")
        print(Colours.CYAN, f"Local project data path would be: '{local_data_path}'")

        effective_source_path = local_data_path

        if not os.path.exists(local_data_path):
            print(Colours.YELLOW, "\nChoose how to use the source files:")
            print(Colours.CYAN, "  1) " + Colours.GREEN + "Copy files" + Colours.YELLOW + f" from '{os.path.basename(path_from_config)}' to local '{os.path.basename(local_data_path)}' (Recommended, Safe)")
            print(Colours.CYAN, "  2) " + Colours.RED + "Move files" + Colours.YELLOW + f" from '{os.path.basename(path_from_config)}' to local '{os.path.basename(local_data_path)}' (Warning: Deletes original Files at Source location)")
            print(Colours.CYAN, "  3) " + Colours.CYAN + "Use original path" + Colours.YELLOW + f" '{os.path.basename(path_from_config)}' directly (Warning: This Tool might modify/corrupt original files)")

            while True:
                choice = input("Enter your choice (1, 2, or 3): ").strip()

                # --- Option 1: Copy with Progress ---
                if choice == '1':
                    # --- Start: Enhanced copy logic with progress ---
                    print(Colours.GREEN, f"\nPreparing to copy files from '{path_from_config}' to '{local_data_path}'...")

                    # 1. Pre-calculate total number of files for progress reporting
                    try:
                        total_files = 0
                        print(Colours.CYAN, "Calculating total number of files...")
                        for _, _, files in os.walk(path_from_config):
                            total_files += len(files)
                        print(Colours.CYAN, f"Found {total_files} files to copy.")
                        if total_files == 0:
                            print(Colours.GREEN, "Source directory is empty or contains no files. Nothing to copy.")
                            effective_source_path = local_data_path # Set path even if empty
                            # Ensure destination exists if source was empty but valid
                            os.makedirs(local_data_path, exist_ok=True)
                            break # Exit the loop successfully

                    except OSError as e:
                        print(Colours.RED, f"Error accessing source path '{path_from_config}' to count files: {e}")
                        print(Colours.RED, "Cannot proceed with file operations.")
                        # Consider if this should be a critical error or allow retrying
                        # return ERROR_FILE_OPERATION, None # Option: Critical error
                        continue # Option: Go back to the start of the while loop to re-select choice

                    # --- Variables for progress tracking ---
                    copied_files_count = 0
                    LINE_CLEAR = '\r' + ' ' * 80 + '\r' # Predefine line clearing string

                    # 2. Define the custom copy function with progress update
                    def copy_with_progress(src, dst, *, follow_symlinks=True):
                        nonlocal copied_files_count # Use nonlocal to modify the outer scope variable
                        # Perform the actual copy (use copy2 to preserve metadata)
                        shutil.copy2(src, dst, follow_symlinks=follow_symlinks)
                        copied_files_count += 1
                        # Display progress - use carriage return '\r' to overwrite the line
                        progress = (copied_files_count / total_files) * 100
                        # Use sys.stdout.write for better control with \r
                        # Pad the output string to ensure it overwrites previous longer lines
                        progress_text = f"\rCopying... {copied_files_count}/{total_files} files ({progress:.1f}%) copied. ".ljust(80)
                        sys.stdout.write(progress_text)
                        sys.stdout.flush() # Ensure the output is displayed immediately

                    # --- Perform the copy operation ---
                    # print(Colours.GREEN + f"Attempting to copy files from '{path_from_config}' to '{local_data_path}'...") # Already announced preparation
                    try:
                        # 3. Use copytree with the custom copy_function
                        shutil.copytree(path_from_config,
                                        local_data_path,
                                        dirs_exist_ok=True,  # Requires Python 3.8+
                                        copy_function=copy_with_progress) # Pass the custom function

                        # Ensure the final message overwrites the progress line completely
                        sys.stdout.write(LINE_CLEAR) # Clear the line
                        sys.stdout.flush()
                        print(Colours.GREEN, "Copy successful.")
                        effective_source_path = local_data_path
                        break # Exit the loop on success

                    except (shutil.Error, OSError, Exception) as e:
                        # Ensure the final message overwrites the progress line completely
                        sys.stdout.write(LINE_CLEAR) # Clear the line
                        sys.stdout.flush()
                        print(Colours.RED, f"\nError during copy operation: {e}") # Add newline for clarity
                        print(Colours.RED, "Cannot proceed with file operations.")
                        return ERROR_FILE_OPERATION, None # Critical error, stop
                    # --- End: Enhanced copy logic ---

                elif choice == '2':
                    print(Colours.RED, f"\nAttempting to move files from '{path_from_config}' to '{local_data_path}'...")
                    if os.path.exists(local_data_path):
                        print(Colours.RED, f"Error: Destination path '{local_data_path}' already exists. Cannot move.")
                        print(Colours.YELLOW, "Please remove the existing directory or choose 'Copy' (option 1) or 'Use original' (option 3).")
                        # Loop again to ask for choice
                        continue
                        # Alternative: Ask user to confirm overwrite (more complex)
                        # confirmed = input(f"Warning: '{local_data_path}' exists. Overwrite? (yes/no): ").lower()
                        # if confirmed == 'yes':
                        #     try: shutil.rmtree(local_data_path) except Exception as e: print(Colours.CYAN, f"Error removing existing dir: {e}"); return ERROR_FILE_OPERATION, None
                        # else: continue # Go back to choice prompt
                    try:
                        shutil.move(path_from_config, local_data_path)
                        print(Colours.GREEN, "Move successful.")
                        effective_source_path = local_data_path
                        break
                    except (shutil.Error, OSError, Exception) as e:
                        print(Colours.RED, f"Error during move operation: {e}")
                        print(Colours.RED, "Cannot proceed with file operations.")
                        # Note: If move fails partially, source might be corrupted.
                        return ERROR_FILE_OPERATION, None # Critical error, stop

                elif choice == '3':
                    print(Colours.CYAN, f"\nUsing original path '{path_from_config}' directly.")
                    print(Colours.YELLOW, "Warning: Ensure you have a backup, as subsequent operations might modify these files.")
                    effective_source_path = path_from_config
                    break

                else:
                    print(Colours.YELLOW, "Invalid choice. Please enter 1, 2, or 3.")

        print(Colours.YELLOW, f"  Attempting to update '{filename}' with local Source Path...")
        try:
            if "RemakeEngine" not in config_data:
                config_data["RemakeEngine"] = {}
            if "Directories" not in config_data["RemakeEngine"]:
                config_data["RemakeEngine"]["Directories"] = {}
            config_data["RemakeEngine"]["Directories"]["SourcePath"] = effective_source_path
            with open(config_file_path, 'w', encoding='utf-8') as f:
                json.dump(config_data, f, indent=4, ensure_ascii=False)
            print(Colours.GREEN, f"  Success: Config file '{filename}' updated.")
        except Exception as e:
            print(Colours.RED, f"  Error updating config file '{filename}': {e}")
            print(Colours.YELLOW, "  Warning: Proceeding with the provided path, but config file was not saved.")

        # --- Proceed with the 'effective_source_path' ---
        print(Colours.BLUE, f"\nUsing effective source path for validation: '{effective_source_path}'")

        # --- Check 4: USRDIR subdirectory check & potential config update ---
        # This logic now runs on the *effective* path (original, copied, or moved)
        potential_usrdir_path = os.path.join(effective_source_path, "USRDIR")
        path_to_validate = effective_source_path # Start with the effective path
        config_updated_for_usrdir = False

        if os.path.isdir(potential_usrdir_path):
            print(Colours.BLUE, f"  Info: Found 'USRDIR' subdirectory within effective path.")
            print(Colours.BLUE, f"  Info: Will check for required subdirectories inside: '{potential_usrdir_path}'")
            path_to_validate = potential_usrdir_path # Update path for subdir check

            print(Colours.BLUE, f"  Info: Using '{path_to_validate}' for subdirectory validation due to found USRDIR.")

        else:
            print(Colours.BLUE, f"  Info: 'USRDIR' subdirectory not found within effective path '{effective_source_path}'.")
            print(Colours.BLUE, f"  Info: Will check for required subdirectories directly inside: '{effective_source_path}'")
            # path_to_validate remains effective_source_path

        # --- Check 5: Subdirectory validation using the 'path_to_validate' ---
        print(Colours.CYAN, f"  Starting subdirectory validation using path: '{path_to_validate}'...")
        found_original = check_dirs_exist(path_to_validate, USRDIR_DIRS_ORIGINAL, "USRDIR_DIRS_ORIGINAL")

        found_usrdir = False
        if not found_original:
            print(Colours.BLUE, f"  Info: Did not find all directories from the 'ORIGINAL' list. Checking second list ('USRDIR_DIRS')...")
            found_usrdir = check_dirs_exist(path_to_validate, USRDIR_DIRS, "USRDIR_DIRS")

        # Final validation result
        if found_usrdir or found_original:
            list_name = "USRDIR_DIRS" if found_usrdir else "USRDIR_DIRS_ORIGINAL"
            print(Colours.GREEN, f"\nSuccess: Validation passed. All required subdirectories from list '{list_name}' found within '{path_to_validate}'.")

            print(Colours.YELLOW, f"  Attempting to update '{filename}' with Valid Source Path...")
            try:
                if "RemakeEngine" not in config_data:
                    config_data["RemakeEngine"] = {}
                if "Directories" not in config_data["RemakeEngine"]:
                    config_data["RemakeEngine"]["Directories"] = {}
                config_data["RemakeEngine"]["Directories"]["SourcePath"] = path_to_validate
                with open(config_file_path, 'w', encoding='utf-8') as f:
                    json.dump(config_data, f, indent=4, ensure_ascii=False)
                print(Colours.GREEN, f"  Success: Config file '{filename}' updated.")
            except Exception as e:
                print(Colours.RED, f"  Error updating config file '{filename}': {e}")
                print(Colours.YELLOW, "  Warning: Proceeding with the provided path, but config file was not saved.")

            return EXISTS_VALID, path_to_validate
        else:
            print(Colours.RED, f"\nError: Validation failed. Could not find all required subdirectories from *either* list within '{path_to_validate}'.")
            print(Colours.GRAY, f"  Checked within path: '{path_to_validate}'.")
            if path_to_validate != effective_source_path:
                print(Colours.GRAY, f"  (This path was checked because 'USRDIR' was found inside '{effective_source_path}')")
            elif effective_source_path != path_from_config:
                print(Colours.GRAY, f"  (This path resulted from a '{'Copy' if choice == '1' else 'Move'} operation' based on original '{path_from_config}')")

            print(Colours.GRAY, f"  Expected all subdirs from list 'USRDIR_DIRS' OR all from list 'USRDIR_DIRS_ORIGINAL'.")
            print(Colours.RED, f"  Action Required: Verify the contents of '{path_to_validate}'.")
            # Return the path that failed validation
            return EXISTS_INVALID_SUBDIRS, path_to_validate


# --- Main Execution Block (Updated with Colours) ---
def main():
    config_file_name = "project.json"

    # Call the function to check/create/validate/prompt/operate
    status, path_value = check_or_create_config(config_file_name)

    print(Colours.BLUE, f"\n--- Final Status: {status} ---")
    if status == CREATED:
        print(Colours.GREEN, "Configuration file was newly created.")
        print(Colours.RED, "Action Required: Running the script again, provide the 'SourcePath' and choose handling.")
        main()
    elif status == EXISTS_VALID:
        print(Colours.GREEN, f"Configuration is valid. Effective source path '{path_value}' contains required subdirectories.")
    elif status == EXISTS_MISSING_SOURCEPATH: # Less likely now
        print(Colours.YELLOW, "Configuration file exists but is missing a valid 'SourcePath'.")
        print(Colours.RED, "Action Required: Run again to provide the path when prompted.")
    elif status == EXISTS_INVALID_SUBDIRS:
        print(Colours.RED, f"Validation failed: Required subdirectories are missing within the path '{path_value}'.")
        print(Colours.RED, "Action Required: Check the contents of this directory.")
    elif status == ERROR_INVALID_SOURCEPATH_DIR:
        print(Colours.RED, f"Configuration file exists, but the configured/provided SourcePath ('{path_value}') is not a directory.")
        print(Colours.RED, "Action Required: Correct the 'SourcePath' or provide a valid path when prompted.")
    elif status == USER_PROVIDED_PATH_INVALID:
        print(Colours.RED, "Failed to obtain a valid source directory path from user input.")
        print(Colours.RED, "Action Required: Run the script again and provide a valid directory path.")
    elif status == ERROR_FILE_OPERATION:
        print(Colours.RED, f"A critical error occurred during file Copy/Move operations.")
        print(Colours.RED, "Action Required: Check disk space, permissions, and previous error messages. The source/destination state may be inconsistent.")
    elif status == ERROR_CREATE or status == ERROR_READ:
        print(Colours.RED, "An error occurred during config file creation or reading.")
        print(Colours.RED, "Action Required: Check file permissions or disk space.")
    else:
        print(Colours.MAGENTA, "An unexpected status was returned.")

    # Example use of path_value
    if status == EXISTS_VALID and path_value:
        print(Colours.GREEN, f"\nProceeding with operations using validated source directory: {path_value}")
        # Add application logic here...
        pass
    elif status not in [CREATED]: # Don't print 'Cannot proceed' if just created
        print(Colours.RED, "\nCannot proceed due to configuration or file operation issues.")

    return status, path_value

# --- Example Usage ---
if __name__ == "__main__":
    main()

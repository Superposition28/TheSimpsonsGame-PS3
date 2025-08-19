import hashlib
import json
import shutil
import time
import traceback
from pathlib import Path
import argparse
import sqlite3

import os
import sys
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..', '..', '..', '..', 'Utils')))
from printer import printerprint as print
from printer import Colours, print_error, print_verbose, print_debug, printc


VERBOSE = False # Global verbose flag
DB_FILENAME = "asset_map.sqlite" # Define the database filename

def extract_map_subdirectory(full_path, markerParam):
    full_path_normalized = full_path.replace('/', os.sep).replace('\\', os.sep)
    marker = markerParam.replace('/', os.sep).replace('\\', os.sep) # Normalize marker too

    if not marker:
        print(colour="YELLOW", prefix="BlendInit", msg=f"Warning: Marker is not provided. Cannot extract map subdirectory from path: {full_path_normalized}. Returning _UNKNOWN_MAP_NO_MARKER.")
        return "_UNKNOWN_MAP_NO_MARKER" # No exit

    idx = full_path_normalized.lower().find(marker.lower())

    if idx >= 0:
        # Marker was found. Get the part of the string that comes *after* the marker.
        start_of_remainder = idx + len(marker)
        remaining_path = full_path_normalized[start_of_remainder:]

        # Strip any leading path separators from this remaining_path.
        # This handles cases where:
        #   - marker="DIR", path=".../DIR/SUBDIR..." -> remaining_path="/SUBDIR...", lstrip -> "SUBDIR..."
        #   - marker="DIR/", path=".../DIR/SUBDIR..." -> remaining_path="SUBDIR...", lstrip -> "SUBDIR..."
        subdir_candidate = remaining_path.lstrip(os.sep)

        if not subdir_candidate:
            # Path ended with the marker, or marker + only slashes.
            print(colour="CYAN", prefix="BlendInit", msg=f"Info: Marker '{marker}' found in '{full_path_normalized}', but path ends with marker or only separators follow. No specific subdirectory extracted. Returning _NO_SUBDIR_AFTER_MARKER.")
            return "_NO_SUBDIR_AFTER_MARKER" # No exit

        # Split the remaining part by the OS path separator.
        # The first element should be our target subdirectory.
        parts = [p for p in subdir_candidate.split(os.sep) if p] # Filter out empty parts (e.g., from "//")

        if parts:
            # Successfully found the first directory component after the marker.
            if VERBOSE: # Optional: print only if verbose
                print(colour="GREEN", prefix="BlendInit", msg=f"Success: Marker '{marker}', Path '{full_path_normalized}', Subdir Part '{parts[0]}'")
            return parts[0]
        else:
            # This might happen if subdir_candidate was, for example, just "////"
            print(colour="YELLOW", prefix="BlendInit", msg=f"Warning: Marker '{marker}' found in '{full_path_normalized}', but could not isolate a subdirectory from the remainder '{subdir_candidate}'. Returning _NO_SUBDIR_PARTS_FOUND.")
            return "_NO_SUBDIR_PARTS_FOUND" # No exit
    else:
        # Marker string was not found anywhere in the path.
        print(colour="YELLOW", prefix="BlendInit", msg=f"Warning: Marker '{marker}' was not found in path: {full_path_normalized}. Returning _UNKNOWN_MAP_NOT_FOUND.")
        return "_UNKNOWN_MAP_NOT_FOUND" # No exit

def md5_hash(s):
    return hashlib.md5(s.encode('utf-8')).hexdigest()

def init_db(db_file_path): # Renamed parameter for clarity
    """Initializes the SQLite database and creates the asset_map table if it doesn't exist."""
    conn = sqlite3.connect(db_file_path)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS asset_map (
            identifier TEXT PRIMARY KEY,
            map_subdirectory TEXT,
            filename TEXT,
            preinstanced_full TEXT,
            blend_full TEXT,
            glb_full TEXT,
            existing_glb_full TEXT,
            preinstanced_symlink TEXT,
            blend_symlink TEXT,
            glb_symlink TEXT
        )
    ''')
    conn.commit()
    return conn

def generate_asset_mapping(conn, root_drive, preinstanced_root, blend_root, marker, glb_root=None, check_existence=False):
    global VERBOSE
    if not os.path.isdir(preinstanced_root):
        raise FileNotFoundError(f"Preinstanced root directory not found: {preinstanced_root}")
    if not os.path.isdir(blend_root):
        raise FileNotFoundError(f"Blend root directory not found: {blend_root}")
    if glb_root and not os.path.isdir(glb_root):
        print(colour="CYAN", prefix="BlendInit", msg=f"GLB root directory {glb_root} not found, creating it.")
        os.makedirs(glb_root, exist_ok=True)

    cursor = conn.cursor()
    assets_processed_count = 0

    preinstanced_root_abs = os.path.abspath(preinstanced_root)
    for dirpath, _, files in os.walk(preinstanced_root_abs):
        for file in files:
            if not file.endswith('.preinstanced'):
                continue

            preinstanced_file_abs = os.path.join(dirpath, file)
            preinstanced_rel = os.path.relpath(preinstanced_file_abs, preinstanced_root_abs)

            blend_rel = os.path.splitext(preinstanced_rel)[0] + '.blend'
            blend_full_abs = os.path.join(os.path.abspath(blend_root), blend_rel)

            glb_full_abs = None
            if glb_root:
                glb_rel = os.path.splitext(preinstanced_rel)[0] + '.glb'
                glb_full_abs = os.path.join(os.path.abspath(glb_root), glb_rel)

            if check_existence and not os.path.isfile(blend_full_abs):
                print(colour="YELLOW", prefix="BlendInit", msg=f"Warning: Corresponding blend file not found: {blend_full_abs}")
                continue

            map_subdir = extract_map_subdirectory(preinstanced_file_abs, marker)
            if VERBOSE:
                print(colour="CYAN", prefix="BlendInit", msg=f"Extracted Map Subdirectory: '{map_subdir}' for {preinstanced_file_abs}")

            identifier = md5_hash(preinstanced_rel.replace('\\', '/')) # Use normalized relative path for hash

            asset_info = {
                "identifier": identifier,
                "map_subdirectory": map_subdir,
                "filename": os.path.splitext(os.path.basename(preinstanced_file_abs))[0],
                "preinstanced_full": preinstanced_file_abs,
                "blend_full": blend_full_abs,
                "glb_full": glb_full_abs, # Can be None
                "existing_glb_full": None
            }

            if glb_full_abs and os.path.isfile(glb_full_abs):
                asset_info["existing_glb_full"] = glb_full_abs

            try:
                cursor.execute('''
                    INSERT OR REPLACE INTO asset_map
                    (identifier, map_subdirectory, filename, preinstanced_full, blend_full, glb_full, existing_glb_full)
                    VALUES (:identifier, :map_subdirectory, :filename, :preinstanced_full, :blend_full, :glb_full, :existing_glb_full)
                ''', asset_info)
                assets_processed_count +=1
            except sqlite3.Error as e:
                print(colour="RED", prefix="BlendInit", msg=f"Error inserting/replacing asset {identifier} into DB: {e}")

    conn.commit()
    return assets_processed_count

def create_symlink_entry(src, dst, is_dir=True, debug_sleep_duration=0):
    try:
        if os.path.lexists(dst):
            if os.path.islink(dst):
                 return True
            else:
                print(colour="YELLOW", prefix="BlendInit", msg=f"Warning: Path {dst} exists and is not a symlink. Removing to create symlink.")
                if os.path.isdir(dst) and not os.path.islink(dst): # Check again it's not a link before rmtree
                    shutil.rmtree(dst)
                else:
                    os.remove(dst)

        os.symlink(src, dst, target_is_directory=is_dir)
        if VERBOSE: # Only print if verbose
            print(colour="GREEN", prefix="BlendInit", msg=f"Created symlink: {dst} -> {src}")
        return True
    except PermissionError as e:
        print(colour="RED", prefix="BlendInit", msg=f"Permission error creating symlink {dst} -> {src}: {e}. Try running as administrator or enabling Developer Mode on Windows.")
        if debug_sleep_duration > 0: time.sleep(debug_sleep_duration)
        return False
    except Exception as e:
        print(colour="RED", prefix="BlendInit", msg=f"Error creating symlink {dst} -> {src}: {e}")
        if debug_sleep_duration > 0: time.sleep(debug_sleep_duration)
        return False

def create_symbolic_links(conn, root_drive, debug_sleep_enabled=False): # Changed param name
    global VERBOSE
    VERBOSE = True # Set to True for verbose output
    cursor = conn.cursor()
    cursor.execute("SELECT identifier, map_subdirectory, preinstanced_full, blend_full, glb_full FROM asset_map")
    assets = cursor.fetchall()

    updated_symlinks_count = 0
    debug_sleep_actual_duration = 5 if debug_sleep_enabled else 0

    if VERBOSE:
        print(colour="CYAN", prefix="BlendInit", msg=f"Starting symbolic link creation for {len(assets)} assets.")

    for asset_row in assets: # Renamed to avoid conflict
        identifier, map_subdir, preinstanced_full, blend_full, glb_path_from_db = asset_row

        if VERBOSE:
            print(colour="CYAN", prefix="BlendInit", msg=f"Processing asset: {identifier}, map_subdir: {map_subdir}")

        if not map_subdir or map_subdir.startswith("_UNKNOWN_MAP") or map_subdir == "_NO_SUBDIR_AFTER_MARKER":
            print(colour="YELLOW", prefix="BlendInit", msg=f"Warning: Map subdirectory '{map_subdir}' for asset {identifier} is not suitable for symlink creation. Skipping.")
            continue

        target_base = os.path.join(root_drive, map_subdir)
        try:
            if VERBOSE:
                print(colour="CYAN", prefix="BlendInit", msg=f"Ensuring target base directory exists: {target_base}")
            os.makedirs(target_base, exist_ok=True)
        except OSError as e:
            print(colour="RED", prefix="BlendInit", msg=f"Error creating target base directory {target_base} for symlinks: {e}")
            exit(1)

        symlinks_to_update_in_db = {}

        # --- Helper function for symlink verification ---
        def verify_symlink(link_folder_path, src_folder_path, asset_id, link_type_name):
            if not (os.path.exists(link_folder_path) and os.path.islink(link_folder_path)):
                print(colour="RED", prefix="BlendInit", msg=f"Error: {link_type_name} symlink {link_folder_path} for asset {asset_id} was not created or is not a symlink.")
                return False

            # Check if the symlink (when resolved) is a directory
            if not os.path.isdir(link_folder_path):
                print(colour="RED", prefix="BlendInit", msg=f"Error: {link_type_name} symlink {link_folder_path} for asset {asset_id} does not point to a directory.")
                return False

            try:
                resolved_link_target = os.path.realpath(link_folder_path)
                resolved_src_folder = os.path.realpath(src_folder_path)

                if resolved_link_target != resolved_src_folder:
                    actual_target_raw = os.readlink(link_folder_path)
                    print(colour="RED", prefix="BlendInit", msg=f"Error: {link_type_name} symlink {link_folder_path} for asset {asset_id} points to '{resolved_link_target}' (raw: '{actual_target_raw}') instead of expected '{resolved_src_folder}'.")
                    return False
                elif VERBOSE:
                    print(colour="GREEN", prefix="BlendInit", msg=f"Successfully verified {link_type_name} symlink for {asset_id}: {link_folder_path} -> {resolved_src_folder}")
                return True
            except OSError as e_resolve:
                print(colour="RED", prefix="BlendInit", msg=f"Error reading/resolving {link_type_name} symlink {link_folder_path} for asset {asset_id}: {e_resolve}")
                return False
        # --- End of helper function ---

        if preinstanced_full and os.path.isfile(preinstanced_full):
            src_folder = os.path.dirname(preinstanced_full)
            link_folder = os.path.join(target_base, f"{identifier}_preinstanced")
            if VERBOSE:
                print(colour="CYAN", prefix="BlendInit", msg=f"Attempting to create preinstanced symlink: {link_folder} -> {src_folder}")
            if create_symlink_entry(src_folder, link_folder, is_dir=True, debug_sleep_duration=debug_sleep_actual_duration):
                if verify_symlink(link_folder, src_folder, identifier, "preinstanced"):
                    symlinks_to_update_in_db["preinstanced_symlink"] = link_folder
            elif VERBOSE: # create_symlink_entry failed
                print(colour="YELLOW", prefix="BlendInit", msg=f"Failed to create preinstanced symlink for {identifier} (function returned false).")


        if blend_full and os.path.isfile(blend_full):
            src_folder = os.path.dirname(blend_full)
            link_folder = os.path.join(target_base, f"{identifier}_blend")
            if VERBOSE:
                print(colour="CYAN", prefix="BlendInit", msg=f"Attempting to create blend symlink: {link_folder} -> {src_folder}")
            if create_symlink_entry(src_folder, link_folder, is_dir=True, debug_sleep_duration=debug_sleep_actual_duration):
                if verify_symlink(link_folder, src_folder, identifier, "blend"):
                    symlinks_to_update_in_db["blend_symlink"] = link_folder
            elif VERBOSE: # create_symlink_entry failed
                print(colour="YELLOW", prefix="BlendInit", msg=f"Failed to create blend symlink for {identifier} (function returned false).")


        if glb_path_from_db: # glb_path_from_db is a full path to a file
            src_folder = os.path.dirname(glb_path_from_db) # We link to the directory containing the GLB
            if os.path.isdir(src_folder): # Check if the source *directory* for GLB exists
                link_folder = os.path.join(target_base, f"{identifier}_glb")
                if VERBOSE:
                    print(colour="CYAN", prefix="BlendInit", msg=f"Attempting to create GLB symlink: {link_folder} -> {src_folder}")
                if create_symlink_entry(src_folder, link_folder, is_dir=True, debug_sleep_duration=debug_sleep_actual_duration):
                    if verify_symlink(link_folder, src_folder, identifier, "GLB"):
                        symlinks_to_update_in_db["glb_symlink"] = link_folder
                elif VERBOSE: # create_symlink_entry failed
                    print(colour="YELLOW", prefix="BlendInit", msg=f"Failed to create GLB symlink for {identifier} (function returned false).")
            elif VERBOSE: # src_folder for GLB does not exist
                # This condition was already present, just ensuring it's clear
                if os.path.exists(glb_path_from_db): # If the GLB file exists but its parent dir somehow doesn't (unlikely with dirname)
                    print(colour="YELLOW", prefix="BlendInit", msg=f"GLB source folder {src_folder} for asset {identifier} does not exist, but GLB file {glb_path_from_db} does. Symlink not created.")
                else: # GLB file itself also doesn't exist (implies src_folder based on it also wouldn't)
                    print(colour="YELLOW", prefix="BlendInit", msg=f"GLB file {glb_path_from_db} and its source folder {src_folder} do not exist for asset {identifier}. GLB symlink not created.")


        if symlinks_to_update_in_db:
            try:
                set_clauses = ", ".join([f"{key} = :{key}" for key in symlinks_to_update_in_db.keys()])
                update_query = f"UPDATE asset_map SET {set_clauses} WHERE identifier = :identifier"

                params_for_update = symlinks_to_update_in_db.copy()
                params_for_update["identifier"] = identifier

                if VERBOSE:
                    print(colour="CYAN", prefix="BlendInit", msg=f"Updating DB for {identifier} with symlinks: {symlinks_to_update_in_db}")

                cursor.execute(update_query, params_for_update)
                conn.commit() # Commit per asset update if symlinks were made
                updated_symlinks_count += 1
                if VERBOSE:
                    print(colour="GREEN", prefix="BlendInit", msg=f"Successfully updated symlink paths in DB for {identifier}")
            except sqlite3.Error as e:
                print(colour="RED", prefix="BlendInit", msg=f"Error updating symlinks for asset {identifier} in DB: {e}")
                # Potentially rollback if a commit per asset is not desired and an error occurs
                # For now, it commits per asset if symlinks_to_update_in_db is non-empty

        if VERBOSE:
            print(colour="CYAN", prefix="BlendInit", msg=f"Finished processing symlinks for {identifier} in '{map_subdir}'")
            if debug_sleep_enabled and debug_sleep_actual_duration > 0: # Ensure duration is positive
                time.sleep(debug_sleep_actual_duration)

    # conn.commit() # Original final commit. Moved to per-asset commit if updates are made for that asset.
    # If you prefer a single commit at the end, move conn.commit() back here and remove from loop.
    # However, committing after each successful asset update makes progress persistent.
    
    final_commit_message = "Committed all changes to DB." if updated_symlinks_count > 0 else "No changes to commit to DB."
    # If not committing per asset, uncomment the line below
    # conn.commit() 
    # print(colour="BLUE", prefix="BlendInit", msg=final_commit_message) # Example final message
    
    print(colour="GREEN", prefix="BlendInit", msg=f"Total assets updated with symlink information in DB: {updated_symlinks_count}")

class PreinstancedFileProcessor:
    def __init__(self, input_dir, blend_dir, glb_dir, blank_blend_source, debug_sleep_enabled, verbose_flag):
        self.input_dir = input_dir
        self.blend_dir = blend_dir
        self.glb_dir = glb_dir
        self.blank_blend_source = blank_blend_source
        self.debug_sleep_enabled = debug_sleep_enabled
        self.verbose = verbose_flag

    def process_files(self):
        if not self.input_dir or not os.path.isdir(self.input_dir):
            print(colour="RED", prefix="BlendInit", msg=f"InputDirectory '{self.input_dir}' is not set or does not exist.")
            raise FileNotFoundError(f"InputDirectory '{self.input_dir}' is not set or does not exist.")
        if not self.blend_dir:
            print(colour="RED", prefix="BlendInit", msg="BlendDirectory is not set.")
            raise ValueError("BlendDirectory is not set.")
        os.makedirs(self.blend_dir, exist_ok=True)
        if not self.glb_dir:
            print(colour="RED", prefix="BlendInit", msg="GLBOutputDirectory is not set.")
            raise ValueError("GLBOutputDirectory is not set.")
        os.makedirs(self.glb_dir, exist_ok=True)
        if not self.blank_blend_source or not os.path.isfile(self.blank_blend_source):
            print(colour="RED", prefix="BlendInit", msg=f"BlankBlendSource '{self.blank_blend_source}' is not set or does not exist.")
            raise FileNotFoundError(f"BlankBlendSource '{self.blank_blend_source}' is not set or does not exist.")
            exit(1)

        preinstanced_files = []
        for dirpath, _, files in os.walk(self.input_dir):
            for file_item in files:
                if file_item.endswith('.preinstanced'):
                    preinstanced_files.append(os.path.join(dirpath, file_item))

        print(colour="CYAN", prefix="BlendInit", msg=f"Found {len(preinstanced_files)} .preinstanced files in {self.input_dir}.")
        input_dir_abs = os.path.abspath(self.input_dir)

        for preinst_path in preinstanced_files:
            if self.verbose:
                print(colour="CYAN", prefix="BlendInit", msg=f"Processing preinstanced file: {preinst_path}")

            rel_path = os.path.relpath(preinst_path, input_dir_abs)
            blend_dest_dir = os.path.join(os.path.abspath(self.blend_dir), os.path.dirname(rel_path))
            glb_dest_dir = os.path.join(os.path.abspath(self.glb_dir), os.path.dirname(rel_path))

            os.makedirs(blend_dest_dir, exist_ok=True)
            os.makedirs(glb_dest_dir, exist_ok=True)

            blend_dest_filename = os.path.splitext(os.path.basename(preinst_path))[0] + ".blend"
            blend_dest_full_path = os.path.join(blend_dest_dir, blend_dest_filename)

            if not os.path.isfile(blend_dest_full_path):
                try:
                    shutil.copy2(self.blank_blend_source, blend_dest_full_path)
                    if self.verbose:
                        print(colour="CYAN", prefix="BlendInit", msg=f"Copied {self.blank_blend_source} to {blend_dest_full_path}")
                except Exception as ex:
                    print(colour="RED", prefix="BlendInit", msg=f"Error copying blank blend file to '{blend_dest_full_path}': {ex}")
                    if self.debug_sleep_enabled: time.sleep(1)
            #else:
                #if self.verbose:
                    #print(colour="BLUE", prefix="BlendInit", msg=f"{os.path.basename(blend_dest_full_path)} already exists, skipping copy.")

            if self.debug_sleep_enabled: time.sleep(0.05)
        print(colour="GREEN", prefix="BlendInit", msg=f"Total .preinstanced files processed for blend/glb structure setup: {len(preinstanced_files)}")

def run(args):
    global VERBOSE
    VERBOSE = args.verbose

    print(colour="CYAN", prefix="BlendInit", msg=f"Input args: {args}")

    marker = args.marker
    print(colour="CYAN", prefix="BlendInit", msg=f"Marker: {marker}")
    preinstanced_dir = os.path.abspath(args.preinstanced_dir)
    print(colour="CYAN", prefix="BlendInit", msg=f"Preinstanced Directory: {preinstanced_dir}")
    blend_dir = os.path.abspath(args.blend_dir)
    print(colour="CYAN", prefix="BlendInit", msg=f"Blend Directory: {blend_dir}")
    glb_dir = os.path.abspath(args.glb_dir)
    print(colour="CYAN", prefix="BlendInit", msg=f"GLB Directory: {glb_dir}")

    database_output_directory = os.path.abspath(args.output_dir)
    print(colour="CYAN", prefix="BlendInit", msg=f"Database Output Directory: {database_output_directory}")

    try:
        os.makedirs(database_output_directory, exist_ok=True)
        print(colour="GREEN", prefix="BlendInit", msg=f"Ensured database output directory exists: {database_output_directory}")
    except OSError as e:
        print(colour="RED", prefix="BlendInit", msg=f"Could not create database output directory {database_output_directory}: {e}")
        exit(1)

    actual_db_file_path = os.path.join(database_output_directory, DB_FILENAME)
    print(colour="CYAN", prefix="BlendInit", msg=f"Database file will be at: {actual_db_file_path}")

    root_drive = os.path.abspath(args.root_drive)
    print(colour="CYAN", prefix="BlendInit", msg=f"Root Drive for Symlinks: {root_drive}")
    blank_blend_source = os.path.abspath(args.blank_blend_source)
    print(colour="CYAN", prefix="BlendInit", msg=f"Blank Blend Source: {blank_blend_source}")
    debug_sleep_enabled = args.debug_sleep
    print(colour="CYAN", prefix="BlendInit", msg=f"Debug Sleep Enabled: {debug_sleep_enabled}")

    conn = None
    try:
        print(colour="CYAN", prefix="BlendInit", msg="--- Initializing Database ---")
        # if db file exists delete
        if os.path.exists(actual_db_file_path):
            os.remove(actual_db_file_path)
            print(colour="GREEN", prefix="BlendInit", msg=f"Deleted existing database file: {actual_db_file_path}")
        conn = init_db(actual_db_file_path)
        print(colour="GREEN", prefix="BlendInit", msg=f"Database initialized/opened at: {actual_db_file_path}")
        if debug_sleep_enabled: time.sleep(2)

        print(colour="CYAN", prefix="BlendInit", msg="--- Step 1: Processing Preinstanced Files (Copy blank blends, create dir structure) ---")
        processor = PreinstancedFileProcessor(
            input_dir=preinstanced_dir,
            blend_dir=blend_dir,
            glb_dir=glb_dir,
            blank_blend_source=blank_blend_source,
            debug_sleep_enabled=debug_sleep_enabled,
            verbose_flag=VERBOSE
        )
        if debug_sleep_enabled: time.sleep(2)
        processor.process_files()
        print(colour="GREEN", prefix="BlendInit", msg="--- Step 1: Completed ---")
        if debug_sleep_enabled: time.sleep(2)

        print(colour="CYAN", prefix="BlendInit", msg=f"--- Step 2: Preparing Symbolic Link Root Directory: {root_drive} ---")
        if os.path.exists(root_drive) and not os.path.isdir(root_drive):
            print(colour="RED", prefix="BlendInit", msg=f"Symlink root path {root_drive} exists but is not a directory. Please resolve this.")
            exit(1)
        elif not os.path.exists(root_drive):
            print(colour="CYAN", prefix="BlendInit", msg=f"Symlink root directory {root_drive} does not exist. Creating it.")
            os.makedirs(root_drive, exist_ok=True)
        elif os.path.isdir(root_drive):
            print(colour="CYAN", prefix="BlendInit", msg=f"Symlink root directory {root_drive} already exists. Proceeding.")
            try:
                shutil.rmtree(root_drive) # Remove existing directory to ensure a clean state
                os.makedirs(root_drive, exist_ok=True) # Recreate the directory
            except OSError as e:
                print(colour="RED", prefix="BlendInit", msg=f"Could not remove existing directory {root_drive}: {e}")
                exit(1)
        print(colour="GREEN", prefix="BlendInit", msg=f"Root directory for symbolic links ensured: {root_drive}")
        if debug_sleep_enabled: time.sleep(2)

        print(colour="CYAN", prefix="BlendInit", msg="--- Step 3: Generating Asset Map & Populating Database ---")
        if debug_sleep_enabled: time.sleep(2)
        asset_count = generate_asset_mapping(conn, root_drive, preinstanced_dir, blend_dir, marker, glb_dir, check_existence=False)
        print(colour="GREEN", prefix="BlendInit", msg=f"Generated and stored map for {asset_count} assets in the database.")
        if debug_sleep_enabled: time.sleep(2)

        print(colour="CYAN", prefix="BlendInit", msg=f"--- Step 4: Creating Symbolic Links in: {root_drive} ---")
        if debug_sleep_enabled: time.sleep(2)
        create_symbolic_links(conn, root_drive, debug_sleep_enabled=debug_sleep_enabled)
        print(colour="GREEN", prefix="BlendInit", msg="--- Step 4: Symbolic links creation and DB update process completed. ---")
        if debug_sleep_enabled: time.sleep(2)

        if conn:
            conn.commit()

    except FileNotFoundError as e:
        print(colour="RED", prefix="BlendInit", msg=f"A required file or directory was not found: {e}")
        if conn: conn.rollback()
        exit(1)
    except ValueError as e:
        print(colour="RED", prefix="BlendInit", msg=f"A configuration value is invalid: {e}")
        if conn: conn.rollback()
        exit(1)
    except PermissionError as e:
        print(colour="RED", prefix="BlendInit", msg=f"A permission error occurred: {e}. Try running with appropriate privileges.")
        if conn: conn.rollback()
        exit(1)
    except Exception as e:
        print(colour="RED", prefix="BlendInit", msg=f"An unexpected ERROR occurred: {type(e).__name__} - {e}")
        print(colour="RED", prefix="BlendInit", msg=f"{traceback.format_exc()}")
        if conn: conn.rollback()
        exit(1)
    finally:
        if conn:
            conn.close()
            print(colour="CYAN", prefix="BlendInit", msg="Database connection closed.")

if __name__ == "__main__":
    argsparse = argparse.ArgumentParser(description="Process preinstanced files, manage assets in SQLite DB, and create symbolic links.")
    argsparse.add_argument("--preinstanced-dir", type=str, required=True, help="Directory containing preinstanced files.")
    argsparse.add_argument("--blend-dir", type=str, required=True, help="Directory for storing and finding blend files.")
    argsparse.add_argument("--glb-dir", type=str, required=True, help="Directory for storing and finding glb files.")
    argsparse.add_argument("--output-dir", type=str, required=True, help=f"Directory where the SQLite database file ('{DB_FILENAME}') will be created/managed.")
    argsparse.add_argument("--root-drive", type=str, required=True, help="Root directory where symbolic link structures will be created (e.g., 'P:\\' or '/mnt/symlinks').")
    argsparse.add_argument("--blank-blend-source", type=str, required=True, help="Full path to the source file for blank .blend files.")
    argsparse.add_argument("--debug-sleep", action='store_true', help="Enable short pauses for debugging observation.")
    argsparse.add_argument("--verbose", action='store_true', help="Enable verbose output.")
    argsparse.add_argument("--marker", type=str, required=True, help="Marker string used to extract map subdirectory from preinstanced file paths (e.g., 'Maps', 'Levels').")

    args = argsparse.parse_args()

    try:
        run(args)
    except SystemExit:
        print(colour="YELLOW", prefix="BlendInit", msg="Script exited.")
    except Exception as e:
        print(colour="RED", prefix="BlendInit", msg=f"A critical unhandled ERROR occurred at the top level: {type(e).__name__} - {e}")
        print(colour="RED", prefix="BlendInit", msg=f"{traceback.format_exc()}")
    else:
        print(colour="GREEN", prefix="BlendInit", msg="Script finished successfully.")
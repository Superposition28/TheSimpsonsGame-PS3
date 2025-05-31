import json
import subprocess
import configparser # This import is not used, consider removing if not needed elsewhere
from pathlib import Path
import argparse
import sqlite3 # Added for database interaction

import os
import sys
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..', '..', '..', '..', 'Utils')))
from printer import print, Colours, print_error, print_verbose, print_debug, printc


# Global variables for paths (consider making these configurable or passed as arguments)
global python_script_path, blender_exe_path
global verbose, debug_sleep, export, current_dir, db_file_path

# Command-line argument parsing (values will be set in main)
verbose = False
debug_sleep = False
export = set()

# path to this file
current_dir = os.path.dirname(os.path.abspath(__file__))

# Hardcoded paths - consider moving to a config file or command-line arguments for more flexibility
python_script_path = "RemakeRegistry/Games/TheSimpsonsGame/Scripts/Blender-fixer/MainBlendPatch.py"
# asset_mapping_file = "Tools/Blender/asset_mapping.json" # Replaced by db_file_path
blender_exe_path = "Tools/Blender/blender-4.0.2-windows-x64/blender.exe"
DB_FILENAME_DEFAULT = "asset_map.sqlite" # Default name if only a directory is provided for DB

def blender_processing():
    global python_script_path, blender_exe_path
    global verbose, debug_sleep, export, current_dir, db_file_path # Ensure db_file_path is accessible

    loop_count = 0
    print(Colours.DARKGRAY, "Starting Blender processing using SQLite asset map...")

    if not db_file_path or not os.path.isfile(db_file_path):
        print(Colours.RED, f"Error: Database file not found or not specified: {db_file_path}")
        sys.exit(1)

    conn = None
    try:
        conn = sqlite3.connect(db_file_path)
        conn.row_factory = sqlite3.Row # Access columns by name
        cursor = conn.cursor()

        # Fetch necessary columns. Add 'identifier' if you need it for logging as 'key' was used.
        cursor.execute("""
            SELECT identifier, filename, blend_symlink, glb_symlink
            FROM asset_map
        """)
        assets = cursor.fetchall()

        if not assets:
            print(Colours.YELLOW, f"No assets found in the database: {db_file_path}")
            return

        for asset_row in assets:
            loop_count += 1
            print(Colours.RESET, "")
            print(Colours.YELLOW, f"Loop Count: {loop_count} (Asset ID: {asset_row['identifier']})")
            print(Colours.RESET, "")

            # Check if essential symlink paths and filename are present in the DB row
            # These columns in the DB can be NULL if not populated by the first script
            filename = asset_row["filename"]
            blend_symlink_path = asset_row["blend_symlink"]
            glb_symlink_path = asset_row["glb_symlink"]

            if not all([filename, blend_symlink_path, glb_symlink_path]):
                print(Colours.YELLOW, f"Warning: Missing one or more required symlink paths or filename for asset ID: {asset_row['identifier']}. Skipping.")
                if verbose:
                    print(Colours.YELLOW, f"  Filename: {filename}")
                    print(Colours.YELLOW, f"  Blend Symlink Path: {blend_symlink_path}")
                    print(Colours.YELLOW, f"  GLB Symlink Path: {glb_symlink_path}")
                continue

            blend_symlink_file = os.path.join(blend_symlink_path, filename + ".blend")
            glb_symlink_file = os.path.join(glb_symlink_path, filename + ".glb")
            # fbx uses the same directory structure as glb as per original logic
            fbx_symlink_path = glb_symlink_path
            fbx_symlink_file = os.path.join(fbx_symlink_path, filename + ".fbx")

            if os.path.isfile(blend_symlink_file):
                try:
                    # Determine if export is needed based on existence of target files and --export flags
                    needs_export = False
                    if 'glb' in export and not os.path.isfile(glb_symlink_file):
                        needs_export = True
                    if 'fbx' in export and not os.path.isfile(fbx_symlink_file):
                        needs_export = True

                    run_blender = True
                    if not export:
                        pass

                    #if 'glb' in export and not os.path.isfile(glb_symlink_file):
                    #    run_blender = True
                    #if 'fbx' in export and not os.path.isfile(fbx_symlink_file):
                    #    run_blender = True

                    # If no export types are specified, but we want to process if files are missing (original implicit behavior)
                    if not export and (not os.path.isfile(glb_symlink_file) or not os.path.isfile(fbx_symlink_file)):
                        print(Colours.YELLOW, f"Skipping Blender for {filename}: No export formats specified in --export and files might be missing.")

                    if run_blender:
                        verbose_str = "true" if verbose else "false"
                        debug_sleep_str = "true" if debug_sleep else "false"
                        export_str = ",".join(sorted(list(export))) # Pass the requested export formats, ensure consistent order

                        print(Colours.GRAY, "# Start Blender Output")
                        args = [
                            blender_exe_path,
                            "-b", blend_symlink_file,
                            "--python", python_script_path,
                            "--",
                            blend_symlink_file,
                            preinstanced_symlink_file,
                            glb_symlink_file, # MainPreinstancedConvert.py might still expect this path for .glb
                            verbose_str,
                            debug_sleep_str,
                            export_str, # Pass the set of exports
                            current_dir,
                            fbx_symlink_file # Pass FBX path too, if your script supports it
                        ]
                        blender_command = ' '.join(f'"{a}"' if ' ' in a else a for a in args)
                        print(Colours.MAGENTA, f"Blender command --> {blender_command}")

                        proc = subprocess.Popen(
                            args,
                            stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE,
                            text=True
                        )
                        output, error = proc.communicate()
                        print(Colours.RESET, output)
                        if error:
                            print(Colours.RED, error)
                        print(Colours.GRAY, "# End Blender Output")

                        # Post-processing check (original logic had 'if export == True:')
                        # This check should be more specific, e.g., if 'glb' was requested
                        if 'glb' in export: # Check if GLB export was attempted
                            if os.path.isfile(glb_symlink_file):
                                # Check for errors within the GLB file content (if it's text, like an error message)
                                try:
                                    with open(glb_symlink_file, "r", encoding="utf-8", errors="ignore") as f_glb:
                                        glb_content_sample = f_glb.read(512) # Read a sample
                                    if "Error:" in glb_content_sample or "Exception:" in glb_content_sample or proc.returncode != 0:
                                        print(Colours.RED, f"Blender execution for {filename} might have failed or GLB contains errors (check Blender output above).")
                                    else:
                                        print(Colours.GREEN, f"GLB file processed/verified for: {glb_symlink_file}")
                                except Exception as e_read:
                                    print(Colours.YELLOW, f"Could not read GLB {glb_symlink_file} for error checking: {e_read}")
                            else:
                                print(Colours.RED, f"Failed to create GLB output file: {glb_symlink_file}")
                        if 'fbx' in export: # Check if FBX export was attempted
                            if os.path.isfile(fbx_symlink_file):
                                    print(Colours.GREEN, f"FBX file processed/verified for: {fbx_symlink_file}")
                            else:
                                print(Colours.RED, f"Failed to create FBX output file: {fbx_symlink_file}")
                    else:
                        print(Colours.YELLOW, f"Skipping Blender for {filename}: Requested output files already exist or not specified in --export.")
                        if 'glb' in export and os.path.isfile(glb_symlink_file):
                            print(Colours.GREEN, f"GLB file already exists: {glb_symlink_file}")
                        if 'fbx' in export and os.path.isfile(fbx_symlink_file):
                            print(Colours.GREEN, f"FBX file already exists: {fbx_symlink_file}")

                except Exception as ex:
                    print(Colours.RED, f"Error processing asset {filename} (ID: {asset_row['identifier']}): {ex}")
                    # Consider if this should be sys.exit(1) or just skip the asset
            else:
                print(Colours.RED, f"Error: Blend symlink file not found: {blend_symlink_file} (asset ID: {asset_row['identifier']})")
                # Consider if this should be sys.exit(1) or just skip the asset

    except sqlite3.Error as e:
        print(Colours.RED, f"SQLite error: {e}")
        sys.exit(1)
    except FileNotFoundError: # Should be caught by the initial db_file_path check
        print(Colours.RED, f"Error: Database file not found: {db_file_path}")
        sys.exit(1)
    except Exception as e_outer:
        print(Colours.RED, f"An unexpected error occurred in blender_processing: {e_outer}")
        sys.exit(1)
    finally:
        if conn:
            conn.close()
            print(Colours.DARKGRAY, "Database connection closed.")


def main(verbose_param: bool, debug_sleep_param: bool, export_param: set, db_path_param: str) -> None:
    global verbose, debug_sleep, export, db_file_path # Add db_file_path to globals updated by main

    verbose = verbose_param
    print(Colours.BLUE, f"Verbose mode: {verbose}")
    debug_sleep = debug_sleep_param
    print(Colours.BLUE, f"Debug sleep: {debug_sleep}")
    export = export_param if export_param is not None else set() # Ensure export is a set
    print(Colours.BLUE, f"Export formats: {export}")
    db_file_path = db_path_param
    print(Colours.BLUE, f"Database file path: {db_file_path}")


    print(Colours.BLUE, "Initializing...")

    # Validate essential paths early
    if not os.path.isfile(blender_exe_path):
        print(Colours.RED, f"Blender executable not found: {blender_exe_path}")
        sys.exit(1)
    if not os.path.isfile(python_script_path):
        print(Colours.RED, f"Blender Python script not found: {python_script_path}")
        sys.exit(1)


    print(Colours.DARKGRAY, "Blender Processing using SQLite database...")
    blender_processing()
    print(Colours.GREEN, "Processing complete.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Process assets using Blender, based on an SQLite asset map.")
    parser.add_argument("--verbose", action="store_true", help="Enable verbose output")
    parser.add_argument("--debug-sleep", action="store_true", help="Enable debug sleep pauses in Blender script (if supported by it)")
    parser.add_argument("--export", type=str, nargs='*', help="Export formats (e.g., --export fbx glb). If not specified, existing files won't be regenerated by default.")
    parser.add_argument("--db-file-path", type=str, required=True, help=f"Full path to the SQLite database file (e.g., 'output/{DB_FILENAME_DEFAULT}').")

    args = parser.parse_args()

    parsed_export_formats = set()
    if args.export:
        for item in args.export:
            parsed_export_formats.update(item.lower().split()) # Split space-separated and add to set, ensure lowercase

    if not os.path.isabs(args.db_file_path):
        print(Colours.YELLOW, f"Database path '{args.db_file_path}' is not absolute. Resolving relative to current directory '{os.getcwd()}'.")
        db_path = os.path.abspath(args.db_file_path)
    else:
        db_path = args.db_file_path

    if not os.path.isfile(db_path):
        print(Colours.RED, f"Error: Database file does not exist at the specified path: {db_path}")
        sys.exit(1)

    main(args.verbose, args.debug_sleep, parsed_export_formats, db_path)
# RemakeRegistry\Games\TheSimpsonsGame-PS3\Scripts\Blender\Main\BlenderCore.py
import subprocess
from pathlib import Path
import argparse
import sqlite3
import multiprocessing
import os
import sys
from functools import partial # ADDED: For cleaner worker function calls
from collections import namedtuple # ADDED: For more readable results
from tqdm import tqdm # ADDED: For the progress bar

import tempfile # ADDED: For temporary directories
import shutil   # ADDED: For safely removing directories


# Add Utils path for printer
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..', '..', '..', '..', '.')))
from Engine.Utils.printer import Colours, print

# --- Configuration (Kept global as these are constants for the script's lifetime) ---
current_dir = os.path.dirname(os.path.abspath(__file__))
python_script_path = Path(current_dir).parent / "MainPreinstancedConvert.py"
python_extension_file = Path(current_dir).parent / "PreinstancedImportExtension.py"
blender_exe_path = "Tools/Blender/blender-4.0.2-windows-x64/blender.exe"
DB_FILENAME_DEFAULT = "asset_map.sqlite"

# ADDED: A named tuple for structured, readable results from the worker
ProcessResult = namedtuple("ProcessResult", ["asset_id", "success", "message"])

# --- Worker Function (Modified to capture and print output to console) ---
def run_blender_for_asset(asset_row: dict, export_formats: list, be_verbose: bool, use_debug_sleep: bool) -> ProcessResult:
    """
    Worker function that processes a single asset.
    This version now uses an isolated, temporary directory for the Blender addon.
    This version captures subprocess output and prints it to the console if --verbose is used.
    """
    asset_id = asset_row["identifier"]
    filename = asset_row["filename"]

    temp_addon_dir = tempfile.mkdtemp(prefix="blender_addon_")

    try:
        blend_symlink_path = asset_row["blend_symlink"]
        glb_symlink_path = asset_row["glb_symlink"]
        preinstanced_symlink_path = asset_row["preinstanced_symlink"]

        if not all([filename, blend_symlink_path, glb_symlink_path, preinstanced_symlink_path]):
            return ProcessResult(asset_id, False, "Missing required symlink paths or filename")

        blend_symlink_file = os.path.join(blend_symlink_path, filename + ".blend")
        glb_symlink_file = os.path.join(glb_symlink_path, filename + ".glb")
        fbx_symlink_file = os.path.join(glb_symlink_path, filename + ".fbx")
        preinstanced_symlink_file = os.path.join(preinstanced_symlink_path, filename + ".preinstanced")

        if not os.path.isfile(blend_symlink_file):
            return ProcessResult(asset_id, False, f"Blend symlink not found: {blend_symlink_file}")

        run_blender_flag = False
        if 'glb' in export_formats and not os.path.isfile(glb_symlink_file):
            run_blender_flag = True
        if 'fbx' in export_formats and not os.path.isfile(fbx_symlink_file):
            run_blender_flag = True

        if not run_blender_flag:
            return ProcessResult(asset_id, True, f"Skipped: requested exports already exist for {filename}")

        if not os.path.isfile(preinstanced_symlink_file):
            return ProcessResult(asset_id, False, f"Preinstanced symlink missing: {preinstanced_symlink_file}")

        args = [
            str(blender_exe_path),
            "-b", blend_symlink_file,
            "--python", str(python_script_path),
            "--",
            blend_symlink_file,
            preinstanced_symlink_file,
            glb_symlink_file,
            str(python_extension_file),
            "true" if be_verbose else "false",
            "true" if use_debug_sleep else "false",
            current_dir,
            fbx_symlink_file,
            asset_id,
            temp_addon_dir,
            ",".join(sorted(list(export_formats))),
        ]
        # CHANGE: Conditionally print the output based on the --verbose flag
        if be_verbose:
            # CHANGE: Use subprocess.run to wait for the command and capture its output
            proc = subprocess.run(args, capture_output=True, text=True, encoding='utf-8')

            # Use a lock to prevent interleaved printing from multiple processes
            #with tqdm.get_lock():

            # allow interleaved printing
            print(colour=Colours.DARKGRAY, message=f"\n--- Output for Asset ID: {asset_id} ---")
            # Print stdout if it contains anything
            if proc.stdout:
                print(colour=Colours.GRAY, message=proc.stdout.strip())
            # Print stderr if it contains anything
            if proc.stderr:
                print(colour=Colours.YELLOW, message=proc.stderr.strip())
            print(colour=Colours.DARKGRAY, message=f"--- End of Output for Asset ID: {asset_id} ---\n")
        else:
            proc = subprocess.run(args, capture_output=True, text=True, encoding='utf-8')

        # Check for errors after execution
        if proc.returncode != 0:
            error_details = proc.stderr or proc.stdout or "Blender process produced no output."
            return ProcessResult(asset_id, False, f"Blender exited with code {proc.returncode}. Details: {error_details}")

        # Post-checks
        if 'glb' in export_formats and not os.path.isfile(glb_symlink_file):
            return ProcessResult(asset_id, False, f"GLB file was not created: {glb_symlink_file}")
        if 'fbx' in export_formats and not os.path.isfile(fbx_symlink_file):
            return ProcessResult(asset_id, False, f"FBX file was not created: {fbx_symlink_file}")

        return ProcessResult(asset_id, True, f"Processed successfully: {filename}")

    except Exception as e:
        return ProcessResult(asset_id, False, f"A critical exception occurred in the worker: {str(e)}")
    finally:
        # ADDED: Ensure the temporary directory is always cleaned up
        if os.path.isdir(temp_addon_dir):
            shutil.rmtree(temp_addon_dir)

# --- Main Orchestration ---
def blender_processing(db_path: str, num_workers: int, export_formats, be_verbose: bool, use_debug_sleep: bool) -> None:
    print(colour=Colours.DARKGRAY, message=f"Starting Blender processing with {num_workers} workers...")

    try:
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        # Fetch the rows as sqlite3.Row objects first
        rows_from_db = conn.execute("SELECT identifier, filename, preinstanced_symlink, blend_symlink, glb_symlink FROM asset_map").fetchall()
        conn.close()

        # CHANGE: Convert sqlite3.Row objects to standard dictionaries
        assets_to_process = [dict(row) for row in rows_from_db]

    except sqlite3.Error as e:
        print(colour=Colours.RED, message=f"SQLite error: {e}")
        sys.exit(1)

    if not assets_to_process:
        print(colour=Colours.YELLOW, message=f"No assets found in database: {db_path}")
        return

    # Use 'partial' to create a new function with the constant arguments already "baked in".
    # This is a clean way to pass extra, non-changing arguments to a pool worker.
    worker_func = partial(run_blender_for_asset,
                          export_formats=export_formats,
                          be_verbose=be_verbose,
                          use_debug_sleep=use_debug_sleep)

    results = []
    print(colour=Colours.BLUE, message=f"Found {len(assets_to_process)} assets. Dispatching to workers...")

    # Use a multiprocessing Pool and wrap the iterator with tqdm for a progress bar
    with multiprocessing.Pool(processes=num_workers) as pool:
        # pool.imap_unordered is memory efficient and lets us see progress as tasks finish
        result_iterator = pool.imap_unordered(worker_func, assets_to_process)
        for result in tqdm(result_iterator, total=len(assets_to_process), desc="Processing Assets"):
            results.append(result)

    # Now we process the results using the named tuple for clarity
    successes = [r for r in results if r.success]
    failures = [r for r in results if not r.success]
    skipped = [r for r in successes if r.message.startswith("Skipped")]

    print(colour=Colours.GREEN, message=f"\n✅ {len(successes) - len(skipped)} assets processed successfully.")
    print(colour=Colours.YELLOW, message=f"⚪ {len(skipped)} assets skipped (already exist).")
    print(colour=Colours.RED, message=f"❌ {len(failures)} assets failed.")

    if failures:
        print(colour=Colours.RED, message="\n--- Failure Details ---")
        for result in failures:
            print(colour=Colours.RED, message=f"  - ID {result.asset_id}: {result.message}")

def main() -> None:
    parser = argparse.ArgumentParser(description="Process assets in parallel using Blender with an SQLite asset map.")
    parser.add_argument("--verbose", action="store_true", help="Enable verbose output from Blender subprocesses.")
    parser.add_argument("--debug-sleep", action="store_true", help="Enable debug sleep pauses in the Blender script.")
    parser.add_argument("--export", type=str, nargs='*', help="Export formats (e.g., --export fbx glb).")
    parser.add_argument("--db-file-path", type=str, required=True, help=f"Path to SQLite database file.")
    parser.add_argument("--workers", type=int, help="Number of parallel Blender instances. Defaults to number of CPU cores.")
    args = parser.parse_args()

    export_formats = set()
    if args.export:
        for item in args.export:
            export_formats.update(item.lower().split())

    # avoid too many workers if not specified
    if args.workers is None:
        # Calculate 75% of CPU cores, ensuring it's a whole number and at least 1.
        #args.workers = max(1, int(multiprocessing.cpu_count() * 0.75))
        args.workers = int(multiprocessing.cpu_count())

    if args.debug_sleep:
        print(colour=Colours.BLUE, message="Debug sleep mode enabled.")
        debug_sleep = True
    else:
        debug_sleep = False

    if args.verbose:
        print(colour=Colours.BLUE, message="Verbose mode enabled.")
        verbose = True
    else:
        verbose = False

    db_path = os.path.abspath(args.db_file_path) if not os.path.isabs(args.db_file_path) else args.db_file_path

    # --- Path and Argument Validation ---
    for path in [blender_exe_path, python_script_path, python_extension_file, db_path]:
        if not os.path.exists(path):
            print(colour=Colours.RED, message=f"Error: Required file or directory not found: {path}")
            sys.exit(1)

    # delete blend.log before starting new process
    blend_log_path = os.path.join(os.path.dirname(__file__), "blend.log")
    if os.path.exists(blend_log_path):
        os.remove(blend_log_path)

    print(colour=Colours.BLUE, message=f"Export formats: {export_formats or 'None'}")
    print(colour=Colours.BLUE, message=f"Database: {db_path}")
    print(colour=Colours.BLUE, message=f"Workers: {args.workers}")

    blender_processing(db_path, args.workers, export_formats, verbose, debug_sleep)
    print(colour=Colours.GREEN, message="\nProcessing complete.")

if __name__ == "__main__":
    main()

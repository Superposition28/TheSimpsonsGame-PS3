# RemakeRegistry\Games\TheSimpsonsGame-PS3\Godot\init.py
"""

"""
import os
import shutil
import subprocess
import time
import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
import re
import errno

# Add optional tqdm import (graceful fallback if not installed)
try:
    from tqdm import tqdm
    def _progress(iterable, **kwargs):
        return tqdm(iterable, **kwargs)
except Exception:
    # tqdm not available -> no progress bar, iterate normally
    def _progress(iterable, **kwargs):
        return iterable

def countdown(count: int) -> None:
    """
    Simple countdown timer that prints the remaining seconds.
    """
    while count > 0:
        print(f"Waiting... {count} seconds remaining.")
        time.sleep(1)
        count -= 1

def copy_assets(folders_to_copy: list, project_dir: str, asset_extensions: list, logo_image_files: list) -> None:
    """
    Copy asset files from specified folders to the Godot project directory.
    """
    assets_dest_dir = os.path.join(project_dir, 'assets')
    os.makedirs(assets_dest_dir, exist_ok=True)

    for folder_path in folders_to_copy:
        if not os.path.exists(folder_path):
            print(f"Warning: Asset source folder path does not exist: {folder_path}")
            continue

        # First collect all matching files so we can show progress
        matched_files = []
        for root, dirs, files in os.walk(folder_path):
            for filename in files:
                if any(filename.lower().endswith(ext.lower()) for ext in asset_extensions):
                    source_file_path = os.path.join(root, filename)
                    relative_path = os.path.relpath(source_file_path, folder_path)
                    matched_files.append((source_file_path, relative_path))

        if matched_files:
            print(f"Copying {len(matched_files)} file(s) with extensions {asset_extensions} from {folder_path} to {assets_dest_dir}...")
            copied_count = 0
            # Use progress wrapper (tqdm when available)
            for source_file_path, relative_path in _progress(matched_files, desc=f"Copying from {os.path.basename(folder_path)}", unit="file"):
                destination_file_path = os.path.join(assets_dest_dir, relative_path)
                os.makedirs(os.path.dirname(destination_file_path), exist_ok=True)
                shutil.copy2(source_file_path, destination_file_path)
                copied_count += 1

            print(f"Files copied: {copied_count} file(s) from {folder_path}.")
        else:
            print(f"No files found with extensions {asset_extensions} in {folder_path}.")

    # copy all logo image files to the project directory, with progress
    if logo_image_files:
        logos_dest = os.path.join(project_dir, "logos")
        os.makedirs(logos_dest, exist_ok=True)
        print(f"Copying {len(logo_image_files)} logo image(s) to {logos_dest}...")
        for logo_file in _progress(logo_image_files, desc="Copying logos", unit="file"):
            try:
                shutil.copy2(logo_file, logos_dest)
            except Exception as e:
                print(f"Warning: Failed to copy logo '{logo_file}': {e}")


def run_godot_command(command: list, step_name: str):
    """Runs a Godot command and checks for errors."""
    print(f"\n--- Running Godot Step: {step_name} ---")
    print(f"Command: {' '.join(command)}")
    try:
        # Using check=True will raise an exception if Godot returns a non-zero exit code
        subprocess.run(command, check=True)
        print(f"--- {step_name} completed successfully. ---")
    except subprocess.CalledProcessError as e:
        print(f"!!! ERROR during '{step_name}'. Godot exited with error code {e.returncode}.")
        print("!!! Build process halted. Please check the Godot logs above for details.")
        exit(1) # Stop the script
    except FileNotFoundError:
        print(f"!!! ERROR: Could not find the Godot executable at '{command[0]}'.")
        print("!!! Please ensure the path in the script is correct and it's a console-enabled version.")
        exit(1)

# MODIFIED: Added `no_exit` parameter
def create_godot_project(project_name: str, project_path: str, asset_folders: list, scripts_folder: str, addons_folder: str, json_path: str, asset_extensions: list, godot_executable: str, no_exit: bool, logo_image_files: list) -> None:
    """Creates a Godot project with the given name and assets."""
    project_dir = os.path.join(project_path, project_name)
    if not os.path.exists(project_dir):
        os.makedirs(project_dir, exist_ok=True)
    print(f"Godot Project Directory: {project_dir}")

    # Create project.godot file if it doesn't exist
    project_godot_path = os.path.join(project_dir, "project.godot")
    if not os.path.exists(project_godot_path):
        # get project_file_content from file
        with open(f"{project_path}\\..\\conf\\project.godot", "r", encoding="utf-8") as f:
            project_file_content = f.read()

        with open(project_godot_path, "w", encoding="utf-8") as f:
            f.write(project_file_content)
        print(f"Created project.godot file.")

    # --- NEW: batching + parallel import workflow ---
    assets_dir = os.path.join(project_dir, "assets")
    need_assets_import = not os.path.exists(assets_dir) or not os.listdir(assets_dir)

    if need_assets_import:
        # Discover subfolders under each asset source folder and treat each subfolder as its own subproject.
        # subfolders will be list of tuples (subfolder_path, asset_root)
        subfolders = []
        for af in asset_folders:
            if not os.path.exists(af):
                continue
            # add each subdirectory as a subproject, remember its top-level asset root (af)
            for name in os.listdir(af):
                full = os.path.join(af, name)
                if os.path.isdir(full):
                    subfolders.append((full, af))
            # if there are files directly in the asset root that match extensions, include the root itself (use af as its own root)
            has_root_files = False
            for root, dirs, files in os.walk(af):
                # only check top-level files in af
                if root != af:
                    continue
                for f in files:
                    if any(f.lower().endswith(ext.lower()) for ext in asset_extensions):
                        has_root_files = True
                        break
                break
            if has_root_files:
                subfolders.append((af, af))

        # --- NEW: batch large folders into several subprojects to avoid copying 30k+ files at once ---
        BATCH_SIZE = 2000  # tuneable: how many files per temp subproject
        # Map subfolder_path -> (files_list, asset_root)
        folder_to_files = {}
        for sf_path, af in subfolders:
            files = gather_matching_files([sf_path], asset_extensions)
            if files:
                folder_to_files[sf_path] = (files, af)

        # compute total expected subprojects (after batching)
        total_subprojects = sum((len(files) + BATCH_SIZE - 1) // BATCH_SIZE for files, _ in folder_to_files.values())
        if total_subprojects == 0:
            print("No asset subfolders or top-level asset files found to import.")
            # fallback to copying anything matching into project and doing an import
            copy_assets(asset_folders, project_dir, asset_extensions, logo_image_files)
            run_godot_command([godot_executable, "--headless", "--path", project_dir, "--import"], "Asset Importer")
        else:
            print(f"Discovered {len(folder_to_files)} asset source folder(s). Creating {total_subprojects} temp subproject(s) in batches of up to {BATCH_SIZE} files each.")
            tmp_parent = os.path.join(project_dir, "tmp_group_projects")
            os.makedirs(tmp_parent, exist_ok=True)

            subproject_dirs = []
            try:
                cur_idx = 0
                for sf, (files, af) in folder_to_files.items():
                    if len(files) > BATCH_SIZE:
                        print(f"Large folder '{os.path.basename(sf)}' contains {len(files)} asset files; splitting into batches of {BATCH_SIZE}.")
                    for batch in split_into_batches(files, BATCH_SIZE):
                        cur_idx += 1
                        print(f"Creating subproject {cur_idx}/{total_subprojects} for '{os.path.basename(sf)}' (batch size: {len(batch)})...")
                        sp = create_temp_project_for_batch(tmp_parent, batch, cur_idx, name=os.path.basename(sf), asset_root=af)
                        subproject_dirs.append(sp)

                MAX_WORKERS = max(1, min(8, (os.cpu_count() or 4)))
                parallel_import_subprojects(godot_executable, subproject_dirs, max_workers=MAX_WORKERS)

                print("Merging assets and import metadata from subprojects into main project...")
                # CHANGED: use new merge function
                merge_subprojects_into_main(subproject_dirs, project_dir)

                # Ensure logos (found outside asset roots) are still copied into the project if provided
                if logo_image_files:
                    logos_dest = os.path.join(project_dir, "logos")
                    os.makedirs(logos_dest, exist_ok=True)
                    for logo_file in logo_image_files:
                        try:
                            if not os.path.exists(os.path.join(logos_dest, os.path.basename(logo_file))):
                                shutil.copy2(logo_file, logos_dest)
                        except Exception as e:
                            print(f"Warning: Failed to copy logo '{logo_file}': {e}")

                # Final import to let Godot reconcile any remaining metadata, redundent
                #run_godot_command([godot_executable, "--headless", "--path", project_dir, "--import"], "Final Asset Import (main project)")
            finally:
                try:
                    print("Cleaning up temporary group projects...")
                    shutil.rmtree(tmp_parent, ignore_errors=True)
                except Exception as e:
                    print(f"Warning: Failed to remove temp group projects: {e}")
    else:
        print("Assets already imported. Skipping asset copy and import steps.")

    print("\nAssets directory is ready. Preparing to run tool scripts.")
    countdown(3)

    # copy addons
    if os.path.exists(addons_folder):
        shutil.copytree(addons_folder, os.path.join(project_dir, "addons"), dirs_exist_ok=True)

    # 2. Copy config and script files needed for scene generation
    shutil.copy2(json_path, os.path.join(project_dir, "scene_config.json"))

    scripts_dest_dir = os.path.join(project_dir, "Scripts")
    if os.path.exists(scripts_folder):
        # always copy the scripts folder to ensure we have the latest
        shutil.copytree(scripts_folder, scripts_dest_dir, dirs_exist_ok=True)
        print(f"Copied scene_config.json and tool scripts into the project.")

    # 3. Run Scene Building Script
    scene_build_command = [
        godot_executable,
        "--editor",
        "--path", project_dir,
        "--script", "res://Scripts/_BuildScenes.gd"
    ]
    if no_exit:
        scene_build_command.append("--no-exit")
        print("\n'--no-exit' flag detected. Godot will remain open after script execution.")

    run_godot_command(scene_build_command, "Scene Building")

    print("\n✅✅✅ Godot project setup and scene generation complete! ✅✅✅")
    countdown(3)


# NEW: gather all matching files from asset source folders
def gather_matching_files(folder_paths: list, asset_extensions: list):
    """
    Returns a list of tuples (source_file_path, relative_path, source_folder_base)
    relative_path is relative to the source folder base so we preserve the same layout in subprojects.
    """
    matched = []
    for folder_path in folder_paths:
        if not os.path.exists(folder_path):
            continue
        for root, dirs, files in os.walk(folder_path):
            for filename in files:
                if any(filename.lower().endswith(ext.lower()) for ext in asset_extensions):
                    source_file_path = os.path.join(root, filename)
                    relative_path = os.path.relpath(source_file_path, folder_path)
                    matched.append((source_file_path, relative_path, folder_path))
    return matched

# NEW: split list into batches
def split_into_batches(items, batch_size):
    for i in range(0, len(items), batch_size):
        yield items[i:i + batch_size]

# NEW: create a minimal Godot project and copy a batch of assets into it
def create_temp_project_for_batch(base_parent_dir: str, batch_files: list, index: int = None, name: str = None, asset_root: str = None, use_hardlinks: bool = True):
    """
    Create a minimal Godot project for a batch and name it after the source folder when possible.
    Uses hard links (os.link) where possible to avoid heavy copies; falls back to shutil.copy2 when necessary.
    Example resulting name: tmp_MapName_001
    """
    # sanitize provided name (allow letters, numbers, dot, underscore, hyphen)
    if name:
        safe = re.sub(r'[^A-Za-z0-9._-]', '_', name).strip('_')
    else:
        safe = f"project"
    # include the index to ensure uniqueness
    idx_part = f"_{index:03d}" if index is not None else ""
    subproject_dir = os.path.join(base_parent_dir, f"tmp_{safe}{idx_part}")
    os.makedirs(subproject_dir, exist_ok=True)

    # minimal project.godot to allow import
    project_file = os.path.join(subproject_dir, "project.godot")
    if not os.path.exists(project_file):
        with open(project_file, "w", encoding="utf-8") as f:
            f.write("config_version=5\n[application]\nconfig/name=\"BatchImport\"\n")

    # copy/hardlink only batch_files, preserving relative paths
    for src, rel, src_base in batch_files:
        base_for_rel = asset_root if asset_root else src_base
        rel_from_root = os.path.relpath(src, base_for_rel)
        # CHANGED: place all files under assets/
        dest = os.path.join(subproject_dir, "assets", rel_from_root)
        os.makedirs(os.path.dirname(dest), exist_ok=True)
        try:
            # If the destination already exists and looks identical, skip
            if os.path.exists(dest):
                try:
                    sst = os.stat(src)
                    dstt = os.stat(dest)
                    if sst.st_size == dstt.st_size and abs(sst.st_mtime - dstt.st_mtime) < 1.0:
                        continue
                except Exception:
                    pass

            if use_hardlinks:
                try:
                    os.link(src, dest)
                except OSError as e:
                    # cross-device link or other link error -> fallback to copy
                    if e.errno == errno.EXDEV:
                        shutil.copy2(src, dest)
                    else:
                        # unexpected link error, attempt copy as fallback
                        try:
                            shutil.copy2(src, dest)
                        except Exception as e2:
                            print(f"Warning: Failed to copy '{src}' -> '{dest}': {e2}")
                except Exception as e:
                    # general fallback to copy
                    try:
                        shutil.copy2(src, dest)
                    except Exception as e2:
                        print(f"Warning: Failed to copy '{src}' -> '{dest}': {e2}")
            else:
                shutil.copy2(src, dest)
        except Exception as e:
            # copy failures should be non-fatal for the batch; log and continue
            print(f"Warning: Failed to link/copy '{src}' -> '{dest}': {e}")
    return subproject_dir

# NEW: run imports in parallel using ThreadPoolExecutor (subprocess.run is I/O/CPU heavy but this launches separate processes)
def parallel_import_subprojects(godot_executable: str, subproject_dirs: list, max_workers: int = 4):
    print(f"Launching {len(subproject_dirs)} Godot import processes with max_workers={max_workers}...")
    results = []
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {}
        for sp in subproject_dirs:
            cmd = [godot_executable, "--headless", "--path", sp, "--import"]
            futures[executor.submit(subprocess.run, cmd, check=True)] = (sp, cmd)
        for fut in as_completed(futures):
            sp, cmd = futures[fut]
            try:
                fut.result()
                print(f"Import succeeded for subproject: {sp}")
            except subprocess.CalledProcessError as e:
                print(f"ERROR: Godot exited with {e.returncode} for subproject {sp}. Command: {' '.join(cmd)}")
                raise
            except FileNotFoundError:
                print(f"ERROR: Godot executable not found at '{godot_executable}'")
                raise

# NEW: helpers for safe copy/link and tree merge
def _safe_link_or_copy(src: str, dest: str) -> None:
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    if os.path.exists(dest):
        return
    try:
        try:
            os.link(src, dest)
        except Exception:
            shutil.copy2(src, dest)
    except Exception as e:
        print(f"Warning: could not place '{src}' -> '{dest}': {e}")

def _copy_tree_skip_existing(src_dir: str, dest_dir: str) -> None:
    if not os.path.exists(src_dir):
        return
    for root, _, files in os.walk(src_dir):
        rel = os.path.relpath(root, src_dir)
        for fn in files:
            _safe_link_or_copy(os.path.join(root, fn),
                               os.path.join(dest_dir, rel, fn))

# REPLACE merge_import_metadata with new merge function
def merge_subprojects_into_main(subproject_dirs: list, main_project_dir: str) -> None:
    """
    Merge strategy for Godot 4.4:
      - Copy <sub>/assets/* -> <main>/assets/* (skip if exists)
      - Copy <sub>/.godot/imported/* -> <main>/.godot/imported/* (skip if exists)
      - Copy <sub>/.godot/editor/*   -> <main>/.godot/editor/*   (skip if exists)
    Sidecar .import/.uid travel with their sibling assets under assets/.
    """
    main_assets = os.path.join(main_project_dir, "assets")
    os.makedirs(main_assets, exist_ok=True)
    os.makedirs(os.path.join(main_project_dir, ".godot", "imported"), exist_ok=True)
    os.makedirs(os.path.join(main_project_dir, ".godot", "editor"), exist_ok=True)

    for sp in subproject_dirs:
        # 1) assets (includes .import/.uid sidecars next to each asset)
        sp_assets = os.path.join(sp, "assets")
        print(f"Merging assets from {sp_assets} -> {main_assets}")
        _copy_tree_skip_existing(sp_assets, main_assets)

        # 2) .godot/imported cache
        sp_imported = os.path.join(sp, ".godot", "imported")
        print(f"Merging .godot/imported from {sp_imported}")
        _copy_tree_skip_existing(sp_imported, os.path.join(main_project_dir, ".godot", "imported"))

        # 3) .godot/editor state
        sp_editor = os.path.join(sp, ".godot", "editor")
        print(f"Merging .godot/editor from {sp_editor}")
        _copy_tree_skip_existing(sp_editor, os.path.join(main_project_dir, ".godot", "editor"))

def main(project_name: str, repo_root: str, no_exit: bool, sourcePath: str) -> None:
    # --- Path Discovery ---
    module_root = os.path.abspath(os.path.dirname(__file__))
    print(f"Module Root (for generated content): {module_root}")

    if not repo_root:
        print("WARNING: --repo-root not specified. Assuming it's the same as the module root.")
        repo_root = module_root
    print(f"Repository Root (for asset sources): {repo_root}")

    # --- Path Definitions ---
    asset_source_folders = [os.path.join(repo_root, "GameFiles", "ExtractedOut")]
    tool_scripts_source_folder = os.path.join(module_root, "Scripts")
    addons_source_folder = os.path.join(module_root, "addons")
    scene_config_json_path = os.path.join(module_root, 'scene_config.json')
    godot_project_parent_dir = os.path.join(module_root, 'GodotGame')

    # --- Configuration ---
    GODOT_EXECUTABLE = os.path.join(repo_root, "Tools", "Godot", "Godot_v4.4.1-stable_mono_win64", "Godot_v4.4.1-stable_mono_win64.exe")
    GAME_ASSET_EXTENSIONS = [".dds", ".glb", ".wav", ".ogv"]

    # attempt to locate game logo image files in parent of sourcePath
    logo_image_files = []
    for root, dirs, files in os.walk(os.path.dirname(sourcePath)):
        for filename in files:
            if filename.lower().endswith((".png")):
                logo_image_files.append(os.path.join(root, filename))
    if logo_image_files:
        print(f"Found game logo image files: {logo_image_files}")

    # --- Execution ---
    create_godot_project(
        project_name=project_name,
        project_path=godot_project_parent_dir,
        asset_folders=asset_source_folders,
        scripts_folder=tool_scripts_source_folder,
        addons_folder=addons_source_folder,
        json_path=scene_config_json_path,
        asset_extensions=GAME_ASSET_EXTENSIONS,
        godot_executable=GODOT_EXECUTABLE,
        no_exit=no_exit, # Pass the flag down
        logo_image_files=logo_image_files
    )

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Godot Project Setup")
    parser.add_argument("--project-name", default="Game", help="Name of the Godot project")
    parser.add_argument("--repo-root", required=True, help="Path to the repository root directory")
    parser.add_argument("--no-exit", action="store_true", help="Do not exit Godot after running the GDScript (for debugging purposes)")
    parser.add_argument("--sourcePath", required=True, help="Path to the source directory")
    args = parser.parse_args()

    main(
        project_name=args.project_name,
        repo_root=args.repo_root,
        no_exit=args.no_exit,
        sourcePath=args.sourcePath
    )
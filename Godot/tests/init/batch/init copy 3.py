# RemakeRegistry\Games\TheSimpsonsGame-PS3\Godot\init.py
"""

"""
import os
import shutil
import subprocess
import time
import argparse

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
        project_file_content = """
            config_version=5
            [application]
            config/name="Game"
            run/main_scene="res://Node4D.tscn"
            config/features=PackedStringArray("4.4", "Forward Plus")
            config/icon="res://icon.svg"
            [dotnet]
            project/assembly_name="Game"
            """
        with open(project_godot_path, "w", encoding="utf-8") as f:
            f.write(project_file_content)
        print(f"Created project.godot file.")

    # --- NEW: batching + parallel import workflow ---
    assets_dir = os.path.join(project_dir, "assets")
    need_assets_import = not os.path.exists(assets_dir) or not os.listdir(assets_dir)

    if need_assets_import:
        all_files = gather_matching_files(asset_folders, asset_extensions)
        total_assets = len(all_files)
        print(f"Discovered {total_assets} asset file(s) for import.")

        # Thresholds can be tuned
        BATCH_SIZE = 2000
        MAX_WORKERS = max(1, min(8, (os.cpu_count() or 4)))  # tune to machine; default up to 8

        if total_assets == 0:
            print("No assets found to import.")
        elif total_assets > BATCH_SIZE:
            print(f"Large asset set detected (> {BATCH_SIZE}). Using batched parallel import with batch_size={BATCH_SIZE} and max_workers={MAX_WORKERS}.")

            # create a tmp parent directory for subprojects
            tmp_parent = os.path.join(project_dir, "tmp_batch_projects")
            os.makedirs(tmp_parent, exist_ok=True)

            subproject_dirs = []
            batches = list(split_into_batches(all_files, BATCH_SIZE))
            try:
                for idx, batch in enumerate(batches, start=1):
                    print(f"Creating subproject for batch {idx}/{len(batches)} ({len(batch)} files)...")
                    sp = create_temp_project_for_batch(tmp_parent, batch, idx)
                    subproject_dirs.append(sp)

                # Run imports in parallel
                parallel_import_subprojects(godot_executable, subproject_dirs, max_workers=MAX_WORKERS)

                # Merge .import metadata back into main project
                print("Merging import metadata from subprojects into main project...")
                merge_import_metadata(subproject_dirs, project_dir)

                # Copy the original asset files into the main project's assets folder (once)
                print("Copying original asset files into the main project's assets/ ...")
                # Use the existing copy_assets function to maintain behavior/feedback
                copy_assets(asset_folders, project_dir, asset_extensions, logo_image_files)

                # Optionally do a final import call to ensure everything is recognized
                run_godot_command(
                    [
                        godot_executable,
                        "--headless",
                        "--path", project_dir,
                        "--import"
                    ], "Final Asset Import (main project)"
                )
            finally:
                # Clean up temporary subprojects to free disk space
                try:
                    print("Cleaning up temporary batch projects...")
                    shutil.rmtree(tmp_parent, ignore_errors=True)
                except Exception as e:
                    print(f"Warning: Failed to remove temp batch projects: {e}")

        else:
            # small asset set -> use original single-project flow
            print("Using single-project import path (small asset set).")
            copy_assets(asset_folders, project_dir, asset_extensions, logo_image_files)
            run_godot_command(
                [
                    godot_executable,
                    "--headless",
                    "--path", project_dir,
                    "--import"
                ], "Asset Importer"
            )
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
    # MODIFIED: Build the command and conditionally add the --no-exit flag
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
def create_temp_project_for_batch(base_parent_dir: str, batch_files: list, index: int):
	subproject_dir = os.path.join(base_parent_dir, f"tmp_project_{index:03d}")
	assets_dest = os.path.join(subproject_dir, "assets")
	os.makedirs(assets_dest, exist_ok=True)

	# minimal project.godot to allow import
	project_file = os.path.join(subproject_dir, "project.godot")
	if not os.path.exists(project_file):
		with open(project_file, "w", encoding="utf-8") as f:
			f.write("config_version=5\n[application]\nconfig/name=\"BatchImport\"\n")

	# copy only batch_files, preserving relative paths
	for src, rel, src_base in batch_files:
		dest = os.path.join(assets_dest, rel)
		os.makedirs(os.path.dirname(dest), exist_ok=True)
		try:
			shutil.copy2(src, dest)
		except Exception as e:
			# copy failures should be non-fatal for the batch; log and continue
			print(f"Warning: Failed to copy '{src}' -> '{dest}': {e}")
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

# NEW: merge .import folders from subprojects into main project
def merge_import_metadata(subproject_dirs: list, main_project_dir: str):
	main_import_dir = os.path.join(main_project_dir, ".import")
	os.makedirs(main_import_dir, exist_ok=True)
	for sp in subproject_dirs:
		sub_import = os.path.join(sp, ".import")
		if not os.path.exists(sub_import):
			continue
		for root, dirs, files in os.walk(sub_import):
			for fn in files:
				src = os.path.join(root, fn)
				rel = os.path.relpath(src, sub_import)
				dest = os.path.join(main_import_dir, rel)
				os.makedirs(os.path.dirname(dest), exist_ok=True)
				try:
					shutil.copy2(src, dest)
				except Exception as e:
					print(f"Warning: Failed to copy import metadata '{src}' -> '{dest}': {e}")


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
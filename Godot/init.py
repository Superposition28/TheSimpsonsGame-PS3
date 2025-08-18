import os
import shutil
import subprocess
import time
import argparse

def countdown(count: int) -> None:
    """
    Simple countdown timer that prints the remaining seconds.
    """
    while count > 0:
        print(f"Waiting... {count} seconds remaining.")
        time.sleep(1)
        count -= 1

def copy_assets(folders_to_copy: list, project_dir: str, asset_extensions: list) -> None:
    """
    Copy asset files from specified folders to the Godot project directory.
    """
    assets_dest_dir = os.path.join(project_dir, 'assets')
    os.makedirs(assets_dest_dir, exist_ok=True)

    for folder_path in folders_to_copy:
        if not os.path.exists(folder_path):
            print(f"Warning: Asset source folder path does not exist: {folder_path}")
            continue

        print(f"Copying files with extensions {asset_extensions} from {folder_path} to {assets_dest_dir}...")
        copied_count = 0
        for root, dirs, files in os.walk(folder_path):
            for filename in files:
                if any(filename.lower().endswith(ext.lower()) for ext in asset_extensions):
                    source_file_path = os.path.join(root, filename)
                    # Calculate relative path from the *source* folder to maintain structure
                    relative_path = os.path.relpath(source_file_path, folder_path)
                    destination_file_path = os.path.join(assets_dest_dir, relative_path)

                    os.makedirs(os.path.dirname(destination_file_path), exist_ok=True)
                    shutil.copy2(source_file_path, destination_file_path)
                    copied_count += 1

        if copied_count > 0:
            print(f"Files copied: {copied_count} file(s) from {folder_path}.")
        else:
            print(f"No files found with extensions {asset_extensions} in {folder_path}.")

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
def create_godot_project(project_name: str, project_path: str, asset_folders: list, scripts_folder: str, addons_folder: str, json_path: str, asset_extensions: list, godot_executable: str, no_exit: bool) -> None:
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
        with open(project_godot_path, "w") as f:
            f.write(project_file_content)
        print(f"Created project.godot file.")

    # 1. Copy assets and run importer
    if not os.path.exists(os.path.join(project_dir, ".godot")): # Use .godot folder as import marker
        copy_assets(asset_folders, project_dir, asset_extensions)
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


def main(project_name: str, repo_root: str, no_exit: bool) -> None:
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
        no_exit=no_exit # Pass the flag down
    )

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Godot Project Setup")
    parser.add_argument("--project-name", default="Game", help="Name of the Godot project")
    parser.add_argument("--repo-root", required=True, help="Path to the repository root directory")
    parser.add_argument("--no-exit", action="store_true", help="Do not exit Godot after running the GDScript (for debugging purposes)")
    args = parser.parse_args()
    
    main(
        project_name=args.project_name,
        repo_root=args.repo_root,
        no_exit=args.no_exit
    )
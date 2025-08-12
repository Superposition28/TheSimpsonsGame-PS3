"""
RemakeRegistry\Games\TheSimpsonsGame PS3\Godot\init.py
"""

import os
import shutil
import subprocess
import json

"""
godot node scheme

each node corresponds to a scene file
each scene file corresponds to a folder
each scene folder contains the files contained in that scene node

- Node4D : Node4D.tscn
    - Node3D : Node4D/Node3D.tscn
    - Node2D : Node4D/Node2D.tscn
        - Control : Node4D/Node2D/Control.tscn

Folder Structure:

res://assets
- Node4D/
    - Node2D/
        - Control/
        - Control.tscn
    - Node2D.tscn

    - Node3D/
    - Node3D.tscn

- Node4D.tscn

"""

def create_godot_project(project_name: str, project_path: str, folders_to_copy: list, script_path: str, json_path: str, asset_extensions: list, godot_executable: str="godot") -> None:
    """Creates a Godot project with the given name and assets."""
    print(f"--- Starting create_godot_project ---")
    print(f"project_name: {project_name}")
    print(f"project_path: {project_path}")
    print(f"folders_to_copy: {folders_to_copy}")
    print(f"script_path: {script_path}")
    print(f"json_path: {json_path}")
    print(f"asset_extensions: {asset_extensions}")
    print(f"godot_executable: {godot_executable}")

    project_dir = os.path.join(project_path, project_name)
    print(f"project_dir: {project_dir}")

    os.makedirs(project_dir, exist_ok=True)

    # Create a basic project.godot
    # Ensure the main scene path uses forward slashes for Godot compatibility
    main_scene_godot_path = "res://Node4D.tscn"
    print(f"main_scene_godot_path: {main_scene_godot_path}")
    project_file_content = f"""
    [gd_engine]
    config_version=5

    [application]
    config/name="{project_name}"
    run/main_scene="{main_scene_godot_path}"
    config/features=PackedStringArray("4.3", "Forward Plus")
    config/icon="res://icon.svg"
    """
    print(f"project_file_content:\n{project_file_content}")

    project_godot_path = os.path.join(project_dir, "project.godot")
    print(f"Writing to project.godot at: {project_godot_path}")
    with open(project_godot_path, "w") as f:
        f.write(project_file_content.strip())

    # Copy specified folders recursively, filtering by extensions and maintaining structure
    for folder_path in folders_to_copy:
        print(f"Processing folder to copy: {folder_path}")
        if os.path.exists(folder_path):
            print(f"Copying files with extensions {asset_extensions} from {folder_path} to {project_dir}...")
            copied_count = 0
            for root, dirs, files in os.walk(folder_path):
                print(f"Walking directory: root={root}, dirs={dirs}, files={files}")
                for filename in files:
                    if any(filename.lower().endswith(ext.lower()) for ext in asset_extensions):
                        source_file_path = os.path.join(root, filename)
                        # Calculate relative path to maintain structure
                        relative_path = os.path.relpath(source_file_path, folder_path)
                        destination_file_path = os.path.join(project_dir, 'assets', relative_path)

                        # Ensure destination directory exists
                        destination_dir = os.path.dirname(destination_file_path)
                        os.makedirs(destination_dir, exist_ok=True)

                        # Copy the file
                        shutil.copy2(source_file_path, destination_file_path)
                        copied_count += 1
            if copied_count > 0:
                print(f"Files copied: {copied_count} file(s) from {folder_path}.")
            else:
                print(f"No files found with extensions {asset_extensions} in {folder_path}.")
        else:
            print(f"Folder path does not exist: {folder_path}")

    # Copy scene_config.json into the project
    if os.path.exists(json_path):
        dest_json_path = os.path.join(project_dir, "scene_config.json")
        print(f"Copying {json_path} to {dest_json_path}")
        shutil.copy2(json_path, dest_json_path)
        print("scene_config.json copied into the project.")
    else:
        print(f"JSON config path does not exist: {json_path}")

    # Copy the EditorScript into the project directory
    editor_script_dest_path = os.path.join(project_dir, os.path.basename(script_path))
    print(f"editor_script_dest_path: {editor_script_dest_path}")
    if os.path.exists(script_path):
        print(f"Copying {script_path} to {editor_script_dest_path}")
        shutil.copy2(script_path, editor_script_dest_path)
        print(f"{os.path.basename(script_path)} copied into the project.")
    else:
        print(f"Editor script path does not exist: {script_path}")
        return # Exit if the script doesn't exist

    # Construct the res:// path for the script
    script_res_path = os.path.basename(script_path)
    print(f"script_res_path: {script_res_path}")

    # Run the pass1 init GDScript
    command = [
        godot_executable,
        #"--headless",
        "--editor",
        "--path", project_dir,
        "--build-solutions",
        "--verbose",
        "--script", "res://assets/_InitScript.gd" # Use the res:// path inside the project
    ]
    print(f"Running Godot command: {command}")
    subprocess.run(command)

    # run pass2 ready script
    pass2command = [
        godot_executable,
        #"--headless",
        "--editor",
        "--path", project_dir,
        "--build-solutions",
        "--verbose",
        "--script", "res://assets/_Ready.gd"
    ]
    print(f"Running Godot command: {pass2command}")
    subprocess.run(pass2command)

    print("Godot editor script execution attempted.") # Changed message for clarity

# Example usage:
if __name__ == "__main__":
    print("--- Starting script execution ---")

    # locate project.json in this or parent or parent parent directory
    # and use that as the project path
    current_dir = os.path.dirname(os.path.abspath(__file__))
    print(f"Initial current_dir: {current_dir}")

    folders_to_copy = []

    # if current dir contains project.json set asset_path ./GameFiles/Models/tmp
    # else if parent dir contains project.json set asset_path Modules/Model/GameFiles/Models/tmp
    project_path = ""
    search_dir = current_dir
    for i in range(5):
        print(f"\nSearch iteration {i}")
        print(f"search_dir: {search_dir}")
        potential_path = os.path.join(search_dir, 'project.json')
        print(f"potential_path: {potential_path}")
        if os.path.exists(potential_path):
            print("project.json found.")
            project_path = search_dir
            print(f"project_path set to: {project_path}")
            if i == 0:
                print("project.json in current directory (i=0)")
                folders_to_copy = [
                    os.path.join(search_dir, "GameFiles", "ExtractedOut"),
                    os.path.join(current_dir, "Scripts")
                ]
                print(f"folders_to_copy set to: {folders_to_copy}")
            elif i > 0:
                print(f"project.json in parent directory (i={i})")
                # parent dir
                folders_to_copy = [
                    os.path.join(search_dir, "GameFiles", "ExtractedOut"),
                    os.path.join(current_dir, "Scripts")
                ]
                print(f"folders_to_copy set to: {folders_to_copy}")
                project_path = os.path.join(current_dir, 'GameFiles', 'GodotGame')
                print(f"project_path updated to: {project_path}")
            else:
                # fallback, just use a default or None
                assets_path = None
                print(f"assets_path set to: {assets_path}")
            break
        search_dir = os.path.dirname(search_dir)

    json_path = os.path.join(current_dir, 'scene_config.json')

    print("\n--- Final Configuration ---")
    print(f"Project path: {project_path}")
    print(f"Folders to copy: {folders_to_copy}")
    print(f"JSON config path: {json_path}")
    print(f"current_dir: {current_dir}")
    print("---------------------------\n")


    create_godot_project(
        project_name="Game",
        project_path=project_path,
        folders_to_copy=folders_to_copy,
        script_path=os.path.join(current_dir, "Scripts\\_InitScript.gd"),
        json_path=json_path,
        asset_extensions=[".gd", ".png", ".glb", ".fbx", ".blend"],
        godot_executable="A:\\Godot_v4.4.1-stable_mono_win64\\Godot_v4.4.1-stable_mono_win64_console.exe"
    )

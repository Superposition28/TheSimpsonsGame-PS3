import subprocess
import os
import json
import tempfile
import shutil

BLENDER_EXE = r"A:\RemakeEngine\Main\EngineApps\Tools\Blender-4.5.4-win-x64\blender.exe"
PYTHON_DRIVER = r"A:\RemakeEngine\Main\EngineApps\Games\TheSimpsonsGame-PS3\operations\Blender\MainPreinstancedConvert.py"
PYTHON_EXT = r"A:\RemakeEngine\Main\EngineApps\Games\TheSimpsonsGame-PS3\operations\Blender\blender_addon"
GAME_ROOT = r"A:\RemakeEngine\Main\EngineApps\Games\TheSimpsonsGame-PS3"
BLENDER_DIR = r"A:\RemakeEngine\Main\EngineApps\Games\TheSimpsonsGame-PS3\operations\Blender"

BLANK_BLEND = r"A:\RemakeEngine\Main\EngineApps\Games\TheSimpsonsGame-PS3\blank.blend"
BASE_ASSET_PATH = r"A:\RemakeEngine\Main\EngineApps\Games\TheSimpsonsGame-PS3\GameFiles\EU-FullFlattened-audio_reorg-isRenamed"

# Get the directory where test.py is currently located
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
# Define the local output folder
LOCAL_BLEND_DIR = os.path.join(SCRIPT_DIR, "blend")

def find_assets_in_config(data):
    assets = []
    if isinstance(data, list):
        for item in data:
            assets.extend(find_assets_in_config(item))
    elif isinstance(data, dict):
        if "asset" in data and "asset_id" in data["asset"]:
            assets.append({
                "name": data.get("name", "unknown"),
                "id": data["asset"]["asset_id"]
            })
        for key, value in data.items():
            if key == "children":
                assets.extend(find_assets_in_config(value))
    return assets

def run_batch_test(config_path, map_path):
    # Ensure our local testing directory exists
    os.makedirs(LOCAL_BLEND_DIR, exist_ok=True)
    print(f"Test outputs will be saved to: {LOCAL_BLEND_DIR}")

    with open(config_path, 'r') as f:
        config_data = json.load(f)
    with open(map_path, 'r') as f:
        norm_map = json.load(f)

    path_lookup = {item['uid']: item['new_path'] for item in norm_map}
    found_assets = find_assets_in_config(config_data)
    batch_entries = []

    print(f"Checking {len(found_assets)} assets found in config...")

    for asset in found_assets:
        uid = asset['id']
        if uid in path_lookup:
            relative_path = path_lookup[uid]

            # The original preinstanced file remains in its deep directory
            preinstanced_file_path = os.path.normpath(os.path.join(BASE_ASSET_PATH, relative_path))

            # Reroute the outputs to the local blend folder using the asset UID as the filename
            blend_file_path = os.path.join(LOCAL_BLEND_DIR, f"{uid}.blend")
            glb_file_path = os.path.join(LOCAL_BLEND_DIR, f"{uid}.glb")
            fbx_file_path = os.path.join(LOCAL_BLEND_DIR, f"{uid}.fbx")

            # Copy the blank blend file to the new local destination
            shutil.copy2(BLANK_BLEND, blend_file_path)

            batch_entries.append({
                "asset_id": uid,
                "blend_file": blend_file_path,
                "preinstanced_file": preinstanced_file_path,
                "glb_file": glb_file_path,
                "fbx_file": fbx_file_path
            })
        else:
            print(f"Warning: Asset ID {uid} ({asset['name']}) not found in normalized_map.json")

    if not batch_entries:
        print("No valid assets to process. Exiting.")
        return

    temp_dir_obj = tempfile.TemporaryDirectory(prefix="blender_test_")
    temp_addon_dir = temp_dir_obj.name

    temp_batch = os.path.join(temp_addon_dir, "temp_batch_test.json")
    with open(temp_batch, "w") as f:
        json.dump(batch_entries, f, indent=4)

    cmd = [
        BLENDER_EXE, "-b",
        "--python", PYTHON_DRIVER,
        "--",
        "--batch_file", temp_batch,
        "--python_extension_path", PYTHON_EXT,
        "--current_dir", BLENDER_DIR,
        "--temp_addon_dir", temp_addon_dir,
        "--game_root_path", GAME_ROOT,
        "--export_formats", "",
        "--db_path", r"A:\RemakeEngine\Main\EngineApps\Games\TheSimpsonsGame-PS3\GameFiles\EU-FullFlattened-audio_reorg-isRenamed\normalized_map.json",
        "--verbose"
    ]

    print(f"\n--- Launching Blender to process {len(batch_entries)} assets ---")
    try:
        process = subprocess.run(cmd, capture_output=False)
        if process.returncode == 0:
            print("\nBatch processing finished successfully.")
        else:
            print(f"\nBlender returned error code: {process.returncode}")
    finally:
        temp_dir_obj.cleanup()

if __name__ == "__main__":
    config = r"A:\RemakeEngine\Main\EngineApps\Games\TheSimpsonsGame-PS3\Godot\Core\Json\Node4D\Node3D\Levels\L02_BartmanBegins.json"
    mapping = r"A:\RemakeEngine\Main\EngineApps\Games\TheSimpsonsGame-PS3\GameFiles\EU-FullFlattened-audio_reorg-isRenamed\normalized_map.json"

    if not os.path.exists(BLANK_BLEND):
        print(f"ERROR: Cannot find blank blend file at {BLANK_BLEND}")
    else:
        run_batch_test(config, mapping)
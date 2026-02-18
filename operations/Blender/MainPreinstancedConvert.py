# EngineApps\Games\TheSimpsonsGame-PS3\Scripts\Blender\MainPreinstancedConvert.py
"""
This script automates the process of opening a Blender file, importing a .preinstanced file,
exporting the scene to .glb format, and then quitting Blender.
It uses specific exception handling for robust error reporting.
"""

# --- Imports and Setup ---
import bpy # pyright: ignore[reportMissingImports]
import sys
import os
import time
import importlib
from dataclasses import dataclass
from typing import Set, Optional

# --- Constants ---
ADDON_MODULE_NAME = 'PreinstancedImportExtension'
LOG_TEXT_BLOCK_NAME = "SimpGame_Import_Log"

# --- MODIFIED: Custom Exception for Better Error Handling ---
class BlenderScriptError(Exception):
    """Custom exception for clear, predictable errors within the script's workflow."""
    pass

# --- Configuration Data Class ---
@dataclass
class ScriptConfig:
    """A data class to hold all script configuration parameters."""
    base_blend_file: str
    input_preinstanced_file: str
    output_glb: str
    python_extension_file: str
    current_dir: str
    verbose: bool
    debug_sleep: bool
    export_formats: Optional[Set[str]]
    asset_id: str
    temp_addon_dir: str
    main_db_path: str
    game_root_path: str
    output_fbx: Optional[str] = None

# --- Utility and Logging Functions ---

def printc(message: str, colour: Optional[str] = None) -> None:
    """Prints a message to the console with optional colour support."""
    colours = { 'red': '\033[91m', 'green': '\033[92m', 'yellow': '\033[93m', 'blue': '\033[94m', 'magenta': '\033[95m', 'cyan': '\033[96m', 'white': '\033[97m', 'darkcyan': '\033[36m', 'darkyellow': '\033[33m', 'darkred': '\033[31m', 'reset': '\033[0m' }
    endc = colours['reset']
    prefix = f"{colours['magenta']}BLENDER-SCRIPT:{endc}"
    if colour and colour.lower() in colours:
        print(f"{prefix} {colours[colour.lower()]}{message}{endc}")
    else:
        print(f"{prefix} {colours['darkcyan']}{message}{endc}")

def log_to_blender(text: str) -> None:
    """Appends a message to a text block in Blender's text editor and prints to console."""
    printc(text)
    if hasattr(bpy.data, "texts"):
        if LOG_TEXT_BLOCK_NAME not in bpy.data.texts:
            bpy.data.texts.new(LOG_TEXT_BLOCK_NAME)
        bpy.data.texts[LOG_TEXT_BLOCK_NAME].write(text + "\n")

def log_to_file(text: str, log_directory: str) -> None:
    """Appends a message to a log file in the specified directory."""
    if not os.path.isdir(log_directory):
        printc(f"Log directory does not exist, cannot write log file: {log_directory}", colour='red')
        return
    file_path = os.path.join(log_directory, "blend.log")
    try:
        with open(file_path, "a", encoding='utf-8') as log_file:
            log_file.write(f"{time.strftime('%Y-%m-%d %H:%M:%S')} - {text}\n")
    except Exception as e:
        printc(f"Error writing to log file: {e}", colour='red')

# --- Core Logic Functions ---

def get_script_config() -> ScriptConfig:
    """Parses command-line arguments and returns a populated ScriptConfig object."""
    try:
        argv = sys.argv
        arg_start_index = argv.index('--') + 1
        def to_bool(arg_str: str) -> bool: return arg_str.strip().lower() == "true"
        return ScriptConfig(
            base_blend_file=argv[arg_start_index],
            input_preinstanced_file=argv[arg_start_index + 1],
            output_glb=argv[arg_start_index + 2],
            python_extension_file=argv[arg_start_index + 3],
            verbose=to_bool(argv[arg_start_index + 4]),
            debug_sleep=to_bool(argv[arg_start_index + 5]),
            current_dir=argv[arg_start_index + 6],
            output_fbx=argv[arg_start_index + 7],
            asset_id=argv[arg_start_index + 8],
            temp_addon_dir=argv[arg_start_index + 9],
            main_db_path=argv[arg_start_index + 10],
            game_root_path=argv[arg_start_index + 11],
            export_formats={fmt.strip() for fmt in argv[arg_start_index + 12].lower().replace(",", " ").split() if fmt.strip() in {"glb", "fbx"}} or None,
        )
    except (ValueError, IndexError) as e:
        printc("Usage: ... -- <base.blend> ... <asset_id> <temp_addon_dir> <main_db_path> <game_root_path> <export_formats>", colour='yellow')
        raise BlenderScriptError(f"Argument parsing failed: {e}") from e

def log_script_config(config: ScriptConfig) -> None:
    log_to_blender("Script started with arguments:")
    for i, (key, value) in enumerate(vars(config).items()):
        log_to_blender(f"{i+1}: {key}: {value}")
    printc("-" * 20)

def validate_file_paths(config: ScriptConfig) -> None:
    """Validates that all necessary input files and output directories exist."""
    log_to_blender("Validating file paths...")
    paths_to_check = {"Blend file": config.base_blend_file, "Preinstanced file": config.input_preinstanced_file, "Python extension file": config.python_extension_file}
    for name, path in paths_to_check.items():
        if not os.path.exists(path):
            raise FileNotFoundError(f"{name} not found at: {path}")
        log_to_blender(f"   - Found {name}: {path}")
    output_dir = os.path.dirname(config.output_glb)
    if output_dir and not os.path.exists(output_dir):
        raise FileNotFoundError(f"Output directory does not exist: {output_dir}")
    log_to_blender("All paths validated successfully.")

def setup_blender_environment(config: ScriptConfig) -> None:
    """Loads the addon directly from source without installing it to the global user dir."""
    try:
        log_to_blender(f"Opening blend file: {config.base_blend_file}")
        bpy.ops.wm.open_mainfile(filepath=config.base_blend_file)
        log_to_blender("Blend file opened successfully.")

        # Set the texture DB path from the config argument
        log_to_blender("Setting dynamic DB path...")
        db_path = config.main_db_path
        if db_path and os.path.exists(db_path):
            bpy.context.scene["tsg_db_path"] = db_path
            log_to_blender(f"Set scene property 'tsg_db_path' to: {db_path}")
        elif db_path:
            log_to_blender(f"Warning: Texture DB path not found: {db_path}")
        else:
            log_to_blender("Warning: No texture DB path was provided.")

        if not config.game_root_path or not os.path.exists(config.game_root_path):
            log_to_blender(f"Warning: Game root path not found or not provided: {config.game_root_path}")
            exit(1)

        # Create tsg_gameroot_path if it doesn't exist
        if "tsg_gameroot_path" not in bpy.context.scene or bpy.context.scene["tsg_gameroot_path"] != config.game_root_path:
            bpy.context.scene["tsg_gameroot_path"] = config.game_root_path
            log_to_blender(f"Set scene property 'tsg_gameroot_path' to: {config.game_root_path}")
        else:
            log_to_blender(f"Scene property 'tsg_gameroot_path' already set to: {bpy.context.scene['tsg_gameroot_path']}")

        # Direct module loading avoids global addon install race conditions.
        addon_path = os.path.abspath(config.python_extension_file)
        addon_dir = os.path.dirname(addon_path)
        addon_name = os.path.splitext(os.path.basename(addon_path))[0]

        log_to_blender(f"Directly loading addon module '{addon_name}' from '{addon_dir}'...")

        if addon_dir not in sys.path:
            sys.path.append(addon_dir)

        importlib.invalidate_caches()
        if addon_name in sys.modules:
            addon_module = importlib.reload(sys.modules[addon_name])
        else:
            addon_module = importlib.import_module(addon_name)

        if hasattr(addon_module, "register"):
            try:
                addon_module.register()
                log_to_blender(f"Successfully registered '{addon_name}' in memory.")
            except ValueError:
                log_to_blender(f"'{addon_name}' was already registered. Skipping.")
        else:
            raise BlenderScriptError(f"Module '{addon_name}' has no 'register' function.")

    except Exception as e:
        raise BlenderScriptError(f"Error during direct addon loading: {e}") from e

def process_scene(config: ScriptConfig) -> None:
    """Imports the preinstanced file, exports to formats, and saves the blend file."""
    try:
        log_to_blender(f"Importing preinstanced file: {config.input_preinstanced_file}")
        bpy.ops.custom_import_scene.simpgame(filepath=config.input_preinstanced_file)
        log_to_blender("Preinstanced file imported successfully.")

        imported_collection = bpy.data.collections.get("New Mesh")
        if not imported_collection or not imported_collection.objects:
            log_to_file(f"Warning: No objects found in 'New Mesh' collection after import of {os.path.basename(config.input_preinstanced_file)}.", config.current_dir)

        if config.export_formats:
            if 'glb' in config.export_formats:
                log_to_blender(f"Exporting to GLB file: {config.output_glb}")
                bpy.ops.export_scene.gltf(filepath=config.output_glb, export_format='GLB', use_selection=False)
            if 'fbx' in config.export_formats and config.output_fbx:
                log_to_blender(f"Exporting to FBX file: {config.output_fbx}")
                bpy.ops.export_scene.fbx(filepath=config.output_fbx, use_selection=False)

        log_to_blender(f"Saving blend file to: {config.base_blend_file}")
        if bpy.data.is_dirty:
            # Use save_as_mainfile with check_existing=False to avoid "old file (file saved with @)" errors 
            # when using long path prefixes (\\?\) or path variations.
            bpy.ops.wm.save_as_mainfile(filepath=config.base_blend_file, check_existing=False)
        else:
            log_to_blender("No changes to save.")
    except RuntimeError as e:
        raise BlenderScriptError(f"Blender API error during scene processing: {e}") from e

# --- Main Execution ---
def main() -> None:
    """Main function to orchestrate the entire conversion process."""
    config = None
    error_message = ""
    try:
        config = get_script_config()
        log_script_config(config)
        if config.debug_sleep: time.sleep(5)
        validate_file_paths(config)
        setup_blender_environment(config)
        process_scene(config)
        log_to_blender("Script finished successfully.")
    # --- MODIFIED: Specific Exception Handling ---
    except (FileNotFoundError, PermissionError) as e:
        error_message = f"FATAL FILE SYSTEM ERROR: {e}"
    except BlenderScriptError as e:
        error_message = f"FATAL SCRIPT ERROR: {e}"
    except Exception as e:
        # Catch any other unexpected errors
        error_message = f"FATAL UNEXPECTED ERROR: {e}"
    finally:
        if error_message:
            asset_info = f"[Asset ID: {config.asset_id}] " if config else ""
            full_error = f"{error_message} {asset_info}"
            log_to_blender(full_error)

            # Robustly log to file
            log_dir = config.current_dir if config else None
            if not log_dir:
                try: log_dir = sys.argv[sys.argv.index('--') + 8]
                except (ValueError, IndexError): pass
            if log_dir: log_to_file(full_error, log_dir)

            sys.exit(1)

        log_to_blender("Exiting Blender.")
        bpy.ops.wm.quit_blender()

if __name__ == "__main__":
    printc("Blender Python script starting...")
    main()

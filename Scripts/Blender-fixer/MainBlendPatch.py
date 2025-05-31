"""
This script automates the process of opening a Blender file, importing a .preinstanced file,
exporting the scene to .glb format, and then quitting Blender.
It includes cache clearing for Python extensions.
"""

# --- Imports and Setup ---
import bpy
import sys
import os
import time
import shutil
import importlib
import time

global current_dir
# Define the addon module name once
ADDON_MODULE_NAME = 'PreinstancedImportExtension' # <--- MAKE SURE THIS MATCHES YOUR ADDON'S MODULE NAME
# --- End Imports and Setup ---

def printc(message: str, colour: str | None = None) -> None:
    """Prints a message to the console with optional colour support."""
    # Simple colour support for Windows/cmd
    colours = {
        'red': '\033[91m', 'green': '\033[92m', 'yellow': '\033[93m',
        'blue': '\033[94m', 'magenta': '\033[95m', 'cyan': '\033[96m',
        'white': '\033[97m', 'darkcyan': '\033[36m', 'darkyellow': '\033[33m',
        'darkred': '\033[31m', 'reset': '\033[0m'
    }
    endc = '\033[0m'
    if colour and colour.lower() in colours:
        print(f"{colours['magenta']}BLENDER-SCRIPT:{endc} {colours[colour.lower()]}{message}{endc}")
    else:
        print(f"{colours['magenta']}BLENDER-SCRIPT:{endc} {colours['darkcyan']}{message}{endc}")


# --- Logging Function ---
def log_to_blender(text: str, block_name: str = "SimpGame_Import_Log", to_blender_editor: bool = False) -> None:
    """Appends a message to a text block in Blender's text editor if requested, and always prints to console."""
    # Print to the console for immediate feedback
    printc(text)

    # Only try to write to Blender's text editor if requested and bpy.data has 'texts'
    if to_blender_editor and hasattr(bpy.data, "texts"):
        if block_name not in bpy.data.texts:
            text_block = bpy.data.texts.new(block_name)
        else:
            text_block = bpy.data.texts[block_name]
        text_block.write(text + "\n")

def log_to_file(text: str) -> None:
    """Appends a message to a log file."""
    global current_dir
    #time.sleep(5)
    file_path = os.path.join(current_dir, "blend.log")

    try:
        with open(file_path, "a") as log_file:
            log_file.write(text + "\n")
    except Exception as e:
        printc(f"Error writing to log file: {e}")
# --- End Logging Function ---


# --- Cache Clearing Function ---
def clear_addon_cache() -> None:
    """Deletes __pycache__ directories from the Blender user scripts/addons path."""
    log_to_blender("Attempting to clear addon Python cache...")
    try:
        # Get the path to the user's addons directory for the current Blender version
        addons_path = bpy.utils.user_resource('SCRIPTS', path='addons')
        log_to_blender(f"Checking for cache in: {addons_path}")

        if not os.path.exists(addons_path):
            log_to_blender(f"Warning: Addons path not found: {addons_path}. No cache to clear.", to_blender_editor=True) # Log warning to editor
            return

        cache_cleared = False
        # Walk through the addons directory to find __pycache__ folders
        for dirpath, dirnames, filenames in os.walk(addons_path):
            if '__pycache__' in dirnames:
                cache_path = os.path.join(dirpath, '__pycache__')
                log_to_blender(f"Deleting cache directory: {cache_path}")
                try:
                    shutil.rmtree(cache_path)
                    cache_cleared = True
                except OSError as e:
                    log_to_blender(f"Error deleting cache directory {cache_path}: {e}", to_blender_editor=True) # Log error to editor
                except Exception as e:
                    log_to_blender(f"An unexpected error occurred while deleting cache {cache_path}: {e}", to_blender_editor=True) # Log error to editor

        if cache_cleared:
            log_to_blender("Addon Python cache clearing process completed.")
        else:
            log_to_blender("No addon Python cache directories found or cleared.")

    except Exception as e:
        log_to_blender(f"An error occurred during cache clearing: {e}", to_blender_editor=True) # Log error to editor
# --- End Cache Clearing Function ---


# --- Script Execution Starts Here ---
def main():
    try:
        # --- Argument Parsing ---
        try:
            argv_start_index = sys.argv.index('--') + 1
            base_blend_file = sys.argv[argv_start_index]
            input_preinstanced_file = sys.argv[argv_start_index + 1]
            output_glb = sys.argv[argv_start_index + 2]
            pythonextension_file = sys.argv[argv_start_index + 3]

            verbose_arg = sys.argv[argv_start_index + 4].lower()
            if verbose_arg == "true":
                verbose = True
            elif verbose_arg == "false":
                verbose = False

            debugsleep_arg = sys.argv[argv_start_index + 5].strip().lower()
            if debugsleep_arg == "true":
                debugsleep = True
            elif debugsleep_arg == "false":
                debugsleep = False

            # get argument for optional export to glb/fbx
            export_arg = sys.argv[argv_start_index + 6].lower().replace(",", " ").split()
            export = set(x.strip() for x in export_arg if x.strip() in {"glb", "fbx"}) or None
            if verbose:
                printc(f"Export formats: {export}")

            global current_dir
            current_dir_arg = sys.argv[argv_start_index + 7].lower()
            current_dir = current_dir_arg

        except (ValueError, IndexError) as e:
            printc(f"Error parsing arguments: {e}")
            printc("Usage: blender -b --python <script_name.py> -- <base_blend_file> <input_preinstanced_file> <output_glb> <pythonextension_file> <verbose> <debugsleep>")
            sys.exit(1)
        # --- End Argument Parsing ---

        # --- Log Arguments ---
        #if verbose:
        printc(f"Script started with arguments:")
        printc(f"1: base_blend_file: {base_blend_file}")
        printc(f"2: input_preinstanced_file: {input_preinstanced_file}")
        printc(f"3: output_glb: {output_glb}")
        printc(f"4: pythonextension_file: {pythonextension_file}")
        printc(f"5: verbose: {verbose}")
        printc(f"6: debugsleep: {debugsleep}")
        printc(f"7: export: {export}")
        if 'glb' in export:
            printc(f"8: Exporting to GLB file: {output_glb}")
        if 'fbx' in export:
            # get fbx path/name from output_glb, remove .glb and add .fbx
            output_fbx = os.path.splitext(output_glb)[0] + ".fbx"
            printc(f"8: Exporting to FBX file: {output_fbx}")
        printc("-" * 20)
        # --- End Log Arguments ---


        if debugsleep:
            log_to_blender("Debug sleep mode enabled. The script will pause for debugging.")
            time.sleep(5)

        # --- Argument Validation ---
        # Check if base_blend_file exists
        if not os.path.exists(base_blend_file):
            log_to_blender(f"9: Error: Blend file not found: {base_blend_file}", to_blender_editor=True) # Log error to editor
            if debugsleep: time.sleep(5)
            sys.exit(1) # Use sys.exit for script termination
        log_to_blender(f"10: Blend file exists: {base_blend_file}")

        # Check if input_preinstanced_file exists
        if not os.path.exists(input_preinstanced_file):
            log_to_blender(f"11: Error: Preinstanced file not found: {input_preinstanced_file}", to_blender_editor=True) # Log error to editor
            if debugsleep: time.sleep(5)
            sys.exit(1)
        log_to_blender(f"12: Preinstanced file exists: {input_preinstanced_file}", to_blender_editor=True) # Log path to editor

        # Get the directory for output_glb and check if it exists
        output_dir = os.path.dirname(output_glb)

        # Your check for output directory assuming it's a symbolic link and cannot be made by makedirs
        # If the parent directory of the symbolic link needs to exist, this check is relevant.
        # If the symbolic link itself needs to exist beforehand, you might check os.path.exists(output_glb) earlier
        # and handle the case where the target doesn't exist yet.
        # The original script's logic here seems intended for a specific setup where the output dir
        # is a symlink and makedirs won't work on it, but the path *should* exist.
        if output_dir and not os.path.exists(output_dir):
            log_to_blender(f"13: Error: Output directory does not exist (and cannot be created/checked as symlink target): {output_dir}", to_blender_editor=True) # Log error to editor
            if debugsleep: time.sleep(5)
            sys.exit(1)
        elif output_dir:
            log_to_blender(f"14: Output directory exists: {output_dir}")


        # Check if pythonextension_file exists
        if not os.path.exists(pythonextension_file):
            log_to_blender(f"16: Error: Python extension file not found: {pythonextension_file}", to_blender_editor=True) # Log error to editor
            if debugsleep: time.sleep(5)
            sys.exit(1)
        log_to_blender(f"17: Python extension file exists: {pythonextension_file}")
        # --- End Argument Validation ---

        # --- Cache Clearing Step ---
        clear_addon_cache() # Keep internal logging to console only
        # --- End Cache Clearing Step ---


        # --- Open Blend File ---
        try:
            # Open the blend file
            bpy.ops.wm.open_mainfile(filepath=base_blend_file)
            log_to_blender(f"18: Blend file opened: {base_blend_file}")
        except Exception as e:
            log_to_blender(f"19: Error opening blend file: {e}", to_blender_editor=True) # Log error to editor
            if debugsleep: time.sleep(5)
            sys.exit(1)
        # --- End Open Blend File ---

        # --- Addon Installation and Enabling ---
        log_to_blender(f"Attempting to install and enable {ADDON_MODULE_NAME} addon from {pythonextension_file}")

        # Use absolute path for installation
        addon_filepath_abs = os.path.abspath(pythonextension_file)

        if not os.path.isfile(addon_filepath_abs):
            log_to_blender(f"Error: Addon file not found at: {addon_filepath_abs}", to_blender_editor=True) # Log error to editor
            if debugsleep: time.sleep(5)
            sys.exit(1)
        else:
            log_to_blender(f"Addon file exists at: {addon_filepath_abs}")

        try:
            # Install the addon, overwriting if it exists
            bpy.ops.preferences.addon_install(filepath=addon_filepath_abs, overwrite=True)
            log_to_blender(f"21: Addon installed/overwritten from: {addon_filepath_abs}")

            # Enable the addon
            bpy.ops.preferences.addon_enable(module=ADDON_MODULE_NAME)
            log_to_blender(f"26: Addon {ADDON_MODULE_NAME} enabled.")

            # Invalidate import caches and attempt to reload the module
            # This helps ensure Blender uses the newly installed/enabled code immediately
            importlib.invalidate_caches()
            # Check if the module is already loaded before attempting to reload
            if ADDON_MODULE_NAME in sys.modules:
                log_to_blender(f"Attempting to reload {ADDON_MODULE_NAME} module.")
                addon_module = importlib.reload(sys.modules[ADDON_MODULE_NAME])
                log_to_blender(f"26.1: Addon {ADDON_MODULE_NAME} reloaded successfully.")
            else:
                # If not already in sys.modules, a standard import should pick up the enabled addon
                log_to_blender(f"{ADDON_MODULE_NAME} module not found in sys.modules, standard import expected on next access.")
                # You might explicitly import it here if you need to access its contents immediately,
                # but enabling should make its operators available.
                # addon_module = importlib.import_module(ADDON_MODULE_NAME)


        except ModuleNotFoundError as e:
            log_to_blender(f"27: Error enabling addon {ADDON_MODULE_NAME}: {e}. Ensure the addon file is correctly installed and named ('{ADDON_MODULE_NAME}').", to_blender_editor=True) # Log error to editor
            if debugsleep: time.sleep(5)
            # Optionally exit here if the core addon is required for import
            # sys.exit(1)
        except Exception as e:
            log_to_blender(f"27: An unexpected error occurred during addon installation/enabling: {e}", to_blender_editor=True) # Log error to editor
            if debugsleep: time.sleep(5)
            # Optionally exit here if the core addon is required for import
            # sys.exit(1)
        # --- End Addon Installation and Enabling ---


        # --- Import Preinstanced File ---
        log_to_blender(f"Importing preinstanced file: {input_preinstanced_file}", to_blender_editor=True) # Log path to editor

        try:
            # Call your custom import operator
            # Ensure the operator bl_idname matches what's registered by your addon
            bpy.ops.custom_import_scene.simpgame(filepath=input_preinstanced_file)
            log_to_blender(f"32: Preinstanced file imported: {input_preinstanced_file}", to_blender_editor=True) # Log path to editor
        except Exception as e:
            log_to_blender(f"33: Error importing preinstanced file: {e}", to_blender_editor=True) # Log error to editor
            if debugsleep: time.sleep(5)
            sys.exit(1) # Exit if import fails

        # Check if any objects were imported (optional but good practice)
        # You might want to check if the collection "New Mesh" is linked and contains objects
        imported_collection = bpy.data.collections.get("New Mesh")
        if not imported_collection or not imported_collection.objects:
            log_to_blender("Warning: No objects found in 'New Mesh' collection after import. Export might be empty.", to_blender_editor=True) # Log warning to editor
            log_to_file("Warning: No objects found in 'New Mesh' collection after import. Export might be empty. for file: " + input_preinstanced_file)
            # Decide if you want to exit here or continue to export an empty/base file
        # --- End Import Preinstanced File ---

        # --- Exporting to GLB/FBX ---
        if export is not None:
            if 'glb' in export:
                log_to_blender(f"Exporting to GLB file: {output_glb}")

                try:
                    # Export the scene to .glb
                    # Ensure output directory exists before exporting
                    output_dir = os.path.dirname(output_glb)
                    if output_dir and not os.path.exists(output_dir):
                        # This check was done earlier, but double-checking before export is safer
                        log_to_blender(f"Error: Output directory does not exist before GLB export: {output_dir}", to_blender_editor=True) # Log error to editor
                        if debugsleep: time.sleep(5)
                        sys.exit(1) # Cannot export if directory doesn't exist
                    elif output_dir:
                        log_to_blender(f"Output directory confirmed before export: {output_dir}")

                    # Select all objects you want to export if necessary,
                    # or export the entire scene if that's the default behavior of gltf exporter
                    # bpy.ops.object.select_all(action='SELECT') # Example: select all objects

                    bpy.ops.export_scene.gltf(filepath=output_glb, export_format='GLB', use_selection=False) # use_selection=False exports everything
                    log_to_blender(f"39: Exported to GLB file: {output_glb}")
                except Exception as e:
                    log_to_blender(f"40: Error exporting to GLB: {e}", to_blender_editor=True) # Log error to editor
                    if debugsleep: time.sleep(5)
                    sys.exit(1) # Exit if export fails

                log_to_blender("41: Export complete. Script finished successfully.")
            if 'fbx' in export:
                # get fbx path/name from output_glb, remove .glb and add .fbx
                output_fbx = os.path.splitext(output_glb)[0] + ".fbx"
                log_to_blender(f"Exporting to FBX file: {output_fbx}")

                try:
                    # Export the scene to .fbx
                    # Ensure output directory exists before exporting
                    output_dir = os.path.dirname(output_fbx)
                    if output_dir and not os.path.exists(output_dir):
                        # This check was done earlier, but double-checking before export is safer
                        log_to_blender(f"Error: Output directory does not exist before FBX export: {output_dir}", to_blender_editor=True) # Log error to editor
                        if debugsleep: time.sleep(5)
                        sys.exit(1) # Cannot export if directory doesn't exist
                    elif output_dir:
                        log_to_blender(f"Output directory confirmed before export: {output_dir}")

                    # Select all objects you want to export if necessary,
                    # or export the entire scene if that's the default behavior of gltf exporter
                    # bpy.ops.object.select_all(action='SELECT') # Example: select all objects

                    bpy.ops.export_scene.fbx(filepath=output_fbx, use_selection=False) # use_selection=False exports everything
                    log_to_blender(f"39: Exported to FBX file: {output_fbx}")
                except Exception as e:
                    log_to_blender(f"40: Error exporting to FBX: {e}", to_blender_editor=True) # Log error to editor
                    if debugsleep: time.sleep(5)
                    sys.exit(1) # Exit if export fails

                log_to_blender("41: Export complete. Script finished successfully.")
        # --- End Exporting to GLB/FBX ---

        # --- Saving the Blend File ---
        try:
            # Save the import changes to the blend file
            saved_blend_file_path = base_blend_file

            log_to_blender(f"34: Saving blend file to: {saved_blend_file_path}")

            # Save the blend file
            if bpy.data.is_dirty:
                bpy.ops.wm.save_mainfile(filepath=saved_blend_file_path) # Explicitly set filepath
                log_to_blender(f"37: Saved modified blend file: {saved_blend_file_path}")
            else:
                log_to_blender("37: No changes to save to blend file.")
                sys.exit(1)

        except Exception as e:
            log_to_blender(f"38: Error saving blend file: {e}", to_blender_editor=True) # Log error to editor
            if debugsleep: time.sleep(5)
            # Decide if a save error should stop the GLB export
            # sys.exit(1)
        # --- End Saving the Blend File ---

    # --- Main Exception Handling ---
    except Exception as e:
        # Catch any exceptions not specifically handled above
        log_to_blender(f"45: An unexpected error occurred during script execution: {e}", to_blender_editor=True) # Log error to editor
        if debugsleep: time.sleep(5)
        sys.exit(1) # Ensure script exits on unhandled error
    # --- End Main Exception Handling ---

    # --- Final Cleanup ---
    finally:
        # Ensure Blender quits even if there were errors
        log_to_blender("Exiting Blender.")
        bpy.ops.wm.quit_blender()
    # --- End Final Cleanup ---

if __name__ == "__main__":
    printc("Script started.")
    #time.sleep(3)
    main()

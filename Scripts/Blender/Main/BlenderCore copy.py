
import json
import subprocess
import configparser
from pathlib import Path
import argparse

import os
import sys
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..', '..', '..', '..', 'Utils')))
from printer import print, Colours, print_error, print_verbose, print_debug, printc


global python_script_path, python_extension_file, asset_mapping_file, blender_exe_path

global verbose, debug_sleep, export, current_dir
# Command-line argument parsing
verbose = False
debug_sleep = False
export = set()

# path to this file
current_dir = os.path.dirname(os.path.abspath(__file__))

global python_script_path, python_extension_file, asset_mapping_file, blender_exe_path
python_script_path = "RemakeRegistry/Games/TheSimpsonsGame/Scripts/Blender/MainPreinstancedConvert.py"
python_extension_file = "RemakeRegistry/Games/TheSimpsonsGame/Scripts/Blender/PreinstancedImportExtension.py"
asset_mapping_file = "Tools/Blender/asset_mapping.json"
blender_exe_path = "Tools/Blender/blender-4.0.2-windows-x64/blender.exe"

def blender_processing():
    global python_script_path, python_extension_file, asset_mapping_file, blender_exe_path
    global verbose, debug_sleep, export, current_dir
    loop_count = 0
    print(Colours.DARKGRAY, "Starting Blender processing using asset mapping file...")
    try:
        with open(asset_mapping_file, "r", encoding="utf-8") as f:
            asset_map = json.load(f)
        if isinstance(asset_map, dict):
            for key, asset_info in asset_map.items():
                loop_count += 1
                print(Colours.RESET, "")
                print(Colours.YELLOW, f"Loop Count: {loop_count}")
                print(Colours.RESET, "")
                #print(Colours.CYAN, f"assetInfo: {asset_info}")
                if isinstance(asset_info, dict):
                    required_keys = ["preinstanced_symlink", "blend_symlink", "filename", "glb_symlink"]
                    if all(k in asset_info for k in required_keys):
                        filename = asset_info["filename"]
                        blend_symlink_path = asset_info["blend_symlink"]
                        blend_symlink_file = os.path.join(blend_symlink_path, filename + ".blend")
                        glb_symlink_path = asset_info["glb_symlink"]
                        glb_symlink_file = os.path.join(glb_symlink_path, filename + ".glb")
                        fbx_symlink_path = asset_info["glb_symlink"] # theres no fbx symlink in the asset_mapping file yet so we use the glb symlink folder
                        fbx_symlink_file = os.path.join(fbx_symlink_path, filename + ".fbx")
                        preinstanced_symlink_path = asset_info["preinstanced_symlink"]
                        preinstanced_symlink_file = os.path.join(preinstanced_symlink_path, filename + ".preinstanced")

                        if os.path.isfile(blend_symlink_file):
                            try:
                                if not os.path.isfile(glb_symlink_file) or not os.path.isfile(fbx_symlink_file):
                                    if os.path.isfile(preinstanced_symlink_file):
                                        verbose_str = "true" if verbose else "false"
                                        debug_sleep_str = "true" if debug_sleep else "false"
                                        export_str = ", ".join(export) if export else ""
                                        print(Colours.GRAY, "# Start Blender Output")
                                        args = [
                                            blender_exe_path,
                                            "-b", blend_symlink_file,
                                            "--python", python_script_path,
                                            "--",
                                            blend_symlink_file,
                                            preinstanced_symlink_file,
                                            glb_symlink_file,
                                            python_extension_file,
                                            verbose_str,
                                            debug_sleep_str,
                                            export_str,
                                            current_dir
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
                                        print(Colours.RED, error)
                                        print(Colours.GRAY, "# End Blender Output")
                                        if export == True:
                                            if os.path.isfile(glb_symlink_file):
                                                with open(glb_symlink_file, "r", encoding="utf-8", errors="ignore") as f:
                                                    glb_content = f.read()
                                                if "Error:" in glb_content or "Exception:" in glb_content:
                                                    print(Colours.RED, "Blender encountered an error:")
                                                    for line in glb_content.splitlines():
                                                        if "Error:" in line or "Exception:" in line:
                                                            print(Colours.RED, f"  {line}")
                                                    blank_blender_file = "blank.blend"
                                                    if os.path.isfile(blank_blender_file):
                                                        print(Colours.GREEN, f"Blank Blender file exists: {blank_blender_file}")
                                                    else:
                                                        print(Colours.RED, f"Blank Blender file does not exist: {blank_blender_file}")
                                                else:
                                                    print(Colours.GREEN, "Blender executed successfully.")
                                                print(Colours.GREEN, f"Output file created successfully: {glb_symlink_file}")
                                            else:
                                                print(Colours.RED, f"Failed to create output file: {glb_symlink_file}")
                                    else:
                                        print(Colours.RED, f"Error: No corresponding .preinstanced symlink for: {blend_symlink_path}")
                                        sys.exit(1)
                                else:
                                    print(Colours.YELLOW, f"Skipping: .glb and .fbx exists for: {blend_symlink_path}")
                                    print(Colours.GREEN, f"glb file already exists: {glb_symlink_file}")
                                    print(Colours.GREEN, f"fbx file already exists: {fbx_symlink_file}")
                            except Exception as ex:
                                print(Colours.RED, f"Error message: {ex}")
                                sys.exit(1)
                        else:
                            print(Colours.RED, f"Error: 404 Blend symlink not found: {blend_symlink_file}")
                            sys.exit(1)
                    else:
                        print(Colours.YELLOW, f"Warning: Missing required properties in asset mapping entry for key: {key}")
                else:
                    print(Colours.YELLOW, f"Warning: Asset info for key: {key} is not a JSON object.")
        else:
            print(Colours.RED, "Error: Asset mapping file does not contain a JSON object at the root.")
    except FileNotFoundError:
        print(Colours.RED, f"Error: Asset mapping file not found: {asset_mapping_file}")
        sys.exit(1)
    except json.JSONDecodeError as ex:
        print(Colours.RED, f"Error: Failed to read or parse the asset mapping JSON file: {asset_mapping_file}")
        print(ex)
        sys.exit(1)

def main(verbose_param: bool, debug_sleep_param: bool, export_param: set) -> None:
    global verbose, debug_sleep, export

    verbose = verbose_param
    print(Colours.BLUE, f"Verbose mode: {verbose}")
    debug_sleep = debug_sleep_param
    print(Colours.BLUE, f"Debug sleep: {debug_sleep}")
    export = export_param
    print(Colours.BLUE, f"Export formats: {export}")

    print(Colours.BLUE, "Initializing...")

    print(Colours.DARKGRAY, "Blender Processing using asset_mapping.json...")
    blender_processing()
    print(Colours.GREEN, "Processing complete.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Process some settings for Blender asset export.")
    parser.add_argument("--verbose", action="store_true", help="Enable verbose output")
    parser.add_argument("--debug-sleep", action="store_true", help="Enable debug sleep")
    parser.add_argument("--export", type=str, nargs='+', help="Exported imput '--export', 'fbx glb'")

    args = parser.parse_args()
    # expected Namespace(verbose=False, debug_sleep=False, export=['fbx glb'])
    #print(Colours.BLUE, f"Arguments: {args}")

    export = args.export
    #print(Colours.BLUE, f"Export: {export}")

    # Handle the case where the export formats are provided as a single string
    if export is not None:
        # If export is a single string with space-separated values like 'fbx glb'
        if len(export) == 1 and ' ' in export[0]:
            # Split the string into individual formats
            export = export[0].split()
            #print(Colours.BLUE, f"Export formats after split: {export}")

        if len(export) == 2:
            # Unpack to two variables if there are exactly two formats
            export_fbx, export_glb = export
            print(Colours.BLUE, f"Export FBX: {export_fbx}")
            print(Colours.BLUE, f"Export GLB: {export_glb}")
            # create a set from the two variables
            export_set = {export_fbx, export_glb}
        elif len(export) == 1:
            # Handle case where only one export format is provided
            export_single = export[0]
            if export_single == "fbx":
                export_fbx = export_single
            elif export_single == "glb":
                export_glb = export_single
            print(Colours.BLUE, f"Export: {export_single}")
            export_set = {export_single}
        else:
            # Handle the case where the list has an unexpected number of formats
            print(Colours.RED, "Error: Expected one or two export formats.")
            exit(1)
    else:
        print(Colours.RED, "Error: No export formats provided.")
        exit(1)

    main(verbose, debug_sleep, export_set)

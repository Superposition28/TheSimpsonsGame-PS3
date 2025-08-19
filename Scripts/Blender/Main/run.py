"""
This module orchestrates the execution of init and blend CLI commands.
RemakeRegistry\Games\TheSimpsonsGame-PS3\Scripts\Blender\Main\run.py
"""

import subprocess
import sys
from pathlib import Path
import argparse

import time

import os
import sys
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..', '..', '..', '..', 'Engine')))
from Utils.printer import print, Colours, error, print_verbose, print_debug, printc

current_dir = os.path.dirname(os.path.abspath(__file__))

def main(working_dir, preinstanced_dir, blend_dir, glb_dir, output_dir, root_drive, blank_blend_source, verbose, debug_sleep, export_fbx, export_glb, export_single, marker) -> None:
    """Main function to execute init and blend processes as CLI commands."""
    try:

        print(colour=Colours.CYAN, message="Running init")
        init_args = [sys.executable, str(Path(current_dir) / "BlenderInit.py")]
        init_args.extend(["--preinstanced-dir", str(preinstanced_dir)])
        init_args.extend(["--blend-dir", str(blend_dir)])
        init_args.extend(["--glb-dir", str(glb_dir)])
        init_args.extend(["--output-dir", str(output_dir)])
        init_args.extend(["--root-drive", str(root_drive)])
        init_args.extend(["--blank-blend-source", str(blank_blend_source)])
        if debug_sleep == "True":
            init_args.extend(["--debug-sleep"])
        if verbose == "True":
            init_args.extend(["--verbose"])
        init_args.extend(["--marker", str(marker)])

        print(colour=Colours.CYAN, message=f"Running command: {init_args}")

        # Run init script and capture exit code
        init_result = subprocess.run(init_args)
        if init_result.returncode != 0:
            print(colour=Colours.RED, message=f"Init script failed with exit code {init_result.returncode}. Aborting blend script.")
            sys.exit(init_result.returncode)

        print(colour=Colours.CYAN, message="Running blend")

        # Construct CLI arguments
        blend_args = [sys.executable, str(Path(current_dir) / "BlenderCore.py")]

        if verbose == "True":
            blend_args.append("--verbose")

        if debug_sleep == "True":
            blend_args.append("--debug-sleep")

        # Handling export argument for multiple formats
        if export_single is None:
            if export_fbx and export_glb is not None:
                blend_args.extend(["--export", f"{export_fbx} {export_glb}"])
        else:
            blend_args.extend(["--export", export_single])

        blend_args.extend(["--db-file-path", "Tools\\Blender\\asset_map.sqlite"])

        print(colour=Colours.CYAN, message=f"running command: {blend_args}")
        if debug_sleep == "True":
            print(colour=Colours.CYAN, message="debug sleep is true")
            for name, value in locals().items():
                print(colour=Colours.DARK_GREEN, message=f"{name}: {value}")
            time.sleep(15)
        subprocess.run(blend_args, check=True)
    except subprocess.CalledProcessError as e:
        print(colour=Colours.RED, message=f"An error occurred while executing the command: {e}")
        sys.exit(1)

if __name__ == "__main__":
    # Initialize ArgumentParser
    parser = argparse.ArgumentParser(description="Process some settings for Blender asset export.")

    # Add arguments for each of the values
    parser.add_argument("--verbose", action="store_true", help="Enable verbose output")
    parser.add_argument("--debug-sleep", action="store_true", help="Enable debug sleep")
    parser.add_argument("--export", type=str, nargs='+', choices=["fbx", "glb"], help="Export formats (fbx, glb)")

    args = parser.parse_args()

    verbose = args.verbose
    print(colour=Colours.BLUE, message=f"Verbose: {verbose}")
    debug_sleep = str(args.debug_sleep)
    print(colour=Colours.BLUE, message=f"Debug sleep: {debug_sleep}")
    export = args.export

    export_single = None
    export_fbx = None
    export_glb = None


    #verbose = "True"
    #debug_sleep = "False"
    #export = {"fbx", "glb"}

    # Check if export is not None and handle the number of values
    if export is not None:
        if len(export) == 2:
            # Unpack to two variables if there are exactly two formats
            export_fbx, export_glb = export
            print(colour=Colours.BLUE, message=f"Export FBX: {export_fbx}")
            print(colour=Colours.BLUE, message=f"Export GLB: {export_glb}")
        elif len(export) == 1:
            # Handle case where only one export format is provided
            export_single = export[0]
            if export_single == "fbx":
                export_fbx = export_single
            elif export_single == "glb":
                export_glb = export_single
            print(colour=Colours.BLUE, message=f"Export: {export_single}")
        else:
            # Handle the case where the list has an unexpected number of formats
            print(colour=Colours.RED, message="Error: Expected one or two export formats.")
    #else:
        #print(colour=Colours.RED, "Error: No export formats provided.")
        #sys.exit(1)

    working_dir = execution_path = Path.cwd()
    preinstanced_dir = Path(working_dir, "GameFiles", "STROUT")
    blend_dir = Path(working_dir, "GameFiles", "TEMP_BLEND")
    glb_dir = Path(working_dir, "GameFiles", "STROUT")
    output_dir = Path(working_dir, "Tools", "Blender")
    root_drive = Path(os.path.splitdrive(working_dir)[0] + os.sep, "TMP_TSG_LNKS")
    blank_blend_source = Path(working_dir, "RemakeRegistry", "Games", "TheSimpsonsGame-PS3", "blank.blend")
    marker = os.path.join("GameFiles", "STROUT") + os.sep


    main(working_dir, preinstanced_dir, blend_dir, glb_dir, output_dir, root_drive, blank_blend_source, verbose, debug_sleep, export_fbx, export_glb, export_single, marker)

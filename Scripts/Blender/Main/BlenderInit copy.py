
import hashlib
import json
import shutil
import time
import traceback
from pathlib import Path
import argparse

import os
import sys
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..', '..', '..', '..', 'Utils')))
from printer import print, Colours, print_error, print_verbose, print_debug, printc



def extract_map_subdirectory(full_path, markerParam):
    # Normalize path separators
    full_path = full_path.replace('/', os.sep).replace('\\', os.sep)
    marker = markerParam
    idx = full_path.lower().find(marker.lower())
    if idx >= 0:
        after = full_path[idx + len(marker):]
        parts = [p for p in after.split(os.sep) if p]
        if parts:
            return parts[0]
        else:
            print(Colours.CYAN, f"Warning: Could not extract map subdirectory from path: {full_path}")
    else:
        print(Colours.CYAN, f"Warning: Marker '{marker}' not found in path: {full_path}")
        exit(1)
    return "_UNKNOWN_MAP"

def md5_hash(s):
    return hashlib.md5(s.encode('utf-8')).hexdigest()

def generate_asset_mapping(root_drive, preinstanced_root, blend_root, marker, glb_root=None, check_existence=False):
    global VERBOSE
    if not os.path.isdir(preinstanced_root):
        raise FileNotFoundError(f"Preinstanced root directory not found: {preinstanced_root}")
    if not os.path.isdir(blend_root):
        raise FileNotFoundError(f"Blend root directory not found: {blend_root}")
    if glb_root and not os.path.isdir(glb_root):
        os.makedirs(glb_root, exist_ok=True)

    mapping = {}
    preinstanced_root = os.path.abspath(preinstanced_root)
    for dirpath, _, files in os.walk(preinstanced_root):
        for file in files:
            if not file.endswith('.preinstanced'):
                continue
            preinstanced_file = os.path.join(dirpath, file)
            preinstanced_rel = os.path.relpath(preinstanced_file, preinstanced_root)
            blend_rel = os.path.splitext(preinstanced_rel)[0] + '.blend'
            blend_full = os.path.join(blend_root, blend_rel)
            glb_rel = os.path.splitext(preinstanced_rel)[0] + '.glb'
            glb_full = os.path.join(glb_root, glb_rel) if glb_root else None

            if check_existence and not os.path.isfile(blend_full):
                print(Colours.CYAN, f"Warning: Corresponding blend file not found: {blend_full}")
                continue

            map_subdir = extract_map_subdirectory(preinstanced_file, marker)
            if VERBOSE:
                print(Colours.CYAN, f"Extracted Map Subdirectory: {map_subdir} for {preinstanced_file}")

            identifier = md5_hash(preinstanced_rel.replace('\\', '/'))
            asset_info = {
                "map_subdirectory": map_subdir,
                "filename": os.path.splitext(os.path.basename(preinstanced_file))[0],
                "preinstanced_full": preinstanced_file,
                "blend_full": blend_full,
                "glb_full": glb_full
            }
            mapping[identifier] = asset_info
            if glb_root and os.path.isfile(glb_full):
                mapping[identifier]["existing_glb_full"] = glb_full
    return mapping

def create_symlink(src, dst, is_dir=True):
    try:
        if os.path.exists(dst):
            return
        if is_dir:
            os.symlink(src, dst, target_is_directory=True)
        else:
            os.symlink(src, dst)
        print(Colours.CYAN, f"Created symlink: {dst} -> {src}")
    except Exception as e:
        print(Colours.CYAN, f"Error creating symlink {dst} -> {src}: {e}")
        if self.debug_sleep:
            time.sleep(2)

def create_symbolic_links(asset_map, root_drive):
    global VERBOSE
    for identifier, paths in asset_map.items():
        map_subdir = paths.get("map_subdirectory")
        if not map_subdir:
            print(Colours.CYAN, f"Error: Missing map subdirectory for {identifier}. Skipping.")
            continue
        target_base = os.path.join(root_drive, map_subdir)
        os.makedirs(target_base, exist_ok=True)

        # Preinstanced
        preinst = paths.get("preinstanced_full")
        if preinst and os.path.isfile(preinst):
            src_folder = os.path.dirname(preinst)
            link_folder = os.path.join(target_base, f"{identifier}_preinstanced")
            create_symlink(src_folder, link_folder)
            asset_map[identifier]["preinstanced_symlink"] = link_folder

        # Blend
        blend = paths.get("blend_full")
        if blend and os.path.isfile(blend):
            src_folder = os.path.dirname(blend)
            link_folder = os.path.join(target_base, f"{identifier}_blend")
            create_symlink(src_folder, link_folder)
            asset_map[identifier]["blend_symlink"] = link_folder

        # GLB
        glb = paths.get("glb_full")
        if glb:
            src_folder = os.path.dirname(glb)
            if os.path.isdir(src_folder):
                link_folder = os.path.join(target_base, f"{identifier}_glb")
                create_symlink(src_folder, link_folder)
                asset_map[identifier]["glb_symlink"] = link_folder

        print(Colours.CYAN, f"Created symbolic links for {identifier} in {map_subdir}")
        if VERBOSE:
            if self.debug_sleep:
                time.sleep(0.1)

class PreinstancedFileProcessor:
    global VERBOSE
    def __init__(self, input_dir, blend_dir, glb_dir, blank_blend_source, debug_sleep):
        self.input_dir = input_dir
        self.blend_dir = blend_dir
        self.glb_dir = glb_dir
        self.blank_blend_source = blank_blend_source
        self.debug_sleep = debug_sleep

    def process_files(self):
        if not self.input_dir or not os.path.isdir(self.input_dir):
            print(Colours.RED, f"Error: InputDirectory '{self.input_dir}' is not set or does not exist.")
            exit(1)
        if not self.blend_dir:
            print(Colours.RED, "Error: BlendDirectory is not set.")
            exit(1)
        os.makedirs(self.blend_dir, exist_ok=True)
        if not self.glb_dir:
            print(Colours.RED, "Error: GLBOutputDirectory is not set.")
            exit(1)
        os.makedirs(self.glb_dir, exist_ok=True)
        if not self.blank_blend_source or not os.path.isfile(self.blank_blend_source):
            print(Colours.RED, f"Error: BlankBlendSource '{self.blank_blend_source}' is not set or does not exist.")
            exit(1)

        preinstanced_files = []
        for dirpath, _, files in os.walk(self.input_dir):
            for file in files:
                if file.endswith('.preinstanced'):
                    preinstanced_files.append(os.path.join(dirpath, file))

        print(Colours.CYAN, f"Found {len(preinstanced_files)} .preinstanced files in {self.input_dir}.")
        input_dir_abs = os.path.abspath(self.input_dir)

        for preinst in preinstanced_files:
            print(Colours.CYAN, f"Processing preinstanced file: {preinst}")
            rel_path = os.path.relpath(preinst, input_dir_abs)
            blend_dest_dir = os.path.join(self.blend_dir, os.path.dirname(rel_path))
            glb_dest_dir = os.path.join(self.glb_dir, os.path.dirname(rel_path))
            os.makedirs(blend_dest_dir, exist_ok=True)
            os.makedirs(glb_dest_dir, exist_ok=True)
            blend_dest = os.path.join(blend_dest_dir, os.path.splitext(os.path.basename(preinst))[0] + ".blend")
            if not os.path.isfile(blend_dest):
                try:
                    shutil.copy2(self.blank_blend_source, blend_dest)
                    if VERBOSE:
                        print(Colours.CYAN, f"Copied {self.blank_blend_source} to {blend_dest}")
                except Exception as ex:
                    print(Colours.RED, f"Error copying blank blend file to '{blend_dest}': {ex}")
                    if self.debug_sleep:
                        time.sleep(1)
            else:
                if VERBOSE:
                    print(Colours.BLUE, f"{os.path.basename(blend_dest)} already exists, skipping copy.")
            if self.debug_sleep:
                time.sleep(1)
        print(Colours.CYAN, f"Total .preinstanced files processed: {len(preinstanced_files)}")

def run(args):
    global VERBOSE
    print(Colours.CYAN, f"input args: {args}")

    marker = args.marker
    print(Colours.CYAN, f"Marker: {marker}")
    preinstanced_dir = args.preinstanced_dir
    print(Colours.CYAN, f"Preinstanced Directory: {preinstanced_dir}")
    blend_dir = args.blend_dir
    print(Colours.CYAN, f"Blend Directory: {blend_dir}")
    glb_dir = args.glb_dir
    print(Colours.CYAN, f"GLB Directory: {glb_dir}")
    output_dir = args.output_dir
    print(Colours.CYAN, f"Output Directory: {output_dir}")
    output_file = args.output_file
    print(Colours.CYAN, f"Output File: {output_file}")
    root_drive = args.root_drive
    print(Colours.CYAN, f"Root Drive: {root_drive}")
    blank_blend_source = args.blank_blend_source
    print(Colours.CYAN, f"Blank Blend Source: {blank_blend_source}")
    debug_sleep = args.debug_sleep
    print(Colours.CYAN, f"Debug Sleep: {debug_sleep}")
    VERBOSE = args.verbose
    print(Colours.CYAN, f"Verbose: {VERBOSE}")

    # Step 1: Process Preinstanced Files
    print(Colours.CYAN, "--- Step 1: Processing Preinstanced Files ---")
    processor = PreinstancedFileProcessor(
        input_dir=preinstanced_dir,
        blend_dir=blend_dir,
        glb_dir=glb_dir,
        blank_blend_source=blank_blend_source,
        debug_sleep=debug_sleep
    )
    print(Colours.CYAN, f"Starting to process files in: {preinstanced_dir}")
    if debug_sleep:
        time.sleep(1)
    processor.process_files()
    print(Colours.CYAN, "--- Step 1: Completed ---")
    if debug_sleep:
        time.sleep(1)

    # Step 2: Setup Symbolic Link Root Directory
    print(Colours.CYAN, f"--- Step 2: Preparing Symbolic Link Root Directory: {root_drive} ---")
    if os.path.exists(root_drive):
        print(Colours.CYAN, f"Deleting existing root directory for symbolic links: {root_drive}")
        shutil.rmtree(root_drive)
        if debug_sleep:
            time.sleep(1)
    os.makedirs(root_drive, exist_ok=True)
    print(Colours.CYAN, f"Created root directory for symbolic links: {root_drive}")
    if debug_sleep:
        time.sleep(0.5)

    # Step 3: Generate Asset Mapping
    print(Colours.CYAN, "--- Step 3: Generating Asset Map ---")
    if debug_sleep:
        time.sleep(1)
    asset_map = generate_asset_mapping(root_drive, preinstanced_dir, blend_dir, marker, glb_dir, check_existence=False)
    print(Colours.CYAN, f"Generated map for {len(asset_map)} assets.")
    if debug_sleep:
        time.sleep(1)
    print(Colours.CYAN, f"--- Saving initial asset map to: {output_file} ---")
    try:
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(asset_map, f, indent=2, ensure_ascii=False)
        print(Colours.CYAN, f"Initial asset mapping saved to: {output_file}")
    except Exception as ex:
        print(Colours.CYAN, f"ERROR saving initial asset map: {ex}")
        if debug_sleep:
            time.sleep(2)
    if debug_sleep:
        time.sleep(1)

    # Step 4: Create Symbolic Links
    print(Colours.CYAN, f"--- Step 4: Creating Symbolic Links in: {root_drive} ---")
    if debug_sleep:
        time.sleep(1)
    create_symbolic_links(asset_map, root_drive)
    print(Colours.CYAN, "--- Step 4: Symbolic links creation process completed. ---")
    if debug_sleep:
        time.sleep(0.5)

    # Save updated asset map
    print(Colours.CYAN, f"--- Saving updated asset map with symlink paths to: {output_file} ---")
    try:
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(asset_map, f, indent=2, ensure_ascii=False)
        print(Colours.CYAN, f"Successfully saved updated asset mapping to: {output_file}")
    except Exception as ex:
        print(Colours.CYAN, f"ERROR saving updated asset map: {ex}")
        if debug_sleep:
            time.sleep(2)
    if debug_sleep:
        time.sleep(1)

if __name__ == "__main__":
    argsparse = argparse.ArgumentParser(description="Process preinstanced files and create symbolic links.")
    argsparse.add_argument("--preinstanced-dir", type=str, required=True, help="Directory containing preinstanced files.")
    argsparse.add_argument("--blend-dir", type=str, required=True, help="Directory containing blend files.")
    argsparse.add_argument("--glb-dir", type=str, required=True, help="Directory containing glb files.")
    argsparse.add_argument("--output-dir", type=str, required=True, help="Directory to save output files.")
    argsparse.add_argument("--output-file", type=str, required=True, help="File to save the output mapping.")
    argsparse.add_argument("--root-drive", type=str, required=True, help="Root drive for symbolic links.")
    argsparse.add_argument("--blank-blend-source", type=str, required=True, help="Source file for blank blend.")
    argsparse.add_argument("--debug-sleep", type=bool, nargs='?', const=True, default=False, help="Enable debug sleep.")
    argsparse.add_argument("--verbose", type=bool, nargs='?', const=True, default=False, help="Enable verbose output.")
    argsparse.add_argument("--marker", type=str, help="Marker for extracting subdirectory.")
    args = argsparse.parse_args()

    try:
        run(args)
    except Exception as e:
        print(Colours.RED, f"An unexpected ERROR occurred: {type(e).__name__} - {e}")
        print(Colours.RED, traceback.format_exc())
        exit(1)

    print(Colours.CYAN, "Script finished.")

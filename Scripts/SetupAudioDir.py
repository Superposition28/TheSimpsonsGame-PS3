"""
This script prepares the audio source directory for processing.
It takes the source directory path as a command-line argument and organizes
subdirectories within it into 'EN' (English) and 'Global' folders
based on predefined lists, skipping specified language code directories.
"""
import sys
import json
from pathlib import Path
import shutil
import argparse

# # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # #

def organize_source_directories(
    audio_source_dir_str: str,
    language_blacklist: set[str],
    global_dirs: set[str]
) -> None:
    """Moves subdirectories in source_dir to 'EN' or 'Global' subdirectories, excluding language codes."""
    if not audio_source_dir_str:
        print("Error: AUDIO_SOURCE_DIR not provided or empty.", file=sys.stderr)
        sys.exit(1)

    source_path = Path(audio_source_dir_str).resolve()

    if not source_path.is_dir():
        print(f"Error: Audio source directory does not exist: {source_path}", file=sys.stderr)
        sys.exit(1)

    en_dir_name = 'EN'
    en_dir_path = source_path / en_dir_name

    global_dir_name = 'Global'
    global_dir_path = source_path / global_dir_name

    # Create the 'EN' and 'Global' subdirectories if they don't exist
    en_dir_path.mkdir(parents=True, exist_ok=True)
    global_dir_path.mkdir(parents=True, exist_ok=True)

    print(f"Organizing directories in '{source_path}' into '{en_dir_path}' and '{global_dir_path}'...")

    moved_count = 0
    skipped_count = 0
    error_count = 0

    for item in source_path.iterdir():
        if item.is_dir():
            # Skip the target directories themselves and language directories
            if item.name == en_dir_name or item.name == global_dir_name or item.name.lower() in language_blacklist:
                print(f"Skipping directory: '{item.name}'")
                skipped_count += 1
                continue

            # Determine target directory
            target_parent_path = global_dir_path if item.name in global_dirs else en_dir_path
            target_path = target_parent_path / item.name

            print(f"Moving '{item.name}' to '{target_path}'...")
            try:
                # Ensure target doesn't already exist
                if target_path.exists():
                    print(f"Warning: Target directory '{target_path}' already exists. Skipping move for '{item.name}'.", file=sys.stderr)
                    skipped_count += 1
                    continue
                shutil.move(str(item), str(target_path))
                moved_count += 1
            except Exception as e:
                print(f"Error moving directory {item.name} to {target_parent_path.name}: {e}", file=sys.stderr)
                error_count += 1

    print("Directory organization complete.")
    print(f"Moved: {moved_count}, Skipped: {skipped_count}, Errors: {error_count}")


# # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # #

def main(audio_source_dir_str: str) -> None:
    """Main function to run the setup process using the provided audio source directory."""
    # Hardcoded Language Blacklist
    language_blacklist = {'it', 'es', 'fr'}
    print(f"Using hardcoded Language Blacklist: {language_blacklist}")

    # Hardcoded Global Dirs
    global_dirs = {
        '80b_crow', 'amb_airc', 'amb_chao', 'amb_cour', 'amb_dung', 'amb_ext_',
        'amb_fore', 'amb_fren', 'amb_gara', 'amb_int_', 'amb_mans', 'amb_nort',
        'amb_riot', 'amb_shir', 'amb_vent', 'bin_rev0', 'brt_dino', 'brt_dior',
        'brt_myst', 'brt_plan', 'brt_temp', 'bsh_air_', 'bsh_beac', 'bsh_figh',
        'bsh_fire', 'bsh_ice_', 'bsh_vill', 'bsh__air', 'che_cart', 'che_cent',
        'che_mark', 'che_mo_b', 'che_q_an', 'dod_aqua', 'dod_dock', 'gamehub_',
        'gts_full', 'gts_seas', 'gts_stat', 'gts_subu', 'gts_vent', 'gts_viol',
        'mtp_heav', 'mus_simp', 'sss_cont', 'sss_lab_', 'sss_mall'
    }
    print(f"Using hardcoded Global Dirs: {global_dirs}")

    # Organize the source directories using extracted config values
    organize_source_directories(audio_source_dir_str, language_blacklist, global_dirs)

    # Print the final paths for verification
    print(f"Setup operated on Audio Source Dir: {audio_source_dir_str}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Organize audio source subdirectories into 'EN' and 'Global' folders."
    )
    parser.add_argument(
        "audio_source_dir",
        type=str,
        help="The path to the audio source directory to be reorganized."
    )
    args = parser.parse_args()

    main(args.audio_source_dir)

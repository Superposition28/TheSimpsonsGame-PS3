import os
import subprocess
import sys
import config
from core_utils import ensure_dir_exists, get_relative_path

def get_extraction_output_dir(str_file_path: str, input_base_dir: str, output_base_dir: str) -> str | None:
    """Determines the output directory for a given .str file."""
    try:
        abs_str_input_dir = os.path.abspath(input_base_dir)
        abs_file_path = os.path.abspath(str_file_path)

        if not abs_file_path.startswith(abs_str_input_dir):
            print(f"ERROR: File {str_file_path} is not under STR_INPUT_DIR {input_base_dir}. Cannot determine relative path for extraction output.", file=sys.stderr)
            return None

        relative_path_to_str_file = os.path.relpath(abs_file_path, start=abs_str_input_dir)
        # QuickBMS often creates a directory based on the input filename without extension
        output_dir_name = os.path.splitext(relative_path_to_str_file)[0] + "_str"
        full_output_dir = os.path.join(output_base_dir, output_dir_name)
        return full_output_dir
    except Exception as e:
        print(f"Error preparing output directory path for {str_file_path}: {e}", file=sys.stderr)
        return None


def extract_str_file(str_file_path: str, bms_script_path: str, quickbms_exe_path: str, input_dir:str, output_base_dir: str) -> tuple[bool, str | None]:
    """
    Extracts a .str file using QuickBMS.
    Returns a tuple: (success_status, output_directory_path)
    """
    if not str_file_path.lower().endswith('.str'):
        print(f"INFO: {str_file_path} is not a .str file. Skipping extraction.", file=sys.stderr)
        return False, None

    actual_output_dir = get_extraction_output_dir(str_file_path, input_dir, output_base_dir)
    if not actual_output_dir:
        return False, None

    ensure_dir_exists(actual_output_dir)

    print(f"    Extracting {str_file_path} to {actual_output_dir}...")
    try:
        # QuickBMS requires absolute paths or paths relative to its own working directory.
        # Providing absolute paths is safest.
        abs_bms_script = os.path.abspath(bms_script_path)
        abs_str_file = os.path.abspath(str_file_path)
        abs_output_dir = os.path.abspath(actual_output_dir)
        abs_quickbms_exe = os.path.abspath(quickbms_exe_path)

        if not os.path.isfile(abs_quickbms_exe):
            print(f"ERROR: QuickBMS executable not found at {abs_quickbms_exe}.", file=sys.stderr)
            return False, actual_output_dir
        if not os.path.isfile(abs_bms_script):
            print(f"ERROR: BMS script not found at {abs_bms_script}.", file=sys.stderr)
            return False, actual_output_dir

        process_result = subprocess.run(
            [abs_quickbms_exe, "-o", abs_bms_script, abs_str_file, abs_output_dir],
            check=True, capture_output=False, text=True # Let QuickBMS output directly
        )
        print(f"    Successfully extracted: {str_file_path}")
        return True, actual_output_dir
    except subprocess.CalledProcessError as e:
        print(f"ERROR: Extraction failed for {str_file_path} using QuickBMS.", file=sys.stderr)
        print(f"    Return code: {e.returncode}", file=sys.stderr)
        print(f"    Command: {' '.join(e.cmd)}", file=sys.stderr)
        return False, actual_output_dir # Return dir even on failure for potential cleanup or inspection
    except FileNotFoundError: # Should be caught by earlier checks, but good to have
        print(f"ERROR: QuickBMS executable or BMS script not found (path issue).", file=sys.stderr)
        print(f"    Checked QuickBMS: {abs_quickbms_exe}", file=sys.stderr)
        print(f"    Checked BMS script: {abs_bms_script}", file=sys.stderr)
        return False, actual_output_dir
    except Exception as e:
        print(f"An unexpected error occurred during extraction of {str_file_path}: {e}", file=sys.stderr)
        return False, actual_output_dir
import os
import re # Import the regex module
import subprocess # Import the subprocess module

# Define the list of input and output files
file_configs = [
    {"input": "tree\\ENaudio.tree", "output": "ENAudioTree.md"},
    {"input": "tree\\ESaudio.tree", "output": "ESAudioTree.md"},
    {"input": "tree\\FRaudio.tree", "output": "FRAudioTree.md"},
    {"input": "tree\\Globalaudio.tree", "output": "GlobalAudioTree.md"},
    {"input": "tree\\ITaudio.tree", "output": "ITAudioTree.md"},
]

# Pattern: _xxx_ followed by 7 hex characters (case-insensitive) followed by .exa.
pattern = r"_xxx_([0-9a-fA-F]{7})\.exa\."
replacement = r"_xxx_#######.exa."

def run_tree_command(command, output_filepath):
    """Runs the tree command and saves the output to a file."""
    print(f"Running command: {command}")
    try:
        # Use shell=True because of the redirection, capture output
        # Note: Using shell=True can be a security risk if the command comes from untrusted input.
        # In this case, the command is hardcoded, so it's less of a concern.
        # We capture stdout and stderr. check=True raises CalledProcessError on non-zero exit codes.
        # encoding='utf-8', errors='ignore' handles potential encoding issues in the output.
        result = subprocess.run(command, shell=True, capture_output=True, text=True, check=True, encoding='utf-8', errors='ignore')

        # Write the output to the file
        print(f"Writing command output to {os.path.basename(output_filepath)}")
        with open(output_filepath, "w", encoding="utf-8") as f:
            f.write(result.stdout)
        print("Command executed successfully.")
        return True
    except FileNotFoundError:
        print(f"Error: The 'tree' command was not found. Make sure it's in your system's PATH.")
        return False
    except subprocess.CalledProcessError as e:
        print(f"Error executing command: {e}")
        print(f"Stderr: {e.stderr}")
        return False
    except Exception as e:
        print(f"An unexpected error occurred: {e}")
        return False

def process_tree_file(input_filepath, output_filepath, pattern, replacement):
    """Reads a tree file, applies regex, removes duplicates, and writes to markdown."""
    # Check if input file exists
    if not os.path.exists(input_filepath):
        print(f"Input file not found: {input_filepath}. Skipping.")
        return

    # Read the file
    print(f"Reading the file: {os.path.basename(input_filepath)}")
    try:
        with open(input_filepath, "r", encoding="utf-8") as f:
            lines = f.readlines()
    except Exception as e:
        print(f"Error reading file {input_filepath}: {e}")
        return

    # Apply regex substitution before removing duplicates
    print("Applying regex substitution...")
    processed_lines = []
    for line in lines:
        processed_lines.append(re.sub(pattern, replacement, line))

    # Remove duplicates while preserving order using the processed lines
    print("Removing duplicate lines...")
    seen = set()
    unique_lines = []
    for line in processed_lines: # Use processed_lines here
        if line not in seen:
            seen.add(line)
            unique_lines.append(line)

    # Write the cleaned data back to a new file
    print(f"Writing cleaned data to {os.path.basename(output_filepath)}")
    try:
        with open(output_filepath, "w", encoding="utf-8") as f:
            f.writelines(unique_lines)
        print(f"Finished processing {os.path.basename(input_filepath)} -> {os.path.basename(output_filepath)}")
    except Exception as e:
        print(f"Error writing file {output_filepath}: {e}")


# --- Main execution ---
def main():

    script_dir = os.path.dirname(__file__)
    tree_output_dir = os.path.join(script_dir, "tree") # Define the output directory for tree files

    # Create the tree output directory if it doesn't exist
    os.makedirs(tree_output_dir, exist_ok=True)
    print(f"Ensured tree output directory exists: {tree_output_dir}")

    # --- Tree commands for EN, ES, FR, IT, and Global audio files ---
    tree_command = r"tree /A /F A:\Dev\Games\TheSimpsonsGame\PAL\Modules\QBMS_TSG\GameFiles\USRDIR\Assets_1_Audio_Streams\Global"
    tree_output_filename = "Globalaudio.tree"
    tree_output_filepath = os.path.join(tree_output_dir, tree_output_filename) # Use tree_output_dir
    run_tree_command(tree_command, tree_output_filepath)

    tree_command = r"tree /A /F A:\Dev\Games\TheSimpsonsGame\PAL\Modules\QBMS_TSG\GameFiles\USRDIR\Assets_1_Audio_Streams\EN"
    tree_output_filename = "ENaudio.tree"
    tree_output_filepath = os.path.join(tree_output_dir, tree_output_filename) # Use tree_output_dir
    run_tree_command(tree_command, tree_output_filepath)

    tree_command = r"tree /A /F A:\Dev\Games\TheSimpsonsGame\PAL\Modules\QBMS_TSG\GameFiles\USRDIR\Assets_1_Audio_Streams\ES"
    tree_output_filename = "ESaudio.tree"
    tree_output_filepath = os.path.join(tree_output_dir, tree_output_filename) # Use tree_output_dir
    run_tree_command(tree_command, tree_output_filepath)

    tree_command = r"tree /A /F A:\Dev\Games\TheSimpsonsGame\PAL\Modules\QBMS_TSG\GameFiles\USRDIR\Assets_1_Audio_Streams\FR"
    tree_output_filename = "FRaudio.tree"
    tree_output_filepath = os.path.join(tree_output_dir, tree_output_filename) # Use tree_output_dir
    run_tree_command(tree_command, tree_output_filepath)

    tree_command = r"tree /A /F A:\Dev\Games\TheSimpsonsGame\PAL\Modules\QBMS_TSG\GameFiles\USRDIR\Assets_1_Audio_Streams\IT"
    tree_output_filename = "ITaudio.tree"
    tree_output_filepath = os.path.join(tree_output_dir, tree_output_filename) # Use tree_output_dir
    run_tree_command(tree_command, tree_output_filepath)

    # ---  ---

    # Process each configured file pair
    for config in file_configs:
        input_filename = config["input"]
        output_filename = config["output"]
        input_filepath = os.path.join(script_dir, input_filename)
        output_filepath = os.path.join(script_dir, output_filename)

        process_tree_file(input_filepath, output_filepath, pattern, replacement)

    print("Process completed.")

if __name__ == "__main__":
    main()

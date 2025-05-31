import hashlib
import sys
import os

def sha256_file(path: str) -> str | None:
    """Calculates the SHA256 hash of a file."""
    h = hashlib.sha256()
    try:
        with open(path, "rb") as f:
            for chunk in iter(lambda: f.read(8192), b""):
                h.update(chunk)
            return h.hexdigest()
    except IOError as e:
        print(f"ERROR: Error reading file for SHA256 hashing {path}: {e}", file=sys.stderr)
        return None
    except Exception as e:
        print(f"ERROR: Unexpected error during SHA256 hashing for {path}: {e}", file=sys.stderr)
        return None

def md5_string(s: str) -> str:
    """Calculates the MD5 hash of a string."""
    return hashlib.md5(s.encode('utf-8')).hexdigest()

def generate_uuid(file_hash: str, path_hash: str) -> str:
    """Generates a composite UUID from file and path hashes."""
    if not file_hash or not path_hash:
        raise ValueError("File hash and path hash must be provided to generate UUID.")
    return f"{file_hash[:16]}_{path_hash[:16]}"

def get_relative_path(full_path: str, base_path: str) -> str:
    """
    Calculates a relative path. Falls back to full_path if not under base_path.
    Ensures consistent use of forward slashes.
    """
    abs_full_path = os.path.abspath(full_path)
    abs_base_path = os.path.abspath(base_path)
    try:
        if abs_full_path.startswith(abs_base_path):
            rel_path = os.path.relpath(abs_full_path, start=abs_base_path)
        else:
            # If the file is not under the base_path, using its absolute path
            # might be more informative than a potentially misleading relative path.
            # Or, decide on a different strategy, e.g., raise an error or use a placeholder.
            print(f"WARNING: Path {abs_full_path} is not under base {abs_base_path}. Using full path as relative identifier.", file=sys.stderr)
            rel_path = abs_full_path
    except ValueError as e: # Handles cases like different drives on Windows
        print(f"WARNING: Could not make path {abs_full_path} relative to {abs_base_path} (Error: {e}). Using full path.", file=sys.stderr)
        rel_path = abs_full_path
    return rel_path.replace("\\", "/")


def ensure_dir_exists(dir_path: str):
    """Creates a directory if it doesn't exist."""
    try:
        os.makedirs(dir_path, exist_ok=True)
    except OSError as e:
        print(f"ERROR: Could not create directory {dir_path}: {e}", file=sys.stderr)
        raise # Re-raise critical error
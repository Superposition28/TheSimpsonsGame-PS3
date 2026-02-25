"""
Blender Add-on Information and Version Handling
"""

from pathlib import Path
import tomllib

def get_manifest_data():
    """Reads blender_manifest.toml and returns the data dictionary."""
    manifest_path = Path(__file__).parent / "blender_manifest.toml"
    try:
        with open(manifest_path, "rb") as f:
            return tomllib.load(f)
    except Exception:
        return {}

def get_version_tuple(version_str: str) -> tuple[int, int, int]:
    """Converts a version string like '1.5.8' to a tuple (1, 5, 8)."""
    try:
        parts = [int(p) for p in version_str.split(".")]
        while len(parts) < 3:
            parts.append(0)
        return (parts[0], parts[1], parts[2])
    except (ValueError, AttributeError):
        return (0, 0, 0)

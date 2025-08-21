# RemakeRegistry\Games\TheSimpsonsGame-PS3\Godot\init.py

"""
Batch-safe Godot project initializer for very large asset sets.

Key ideas:
- Copy (or hardlink) assets DIRECTLY into the final project (res://assets/...), not temp projects.
- Create per-batch subfolders (assets/batch_001, assets/batch_002, ...) each gated with a .gdignore.
- For each batch: remove its .gdignore, run a headless import once, move to the next batch.
- Only overwrite files whose content likely changed (size/mtime check), to prevent unnecessary reimports.
- Never move/copy .godot/imported or .godot/editor caches across projects.

This avoids 5+ hour monolithic first imports and prevents "reimport everything" storms.
"""

import os
import shutil
import subprocess
import time
import argparse
from concurrent.futures import ThreadPoolExecutor
import re
import errno
import hashlib
from typing import List, Tuple

# Optional tqdm progress
try:
    from tqdm import tqdm
    def _progress(iterable, **kwargs):
        return tqdm(iterable, **kwargs)
except Exception:
    def _progress(iterable, **kwargs):
        return iterable


# ---------- Small utilities ----------

def countdown(count: int) -> None:
    while count > 0:
        print(f"Waiting... {count} seconds remaining.")
        time.sleep(1)
        count -= 1

def ensure_dir(path: str) -> None:
    os.makedirs(path, exist_ok=True)

def write_empty(path: str) -> None:
    ensure_dir(os.path.dirname(path))
    with open(path, "a", encoding="utf-8"):
        pass

def sha1(path: str, chunk: int = 1 << 20) -> str:
    h = hashlib.sha1()
    with open(path, "rb") as f:
        while True:
            b = f.read(chunk)
            if not b:
                break
            h.update(b)
    return h.hexdigest()

def nearly_same_file(src: str, dst: str) -> bool:
    """
    Fast skip: same size and ~same mtime (within 1s). Good enough for most assets.
    """
    try:
        sst, dstt = os.stat(src), os.stat(dst)
        if sst.st_size != dstt.st_size:
            return False
        # mtime tolerance to avoid FS rounding issues
        return abs(sst.st_mtime - dstt.st_mtime) < 1.0
    except FileNotFoundError:
        return False
    except Exception:
        return False


# ---------- Godot helpers ----------

def run_godot_command(command: List[str], step_name: str):
    print(f"\n--- Running Godot Step: {step_name} ---")
    print(f"Command: {' '.join(command)}")
    try:
        subprocess.run(command, check=True)
        print(f"--- {step_name} completed successfully. ---")
    except subprocess.CalledProcessError as e:
        print(f"!!! ERROR during '{step_name}'. Godot exited with error code {e.returncode}.")
        print("!!! Build process halted. Please check the Godot logs above for details.")
        exit(1)
    except FileNotFoundError:
        print(f"!!! ERROR: Could not find the Godot executable at '{command[0]}'.")
        print("!!! Please ensure the path in the script is correct and it's a console-enabled version.")
        exit(1)


# ---------- Asset discovery & batching ----------

def gather_matching_files(folder_paths: List[str], exts: List[str]) -> List[Tuple[str, str, str]]:
    """
    Returns list[(src_abs, rel_to_root, root)] for files whose extension matches.
    """
    exts_low = [e.lower() for e in exts]
    matched = []
    for root in folder_paths:
        if not os.path.exists(root):
            print(f"Warning: asset source folder not found: {root}")
            continue
        for r, _dirs, files in os.walk(root):
            for fn in files:
                if any(fn.lower().endswith(ext) for ext in exts_low):
                    src = os.path.join(r, fn)
                    rel = os.path.relpath(src, root)
                    matched.append((src, rel, root))
    return matched

def split_into_batches(items: List[Tuple[str, str, str]], batch_size: int):
    for i in range(0, len(items), batch_size):
        yield items[i:i + batch_size]


# ---------- Copy/hardlink into FINAL project (not temp projects) ----------

def copy_batch_into_final_project(
    batch_files: List[Tuple[str, str, str]],
    assets_dir: str,
    batch_name: str,
    use_hardlinks: bool = True,
    verify_hash_for_large: bool = True,
    large_bytes_threshold: int = 50 * (1 << 20)  # 50 MB
) -> None:
    """
    Copies (or hardlinks) a batch directly under res://assets/<batch_name>/...
    Preserves subfolder structure relative to the source root.
    Skips files that haven't changed to avoid reimports.
    """
    base = os.path.join(assets_dir, batch_name)
    ensure_dir(base)

    for src, rel, src_root in _progress(batch_files, desc=f"Staging {batch_name}", unit="file"):
        # Place files under assets/<batch_name>/<original_rel_path>
        dest = os.path.join(base, rel)
        ensure_dir(os.path.dirname(dest))

        # Skip if unchanged
        if os.path.exists(dest):
            if nearly_same_file(src, dest):
                continue
            # Optional: for very large files, compare hashes before overwriting
            if verify_hash_for_large:
                try:
                    if os.path.getsize(src) >= large_bytes_threshold and os.path.getsize(dest) == os.path.getsize(src):
                        if sha1(src) == sha1(dest):
                            continue
                except Exception:
                    pass

        # Write/overwrite
        try:
            if use_hardlinks:
                try:
                    # Create/replace via unlink + link to avoid EXDEV issues later
                    if os.path.exists(dest):
                        os.remove(dest)
                    os.link(src, dest)
                except OSError as e:
                    # Cross-device or not supported -> fallback copy
                    if getattr(e, "errno", None) == errno.EXDEV:
                        shutil.copy2(src, dest)
                    else:
                        # any other link error, try copy
                        shutil.copy2(src, dest)
            else:
                shutil.copy2(src, dest)
        except Exception as e:
            print(f"Warning: Failed to place '{src}' -> '{dest}': {e}")


# ---------- Logos & misc copy ----------

def copy_logos(logo_image_files: List[str], project_dir: str) -> None:
    if not logo_image_files:
        return
    logos_dest = os.path.join(project_dir, "logos")
    ensure_dir(logos_dest)
    print(f"Copying {len(logo_image_files)} logo image(s) to {logos_dest}...")
    for logo in _progress(logo_image_files, desc="Copying logos", unit="file"):
        try:
            shutil.copy2(logo, logos_dest)
        except Exception as e:
            print(f"Warning: Failed to copy logo '{logo}': {e}")


# ---------- Main project creation & batched import ----------

def create_godot_project(
    project_name: str,
    project_path: str,
    asset_folders: List[str],
    scripts_folder: str,
    addons_folder: str,
    json_path: str,
    asset_extensions: List[str],
    godot_executable: str,
    no_exit: bool,
    logo_image_files: List[str],
    batch_size: int = 2000,
    import_threads_hint: int = None  # optional: user can set via Editor Settings too
) -> None:

    project_dir = os.path.join(project_path, project_name)
    ensure_dir(project_dir)
    print(f"Godot Project Directory: {project_dir}")

    # Create project.godot if needed (uses your conf template)
    project_godot_path = os.path.join(project_dir, "project.godot")
    if not os.path.exists(project_godot_path):
        conf_path = os.path.join(project_path, "..", "conf", "project.godot")
        with open(conf_path, "r", encoding="utf-8") as f:
            content = f.read()
        with open(project_godot_path, "w", encoding="utf-8") as f:
            f.write(content)
        print("Created project.godot file.")

    # Optional: set import threads at runtime by editing editor settings (advanced – usually not required).
    # You can manage this via Editor Settings on the machine running the imports.

    # Discover all assets -> batches
    all_assets = gather_matching_files(asset_folders, asset_extensions)
    total_files = len(all_assets)
    if total_files == 0:
        print("No matching assets found. Skipping import.")
    else:
        print(f"Discovered {total_files} asset file(s). Using batches of {batch_size}.")
        batches = list(split_into_batches(all_assets, batch_size))
        print(f"Total batches: {len(batches)}")

        # Prepare assets dir & pre-create gated batch dirs
        assets_dir = os.path.join(project_dir, "assets")
        ensure_dir(assets_dir)

        # Create per-batch directories and gate them with .gdignore
        for i, _batch in enumerate(batches, 1):
            batch_dir = os.path.join(assets_dir, f"batch_{i:03d}")
            ensure_dir(batch_dir)
            gdignore = os.path.join(batch_dir, ".gdignore")
            write_empty(gdignore)

        # Stage each batch into its gated folder
        for i, batch in enumerate(batches, 1):
            batch_name = f"batch_{i:03d}"
            # Adjust rel to live under batch_name/<rel>
            adjusted = [(src, rel, root) for (src, rel, root) in batch]
            copy_batch_into_final_project(
                adjusted,
                assets_dir=assets_dir,
                batch_name=batch_name,
                use_hardlinks=True,
                verify_hash_for_large=True
            )

        # Import each batch INSIDE THE FINAL PROJECT
        # For each batch: remove its .gdignore, then run one headless import.
        for i in range(1, len(batches) + 1):
            batch_dir = os.path.join(assets_dir, f"batch_{i:03d}")
            gdignore = os.path.join(batch_dir, ".gdignore")
            if os.path.exists(gdignore):
                os.remove(gdignore)
            # Single headless import for this batch; already-imported batches remain cached.
            run_godot_command(
                [godot_executable, "--headless", "--path", project_dir, "--import", "-v", "--quit"],
                f"Import Batch {i:03d}"
            )

    print("\nAssets directory is ready. Preparing to run tool scripts.")
    countdown(1)

    # Copy addons (idempotent)
    if os.path.exists(addons_folder):
        shutil.copytree(addons_folder, os.path.join(project_dir, "addons"), dirs_exist_ok=True)

    # Copy config & tool scripts (idempotent)
    shutil.copy2(json_path, os.path.join(project_dir, "scene_config.json"))
    scripts_dest_dir = os.path.join(project_dir, "Scripts")
    if os.path.exists(scripts_folder):
        shutil.copytree(scripts_folder, scripts_dest_dir, dirs_exist_ok=True)
        print("Copied scene_config.json and tool scripts into the project.")

    # Copy logos last (optional)
    copy_logos(logo_image_files, project_dir)

    # Run the scene-building script (in the editor); keep --no-exit if requested
    scene_build_command = [
        godot_executable,
        "--editor",
        "--path", project_dir,
        "--script", "res://Scripts/_BuildScenes.gd"
    ]
    if no_exit:
        scene_build_command.append("--no-exit")
        print("\n'--no-exit' flag detected. Godot will remain open after script execution.")

    run_godot_command(scene_build_command, "Scene Building")

    print("\n✅✅✅ Godot project setup and scene generation complete! ✅✅✅")
    countdown(1)


# ---------- Entry point ----------

def main(project_name: str, repo_root: str, no_exit: bool, sourcePath: str, batch_size: int) -> None:
    # Path discovery
    module_root = os.path.abspath(os.path.dirname(__file__))
    print(f"Module Root (for generated content): {module_root}")

    if not repo_root:
        print("WARNING: --repo-root not specified. Assuming it's the same as the module root.")
        repo_root = module_root
    print(f"Repository Root (for asset sources): {repo_root}")

    # Paths
    asset_source_folders = [os.path.join(repo_root, "GameFiles", "ExtractedOut")]
    tool_scripts_source_folder = os.path.join(module_root, "Scripts")
    addons_source_folder = os.path.join(module_root, "addons")
    scene_config_json_path = os.path.join(module_root, 'scene_config.json')
    godot_project_parent_dir = os.path.join(module_root, 'GodotGame')

    # Configuration
    GODOT_EXECUTABLE = os.path.join(
        repo_root, "Tools", "Godot", "Godot_v4.4.1-stable_mono_win64", "Godot_v4.4.1-stable_mono_win64.exe"
    )
    GAME_ASSET_EXTENSIONS = [".dds", ".glb", ".wav", ".ogv"]

    # Find possible logo images next to sourcePath
    logo_image_files = []
    try:
        for root, _dirs, files in os.walk(os.path.dirname(sourcePath)):
            for filename in files:
                if filename.lower().endswith(".png"):
                    logo_image_files.append(os.path.join(root, filename))
        if logo_image_files:
            print(f"Found game logo image files: {logo_image_files}")
    except Exception as e:
        print(f"Logo scan warning: {e}")

    create_godot_project(
        project_name=project_name,
        project_path=godot_project_parent_dir,
        asset_folders=asset_source_folders,
        scripts_folder=tool_scripts_source_folder,
        addons_folder=addons_source_folder,
        json_path=scene_config_json_path,
        asset_extensions=GAME_ASSET_EXTENSIONS,
        godot_executable=GODOT_EXECUTABLE,
        no_exit=no_exit,
        logo_image_files=logo_image_files,
        batch_size=batch_size
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Godot Project Setup (batched, storm-proof)")
    parser.add_argument("--project-name", default="Game", help="Name of the Godot project")
    parser.add_argument("--repo-root", required=True, help="Path to the repository root directory")
    parser.add_argument("--no-exit", action="store_true", help="Leave the editor open after running the GDScript")
    parser.add_argument("--sourcePath", required=True, help="Path to the source directory")
    parser.add_argument("--batch-size", type=int, default=2000, help="Number of files per import batch")
    args = parser.parse_args()

    main(
        project_name=args.project_name,
        repo_root=args.repo_root,
        no_exit=args.no_exit,
        sourcePath=args.sourcePath,
        batch_size=args.batch_size
    )

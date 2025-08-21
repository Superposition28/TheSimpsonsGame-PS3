# RemakeRegistry\Games\TheSimpsonsGame-PS3\Godot\init.py
"""
Folder-batched Godot import with per-language sub-batches for audio.
- No temp projects
- No staging mirror
- No batch_* folders
- Preserves final res://assets/<TopFolder>/... paths so scene JSON stays valid
"""

import shutil
import subprocess
import time
import argparse
import errno
import hashlib
from typing import List, Tuple

import builtins as py
import os
import sys
# add RemakeEngine Utilities, custom print 'printer' and SDK
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..', '..', '.')))
from Engine.Utils.printer import print, Colours, error, print_verbose, print_debug, printc
import Engine.Utils.Engine_sdk as sdk #import prompt, progress, warn, error, start, end
from Engine.Utils.resolver import resolve_tool

# Optional progress bar
try:
    from tqdm import tqdm
    def _progress(it, **kw): return tqdm(it, **kw)
except Exception:
    def _progress(it, **kw): return it


# ----------------- small utils -----------------

def ensure_dir(p: str) -> None:
    os.makedirs(p, exist_ok=True)

def countdown(sec: int) -> None:
    while sec > 0:
        print(colour=Colours.WHITE, message=f"Waiting... {sec} seconds remaining.")
        time.sleep(1)
        sec -= 1

def nearly_same_file(src: str, dst: str) -> bool:
    try:
        s, d = os.stat(src), os.stat(dst)
        if s.st_size != d.st_size:
            return False
        return abs(s.st_mtime - d.st_mtime) < 1.0
    except FileNotFoundError:
        return False
    except Exception:
        return False

def sha1(path: str, chunk: int = 1 << 20) -> str:
    h = hashlib.sha1()
    with open(path, "rb") as f:
        while True:
            b = f.read(chunk)
            if not b: break
            h.update(b)
    return h.hexdigest()


# ----------------- godot helpers -----------------

def run_godot(command: List[str], label: str):
    print(colour=Colours.WHITE, message=f"\n--- {label} ---")
    print(colour=Colours.WHITE, message=f"Command: {' '.join(command)}")
    try:
        subprocess.run(command, check=True)
        print(colour=Colours.WHITE, message=f"--- {label} finished ---")
    except subprocess.CalledProcessError as e:
        print(colour=Colours.WHITE, message=f"!!! ERROR during {label} (exit {e.returncode})")
        raise SystemExit(1)
    except FileNotFoundError:
        print(colour=Colours.WHITE, message=f"!!! Godot executable not found at '{command[0]}'")
        raise SystemExit(1)


# ----------------- placement (direct to final assets/) -----------------

def copy_tree_incremental(src_root: str, dst_root: str, use_hardlinks: bool = True,
                          verify_hash_for_large: bool = True,
                          large_bytes_threshold: int = 50 * (1 << 20),
                          exts: List[str] = None) -> Tuple[int, int]:
    """
    Copy/hardlink files from src_root -> dst_root, preserving structure.
    Only copy when changed. Returns (total_seen, total_copied).
    If 'exts' provided, only process those extensions (lowercased, with dot).
    """
    total_seen = 0
    total_copied = 0
    exts_low = [e.lower() for e in exts] if exts else None

    walk_iter = list(os.walk(src_root))
    for r, _dirs, files in _progress(walk_iter, desc=f"Sync {os.path.basename(src_root)}", unit="dir"):
        for fn in files:
            if exts_low and all(not fn.lower().endswith(x) for x in exts_low):
                continue
            src = os.path.join(r, fn)
            rel = os.path.relpath(src, src_root)
            dst = os.path.join(dst_root, rel)
            ensure_dir(os.path.dirname(dst))

            total_seen += 1

            # skip if identical (quick)
            if os.path.exists(dst) and nearly_same_file(src, dst):
                continue

            # optional hash check for big files to avoid needless copy
            if os.path.exists(dst) and verify_hash_for_large:
                try:
                    if os.path.getsize(src) == os.path.getsize(dst) >= large_bytes_threshold:
                        if sha1(src) == sha1(dst):
                            continue
                except Exception:
                    pass

            try:
                if use_hardlinks:
                    try:
                        if os.path.exists(dst):
                            os.remove(dst)
                        os.link(src, dst)
                    except OSError as e:
                        if getattr(e, "errno", None) == errno.EXDEV:
                            shutil.copy2(src, dst)
                        else:
                            shutil.copy2(src, dst)
                else:
                    shutil.copy2(src, dst)
                total_copied += 1
            except Exception as e:
                print(colour=Colours.WHITE, message=f"Warn: copy/link failed '{src}' -> '{dst}': {e}")

    return total_seen, total_copied


# ----------------- main create/import -----------------

AUDIO_TOP = "Assets_1_Audio_Streams"
AUDIO_LANG_FOLDERS = {"EN", "ES", "FR", "IT", "Global"}  # detected dynamically too

def create_godot_project(
    project_name: str,
    project_path: str,
    extracted_root: str,
    scripts_folder: str,
    addons_folder: str,
    json_path: str,
    godot_exe: str,
    no_exit: bool,
    logo_images: List[str],
    asset_exts: List[str]
):
    project_dir = os.path.join(project_path, project_name)
    ensure_dir(project_dir)
    print(colour=Colours.WHITE, message=f"Godot Project Directory: {project_dir}")

    # project.godot from conf template
    proj_file = os.path.join(project_dir, "project.godot")
    if not os.path.exists(proj_file):
        conf_path = os.path.join(project_path, "..", "conf", "project.godot")
        with open(conf_path, "r", encoding="utf-8") as f:
            content = f.read()
        with open(proj_file, "w", encoding="utf-8") as f:
            f.write(content)
        print(colour=Colours.WHITE, message="Created project.godot")

    assets_dst_root = os.path.join(project_dir, "assets")
    ensure_dir(assets_dst_root)

    # Discover top-level folders under ExtractedOut
    top_folders = [d for d in os.listdir(extracted_root)
                   if os.path.isdir(os.path.join(extracted_root, d))]
    # Stable order helps with reproducibility
    top_folders.sort()

    print(colour=Colours.WHITE, message="\nTop-level batches detected:")
    for d in top_folders:
        print(colour=Colours.WHITE, message=f" • {d}")

    # Process each top-level folder as a batch
    for batch_idx, top in enumerate(top_folders, 1):
        src_top = os.path.join(extracted_root, top)

        # Special: sub-batch audio by language folders
        if top == AUDIO_TOP:
            # find language subfolders
            langs = [d for d in os.listdir(src_top)
                     if os.path.isdir(os.path.join(src_top, d))]
            # prefer a canonical order
            langs_sorted = sorted(langs, key=lambda x: (x not in AUDIO_LANG_FOLDERS, x))

            for lang in langs_sorted:
                src_lang = os.path.join(src_top, lang)
                dst_lang = os.path.join(assets_dst_root, top, lang)
                ensure_dir(dst_lang)

                # Gate with .gdignore during placement (optional; we remove it just before import)
                gdignore_path = os.path.join(assets_dst_root, top, lang, ".gdignore")
                open(gdignore_path, "a").close()

                print(colour=Colours.WHITE, message=f"\n=== Batch {batch_idx}: {top}/{lang} ===")
                seen, copied = copy_tree_incremental(
                    src_root=src_lang,
                    dst_root=dst_lang,
                    use_hardlinks=True,
                    verify_hash_for_large=True,
                    exts=asset_exts
                )
                print(colour=Colours.WHITE, message=f"Placed {seen} file(s), copied {copied} new/changed.")

                # Reveal + import this sub-batch
                try:
                    os.remove(gdignore_path)
                except FileNotFoundError:
                    pass

                run_godot(
                    [godot_exe, "--headless", "--path", project_dir, "--import", "-v", "--quit"],
                    f"Headless Import: {top}/{lang}"
                )

        else:
            # Regular top-level folder as a single batch
            dst_top = os.path.join(assets_dst_root, top)
            ensure_dir(dst_top)
            gdignore_path = os.path.join(dst_top, ".gdignore")
            open(gdignore_path, "a").close()

            print(colour=Colours.WHITE, message=f"\n=== Batch {batch_idx}: {top} ===")
            seen, copied = copy_tree_incremental(
                src_root=src_top,
                dst_root=dst_top,
                use_hardlinks=True,
                verify_hash_for_large=True,
                exts=asset_exts
            )
            print(colour=Colours.WHITE, message=f"Placed {seen} file(s), copied {copied} new/changed.")

            try:
                os.remove(gdignore_path)
            except FileNotFoundError:
                pass

            run_godot(
                [godot_exe, "--headless", "--path", project_dir, "--import", "-v", "--quit"],
                f"Headless Import: {top}"
            )

    print(colour=Colours.WHITE, message="\nAssets are ready. Preparing to run tool scripts.")
    countdown(1)

    # Addons
    if os.path.exists(addons_folder):
        shutil.copytree(addons_folder, os.path.join(project_dir, "addons"), dirs_exist_ok=True)

    # Scene config & scripts
    shutil.copy2(json_path, os.path.join(project_dir, "scene_config.json"))
    scripts_dst = os.path.join(project_dir, "Scripts")
    if os.path.exists(scripts_folder):
        shutil.copytree(scripts_folder, scripts_dst, dirs_exist_ok=True)
        print(colour=Colours.WHITE, message="Copied scene_config.json and tool scripts.")

    # Logos (optional)
    if logo_images:
        logos_dst = os.path.join(project_dir, "logos")
        ensure_dir(logos_dst)
        for f in _progress(logo_images, desc="Copying logos", unit="file"):
            try:
                shutil.copy2(f, logos_dst)
            except Exception as e:
                print(colour=Colours.WHITE, message=f"Warn: logo copy failed '{f}': {e}")

    # Run scene builder
    cmd = [
        godot_exe, "--editor",
        "--path", project_dir,
        "--script", "res://Scripts/_BuildScenes.gd"
    ]
    if no_exit:
        cmd.append("--no-exit")
        print(colour=Colours.WHITE, message="\n'--no-exit' flag detected. Godot will remain open after script execution.")

    run_godot(cmd, "Scene Building")
    print(colour=Colours.WHITE, message="\n✅✅✅ Godot project setup and scene generation complete! ✅✅✅")
    countdown(1)


# ----------------- CLI -----------------

def main(project_name: str, repo_root: str, no_exit: bool, sourcePath: str):
    godot_module_root = os.path.abspath(os.path.dirname(__file__))
    # get parent of godot_module_root for module root
    module_root = os.path.abspath(os.path.dirname(godot_module_root))
    print(colour=Colours.WHITE, message=f"Godot Module Root: {godot_module_root}")
    print(colour=Colours.WHITE, message=f"Repository Root: {repo_root}")

    extracted_root = os.path.join(repo_root, "GameFiles", "ExtractedOut")
    scripts_folder = os.path.join(godot_module_root, "Scripts")
    addons_folder = os.path.join(godot_module_root, "addons")
    json_path = os.path.join(godot_module_root, 'scene_config.json')
    project_parent = os.path.join(godot_module_root, 'GodotGame')

    godot_exe = resolve_tool(
        repo_root=repo_root,
        tool_name="Godot",
        module_tools_file=os.path.join(module_root, "Tools.json"),
        require_mono=True
    )

    # Only import these formats
    asset_exts = [".dds", ".glb", ".wav", ".ogv"]

    # logos
    logos = []
    try:
        for r, _d, files in os.walk(os.path.dirname(sourcePath)):
            for fn in files:
                if fn.lower().endswith(".png"):
                    logos.append(os.path.join(r, fn))
        if logos:
            print(colour=Colours.WHITE, message=f"Found game logo images: {logos}")
    except Exception as e:
        print(colour=Colours.WHITE, message=f"Logo scan warning: {e}")

    create_godot_project(
        project_name=project_name,
        project_path=project_parent,
        extracted_root=extracted_root,
        scripts_folder=scripts_folder,
        addons_folder=addons_folder,
        json_path=json_path,
        godot_exe=godot_exe,
        no_exit=no_exit,
        logo_images=logos,
        asset_exts=asset_exts
    )

if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="Godot Project Setup (folder-batched, final-path imports)")
    ap.add_argument("--project-name", default="Game", help="Name of the Godot project")
    ap.add_argument("--repo-root", required=True, help="Path to the repository root directory")
    ap.add_argument("--no-exit", action="store_true", help="Keep the editor open after running the GDScript")
    ap.add_argument("--sourcePath", required=True, help="Path to the source directory (for logo auto-discovery)")
    args = ap.parse_args()

    main(
        project_name=args.project_name,
        repo_root=args.repo_root,
        no_exit=args.no_exit,
        sourcePath=args.sourcePath
    )

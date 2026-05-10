# SPDX-License-Identifier: MIT
"""
Materials module for The Simpsons Game Blender Addon.
Handles material creation, shader node setup, and texture path resolution using a JSON database.
"""
import json
import os
import sys
from pathlib import Path
import bpy # type: ignore
from .utils.logger import bPrinter

# --- JSON texture index -----------------------------------------

USE_JSON_DB_LOOKUP = True

_json_db_cache = None

def _load_json_db_if_configured() -> list | None:
    """
    Loads the JSON texture database from the path specified in the scene property.
    Caches the results to avoid redundant file operations.
    """
    global _json_db_cache
    if not USE_JSON_DB_LOOKUP:
        return None

    if _json_db_cache is not None:
        return _json_db_cache

    # Get path dynamically from the scene property set by the driver script
    try:
        # Check if we are in a context where bpy.context is available
        if bpy.context and bpy.context.scene:
            bPrinter("[JSON DB] Attempting to load JSON DB from scene property 'tsg_db_path'...", console_colour="cyan", to_blender_editor=True)
            main_db_path = bpy.context.scene.get("tsg_db_path")
        else:
            bPrinter("[JSON DB] bpy.context.scene is not available. DB lookup unavailable.", console_colour="red", to_blender_editor=True)
            main_db_path = None

    except Exception as e:
        bPrinter(f"[JSON DB] Failed to access bpy.context.scene: {e}", console_colour="red", to_blender_editor=True)
        main_db_path = None

    if not main_db_path:
        bPrinter("[JSON DB] 'tsg_db_path' custom property not found or empty on scene. DB lookup unavailable.", console_colour="red", to_blender_editor=True)
        return None

    try:
        db_path = Path(main_db_path)
        if not db_path.exists():
            bPrinter(f"[JSON DB] DB not found at: {main_db_path}", console_colour="yellow", to_blender_editor=True)
            return None
        with open(db_path, 'r', encoding='utf-8') as f:
            _json_db_cache = json.load(f)
        bPrinter(f"[JSON DB] Loaded DB at: {main_db_path} with {len(_json_db_cache)} entries", console_colour="green", to_blender_editor=True)
        return _json_db_cache
    except Exception as e:
        bPrinter(f"[JSON DB] Failed to load DB at '{main_db_path}': {e}", console_colour="red", to_blender_editor=True)
        return None

def _normalize_tex_name(name: str) -> str:
    """
    Normalizes a texture name by stripping whitespace and removing the .png extension if present.
    """
    n = name.strip()
    if n.lower().endswith('.png'):
        n = n[: -4]
    return n.lower()

def _find_texture_in_tree(tex_name: str, start_filepath: str) -> Path | None:
    """Climbs the directory tree looking for <stringname>*.png."""
    norm_name = _normalize_tex_name(tex_name)
    start_path = Path(start_filepath).resolve()
    current_dir = start_path.parent
    previous_dir = None
    level_root = None

    while current_dir and current_dir.parent != current_dir:
        # Heuristically identify level root (e.g. L08_TheColossalDonut, A2_Frontend)
        if (current_dir.name.startswith("L") and "_" in current_dir.name) or current_dir.name == "A2_Frontend":
            level_root = current_dir

        # Search current_dir recursively, skipping the branch we came from
        for root, dirs, files in os.walk(current_dir):
            root_path = Path(root)
            # Skip the previous directory branch to avoid redundant searches
            if previous_dir and (root_path == previous_dir or previous_dir in root_path.parents):
                dirs[:] = [] # Stop os.walk from descending further down this path
                continue

            for f in files:
                f_lower = f.lower()
                if f_lower.startswith(norm_name) and f_lower.endswith('.png'):
                    # Ensure exact match or exact match + _uid suffix
                    remainder = f_lower[len(norm_name):]
                    if remainder == '.png' or remainder.startswith('_'):
                        return root_path / f

        if level_root and current_dir == level_root:
            break # Reached the top of the level directory, stop climbing

        previous_dir = current_dir
        current_dir = current_dir.parent

    # Fallback to A2_Frontend if not found in the local level tree
    if level_root and level_root.name != "A2_Frontend":
        frontend_dir = level_root.parent / "A2_Frontend"
        if frontend_dir.exists():
            for root, dirs, files in os.walk(frontend_dir):
                for f in files:
                    f_lower = f.lower()
                    if f_lower.startswith(norm_name) and f_lower.endswith('.png'):
                        remainder = f_lower[len(norm_name):]
                        if remainder == '.png' or remainder.startswith('_'):
                            return Path(root) / f
    return None

def _resolve_texture_path_from_db(tex_name: str, preinstanced_filepath: str | None = None) -> str | None:
    """
    Looks up a texture name in the JSON database and returns its new path.
    Uses fuzzy matching against the preinstanced file path to resolve duplicates.
    """
    db = _load_json_db_if_configured()
    if db is None:
        return None
    try:
        norm = _normalize_tex_name(tex_name)
        matches = []
        for entry in db:
            orig_path = entry.get("original_path", "")
            if not orig_path:
                continue

            # Extract filename without extension
            filename_part = orig_path.split('/')[-1].split('\\')[-1]
            if filename_part.lower().endswith('.dds') or filename_part.lower().endswith('.rws') or filename_part.lower().endswith('.dff'):
                filename_part = ".".join(filename_part.split('.')[:-1])

            if filename_part.lower() == norm:
                matches.append(entry)

        if not matches:
            return None

        best_match = matches[0]
        if len(matches) > 1 and preinstanced_filepath:
            preinstanced_parts = [p.lower() for p in Path(preinstanced_filepath).parts]
            best_score = -1

            for match in matches:
                new_path_val = match.get("new_path", "")
                new_parts = [p.lower() for p in Path(new_path_val).parts[:-1]]
                score = 0
                if new_parts and new_parts[0] in preinstanced_parts:
                    # Find the last occurrence of new_parts[0] in preinstanced_parts
                    # to handle cases where the root folder name might be repeated
                    try:
                        start_idx = len(preinstanced_parts) - 1 - preinstanced_parts[::-1].index(new_parts[0])
                        for i in range(min(len(new_parts), len(preinstanced_parts) - start_idx)):
                            if i < len(new_parts) and start_idx + i < len(preinstanced_parts) and new_parts[i] == preinstanced_parts[start_idx + i]:
                                score += 1
                            else:
                                break
                    except ValueError:
                        pass

                # Fallback: just count common parts
                if score == 0:
                    score = len(set(new_parts).intersection(set(preinstanced_parts)))

                if score > best_score:
                    best_score = score
                    best_match = match

        new_path = best_match.get("new_path", "")
        if new_path.lower().endswith('.dds'):
            new_path = new_path[:-4] + ".png"

        return new_path
    except Exception as e:
        bPrinter(f"[JSON DB] Lookup error for '{tex_name}': {e}", console_colour="yellow", to_blender_editor=True)
        return None

def resolve_asset_paths_from_db(asset_name: str, preinstanced_filepath: str | None = None) -> tuple[str | None, str | None]:
    """
    Looks up an asset name (texture or mesh) in the JSON database and returns its (original_path, new_path).
    If the asset name contains a UID suffix (e.g., 'lodmodel1_9c6d15'), it uses that for an exact lookup.
    """
    db = _load_json_db_if_configured()
    if db is None:
        return None, None
    try:
        norm = asset_name.lower()

        # 1. Try UID lookup if name matches typical pattern (e.g. name_uid)
        if "_" in norm:
            uid_part = norm.split("_")[-1]
            # Simple hex check
            if all(c in "0123456789abcdef" for c in uid_part):
                for entry in db:
                    if entry.get("uid", "").lower() == uid_part:
                        return entry.get("original_path"), entry.get("new_path")

        # 2. Fallback to filename based lookup
        matches = []
        for entry in db:
            orig_path = entry.get("original_path", "")
            if not orig_path:
                continue

            # Extract filename without extension
            filename_part = orig_path.split('/')[-1].split('\\')[-1]
            if "." in filename_part:
                filename_part = filename_part.split('.')[0] # Take first part for meshes like lodmodel1

            if filename_part.lower() == norm:
                matches.append(entry)

        if not matches:
            return None, None

        best_match = matches[0]
        # Fuzzy matching if multiple hits
        if len(matches) > 1 and preinstanced_filepath:
            preinstanced_parts = [p.lower() for p in Path(preinstanced_filepath).parts]
            best_score = -1
            for match in matches:
                new_p = match.get("new_path", "")
                new_parts = [p.lower() for p in Path(new_p).parts[:-1]]
                score = len(set(new_parts).intersection(set(preinstanced_parts)))
                if score > best_score:
                    best_score = score
                    best_match = match

        return best_match.get("original_path"), best_match.get("new_path")
    except Exception as e:
        bPrinter(f"[JSON DB] Asset path lookup error for '{asset_name}': {e}", console_colour="yellow", to_blender_editor=True)
        return None, None

def _maybe_cache_texture_path(tex_name: str, cache: dict[str, str], preinstanced_filepath: str | None = None) -> None:
    """
    Resolves a texture path and stores it in the provided cache dictionary.
    """
    key = _normalize_tex_name(tex_name)
    if key in cache:
        bPrinter(f"[Path Resolver] Cache hit for '{tex_name}': {cache[key]}", to_blender_editor=True, print_to_console=False)
        return

    final_path = None

    # 1. Try DB lookup first
    db_rel_path = _resolve_texture_path_from_db(tex_name, preinstanced_filepath)
    if db_rel_path:
        try:
            if bpy.context and bpy.context.scene:
                db_path_str = bpy.context.scene.get("tsg_db_path")
                if db_path_str:
                    db_abs = Path(db_path_str).parent / db_rel_path
                    if db_abs.exists():
                        final_path = str(db_abs)
        except Exception:
            pass

    # 2. Try reverse tree search if DB lookup failed or path didn't exist
    if not final_path and preinstanced_filepath:
        tree_found = _find_texture_in_tree(tex_name, preinstanced_filepath)
        if tree_found:
            final_path = str(tree_found)

    if final_path:
        cache[key] = final_path
        bPrinter(f"[Path Resolver] Resolved '{tex_name}' -> {final_path}", to_blender_editor=True, print_to_console=False)
    else:
        bPrinter(f"[Path Resolver] Could not find texture for '{tex_name}'", console_colour="yellow", to_blender_editor=True)

# --- Material helpers ---------------------------------------------------------

_material_cache: dict[str, bpy.types.Material] = {}

def clear_material_cache() -> None:
    """
    Clears the global material cache to ensure fresh material lookup/creation.
    """
    global _material_cache
    _material_cache.clear()
    bPrinter("[Material] Global material cache cleared.", require_debug_mode=True)

def _ensure_material_for_texture(tex_name: str, resolved_paths: dict[str, str]) -> bpy.types.Material | None:
    """
    Creates or retrieves a Blender material for the given texture name.
    Configures shader nodes and attempts to load the texture image.
    """
    try:
        key = _normalize_tex_name(tex_name)
        mat_name = f"TEX_{key}"
        if key in _material_cache:
            mat = _material_cache[key]
            try:
                # Check if the material still exists and is valid
                _ = mat.name
                return mat
            except (ReferenceError, RuntimeError):
                # Referenced material has been removed or is otherwise invalid
                del _material_cache[key]

        mat = bpy.data.materials.get(mat_name)
        if mat is None:
            mat = bpy.data.materials.new(mat_name)
        mat.use_nodes = True
        nt = mat.node_tree
        nodes = nt.node_tree.nodes if hasattr(nt, "node_tree") else nt.nodes
        links = nt.node_tree.links if hasattr(nt, "node_tree") else nt.links

        # Keep Output node if present, clear others
        out = next((n for n in nodes if n.type == 'OUTPUT_MATERIAL'), None)
        for n in list(nodes):
            if n != out:
                nodes.remove(n)
        if out is None:
            out = nodes.new('ShaderNodeOutputMaterial')
            out.location = (400, 0)
        bsdf = nodes.new('ShaderNodeBsdfPrincipled')
        bsdf.location = (150, 0)
        img_node = nodes.new('ShaderNodeTexImage')
        img_node.location = (-200, 0)

        # Attempt to load image from resolved db path
        img = None
        absolute_path_str = resolved_paths.get(key)

        if absolute_path_str:
            absolute_path = Path(absolute_path_str)
            # Prepend the long path prefix if on Windows
            if sys.platform == 'win32' and not str(absolute_path).startswith('\\\\?\\'):
                absolute_path = Path(f"\\\\?\\{str(absolute_path)}")
                bPrinter(f"[Material] Applied Windows long path prefix. Attempting load from: {absolute_path}", require_debug_mode=True)
            else:
                bPrinter(f"[Material] Attempting to load '{tex_name}' from: {absolute_path}", require_debug_mode=True)

            if absolute_path.exists():
                try:
                    img = bpy.data.images.load(str(absolute_path), check_existing=True)
                except Exception as e:
                    bPrinter(f"[Material] Failed to load image for '{tex_name}' from '{absolute_path}': {e}", console_colour="yellow")
            else:
                bPrinter(f"[Material] File not found at path: {absolute_path}", console_colour="yellow")
        else:
            bPrinter(f"[Material] No resolved path found for '{tex_name}' (key: '{key}').", console_colour="yellow")

        img_node.image = img

        try:
            links.new(img_node.outputs.get('Color'), bsdf.inputs.get('Base Color'))
        except Exception:
            pass
        if 'Alpha' in img_node.outputs and 'Alpha' in bsdf.inputs:
            try:
                links.new(img_node.outputs['Alpha'], bsdf.inputs['Alpha'])
            except Exception:
                pass
        try:
            links.new(bsdf.outputs.get('BSDF'), out.inputs.get('Surface'))
        except Exception:
            pass
        _material_cache[key] = mat
        return mat
    except Exception as e:
        bPrinter(f"[Material] Error creating material for '{tex_name}': {e}", console_colour="red")
        return None

def _create_materials_for_all_textures(all_names: set[str], resolved_paths: dict[str, str]) -> None:
    """
    Convenience function to batch-create materials for all discovered texture names.
    """
    if not all_names:
        return
    bPrinter(f"[Material] Creating materials for {len(all_names)} texture(s).", to_blender_editor=True)
    for n in sorted(all_names):
        mat = _ensure_material_for_texture(n, resolved_paths)
        if mat:
            bPrinter(f"  - {mat.name}", to_blender_editor=True)

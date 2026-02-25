# SPDX-License-Identifier: MIT
"""
Materials module for The Simpsons Game Blender Addon.
Handles material creation, shader node setup, and texture path resolution using a JSON database.
"""
import json
import sys
from pathlib import Path
import bpy
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
            filename = orig_path.split('/')[-1].split('\\')[-1]
            if filename.lower().endswith('.dds'):
                filename = filename[:-4]

            if filename.lower() == norm:
                matches.append(entry)

        if not matches:
            bPrinter(f"[JSON DB] Lookup for '{tex_name}' (normalized: '{norm}') returned no results.", console_colour="yellow", to_blender_editor=True)
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
                            if new_parts[i] == preinstanced_parts[start_idx + i]:
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

        bPrinter(f"[JSON DB] Lookup for '{tex_name}' (normalized: '{norm}') returned: {new_path}", console_colour="green", to_blender_editor=True)
        return new_path
    except Exception as e:
        bPrinter(f"[JSON DB] Lookup error for '{tex_name}': {e}", console_colour="yellow", to_blender_editor=True)
        return None

def _maybe_cache_texture_path(tex_name: str, cache: dict[str, str], preinstanced_filepath: str | None = None) -> None:
    """
    Resolves a texture path and stores it in the provided cache dictionary.
    """
    key = _normalize_tex_name(tex_name)
    if key in cache:
        bPrinter(f"[JSON DB] Cache hit for '{tex_name}': {cache[key]}", console_colour="green", to_blender_editor=True)
        return
    path = _resolve_texture_path_from_db(tex_name, preinstanced_filepath)
    if path:
        cache[key] = path
    bPrinter(f"[JSON DB] Cached path for '{tex_name}': {path if path else 'NOT_FOUND'}", console_colour="green" if path else "yellow", to_blender_editor=True)

# --- Material helpers ---------------------------------------------------------

_material_cache: dict[str, bpy.types.Material] = {}

def _ensure_material_for_texture(tex_name: str, resolved_paths: dict[str, str]) -> bpy.types.Material | None:
    """
    Creates or retrieves a Blender material for the given texture name.
    Configures shader nodes and attempts to load the texture image.
    """
    try:
        key = _normalize_tex_name(tex_name)
        mat_name = f"TEX_{key}"
        if key in _material_cache:
            return _material_cache[key]
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
        relative_path = resolved_paths.get(key) # This is the 'db_source_path'

        if relative_path:
            db_path_str = None
            try:
                # Check if we are in a context where bpy.context is available
                if bpy.context and bpy.context.scene:
                    db_path_str = bpy.context.scene.get("tsg_db_path")
                else:
                    bPrinter("[Material] bpy.context.scene not available.", console_colour="red")
            except Exception as e:
                bPrinter(f"[Material] Error accessing scene or scene property 'tsg_db_path': {e}", console_colour="red")

            if db_path_str:
                # Construct the full absolute path relative to the JSON DB file
                absolute_path = Path(db_path_str).parent / relative_path

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
                    bPrinter(f"[Material] File not found at constructed path: {absolute_path}", console_colour="yellow")
            else:
                bPrinter(f"[Material] 'tsg_db_path' not set in scene. Cannot resolve '{relative_path}'.", console_colour="red")
        else:
            bPrinter(f"[Material] No resolved DB path found for '{tex_name}' (key: '{key}').", console_colour="yellow")

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
    bPrinter(f"[Material] Creating materials for {len(all_names)} texture(s).")
    for n in sorted(all_names):
        _ensure_material_for_texture(n, resolved_paths)

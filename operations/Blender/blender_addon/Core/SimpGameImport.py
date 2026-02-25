"""
Main Blender Operator for importing The Simpsons Game files with texture↔mesh linking.
"""
# SPDX-License-Identifier: MIT

import struct
import io
import math
import sys
from pathlib import Path

# blender imports
import bpy
from bpy.props import StringProperty, CollectionProperty
from bpy_extras.io_utils import ImportHelper
import bmesh

from ..utils.logger import bPrinter
from ..utils.mesh_helpers import strip2face, sanitize_uvs
from ..parser import (
    build_texture_mesh_links,
    find_strings_by_signature_in_data,
    FIXED_SIGNATURES_TO_CHECK,
    MAX_POTENTIAL_STRING_LENGTH,
    MIN_EXTRACTED_STRING_LENGTH,
    CONTEXT_SIZE,
    STRING_CONTEXT_SIZE,
    MESH_REGEX
)
from ..materials import (
    _create_materials_for_all_textures,
    _normalize_tex_name,
    _ensure_material_for_texture
)
from ..bl_info import get_manifest_data, get_version_tuple

class SimpGameImport(bpy.types.Operator, ImportHelper):
    """Blender Operator for importing The Simpsons Game files with texture↔mesh linking."""
    bl_idname = "custom_import_scene.simpgame"
    bl_label = "Import"
    bl_options = {'PRESET', 'UNDO'}
    filter_glob: StringProperty(
        default="*.preinstanced",
        options={'HIDDEN'},
    )
    filepath: StringProperty(subtype='FILE_PATH',)
    files: CollectionProperty(type=bpy.types.PropertyGroup)

    def draw(self, _context: bpy.types.Context) -> None:
        """
        Draw the operator UI in the file browser.
        """
        pass

    def execute(self, _context: bpy.types.Context) -> set:
        """
        Main execution method for the importer. Reads the file, detects textures and meshes, logs information, and prepares for mesh creation.
        """
        manifest = get_manifest_data()
        version = get_version_tuple(manifest.get("version", "1.5.8"))

        bPrinter("== The Simpsons Game Import Log ==", to_blender_editor=True, log_as_metadata=False)
        bPrinter(f"Importer Version: {version[0]}.{version[1]}.{version[2]}", to_blender_editor=True, log_as_metadata=False)
        bPrinter(f"Importing file: {self.filepath}", to_blender_editor=True, log_as_metadata=True)
        file_path = Path(self.filepath)
        bPrinter(f"File size: {file_path.stat().st_size} bytes", to_blender_editor=True, log_as_metadata=False)
        bPrinter(f"File name: {file_path.name}", to_blender_editor=True, log_as_metadata=False)
        bPrinter(f"Output file: {file_path.stem}.blend", to_blender_editor=True, log_as_metadata=False)
        filename = file_path.stem
        bPrinter(f"{filename}", log_as_metadata=True, metadata_key="LOD")

        try:
            with open(self.filepath, "rb") as cur_file:
                tmpRead = cur_file.read()
        except FileNotFoundError:
            bPrinter(f"[Error] File not found: {self.filepath})", console_colour="red")
            return {'CANCELLED'}
        except Exception as e:
            bPrinter(f"[Error] Failed to read file {self.filepath}: {e}", console_colour="red")
            return {'CANCELLED'}

        # --- Dedicated texture pass ---
        bPrinter("\n--- Texture String Pass ---", to_blender_editor=True)
        texture_links_by_mesh_offset, texture_paths_by_name, all_found_tex_names = build_texture_mesh_links(tmpRead, str(self.filepath))
        # Create materials up-front for all discovered textures
        _create_materials_for_all_textures(all_found_tex_names, texture_paths_by_name)

        # --- Log all found texture strings and their resolved paths ---
        bPrinter("\n--- All Found Texture Strings & DB Paths ---", to_blender_editor=True)
        if all_found_tex_names:
            sorted_names = sorted(list(all_found_tex_names), key=lambda s: s.lower())
            bPrinter(f"Found {len(sorted_names)} unique texture strings. Querying DB...", to_blender_editor=True)

            # Get gameroot path once
            gameroot_path = None
            preinstanced_dir = None
            try:
                if bpy.context and bpy.context.scene:
                    gameroot_path = bpy.context.scene.get("tsg_gameroot_path")
                    preinstanced_dir = bpy.context.scene.get("tsg_preinstanced_dir")
            except Exception:
                pass # Fail silently, will be handled in loop

            for name in sorted_names:
                key = _normalize_tex_name(name)
                relative_path = texture_paths_by_name.get(key)

                log_path = "NOT_FOUND_IN_DB"
                if relative_path:
                    if preinstanced_dir:
                        log_path = str(Path(preinstanced_dir) / relative_path)
                    elif gameroot_path:
                        log_path = str(Path(gameroot_path) / "GameFiles" / "STROUT" / relative_path)
                    else:
                        log_path = f"{relative_path} (tsg_preinstanced_dir not set)"

                bPrinter(f"{name} -- {log_path}", to_blender_editor=True)
        else:
            bPrinter("No texture strings were found in the file.", to_blender_editor=True)


        # --- Perform original fixed signature detection (kept for extra visibility) ---
        bPrinter("\n--- Found Embedded Strings (Fixed Signature Scan) ---", to_blender_editor=True)
        string_results = find_strings_by_signature_in_data(
            tmpRead,
            FIXED_SIGNATURES_TO_CHECK,
            MAX_POTENTIAL_STRING_LENGTH,
            MIN_EXTRACTED_STRING_LENGTH,
            CONTEXT_SIZE,
            STRING_CONTEXT_SIZE
        )
        found_string_count = 0
        for item in string_results:
            if item['type'] == 'fixed_signature_string' and item['string_found']:
                found_string_count += 1
                bPrinter(f"{item['string_offset']:08X}: {item['string']}", to_blender_editor=True)

        if found_string_count == 0:
            bPrinter("[String Found] No valid strings found for configured signatures.", to_blender_editor=True)
        else:
            bPrinter(f"[String Found] Total {found_string_count} valid strings found.", to_blender_editor=True)

        # --- Mesh Import Process ---
        bPrinter("\n--- Mesh Import Process ---")
        cur_collection = bpy.data.collections.new("New Mesh")
        bpy.context.scene.collection.children.link(cur_collection)

        mshBytes = MESH_REGEX  # use the compiled regex
        mesh_iter = 0

        data_io = io.BytesIO(tmpRead)

        for x in mshBytes.finditer(tmpRead):
            mesh_chunk_off = x.start()

            data_io.seek(x.end() + 4)
            try:
                FaceDataOff = int.from_bytes(data_io.read(4), byteorder='little')
                MeshDataSize = int.from_bytes(data_io.read(4), byteorder='little')
                MeshChunkStart = data_io.tell()
                data_io.seek(0x14, 1)
                mDataTableCount = int.from_bytes(data_io.read(4), byteorder='big')
                mDataSubCount = int.from_bytes(data_io.read(4), byteorder='big')
                bPrinter(f"[Mesh {mesh_iter}] Found chunk at {x.start():08X}. FaceDataOff: {FaceDataOff}, MeshDataSize: {MeshDataSize}, mDataTableCount: {mDataTableCount}, mDataSubCount: {mDataSubCount}")

                # --- Log linked textures with their full paths ---
                linked_tex_names = texture_links_by_mesh_offset.get(mesh_chunk_off, [])

                # Get gameroot path once for this mesh's log
                gameroot_path = None
                preinstanced_dir = None
                try:
                    if bpy.context and bpy.context.scene:
                        gameroot_path = bpy.context.scene.get("tsg_gameroot_path")
                        preinstanced_dir = bpy.context.scene.get("tsg_preinstanced_dir")
                except Exception:
                    pass # Fail silently, will be handled in loop

                if linked_tex_names:
                    log_entries = []
                    for name in linked_tex_names:
                        # Use the same normalization as the DB cache to find the path
                        key = _normalize_tex_name(name)
                        relative_path = texture_paths_by_name.get(key) # Get path, default if not found

                        log_path = "N/A_IN_CACHE"
                        if relative_path:
                            if preinstanced_dir:
                                full_path = Path(preinstanced_dir) / relative_path
                                if sys.platform == 'win32':
                                    full_path = Path(f"\\\\?\\{str(full_path)}")
                                log_path = str(full_path)
                                if not full_path.exists():
                                    log_path += " (ERROR: texture file not found)"
                                else:
                                    log_path += " (note: texture detected)"
                            elif gameroot_path:
                                full_path = Path(gameroot_path) / "GameFiles" / "STROUT" / relative_path
                                if sys.platform == 'win32':
                                    full_path = Path(f"\\\\?\\{str(full_path)}")
                                log_path = str(full_path)
                                if not full_path.exists():
                                    log_path += " (ERROR: texture file not found)"
                                else:
                                    log_path += " (note: texture detected)"
                            else:
                                log_path = f"{relative_path} (tsg_preinstanced_dir not set)"

                        log_entries.append(f"{name} -- {log_path}")
                    bPrinter(f"[Mesh {mesh_iter}] Linked textures: {', '.join(log_entries)}", to_blender_editor=True)
                else:
                    bPrinter(f"[Mesh {mesh_iter}] Linked textures: (none)", to_blender_editor=True)
                # --- END ---

            except Exception as e:
                bPrinter(f"[Error] Failed to read mesh chunk header data at {x.start():08X}: {e}")
                continue

            for i in range(mDataTableCount):
                data_io.seek(4, 1)
                data_io.read(4)

            mDataSubStart = data_io.tell()

            for i in range(mDataSubCount):
                try:
                    data_io.seek(mDataSubStart + i * 0xC + 8)
                    offset = int.from_bytes(data_io.read(4), byteorder='big')
                    data_io.seek(offset + MeshChunkStart + 0xC)
                    VertCountDataOff = int.from_bytes(data_io.read(4), byteorder='big') + MeshChunkStart
                    data_io.seek(VertCountDataOff)
                    VertChunkTotalSize = int.from_bytes(data_io.read(4), byteorder='big')
                    VertChunkSize = int.from_bytes(data_io.read(4), byteorder='big')
                    if VertChunkSize <= 0:
                        bPrinter(f"[Mesh {mesh_iter}_{i}] Warning: VertChunkSize is non-positive ({VertChunkSize}). Skipping mesh part.")
                        continue
                    VertCount = int(VertChunkTotalSize / VertChunkSize)
                    data_io.seek(8, 1)
                    VertexStart = int.from_bytes(data_io.read(4), byteorder='big') + FaceDataOff + MeshChunkStart
                    data_io.seek(0x14, 1)
                    face_count_bytes_offset = data_io.tell()
                    if face_count_bytes_offset + 4 > len(tmpRead):
                        bPrinter(f"[Mesh {mesh_iter}_{i}] Error: Insufficient data to read FaceCount at offset {face_count_bytes_offset:08X}. Skipping mesh part.")
                        continue
                    FaceCount = int(int.from_bytes(data_io.read(4), byteorder='big') / 2)
                    data_io.seek(4, 1)
                    FaceStart = int.from_bytes(data_io.read(4), byteorder='big') + FaceDataOff + MeshChunkStart

                    bPrinter(f"[MeshPart {mesh_iter}_{i}] Reading data. VertCount: {VertCount}, FaceCount: {FaceCount}, VertexStart: {VertexStart:08X}, FaceStart: {FaceStart:08X}")

                except Exception as e:
                    bPrinter(f"[Error] Failed to read sub-mesh header data for part {mesh_iter}_{i}: {e}")
                    continue

                data_io.seek(FaceStart)
                StripList = []
                tmpList = []
                try:
                    if FaceStart < 0 or FaceStart >= len(tmpRead):
                        bPrinter(f"[MeshPart {mesh_iter}_{i}] Error: FaceStart offset {FaceStart:08X} is out of bounds. Skipping face data read.")
                        FaceCount = 0
                    else:
                        data_io.seek(FaceStart)
                        if FaceStart + FaceCount * 2 > len(tmpRead):
                            bPrinter(f"[MeshPart {mesh_iter}_{i}] Warning: Predicted face data size ({FaceCount * 2} bytes) exceeds file bounds from FaceStart {FaceStart:08X}. Reading available data.")
                            FaceCount = (len(tmpRead) - FaceStart) // 2
                            bPrinter(f"[MeshPart {mesh_iter}_{i}] Adjusted FaceCount to {FaceCount} based on available data.")

                    for f in range(FaceCount):
                        if data_io.tell() + 2 > len(tmpRead):
                            bPrinter(f"[MeshPart {mesh_iter}_{i}] Warning: Hit end of data while reading face index {f}. Stopping face index read.")
                            break
                        Indice = int.from_bytes(data_io.read(2), byteorder='big')
                        if Indice == 65535:
                            if tmpList:
                                StripList.append(tmpList.copy())
                            tmpList.clear()
                        else:
                            tmpList.append(Indice)
                    if tmpList:
                        StripList.append(tmpList.copy())
                except Exception as e:
                    bPrinter(f"[Error] Failed to read face indices for mesh part {mesh_iter}_{i}: {e}")
                    continue

                FaceTable = []
                for f in StripList:
                    FaceTable.extend(strip2face(f))

                VertTable = []
                UVTable = []
                CMTable = []
                try:
                    if VertexStart < 0 or VertexStart >= len(tmpRead):
                        bPrinter(f"[MeshPart {mesh_iter}_{i}] Error: VertexStart offset {VertexStart:08X} is out of bounds. Skipping vertex data read.")
                        VertCount = 0

                    for v in range(VertCount):
                        vert_data_start = VertexStart + v * VertChunkSize
                        if vert_data_start + VertChunkSize > len(tmpRead):
                            bPrinter(f"[MeshPart {mesh_iter}_{i}] Warning: Hit end of data while reading vertex {v}. Stopping vertex read.")
                            break

                        data_io.seek(vert_data_start)

                        if data_io.tell() + 12 > len(tmpRead):
                            bPrinter(f"[MeshPart {mesh_iter}_{i}] Warning: Insufficient data for vertex coords at {data_io.tell():08X} for vertex {v}. Skipping.")
                            continue

                        TempVert = struct.unpack('>fff', data_io.read(4 * 3))
                        VertTable.append(TempVert)

                        # Fixed layout discovered by analyzer
                        FIXED_U_OFFSET = 0x14  # 20 bytes (U)
                        FIXED_V_OFFSET = 0x18  # 24 bytes (V)
                        FIXED_CM_OFFSET = 0x1C # 28 bytes (CM U,V)

                        # Main UV (read U and V separately for robustness)
                        u_off = vert_data_start + FIXED_U_OFFSET
                        v_off = vert_data_start + FIXED_V_OFFSET
                        TempU = 0.0
                        TempV = 0.0
                        if u_off + 4 <= len(tmpRead):
                            data_io.seek(u_off)
                            TempU = struct.unpack('>f', data_io.read(4))[0]
                        else:
                            bPrinter(f"[MeshPart {mesh_iter}_{i}] Warning: Insufficient data for U at {u_off:08X} for vertex {v}.", require_debug_mode=True)
                        if v_off + 4 <= len(tmpRead):
                            data_io.seek(v_off)
                            TempV = struct.unpack('>f', data_io.read(4))[0]
                        else:
                            bPrinter(f"[MeshPart {mesh_iter}_{i}] Warning: Insufficient data for V at {v_off:08X} for vertex {v}.", require_debug_mode=True)
                        # Flip V per findings
                        UVTable.append((TempU, 1.0 - TempV))

                        # Secondary (CM) UV
                        cm_off = vert_data_start + FIXED_CM_OFFSET
                        if cm_off + 8 <= len(tmpRead):
                            data_io.seek(cm_off)
                            cm_u, cm_v = struct.unpack('>ff', data_io.read(8))
                        else:
                            bPrinter(f"[MeshPart {mesh_iter}_{i}] Warning: Insufficient data for CM at {cm_off:08X} for vertex {v}.", require_debug_mode=True)
                            cm_u, cm_v = (0.0, 0.0)
                        CMTable.append((cm_u, 1.0 - cm_v))

                    # Diagnostics: stride and UV uniqueness
                    try:
                        uniq_uvs = len({(round(u,5), round(v,5)) for (u,v) in UVTable})
                        bPrinter(f"[MeshPart {mesh_iter}_{i}] Read {len(VertTable)} vertices, {len(UVTable)} UVs, {len(CMTable)} CMs. Stride={VertChunkSize} (0x{VertChunkSize:X}) UniqueUV={uniq_uvs}")
                    except Exception:
                        bPrinter(f"[MeshPart {mesh_iter}_{i}] Read {len(VertTable)} vertices, {len(UVTable)} UVs, {len(CMTable)} CMs.")

                except Exception as e:
                    bPrinter(f"[Error] Failed to read vertex data for mesh part {mesh_iter}_{i}: {e}")
                    continue

                if not VertTable or not FaceTable:
                    bPrinter(f"[MeshPart {mesh_iter}_{i}] Warning: No valid vertices or faces read for mesh part. Skipping mesh creation.")
                    continue

                mesh1 = bpy.data.meshes.new(f"Mesh_{mesh_iter}_{i}")
                # check if mesh1 has .use_auto_smooth attribute before setting it
                if hasattr(mesh1, 'use_auto_smooth'):
                    mesh1.use_auto_smooth = True
                else:
                    bPrinter(f"[MeshPart {mesh_iter}_{i}] Warning: Mesh object does not support 'use_auto_smooth'. Skipping this setting.", require_debug_mode=True, console_colour="yellow", to_blender_editor=True)

                obj = bpy.data.objects.new(f"Mesh_{mesh_iter}_{i}", mesh1)

                cur_collection.objects.link(obj)
                bpy.context.view_layer.objects.active = obj
                obj.select_set(True)
                mesh_data = bpy.context.object.data
                bm = bmesh.new()

                for v_co in VertTable:
                    bm.verts.new(v_co)
                bm.verts.ensure_lookup_table()
                bm.verts.index_update()
                bPrinter(f"[MeshPart {mesh_iter}_{i}] Added {len(bm.verts)} vertices to BMesh.")

                faces_created_count = 0
                for f_indices in FaceTable:
                    try:
                        valid_face = True
                        face_verts = []
                        for idx in f_indices:
                            if idx < 0 or idx >= len(bm.verts):
                                bPrinter(f"[FaceError] Invalid vertex index {idx} in face {f_indices}. Skipping face.")
                                valid_face = False
                                break
                            face_verts.append(bm.verts[idx])
                        if valid_face:
                            try:
                                bm.faces.new(face_verts)
                                faces_created_count += 1
                            except ValueError as e:
                                bPrinter(f"[FaceWarning] Failed to create face {f_indices} ({len(face_verts)} verts): {e}. Skipping.")
                            except Exception as e:
                                bPrinter(f"[FaceError] Unexpected error creating face {f_indices}: {e}. Skipping.")
                    except Exception as e:
                        bPrinter(f"[FaceError] Unhandled error processing face indices {f_indices}: {e}")
                        continue

                bPrinter(f"[MeshPart {mesh_iter}_{i}] Attempted to create {len(FaceTable)} faces, successfully created {faces_created_count}.")
                # Ensure element indices are valid before using l.vert.index
                bm.verts.ensure_lookup_table()
                bm.faces.ensure_lookup_table()
                bm.verts.index_update()
                bm.edges.index_update()
                bm.faces.index_update()

                if not bm.faces:
                    bPrinter(f"[BMeshWarning] No faces created for mesh {mesh_iter}_{i}. Skipping UV assignment and further processing for this mesh part.")
                    bm.free()
                    if mesh1:
                        if mesh1.users == 1:
                            bpy.data.meshes.remove(mesh1)
                            bPrinter(f"[BMeshWarning] Removed unused mesh data block '{mesh1.name}'.")
                    if obj:
                        if obj.users == 1:
                            for col in bpy.data.collections:
                                if obj.name in col.objects:
                                    col.objects.unlink(obj)
                            bpy.data.objects.remove(obj)
                            bPrinter(f"[BMeshWarning] Removed unused object '{obj.name}'.")
                    continue

                uv_layer = bm.loops.layers.uv.get("uvmap")
                if uv_layer is None:
                    uv_layer = bm.loops.layers.uv.new("uvmap")
                    bPrinter("[Info] Created new 'uvmap' layer.")

                cm_layer = bm.loops.layers.uv.get("CM_uv")
                if cm_layer is None:
                    cm_layer = bm.loops.layers.uv.new("CM_uv")
                    bPrinter("[Info] Created new 'CM_uv' layer.")

                uv_layer_name = uv_layer.name
                cm_layer_name = cm_layer.name

                uv_assigned_count = 0
                cm_assigned_count = 0
                unique_loop_uvs = set()
                unique_loop_cmuvs = set()
                used_vert_indices = set()
                for f in bm.faces:
                    f.smooth = True
                    for l in f.loops:
                        vert_index = l.vert.index
                        used_vert_indices.add(vert_index)
                        if vert_index < 0 or vert_index >= len(UVTable) or vert_index >= len(CMTable):
                            bPrinter(f"[UVError] Vertex index {vert_index} out of range for UV/CM tables ({len(UVTable)}/{len(CMTable)}) during assignment for mesh part {mesh_iter}_{i}. Skipping UV assignment for this loop.")
                            l[uv_layer].uv = (0.0, 0.0)
                            l[cm_layer].uv = (0.0, 0.0)
                            continue
                        try:
                            uv_coords = UVTable[vert_index]
                            if all(math.isfinite(c) for c in uv_coords):
                                l[uv_layer].uv = uv_coords
                                uv_assigned_count += 1
                                unique_loop_uvs.add((round(uv_coords[0],5), round(uv_coords[1],5)))
                            else:
                                bPrinter(f"[Inline-Sanitize] Non-finite main UV for vertex {vert_index} in loop of mesh part {mesh_iter}_{i}. Assigning (0.0, 0.0).", require_debug_mode=True)
                                l[uv_layer].uv = (0.0, 0.0)
                                uv_assigned_count += 1
                            cm_coords = CMTable[vert_index]
                            if all(math.isfinite(c) for c in cm_coords):
                                l[cm_layer].uv = cm_coords
                                cm_assigned_count += 1
                                unique_loop_cmuvs.add((round(cm_coords[0],5), round(cm_coords[1],5)))
                            else:
                                bPrinter(f"[Inline-Sanitize] Non-finite CM UV for vertex {vert_index} in loop of mesh part {mesh_iter}_{i}. Assigning (0.0, 0.0).", require_debug_mode=True)
                                l[cm_layer].uv = (0.0, 0.0)
                                cm_assigned_count += 1
                        except Exception as e:
                            bPrinter(f"[UVError] Failed to assign UV/CM for vertex {vert_index} in loop of mesh part {mesh_iter}_{i}: {e}")
                            l[uv_layer].uv = (0.0, 0.0)
                            l[cm_layer].uv = (0.0, 0.0)
                            continue

                try:
                    bPrinter(f"[MeshPart {mesh_iter}_{i}] Assigned UVs to {uv_assigned_count} loops, CM UVs to {cm_assigned_count} loops. UniqueLoopUV={len(unique_loop_uvs)} UniqueLoopCMUV={len(unique_loop_cmuvs)} UsedVerts={len(used_vert_indices)}")
                except Exception:
                    bPrinter(f"[MeshPart {mesh_iter}_{i}] Assigned UVs to {uv_assigned_count} loops, CM UVs to {cm_assigned_count} loops.")
                bm.to_mesh(mesh_data)
                bm.free()
                bPrinter(f"[MeshPart {mesh_iter}_{i}] BMesh converted to mesh data.")

                # Ensure the intended UV layer is active for viewport/export
                try:
                    if uv_layer_name in mesh_data.uv_layers:
                        # Set active and active_render to main UV layer
                        main_idx = None
                        for idx, layer in enumerate(mesh_data.uv_layers):
                            if layer.name == uv_layer_name:
                                main_idx = idx
                                break
                        if main_idx is not None:
                            mesh_data.uv_layers.active = mesh_data.uv_layers[main_idx]
                            mesh_data.uv_layers.active_index = main_idx
                            mesh_data.uv_layers[main_idx].active_render = True

                        if cm_layer_name in mesh_data.uv_layers:
                            for layer in mesh_data.uv_layers:
                                if layer.name == cm_layer_name:
                                    layer.active_render = False
                                    break
                        bPrinter(f"[MeshPart {mesh_iter}_{i}] Set active UV layer to '{uv_layer_name}'.")
                except Exception as e:
                    bPrinter(f"[UV-Active] Failed to set active UV layer: {e}")

                if uv_layer_name in mesh_data.uv_layers:
                    sanitize_uvs(mesh_data.uv_layers[uv_layer_name])
                else:
                    bPrinter(f"[Sanitize] Warning: Main UV layer '{uv_layer_name}' not found on mesh data block after to_mesh for mesh {mesh_iter}_{i}.")

                if cm_layer_name in mesh_data.uv_layers:
                    sanitize_uvs(mesh_data.uv_layers[cm_layer_name])
                else:
                    bPrinter(f"[Sanitize] Warning: CM UV layer '{cm_layer_name}' not found on mesh data block after to_mesh for mesh {mesh_iter}_{i}.")

                # Apply the first linked texture's material to this object by default
                try:
                    # Use the original variable that just has names for material linking
                    linked_tex_for_mat = texture_links_by_mesh_offset.get(mesh_chunk_off, [])

                    if linked_tex_for_mat:
                        # Deduplicate while preserving order
                        unique_tex_names = []
                        for tex_name in linked_tex_for_mat:
                            if tex_name not in unique_tex_names:
                                unique_tex_names.append(tex_name)

                        # Append all unique materials to the object
                        for tex_name in unique_tex_names:
                            mat = _ensure_material_for_texture(tex_name, texture_paths_by_name)
                            if mat:
                                obj.data.materials.append(mat)

                        # Determine target texture for this submesh
                        target_tex_name = linked_tex_for_mat[i] if i < len(linked_tex_for_mat) else linked_tex_for_mat[0]

                        # Find the index of the target material
                        target_mat_index = 0
                        if target_tex_name in unique_tex_names:
                            target_mat_index = unique_tex_names.index(target_tex_name)

                        # Assign the material index to all polygons
                        for poly in obj.data.polygons:
                            poly.material_index = target_mat_index

                        obj.active_material_index = target_mat_index

                        bPrinter(f"[MeshPart {mesh_iter}_{i}] Assigned material '{target_tex_name}' (index {target_mat_index}) and added {len(unique_tex_names)} materials to slots.")
                except Exception as e:
                    bPrinter(f"[Material] Failed to assign material on mesh part {mesh_iter}_{i}: {e}", console_colour="yellow")

                obj.rotation_euler = (1.5707963705062866, 0, 0)
                bPrinter(f"[MeshPart {mesh_iter}_{i}] Object created '{obj.name}' and rotated.")

            mesh_iter += 1

        bPrinter("== Import Complete ==", to_blender_editor=True)
        return {'FINISHED'}

def menu_func_import(self: bpy.types.Menu, _context: bpy.types.Context) -> None:
    """
    Function to add the importer to the Blender file import menu.
    """
    self.layout.operator(SimpGameImport.bl_idname, text="The Simpsons Game (.rws,dff)")

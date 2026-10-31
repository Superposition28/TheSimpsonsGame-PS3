"""
Main Blender Operator for importing The Simpsons Game files with texture↔mesh linking.
"""
# SPDX-License-Identifier: MIT

import io
import os
import struct
import math
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
    _ensure_material_for_texture,
    clear_material_cache,
    resolve_asset_paths_from_db
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
        # Clear global caches to ensure a fresh state
        clear_material_cache()

        # Clear old log text blocks
        for log_name in ["SimpGame_Import_Log", "SimpGame_Importer_Log"]:
            if log_name in bpy.data.texts:
                bpy.data.texts.remove(bpy.data.texts[log_name])

        manifest = get_manifest_data()
        version = get_version_tuple(manifest.get("version", "1.5.8"))

        bPrinter("== The Simpsons Game Import Log ==", to_blender_editor=True, log_as_metadata=False)
        bPrinter(f"Importer Version: {version[0]}.{version[1]}.{version[2]}", to_blender_editor=True, log_as_metadata=False)
        bPrinter(f"Importing file: {self.filepath}", to_blender_editor=True, log_as_metadata=True)
        # Extract base name (e.g., lodmodel1_9c6d15 from lodmodel1_9c6d15.rws.PS3.preinstanced)
        filename = Path(self.filepath).name.split('.')[0]
        orig_p, new_p = resolve_asset_paths_from_db(filename, self.filepath)
        if orig_p:
            bPrinter(f"Original mapping: {orig_p}", console_colour="green", to_blender_editor=True)
        if new_p:
            bPrinter(f"New mapping: {new_p}", console_colour="green", to_blender_editor=True)

        norm_filepath = str(self.filepath)
        if os.name == 'nt' and len(os.path.abspath(norm_filepath)) >= 240 and not norm_filepath.startswith('\\\\?\\'):
            norm_filepath = '\\\\?\\' + os.path.abspath(norm_filepath)

        file_path = Path(norm_filepath)
        file_size = 0
        try:
            file_size = file_path.stat().st_size
        except Exception:
            try:
                file_size = os.path.getsize(norm_filepath)
            except Exception:
                pass

        bPrinter(f"File size: {file_size} bytes", to_blender_editor=True, log_as_metadata=False)
        bPrinter(f"File name: {Path(self.filepath).name}", to_blender_editor=True, log_as_metadata=False)
        bPrinter(f"Output file: {Path(self.filepath).stem}.blend", to_blender_editor=True, log_as_metadata=False)
        filename = Path(self.filepath).stem
        bPrinter(f"{filename}", log_as_metadata=True, metadata_key="LOD")

        try:
            with open(norm_filepath, "rb") as cur_file:
                tmpRead = cur_file.read()
        except FileNotFoundError:
            bPrinter(f"[Error] File not found: {self.filepath})", console_colour="red")
            return {'CANCELLED'}
        except Exception as e:
            bPrinter(f"[Error] Failed to read file {self.filepath}: {e}", console_colour="red")
            return {'CANCELLED'}

        # --- Dedicated texture & material pass ---
        texture_links_by_mesh_offset, texture_paths_by_name, all_found_tex_names, mesh_materials_by_offset = build_texture_mesh_links(tmpRead, str(self.filepath))
        bPrinter(f"\n--- Texture String Pass ({len(all_found_tex_names)} unique textures) ---", to_blender_editor=True)
        # Create materials up-front for all discovered textures
        _create_materials_for_all_textures(all_found_tex_names, texture_paths_by_name)

        # --- Log all found texture strings and their resolved paths ---
        bPrinter("\n--- All Found Texture Strings & DB Paths ---", to_blender_editor=True)
        if all_found_tex_names:
            sorted_names = sorted(list(all_found_tex_names), key=lambda s: s.lower())
            bPrinter(f"Found {len(sorted_names)} unique texture strings. Querying DB...", to_blender_editor=True)

            for name in sorted_names:
                key = _normalize_tex_name(name)
                final_path = texture_paths_by_name.get(key, "NOT_FOUND")
                bPrinter(f"{name} -- {final_path}", to_blender_editor=True, print_to_console=False)
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
                bPrinter(f"{item['string_offset']:08X}: {item['string']}", to_blender_editor=True, print_to_console=False)

        if found_string_count == 0:
            bPrinter("[String Found] No valid strings found for configured signatures.", to_blender_editor=True, print_to_console=False)
        else:
            bPrinter(f"[String Found] Total {found_string_count} valid strings found.", to_blender_editor=True, print_to_console=False)

        # --- Mesh Import Process ---
        mesh_chunks = list(MESH_REGEX.finditer(tmpRead))
        total_meshes = len(mesh_chunks)

        if total_meshes == 0:
            bPrinter(f"Skipping import: No mesh data found in {filename} (Likely an empty/dummy LOD).", console_colour="yellow", to_blender_editor=True)
            return {'FINISHED'}

        total_submeshes = 0

        # Pre-scan for total submesh count for summary
        temp_io = io.BytesIO(tmpRead)
        for x in mesh_chunks:
            try:
                # Buffer 1 base is at x.start() + 24; SubmeshCount is at Buffer 1 base + 0x18
                temp_io.seek(x.start() + 24 + 0x18)
                total_submeshes += int.from_bytes(temp_io.read(4), byteorder='big')
            except Exception:
                pass

        bPrinter(f"\n--- Mesh Import Process (Total Meshes: {total_meshes}, Total Submeshes: {total_submeshes}) ---", to_blender_editor=True)

        # --- Cleanup existing "New Mesh" collection ---
        collection_name = "New Mesh"
        if collection_name in bpy.data.collections:
            old_collection = bpy.data.collections[collection_name]
            bPrinter(f"Found existing '{collection_name}' collection. Cleaning up old meshes...", to_blender_editor=True, console_colour="yellow")

            # Remove all objects inside the collection and their mesh data
            for obj in list(old_collection.objects):
                mesh_data = obj.data if obj.type == 'MESH' else None
                bpy.data.objects.remove(obj, do_unlink=True)
                if mesh_data and mesh_data.users == 0:
                    bpy.data.meshes.remove(mesh_data, do_unlink=True)

            bpy.data.collections.remove(old_collection)

        # --- Create fresh collection ---
        cur_collection = bpy.data.collections.new(collection_name)
        bpy.context.scene.collection.children.link(cur_collection)

        data_io = io.BytesIO(tmpRead)

        for mesh_iter, x in enumerate(mesh_chunks):
            mesh_chunk_off = x.start()
            MeshChunkSize = int.from_bytes(tmpRead[mesh_chunk_off + 4:mesh_chunk_off + 8], byteorder='little')

            data_io.seek(x.end())
            try:
                FormatVersion = int.from_bytes(data_io.read(4), byteorder='little')
                HeaderDataSize = int.from_bytes(data_io.read(4), byteorder='little')
                GpuDataSize = int.from_bytes(data_io.read(4), byteorder='little')

                Buffer1_Base = data_io.tell()
                Buffer2_Base = Buffer1_Base + HeaderDataSize

                is_valid_inv = (12 + HeaderDataSize + GpuDataSize == MeshChunkSize)
                bPrinter(
                    f"[Mesh {mesh_iter}] Offset: {mesh_chunk_off:08X} | ChunkSize: {MeshChunkSize} | Buffer1 (HeaderData): {HeaderDataSize}B | Buffer2 (GPUData): {GpuDataSize}B | Invariant: {is_valid_inv}",
                    to_blender_editor=True
                )

                # Read RelocCount at Buffer1 + 0x14 and SubmeshCount at Buffer1 + 0x18
                data_io.seek(Buffer1_Base + 0x14)
                mDataTableCount = int.from_bytes(data_io.read(4), byteorder='big')
                mDataSubCount = int.from_bytes(data_io.read(4), byteorder='big')

                data_table_bytes = data_io.read(mDataTableCount * 8)
                bPrinter(
                    f"  [DataTable] RelocCount: {mDataTableCount} | SubmeshCount: {mDataSubCount} | RelocBytes: {data_table_bytes.hex(' ').upper()}",
                    to_blender_editor=True
                )

                # Submesh table starts at Buffer1_Base + 0x1C + RelocCount * 8
                mDataSubStart = Buffer1_Base + 0x1C + mDataTableCount * 8

                mat_list = mesh_materials_by_offset.get(mesh_chunk_off, [])
                if mat_list:
                    formatted_mats = [f"[{idx}]: {name if name else '(untextured)'}" for idx, name in enumerate(mat_list)]
                    bPrinter(f"  Geometry Materials: {', '.join(formatted_mats)}", to_blender_editor=True)
                else:
                    bPrinter("  Geometry Materials: (none)", to_blender_editor=True)

            except Exception as e:
                bPrinter(f"[Error] Failed to read mesh chunk header data at {mesh_chunk_off:08X}: {e}")
                continue

            for i in range(mDataSubCount):
                try:
                    data_io.seek(mDataSubStart + i * 0xC + 8)
                    submesh_rel_offset = int.from_bytes(data_io.read(4), byteorder='big')

                    submesh_hdr_off = Buffer1_Base + submesh_rel_offset
                    data_io.seek(submesh_hdr_off)
                    submesh_header = data_io.read(16)
                    material_id = int.from_bytes(submesh_header[8:12], byteorder='big')
                    vert_info_rel_offset = int.from_bytes(submesh_header[12:16], byteorder='big')

                    bPrinter(
                        f"    [Submesh {i}] Material ID: {material_id} | Header: {submesh_header.hex(' ').upper()}",
                        to_blender_editor=True
                    )

                    vert_info_off = Buffer1_Base + vert_info_rel_offset
                    data_io.seek(vert_info_off)
                    VertChunkTotalSize = int.from_bytes(data_io.read(4), byteorder='big')
                    VertChunkSize = int.from_bytes(data_io.read(4), byteorder='big')
                    if VertChunkSize <= 0:
                        bPrinter(f"[Mesh {mesh_iter}_{i}] Warning: VertChunkSize is non-positive ({VertChunkSize}). Skipping mesh part.")
                        continue
                    if VertChunkSize < 12:
                        bPrinter(f"[Mesh {mesh_iter}_{i}] Warning: VertChunkSize is too small for a position ({VertChunkSize}). Skipping mesh part.")
                        continue
                    VertCount = VertChunkTotalSize // VertChunkSize

                    data_io.seek(vert_info_off + 0x10)
                    VertexStartRel = int.from_bytes(data_io.read(4), byteorder='big')
                    VertexStart = Buffer2_Base + VertexStartRel

                    data_io.seek(vert_info_off + 0x28)
                    FaceIndexByteCount = int.from_bytes(data_io.read(4), byteorder='big')
                    FaceCount = FaceIndexByteCount // 2

                    data_io.seek(vert_info_off + 0x30)
                    FaceStartRel = int.from_bytes(data_io.read(4), byteorder='big')
                    FaceStart = Buffer2_Base + FaceStartRel

                    bPrinter(
                        f"[MeshPart {mesh_iter}_{i}] Reading data. VertCount: {VertCount} (Stride: {VertChunkSize}), FaceCount: {FaceCount}, VertexStart: {VertexStart:08X}, FaceStart: {FaceStart:08X}"
                    )

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

                        # Dynamic stride UV layout:
                        # Primary UV is at stride - 8 (U) and stride - 4 (V)
                        # Secondary CM UV is at stride - 16 (U) and stride - 12 (V) when available
                        TempU = 0.0
                        TempV = 0.0
                        cm_u = 0.0
                        cm_v = 0.0

                        if VertChunkSize >= 20:
                            u_off = vert_data_start + VertChunkSize - 8
                            v_off = vert_data_start + VertChunkSize - 4
                            if u_off + 4 <= len(tmpRead) and v_off + 4 <= len(tmpRead):
                                data_io.seek(u_off)
                                TempU = struct.unpack('>f', data_io.read(4))[0]
                                data_io.seek(v_off)
                                TempV = struct.unpack('>f', data_io.read(4))[0]

                        # Flip V per RenderWare / Blender convention
                        UVTable.append((TempU, 1.0 - TempV))

                        if VertChunkSize >= 36:
                            cmu_off = vert_data_start + VertChunkSize - 16
                            cmv_off = vert_data_start + VertChunkSize - 12
                            if cmu_off + 4 <= len(tmpRead) and cmv_off + 4 <= len(tmpRead):
                                data_io.seek(cmu_off)
                                cm_u = struct.unpack('>f', data_io.read(4))[0]
                                data_io.seek(cmv_off)
                                cm_v = struct.unpack('>f', data_io.read(4))[0]

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
                bm.verts.ensure_lookup_table()
                bm.faces.ensure_lookup_table()
                bm.verts.index_update()
                bm.edges.index_update()
                bm.faces.index_update()

                if not bm.faces:
                    bPrinter(f"[BMeshWarning] No faces created for mesh {mesh_iter}_{i}. Skipping UV assignment and further processing for this mesh part.")
                    bm.free()
                    if mesh1 and mesh1.users == 1:
                        bpy.data.meshes.remove(mesh1)
                    if obj and obj.users == 1:
                        for col in bpy.data.collections:
                            if obj.name in col.objects:
                                col.objects.unlink(obj)
                        bpy.data.objects.remove(obj)
                    continue

                uv_layer = bm.loops.layers.uv.get("uvmap")
                if uv_layer is None:
                    uv_layer = bm.loops.layers.uv.new("uvmap")

                cm_layer = bm.loops.layers.uv.get("CM_uv")
                if cm_layer is None:
                    cm_layer = bm.loops.layers.uv.new("CM_uv")

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
                                l[uv_layer].uv = (0.0, 0.0)
                                uv_assigned_count += 1
                            cm_coords = CMTable[vert_index]
                            if all(math.isfinite(c) for c in cm_coords):
                                l[cm_layer].uv = cm_coords
                                cm_assigned_count += 1
                                unique_loop_cmuvs.add((round(cm_coords[0],5), round(cm_coords[1],5)))
                            else:
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
                except Exception as e:
                    bPrinter(f"[UV-Active] Failed to set active UV layer: {e}")

                if uv_layer_name in mesh_data.uv_layers:
                    sanitize_uvs(mesh_data.uv_layers[uv_layer_name])
                if cm_layer_name in mesh_data.uv_layers:
                    sanitize_uvs(mesh_data.uv_layers[cm_layer_name])

                # --- Material Assignment using 1-to-1 Geometry Material Mapping ---
                try:
                    mat_list = mesh_materials_by_offset.get(mesh_chunk_off, [])
                    target_tex_name = None

                    if 0 <= material_id < len(mat_list):
                        target_tex_name = mat_list[material_id]
                    elif mat_list:
                        bPrinter(
                            f"    [Warning] Material ID {material_id} out of bounds for geometry material list (len {len(mat_list)}). Falling back to first material.",
                            console_colour="yellow",
                            to_blender_editor=True
                        )
                        target_tex_name = mat_list[0]
                    else:
                        # Legacy fallback if geometry material list was empty
                        linked_tex_for_mat = texture_links_by_mesh_offset.get(mesh_chunk_off, [])
                        if linked_tex_for_mat:
                            target_tex_name = linked_tex_for_mat[min(material_id, len(linked_tex_for_mat) - 1)]

                    if target_tex_name:
                        mat = _ensure_material_for_texture(target_tex_name, texture_paths_by_name)
                        if mat:
                            if mat.name not in obj.data.materials:
                                obj.data.materials.append(mat)
                            mat_idx = list(obj.data.materials).index(mat)
                            for poly in obj.data.polygons:
                                poly.material_index = mat_idx
                            obj.active_material_index = mat_idx
                            bPrinter(f"    Submesh {i}: Assigned material '{mat.name}' (Material ID: {material_id}, Texture: {target_tex_name})", to_blender_editor=True)
                    else:
                        untextured_name = f"MAT_Untextured_{material_id}"
                        mat = bpy.data.materials.get(untextured_name)
                        if mat is None:
                            mat = bpy.data.materials.new(name=untextured_name)
                            mat.use_nodes = True
                        if mat.name not in obj.data.materials:
                            obj.data.materials.append(mat)
                        mat_idx = list(obj.data.materials).index(mat)
                        for poly in obj.data.polygons:
                            poly.material_index = mat_idx
                        obj.active_material_index = mat_idx
                        bPrinter(f"    Submesh {i}: Assigned untextured material '{untextured_name}' (Material ID: {material_id})", to_blender_editor=True)

                except Exception as e:
                    bPrinter(f"[Material] Failed to assign material on mesh part {mesh_iter}_{i}: {e}", console_colour="yellow", to_blender_editor=True)

                obj.rotation_euler = (1.5707963705062866, 0, 0)
                bPrinter(f"[MeshPart {mesh_iter}_{i}] Object created '{obj.name}' and rotated.")

                # Weld surfaces and separate by loose parts
                try:
                    MERGE_DISTANCE = 0.005

                    bpy.ops.object.select_all(action='DESELECT')
                    bpy.context.view_layer.objects.active = obj
                    obj.select_set(True)

                    bpy.ops.object.mode_set(mode='EDIT')
                    bpy.ops.mesh.select_all(action='SELECT')
                    bpy.ops.mesh.remove_doubles(threshold=MERGE_DISTANCE)
                    bpy.ops.mesh.separate(type='LOOSE')
                    bpy.ops.object.mode_set(mode='OBJECT')

                    bPrinter(f"    Welded seams and separated '{obj.name}' into independent parts.", to_blender_editor=True)
                except Exception as e:
                    if bpy.context.object and bpy.context.object.mode == 'EDIT':
                        bpy.ops.object.mode_set(mode='OBJECT')
                    bPrinter(f"    [Warning] Failed to separate parts for {obj.name}: {e}", console_colour="yellow")

        bPrinter("== Import Complete ==", to_blender_editor=True)
        return {'FINISHED'}

def menu_func_import(self: bpy.types.Menu, _context: bpy.types.Context) -> None:
    """
    Function to add the importer to the Blender file import menu.
    """
    self.layout.operator(SimpGameImport.bl_idname, text="The Simpsons Game (.rws,dff)")

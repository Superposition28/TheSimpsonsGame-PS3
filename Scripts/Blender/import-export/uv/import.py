import bpy
import os
import csv
import json
import time
import struct # Import the struct module for binary unpacking
from bpy_extras.io_utils import ImportHelper
from bpy.types import Operator

# --- Addon Information ---
bl_info = {
    "name": "UV Importer",
    "author": "Samarixum",
    "version": (1, 0, 0),
    "blender": (4, 0, 0),
    "location": "3D View > Tool Shelf > UV Importer",
    "description": "Exports UV data in various formats",
    "category": "Import-Export",
}

# ------------------------
# Helper function to load UV and collection data from file
# Handles CSV, JSON, and Binary (.buvd) formats
# ------------------------

def load_uv_data_from_file(filepath):
    """
    Loads UV and collection data from a file (CSV, JSON, or .buvd).

    Args:
        filepath (str): The path to the file.

    Returns:
        dict: A dictionary containing the structured UV and collection data,
            or None if the file format is not recognized or an error occurs.
    """
    if not os.path.exists(filepath):
        print(f"❌ File not found: {filepath}")
        return None

    _, ext = os.path.splitext(filepath)
    ext = ext.lower()

    uv_data = {"objects": []}

    if ext == '.csv':
        print(f"Loading data from CSV: {filepath}")
        csv_raw_data = {}
        try:
            with open(filepath, 'r', newline='') as csvfile:
                reader = csv.DictReader(csvfile)
                for row in reader:
                    mesh_name = row.get('MeshName')
                    face_str = row.get('Face')
                    loop_str = row.get('Loop')
                    u_str = row.get('U')
                    v_str = row.get('V')
                    center_x = row.get('CenterX')
                    center_y = row.get('CenterY')
                    center_z = row.get('CenterZ')
                    vertex_indices_str = row.get('VertexIndices', '')
                    collections_str = row.get('Collections', '')

                    if not all([mesh_name, face_str, loop_str, u_str, v_str]):
                        print(f"[WARN] Skipping invalid row in CSV: {row}")
                        continue

                    try:
                        face_index = int(face_str.split('_')[1])
                        loop_index = int(loop_str.split('_')[1])
                        u = float(u_str)
                        v = float(v_str)
                        face_center = [float(center_x), float(center_y), float(center_z)] if center_x and center_y and center_z else None
                        vertex_indices = list(map(int, vertex_indices_str.split(','))) if vertex_indices_str else []
                        collections = collections_str.split(', ') if collections_str else []
                    except (ValueError, IndexError) as e:
                        print(f"[WARN] Skipping row with invalid data format in CSV: {row} - {e}")
                        continue

                    if mesh_name not in csv_raw_data:
                        csv_raw_data[mesh_name] = {
                            "collections": collections,
                            "faces": {}
                        }

                    if face_index not in csv_raw_data[mesh_name]["faces"]:
                        csv_raw_data[mesh_name]["faces"][face_index] = {
                            "index": face_index,
                            "center": face_center,
                            "vertex_indices": vertex_indices,
                            "loops": []
                        }

                    csv_raw_data[mesh_name]["faces"][face_index]["loops"].append({
                        "index": loop_index,
                        "uv": [u, v]
                    })

            # Convert the raw CSV data structure to the unified format
            for mesh_name, mesh_data in csv_raw_data.items():
                sorted_faces = sorted(mesh_data["faces"].values(), key=lambda f: f["index"])
                uv_data["objects"].append({
                    "name": mesh_name,
                    "collections": mesh_data["collections"],
                    "faces": sorted_faces
                })

        except Exception as e:
            print(f"❌ Error reading CSV file: {e}")
            return None

    elif ext == '.json':
        print(f"Loading data from JSON: {filepath}")
        try:
            with open(filepath, 'r', encoding='utf-8') as jsonfile:
                loaded_data = json.load(jsonfile)

            # Assuming the JSON structure from the exporter: {"objects": [...]}
            if isinstance(loaded_data, dict) and "objects" in loaded_data and isinstance(loaded_data["objects"], list):
                uv_data = loaded_data
            else:
                print(f"❌ JSON file does not match expected structure.")
                return None

        except Exception as e:
            print(f"❌ Error reading JSON file: {e}")
            return None

    elif ext == '.buvd':
        print(f"Loading data from Binary (.buvd): {filepath}")
        try:
            with open(filepath, 'rb') as binfile:
                # Read Header: Magic (4s), Version (B), NumObjects (I)
                header_format = '<4sBI'
                header_size = struct.calcsize(header_format)
                header_data = binfile.read(header_size)

                if len(header_data) < header_size:
                    print("❌ Binary file is too short to contain header.")
                    return None

                magic, version, num_objects = struct.unpack(header_format, header_data)

                if magic != b'BUVD':
                    print(f"❌ Invalid binary file magic number: {magic}. Expected b'BUVD'.")
                    return None

                if version != 1:
                    print(f"⚠️ Warning: Binary file version is {version}, expected 1. Compatibility issues may occur.")

                print(f"✅ Header read successfully: Magic={magic}, Version={version}, NumObjects={num_objects}")

                # Read Objects
                for obj_index in range(num_objects):
                    # Read Object: NameLen (I), Name (s)
                    name_len_format = '<I'
                    name_len_size = struct.calcsize(name_len_format)
                    name_len_data = binfile.read(name_len_size)
                    if len(name_len_data) < name_len_size:
                        print(f"❌ Binary file ended unexpectedly while reading object {obj_index} name length.")
                        return None
                    name_len = struct.unpack(name_len_format, name_len_data)[0]

                    obj_name_bytes = binfile.read(name_len)
                    if len(obj_name_bytes) < name_len:
                        print(f"❌ Binary file ended unexpectedly while reading object {obj_index} name.")
                        return None
                    obj_name = obj_name_bytes.decode('utf-8')

                    print(f"✅ Object {obj_index}: Name={obj_name}")

                    # Read Collections: NumCollections (I), [Collection: NameLen (I), Name (s)]
                    num_collections_format = '<I'
                    num_collections_size = struct.calcsize(num_collections_format)
                    num_collections_data = binfile.read(num_collections_size)
                    if len(num_collections_data) < num_collections_size:
                        print(f"❌ Binary file ended unexpectedly while reading object {obj_index} number of collections.")
                        return None
                    num_collections = struct.unpack(num_collections_format, num_collections_data)[0]

                    collections = []
                    for col_index in range(num_collections):
                        col_name_len_format = '<I'
                        col_name_len_size = struct.calcsize(col_name_len_format)
                        col_name_len_data = binfile.read(col_name_len_size)
                        if len(col_name_len_data) < col_name_len_size:
                            print(f"❌ Binary file ended unexpectedly while reading collection {col_index} name length.")
                            return None
                        col_name_len = struct.unpack(col_name_len_format, col_name_len_data)[0]

                        col_name_bytes = binfile.read(col_name_len)
                        if len(col_name_bytes) < col_name_len:
                            print(f"❌ Binary file ended unexpectedly while reading collection {col_index} name.")
                            return None
                        collections.append(col_name_bytes.decode('utf-8'))

                    print(f"✅ Object {obj_index}: Collections={collections}")

                    # Read Faces: NumFaces (I), [Face: Index (I), NumLoops (I), [Loop: Index (I), U (f), V (f)]]
                    num_faces_format = '<I'
                    num_faces_size = struct.calcsize(num_faces_format)
                    num_faces_data = binfile.read(num_faces_size)
                    if len(num_faces_data) < num_faces_size:
                        print(f"❌ Binary file ended unexpectedly while reading object {obj_index} number of faces.")
                        return None
                    num_faces = struct.unpack(num_faces_format, num_faces_data)[0]

                    faces_data = []
                    for face_index in range(num_faces):
                        # Read face index
                        face_index_format = '<I'
                        face_index_size = struct.calcsize(face_index_format)
                        face_index_data = binfile.read(face_index_size)
                        if len(face_index_data) < face_index_size:
                            print(f"❌ Binary file ended unexpectedly while reading face {face_index} index.")
                            return None
                        face_index = struct.unpack(face_index_format, face_index_data)[0]

                        # Read number of loops in this face
                        num_loops_format = '<I'
                        num_loops_size = struct.calcsize(num_loops_format)
                        num_loops_data = binfile.read(num_loops_size)
                        if len(num_loops_data) < num_loops_size:
                            print(f"❌ Binary file ended unexpectedly while reading face {face_index} number of loops.")
                            return None
                        num_loops = struct.unpack(num_loops_format, num_loops_data)[0]

                        # Read face center (3 floats)
                        face_center_format = '<3f'
                        face_center_size = struct.calcsize(face_center_format)
                        face_center_data = binfile.read(face_center_size)
                        if len(face_center_data) < face_center_size:
                            print(f"❌ Binary file ended unexpectedly while reading face {face_index} center.")
                            return None
                        face_center = struct.unpack(face_center_format, face_center_data)

                        # Read vertex indices
                        num_vertices_format = '<I'
                        num_vertices_size = struct.calcsize(num_vertices_format)
                        num_vertices_data = binfile.read(num_vertices_size)
                        if len(num_vertices_data) < num_vertices_size:
                            print(f"❌ Binary file ended unexpectedly while reading face {face_index} vertex count.")
                            return None
                        num_vertices = struct.unpack(num_vertices_format, num_vertices_data)[0]

                        vertex_indices_format = f'<{num_vertices}I'
                        vertex_indices_size = struct.calcsize(vertex_indices_format)
                        vertex_indices_data = binfile.read(vertex_indices_size)
                        if len(vertex_indices_data) < vertex_indices_size:
                            print(f"❌ Binary file ended unexpectedly while reading face {face_index} vertex indices.")
                            return None
                        vertex_indices = list(struct.unpack(vertex_indices_format, vertex_indices_data))

                        # Now read loops as expected
                        loops_data = []
                        loop_format = '<Iff'
                        loop_size = struct.calcsize(loop_format)
                        for loop_index in range(num_loops):
                            loop_data = binfile.read(loop_size)
                            if len(loop_data) < loop_size:
                                print(f"❌ Binary file ended unexpectedly while reading loop {loop_index} data.")
                                return None
                            loop_index, u, v = struct.unpack(loop_format, loop_data)
                            loops_data.append({"index": loop_index, "uv": [u, v]})

                        faces_data.append({
                            "index": face_index,
                            "center": face_center,
                            "vertex_indices": vertex_indices,
                            "loops": loops_data
                        })

                    uv_data["objects"].append({
                        "name": obj_name,
                        "collections": collections,
                        "faces": faces_data
                    })

        except Exception as e:
            print(f"❌ Error reading binary file: {e}")
            return None
    else:
        print(f"❌ Unsupported file extension: {ext}")
        return None

    return uv_data

# ------------------------
# Function to apply loaded UV and collection data to a mesh
# ------------------------

def apply_uv_data_to_mesh(obj, mesh_data):
    """
    Applies the loaded UV and collection data to a Blender mesh object.

    Args:
        obj (bpy.types.Object): The Blender mesh object.
        mesh_data (dict): The structured UV and collection data for this object.
    """
    print(f"Applying data to mesh: '{obj.name}'")

    # Ensure the object is active and in OBJECT mode
    if bpy.context.view_layer.objects.active != obj:
        bpy.context.view_layer.objects.active = obj
    if bpy.context.object and bpy.context.object.mode != 'OBJECT':
        try:
            bpy.ops.object.mode_set(mode='OBJECT')
        except RuntimeError as e:
            print(f"[WARN] Could not set object '{obj.name}' to OBJECT mode for UV application: {e}")
            return

    # Access UV layer
    uv_layer = obj.data.uv_layers.active
    if uv_layer is None:
        print(f"⚠️ Mesh '{obj.name}' has no active UV map. Creating one.")
        try:
            uv_layer = obj.data.uv_layers.new(name="Imported_UVMap")
            obj.data.uv_layers.active = uv_layer
        except Exception as e:
            print(f"❌ Error creating UV map for '{obj.name}': {e}")
            return

    # print numbers of faces, loops, vertices, and UVs
    print(f"Mesh '{obj.name}' has {len(obj.data.polygons)} faces, {len(obj.data.loops)} loops, {len(obj.data.vertices)} vertices, and {len(uv_layer.data)} UVs.")

    time.sleep(4)

    # Apply UV data
    applied_count = 0
    for face_data in mesh_data.get("faces", []):
        print(f"Processing face index: {face_data['index']}")
        loops_list = face_data.get("loops", [])
        face_center = face_data.get("center")
        vertex_indices = face_data.get("vertex_indices")

        # Match face by local center coordinates
        target_poly = None
        if face_center:
            print(f"Matching by face center: {face_center}")
            epsilon = 1e-5
            target_poly = next((poly for poly in obj.data.polygons if all(abs(poly.center[i] - face_center[i]) < epsilon for i in range(3))), None)

        # If no match, skip this face
        if not target_poly:
            print(f"[WARN] Couldn't match face with center {face_center} or vertices {vertex_indices} on '{obj.name}'. Skipping.")
            continue

        print(f"Matched face index target_poly: {target_poly.index}")

        # Map UVs per-vertex in the polygon
        for loop_idx_in_poly, loop_index in enumerate(target_poly.loop_indices):
            if loop_idx_in_poly < len(loops_list):
                uv = loops_list[loop_idx_in_poly]["uv"]
                uv_layer.data[loop_index].uv = uv
                applied_count += 1
                print(f"✅ Applied UV {uv} to loop index {loop_index} on '{obj.name}'.")
            else:
                print(f"[WARN] Mismatch in number of loops for face {target_poly.index} on '{obj.name}'.")

    print(f"✅ Applied UVs to {applied_count} loops for '{obj.name}'.")

    # Apply collections
    collections_to_add = mesh_data.get('collections', [])
    for collection_name in collections_to_add:
        # Check if the object is already in the collection
        if collection_name not in [col.name for col in obj.users_collection]:
            collection = bpy.data.collections.get(collection_name)
            if collection:
                try:
                    collection.objects.link(obj)
                    print(f"✅ Mesh '{obj.name}' added to collection '{collection_name}'.")
                except RuntimeError as e:
                    print(f"[WARN] Could not link object '{obj.name}' to collection '{collection_name}': {e}")
            else:
                print(f"⚠️ Collection '{collection_name}' not found. Skipping linking object '{obj.name}'.")


# ------------------------
# Operator to open file dialog and process import
# ------------------------

class ImportUVsOperator(Operator, ImportHelper):
    """Import UVs and Collections from CSV, JSON, or Binary (.buvd)"""
    bl_idname = "import_scene.uv_data"  # Unique ID for the operator
    bl_label = "Import UV Data"         # Display name

    # Allow selecting files with .csv, .json, or .buvd extensions
    filename_ext = "" # No default extension, rely on filter_glob
    filter_glob: bpy.props.StringProperty(
        default="*.csv;*.json;*.buvd",
        options={'HIDDEN'},
    )

    def execute(self, context):
        filepath = self.filepath
        print(f"\n--- Starting UV Data Import ---")
        print(f"✅ Selected file: {filepath}")

        # Load data from the selected file
        loaded_uv_data = load_uv_data_from_file(filepath)

        if loaded_uv_data is None:
            self.report({'ERROR'}, f"Failed to load data from {os.path.basename(filepath)}. Check console for details.")
            print("--- UV Data Import Failed ---")
            return {'CANCELLED'}

        if not loaded_uv_data.get("objects"):
            self.report({'INFO'}, f"No UV data found in {os.path.basename(filepath)} for import.")
            print("--- UV Data Import Finished (No Data) ---")
            return {'FINISHED'}

        print(f"✅ Loaded data for {len(loaded_uv_data['objects'])} objects.")

        # Apply UV and collection data to meshes
        for obj_data in loaded_uv_data["objects"]:
            mesh_name = obj_data.get("name")
            if not mesh_name:
                print("[WARN] Skipping object data with no name.")
                continue

            obj = bpy.context.scene.objects.get(mesh_name)
            if obj is None or obj.type != 'MESH':
                print(f"⚠️ Mesh object '{mesh_name}' not found in the scene or is not a mesh. Skipping.")
                continue

            apply_uv_data_to_mesh(obj, obj_data)

        print("--- UV Data Import Completed ---")

        return {'FINISHED'}

# ------------------------
# Registration
# ------------------------

def menu_func_import(self, context):
    self.layout.operator(ImportUVsOperator.bl_idname, text="UV Data (.csv, .json, .buvd)")

def register():
    bpy.utils.register_class(ImportUVsOperator)
    # Add the operator to the File > Import menu
    bpy.types.TOPBAR_MT_file_import.append(menu_func_import)

def unregister():
    # Remove the operator from the File > Import menu
    bpy.types.TOPBAR_MT_file_import.remove(menu_func_import)
    bpy.utils.unregister_class(ImportUVsOperator)

if __name__ == "__main__":
    register()
    # To run directly in Blender's text editor
    #bpy.ops.import_scene.uv_data('INVOKE_DEFAULT') # Launch file selector

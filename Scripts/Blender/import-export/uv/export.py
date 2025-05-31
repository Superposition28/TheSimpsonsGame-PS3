import json
import csv
import bpy
import os
import hashlib
import sys
import struct # Import the struct module for binary packing
from bpy.props import BoolProperty

# --- Addon Information ---
bl_info = {
    "name": "UV Exporter",
    "author": "Samarixum",
    "version": (1, 0, 0),
    "blender": (4, 0, 0),
    "location": "3D View > Tool Shelf > UV Exporter",
    "description": "Exports UV data in various formats",
    "category": "Import-Export",
}

# --- EXPORT TOGGLES ---
# Set these boolean variables to True or False to enable/disable exports

EXPORT_UV_BINARY = True  # Export UV data in custom binary (.buvd) format
EXPORT_UV_JSON = True   # Export UV data in structured JSON (.json) format
EXPORT_UV_CSV = True    # Export UV data in CSV (.csv) format
EXPORT_METADATA = True   # Export blend file metadata (.json)

# --- END EXPORT TOGGLES ---

def calculate_sha256_hash(filepath):
    """
    Calculates the SHA256 hash of the file.

    Args:
        filepath (str): The path to the file.

    Returns:
        str: The SHA256 hash of the file, or None if the file does not exist or an error occurs.
    """
    if not os.path.exists(filepath):
        # print(f"[WARN] File not found for hashing: {filepath}") # Commented out to reduce console noise
        return None

    hasher = hashlib.sha256()
    try:
        with open(filepath, 'rb') as file:
            while True:
                chunk = file.read(4096)  # Read in 4KB chunks
                if not chunk:
                    break
                hasher.update(chunk)
    except Exception as e:
        print(f"[ERROR] Error reading file for hashing: {filepath} - {e}")
        return None
    return hasher.hexdigest()

def export_uv_data():
    """
    Main function to handle UV data export.
    This function is called by the operator and should not run on script execution.
    """
    # Set the export directory
    # Create a folder named "uv_map_extract" in the blend file's directory
    export_dir = bpy.path.abspath("//uv_map_extract")

    # Check if the directory exists, create it if it doesn't
    if not os.path.exists(export_dir):
        try:
            os.makedirs(export_dir)
            print(f"📁 Created directory: {export_dir}")
        except OSError as e:
            print(f"❌ Error creating directory {export_dir}: {e}")
            # If directory creation fails, stop the script. Important.
            print("Script stopped: Unable to create export directory.")
            raise Exception(f"Failed to create directory: {export_dir}")

    # Set the export file paths
    csv_export_path = os.path.join(export_dir, "uv_export.csv")
    json_export_path = os.path.join(export_dir, "uv_export.json")
    binary_export_path = os.path.join(export_dir, "uv_export.buvd")
    metadata_export_path = os.path.join(export_dir, "blend_metadata.json")

    # Prepare data storage based on toggles
    csv_lines = []
    json_uv_data = {"objects": []}
    binary_uv_data = b''

    # Define binary format structures (only needed if EXPORT_UV_BINARY is True)
    if EXPORT_UV_BINARY:
        # Header: Magic (4s), Version (B), NumObjects (I)
        # Object: NameLen (I), Name (s), NumCollections (I), [Collection: NameLen (I), Name (s)], NumFaces (I), [Face: Index (I), NumLoops (I), [Loop: Index (I), U (f), V (f)]]
        # Using little-endian byte order (<) for consistency.
        magic_number = b'BUVD' # Blender UV Data
        version = 1
        # Count mesh objects only if binary export is enabled
        num_mesh_objects = len([obj for obj in bpy.context.scene.objects if obj.type == 'MESH'])
        binary_uv_data += struct.pack('<4sBI', magic_number, version, num_mesh_objects)
        print(f"📦 Preparing binary export to: {binary_export_path}")


    print("🔍 Processing objects...")

    # Choose objects
    objects = bpy.context.scene.objects

    for obj in objects:
        if obj.type != 'MESH':
            print(f"[INFO] Object '{obj.name}' is not a MESH. Skipping.") # Commented out to reduce console noise
            continue

        mesh = obj.data

        # Make sure we are in object mode to avoid stale data
        if bpy.context.object != obj or bpy.context.object.mode != 'OBJECT':
             try:
                 bpy.context.view_layer.objects.active = obj
                 bpy.ops.object.mode_set(mode='OBJECT')
             except RuntimeError as e:
                 print(f"[WARN] Could not set object '{obj.name}' to OBJECT mode: {e}")
                 continue # Skip this object if we can't get into object mode

        uv_layer = mesh.uv_layers.active

        if uv_layer is None:
            print(f"[WARN] Object '{obj.name}' has NO UV map. Skipping UV export for this object.")
            continue

        if len(mesh.loops) == 0:
            print(f"[WARN] Object '{obj.name}' has NO faces (no loops). Skipping UV export for this object.")
            continue

        if len(uv_layer.data) == 0:
            print(f"[WARN] Object '{obj.name}' has UV map but NO UV data. Skipping UV export for this object.")
            continue

        # Collect collection groupings
        collections = [col.name for col in obj.users_collection]

        # Prepare data for this object for JSON (if enabled)
        obj_json_data = {
            "name": obj.name,
            "collections": collections,
            "faces": []
        } if EXPORT_UV_JSON else None

        # Prepare data for this object for Binary (if enabled)
        if EXPORT_UV_BINARY:
            # Pack Object data for binary
            obj_name_bytes = obj.name.encode('utf-8')
            binary_uv_data += struct.pack('<I', len(obj_name_bytes)) # Pack name length
            binary_uv_data += obj_name_bytes # Pack name bytes

            binary_uv_data += struct.pack('<I', len(collections)) # Pack number of collections
            for col_name in collections:
                col_name_bytes = col_name.encode('utf-8')
                binary_uv_data += struct.pack('<I', len(col_name_bytes)) # Pack collection name length
                binary_uv_data += col_name_bytes # Pack collection name bytes

            # Count faces with UV data for this object for binary header
            faces_with_uv_count = 0
            for poly in mesh.polygons:
                if any(uv_layer.data[loop_index].uv for loop_index in poly.loop_indices):
                    faces_with_uv_count += 1
            binary_uv_data += struct.pack('<I', faces_with_uv_count) # Pack number of faces with UV data


        # Collect UV data for each loop, with face and loop context
        for poly_index, poly in enumerate(mesh.polygons):
            face_loops_data = [] # Temporary storage for loops in this face

            # Check if this face has any UV data before processing loops
            has_uv_data_in_face = any(uv_layer.data[loop_index].uv for loop_index in poly.loop_indices)

            if not has_uv_data_in_face:
                continue # Skip faces without UV data for all export formats

            # capture local-space face center and vertex indices
            face_center = poly.center.copy()  # (Vector) Local-space center
            vertex_indices = list(poly.vertices)  # (list of vertex indices)

            # Prepare JSON face data including center and vertex indices
            if EXPORT_UV_JSON:
                face_json_data = {
                    "index": poly_index,
                    "center": [round(face_center.x,6), round(face_center.y,6), round(face_center.z,6)],
                    "vertex_indices": vertex_indices,
                    "loops": []
                }

            for loop_index in poly.loop_indices:
                uv = uv_layer.data[loop_index].uv  # Get the UV for this loop

                # For CSV (if enabled): Add mesh name, face index, loop index, UV coordinates, and collection groupings
                if EXPORT_UV_CSV is not None:
                    csv_lines.append([
                        obj.name,
                        f"Face_{poly_index}",
                        f"Loop_{loop_index}",
                        f"{uv[0]:.6f}",
                        f"{uv[1]:.6f}",
                        f"{face_center.x:.6f}",
                        f"{face_center.y:.6f}",
                        f"{face_center.z:.6f}",
                        ','.join(map(str, vertex_indices)),
                        ', '.join(collections)
                    ])

                # For JSON (if enabled): Add loop index and UV coordinates
                if EXPORT_UV_JSON is not None:
                    face_json_data["loops"].append({
                        "index": loop_index,
                        "uv": [round(uv[0], 6), round(uv[1], 6)] # Round for cleaner JSON output
                    })

                # For Binary (if enabled): Store loop data temporarily
                if EXPORT_UV_BINARY is not None:
                    face_loops_data.append((loop_index, uv[0], uv[1]))


                print(f"[INFO] Processed UV for '{obj.name}', Face {poly_index}, Loop {loop_index}") # Commented out verbose printing

            # Add face data to JSON object data (if enabled)
            if EXPORT_UV_JSON is not None and face_json_data["loops"]: # Only add face if it has loops with UVs
                obj_json_data["faces"].append(face_json_data)

            # Pack Face and Loop data for Binary (if enabled)
            if EXPORT_UV_BINARY and face_loops_data: # Only pack face if it has loops with UVs
                binary_uv_data += struct.pack('<I', poly_index) # Pack face index
                binary_uv_data += struct.pack('<I', len(face_loops_data)) # Pack number of loops in this face
                # pack face center
                binary_uv_data += struct.pack('<3f', face_center.x, face_center.y, face_center.z)
                # pack vertex indices list
                binary_uv_data += struct.pack('<I', len(vertex_indices))
                for vi in vertex_indices:
                    binary_uv_data += struct.pack('<I', vi)
                # pack loops
                for loop_index, u, v in face_loops_data:
                    binary_uv_data += struct.pack('<Iff', loop_index, u, v)

                print(f"[INFO] Packed UVs for '{obj.name}', Face {poly_index} into binary")


        # Add object data to JSON root data (if enabled)
        if EXPORT_UV_JSON is not None and obj_json_data["faces"]: # Only add object if it has faces with UVs
            json_uv_data["objects"].append(obj_json_data)


    # --- Save Exported Data ---

    # Save to CSV
    if EXPORT_UV_CSV and csv_lines:
        try:
            with open(csv_export_path, 'w', newline='') as csvfile:
                writer = csv.writer(csvfile)
                writer.writerow([
                    'MeshName','Face','Loop','U','V',
                    'CenterX','CenterY','CenterZ','VertexIndices','Collections'
                ])  # Write header
                writer.writerows(csv_lines)
            print(f"\n✅ UV data exported to CSV: {csv_export_path}")
        except Exception as e:
            print(f"❌ Error writing CSV file {csv_export_path}: {e}")
    elif EXPORT_UV_CSV:
        print("\n⚠️ No UV data found to export to CSV.")

    # Save to JSON
    if EXPORT_UV_JSON and json_uv_data and json_uv_data["objects"]:
        try:
            with open(json_export_path, 'w') as jsonfile:
                json.dump(json_uv_data, jsonfile, indent=2) # Use indent for readability
            print(f"\n✅ UV data exported to JSON: {json_export_path}")
        except Exception as e:
            print(f"❌ Error writing JSON file {json_export_path}: {e}")
    elif EXPORT_UV_JSON:
        print("\n⚠️ No UV data found to export to JSON.")

    # Save to Binary File
    if EXPORT_UV_BINARY and binary_uv_data and len(binary_uv_data) > struct.calcsize('<4sBI'): # Check if more than just the header was written
        try:
            with open(binary_export_path, 'wb') as binfile:
                binfile.write(binary_uv_data)
            print(f"\n✅ UV data exported to binary file: {binary_export_path}")
        except Exception as e:
            print(f"❌ Error writing binary file {binary_export_path}: {e}")
    elif EXPORT_UV_BINARY:
        print("\n⚠️ No UV data found to export to binary.")


    # Gather and save metadata
    if EXPORT_METADATA:
        blend_filepath = bpy.data.filepath
        blend_filename = os.path.basename(blend_filepath)
        blend_file_hash = calculate_sha256_hash(blend_filepath)

        metadata = {
            "blend_filepath": blend_filepath,
            "blend_filename": blend_filename,
            "blend_file_hash": blend_file_hash,
            "blender_version": bpy.app.version_string,
            "python_version": sys.version,
            "scene_name": bpy.context.scene.name,
            "object_count": len(bpy.context.scene.objects),
            "uv_data_exported_binary": EXPORT_UV_BINARY and bool(binary_uv_data) and len(binary_uv_data) > struct.calcsize('<4sBI'), # Indicate if binary UV data was exported
            "uv_data_exported_json": EXPORT_UV_JSON and bool(json_uv_data) and bool(json_uv_data.get("objects")), # Indicate if JSON UV data was exported
            "uv_data_exported_csv": EXPORT_UV_CSV and bool(csv_lines), # Indicate if CSV was exported
            "binary_format_version": version if EXPORT_UV_BINARY else None # Include the binary format version if binary export is enabled
        }

        try:
            with open(metadata_export_path, 'w') as metadata_file:
                json.dump(metadata, metadata_file, indent=2)
            print(f"\n✅ Metadata exported to JSON: {metadata_export_path}")
        except Exception as e:
            print(f"❌ Error writing metadata file {metadata_export_path}: {e}")
    else:
        print("\nSkipping metadata export as per toggle.")


    # Export Text Data (optional, keeping for completeness)
    print("\nExporting text blocks...")
    exported_text_blocks = 0
    for text_block in bpy.data.texts:
        text_filename = os.path.join(export_dir, f"{text_block.name}.txt")
        try:
            with open(text_filename, 'w', encoding='utf-8') as text_file:
                text_file.write(text_block.as_string())
            print(f"✅ Text block '{text_block.name}' exported to: {text_filename}")
            exported_text_blocks += 1
        except Exception as e:
            print(f"❌ Error exporting text block '{text_block.name}': {e}")
    if exported_text_blocks == 0:
        print("⚠️ No text blocks found to export.")


# --- Operator for Export ---
class UVExporterOperator(bpy.types.Operator):
    bl_idname = "uv.exporter_operator"
    bl_label = "Export UV Data"
    bl_description = "Export UV data in selected formats"
    bl_options = {'REGISTER', 'UNDO'}

    export_binary: BoolProperty(name="Export Binary", default=True)
    export_json: BoolProperty(name="Export JSON", default=True)
    export_csv: BoolProperty(name="Export CSV", default=True)
    export_metadata: BoolProperty(name="Export Metadata", default=True)

    def execute(self, context):
        global EXPORT_UV_BINARY, EXPORT_UV_JSON, EXPORT_UV_CSV, EXPORT_METADATA
        EXPORT_UV_BINARY = self.export_binary
        EXPORT_UV_JSON = self.export_json
        EXPORT_UV_CSV = self.export_csv
        EXPORT_METADATA = self.export_metadata

        try:
            # Call the main export logic
            export_uv_data()  # Call the encapsulated function
            self.report({'INFO'}, "UV data exported successfully!")
        except Exception as e:
            self.report({'ERROR'}, f"Export failed: {e}")
        return {'FINISHED'}

# --- Add to Export Menu ---
def menu_func_export(self, context):
    self.layout.operator(UVExporterOperator.bl_idname, text="UV Exporter (.buvd/.json/.csv)")

# --- Registration ---
classes = [UVExporterOperator]

def register():
    for cls in classes:
        bpy.utils.register_class(cls)
    bpy.types.TOPBAR_MT_file_export.append(menu_func_export)  # Add to export menu

def unregister():
    for cls in classes:
        bpy.utils.unregister_class(cls)
    bpy.types.TOPBAR_MT_file_export.remove(menu_func_export)  # Remove from export menu

if __name__ == "__main__":
    register()

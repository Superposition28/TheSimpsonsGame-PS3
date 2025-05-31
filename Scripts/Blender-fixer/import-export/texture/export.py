import json
import os
import hashlib
import bpy
import sys
import io
import csv

def calculate_sha256_hash_from_image(image):
    """
    Calculates the SHA256 hash of an image stored inside the Blender file.
    """
    if image is None:
        return "no image"

    if image.packed_file:  # Correct check for packed image
        try:
            file_format = image.file_format if image.file_format != 'NONE' else 'PNG'
            if not image.has_data:
                image.pixels

            with io.BytesIO() as buffer:
                bpy.context.scene.render.image_settings.file_format = file_format
                image.save_render(buffer, scene=bpy.context.scene)
                buffer.seek(0)
                image_data = buffer.read()
                return hashlib.sha256(image_data).hexdigest()
        except Exception as e:
            print(f"[ERROR] Failed to calculate hash for packed image '{image.name}': {e}")
            return "error"
    else:
        print(f"[WARN] Image '{image.name}' is not packed and has no external filepath, skipping hash calculation.")
        return "unpacked"

def calculate_sha256_hash(filepath):
    """
    Calculates the SHA256 hash of a file on disk.
    """
    if not os.path.exists(filepath):
        return None

    hasher = hashlib.sha256()
    try:
        with open(filepath, 'rb') as file:
            while True:
                chunk = file.read(4096)
                if not chunk:
                    break
                hasher.update(chunk)
    except Exception as e:
        print(f"[ERROR] Error reading file for hashing: {filepath} - {e}")
        return None
    return hasher.hexdigest()

# Set export directory
export_dir = bpy.path.abspath("//texture_map_extract")
if not os.path.exists(export_dir):
    try:
        os.makedirs(export_dir)
        print(f"📁 Created directory: {export_dir}")
    except OSError as e:
        print(f"❌ Error creating directory {export_dir}: {e}")
        raise Exception(f"Failed to create directory: {export_dir}")

# Paths
csv_export_path = os.path.join(export_dir, "texture_export.csv")
json_export_path = os.path.join(export_dir, "texture_export.json")
metadata_export_path = os.path.join(export_dir, "blend_metadata.json")

# Storage
csv_lines = []
json_data = {}
unused_materials = []
unused_texture_details = []

# Select objects
objects = [obj for obj in bpy.context.scene.objects if obj.type == 'MESH']

# Track used materials and textures
used_materials = set()
used_textures = set()

print("--- Starting Texture Export Process ---")

for obj in objects:
    print(f"\nProcessing Object: {obj.name}")
    collections = [col.name for col in obj.users_collection]

    if obj.data.materials:
        for mat in obj.data.materials:
            if mat is None:
                print(f"  [WARN] Object '{obj.name}' has a None material slot.")
                continue

            print(f" Processing Material: {mat.name}")

            if not mat.use_nodes:
                print(f"  [INFO] Material '{mat.name}' does not use nodes. Skipping texture export for this material.")
                continue

            used_materials.add(mat.name)

            if obj.name not in json_data:
                json_data[obj.name] = {}
            if mat.name not in json_data[obj.name]:
                json_data[obj.name][mat.name] = []

            for node in mat.node_tree.nodes:
                if node.type == 'TEX_IMAGE':
                    texture_image = node.image
                    if texture_image:
                        texture_filename = texture_image.name
                        texture_file_relative_path = texture_image.filepath
                        texture_file_absolute_path = bpy.path.abspath(texture_file_relative_path)

                        print(f"  Found Image Texture Node: '{texture_image.name}'")
                        print(f"    Blender Filepath: {texture_file_relative_path}")
                        print(f"    Resolved Absolute Path: {texture_file_absolute_path}")

                        texture_file_hash_disk = calculate_sha256_hash(texture_file_absolute_path)
                        texture_file_hash_packed = calculate_sha256_hash_from_image(texture_image)

                        print(f"    Disk Hash: {texture_file_hash_disk}")
                        print(f"    Packed Hash: {texture_file_hash_packed}")

                        csv_lines.append([
                            obj.name,
                            mat.name,
                            texture_filename,
                            texture_file_absolute_path,
                            texture_file_hash_disk,
                            texture_file_hash_packed,
                            ', '.join(collections)
                        ])

                        json_data[obj.name][mat.name].append({
                            "texture_filename": texture_filename,
                            "texture_filepath_relative": texture_file_relative_path,
                            "texture_filepath_absolute": texture_file_absolute_path,
                            "texture_file_hash_disk": texture_file_hash_disk,
                            "texture_file_hash_packed": texture_file_hash_packed,
                            "collections": collections
                        })

                        used_textures.add(texture_image.name)
                        print(f"    [INFO] Texture '{texture_filename}' data collected.")
                    else:
                        print(f"  [WARN] Image Texture Node in material '{mat.name}' has no image assigned.")
    else:
        print(f"  [INFO] Object '{obj.name}' has no materials assigned.")

# Find unused materials
for mat in bpy.data.materials:
    if mat.name not in used_materials:
        unused_materials.append(mat.name)
        print(f"[INFO] Material '{mat.name}' is unused.")

# Find unused textures
for image in bpy.data.images:
    if image.name not in used_textures:
        print(f"[INFO] Image '{image.name}' is unused.")

        texture_file_relative_path = image.filepath
        texture_file_absolute_path = bpy.path.abspath(texture_file_relative_path)

        texture_file_hash_disk = calculate_sha256_hash(texture_file_absolute_path)
        texture_file_hash_packed = calculate_sha256_hash_from_image(image)

        unused_texture_details.append({
            "texture_filename": image.name,
            "texture_filepath_relative": texture_file_relative_path,
            "texture_filepath_absolute": texture_file_absolute_path,
            "texture_file_hash_disk": texture_file_hash_disk,
            "texture_file_hash_packed": texture_file_hash_packed,
        })

# --- NEW: Collect all materials and images ---

all_materials = []
for mat in bpy.data.materials:
    all_materials.append({
        "material_name": mat.name,
        "use_nodes": mat.use_nodes,
        "users": mat.users
    })

all_images = []
for image in bpy.data.images:
    texture_file_relative_path = image.filepath
    texture_file_absolute_path = bpy.path.abspath(texture_file_relative_path)
    texture_file_hash_disk = calculate_sha256_hash(texture_file_absolute_path)
    texture_file_hash_packed = calculate_sha256_hash_from_image(image)

    all_images.append({
        "image_name": image.name,
        "is_packed": bool(image.packed_file),
        "filepath_relative": texture_file_relative_path,
        "filepath_absolute": texture_file_absolute_path,
        "file_hash_disk": texture_file_hash_disk,
        "file_hash_packed": texture_file_hash_packed,
        "users": image.users
    })

# --- EXPORTS ---

# Save CSV
try:
    with open(csv_export_path, 'w', newline='', encoding='utf-8') as csvfile:
        writer = csv.writer(csvfile)
        writer.writerow(['Mesh Name', 'Material Name', 'Texture Filename', 'Texture Filepath (Absolute)', 'Texture File Hash (Disk)', 'Texture File Hash (Packed)', 'Collections'])
        writer.writerows(csv_lines)
    print(f"\n✅ Texture export data exported to CSV: {csv_export_path}")
except Exception as e:
    print(f"\n❌ Error exporting CSV data to {csv_export_path}: {e}")

# Save JSON
final_json_output = {
    "mesh_material_texture_map": json_data,
    "unused_materials": unused_materials,
    "unused_textures": unused_texture_details,
    "all_materials": all_materials,
    "all_images": all_images
}

try:
    with open(json_export_path, 'w', encoding='utf-8') as jsonfile:
        json.dump(final_json_output, jsonfile, indent=2)
    print(f"✅ Texture data exported to JSON: {json_export_path}")
except Exception as e:
    print(f"\n❌ Error exporting JSON data to {json_export_path}: {e}")

# Save metadata
collections_data = {}
for collection in bpy.data.collections:
    collection_meshes = [obj.name for obj in collection.objects if obj.type == 'MESH']
    if collection_meshes:
        collections_data[collection.name] = collection_meshes

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
    "mesh_object_count": len(objects),
    "collections": collections_data
}

try:
    with open(metadata_export_path, 'w', encoding='utf-8') as metadata_file:
        json.dump(metadata, metadata_file, indent=2)
    print(f"✅ Metadata exported to JSON: {metadata_export_path}")
except Exception as e:
    print(f"\n❌ Error exporting metadata to {metadata_export_path}: {e}")

print("\n--- Texture Export Process Finished ---")
print("Check the System Console for details.")

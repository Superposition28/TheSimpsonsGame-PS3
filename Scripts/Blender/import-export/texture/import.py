import bpy
import json
import os
from bpy.props import StringProperty
from bpy_extras.io_utils import ImportHelper
import time

# --- Configuration ---
CREATE_MATERIALS_IF_NEEDED = True

# --- Helper Functions ---


def find_texture_in_inventory(texture_hash, inventory_data):
    """Finds the texture file path in the inventory data using its hash."""
    print(f"Searching for texture hash: {texture_hash}")
    for entry in inventory_data.get("textures", []):
        if entry.get("hash") == texture_hash:
            return entry.get("filepath")
    return None

    dummy_path = inventory_data.get(texture_hash)
    if dummy_path:
        print(f"Found path: {dummy_path}")
        return dummy_path
    else:
        print("Texture hash not found in inventory.")
        return None


def setup_image_texture_node(material, texture_path):
    """Sets up or updates the image texture node for a given material."""
    print(f"Setting up texture '{texture_path}' for material '{material.name}'")
    if not material.use_nodes:
        material.use_nodes = True

    nodes = material.node_tree.nodes
    principled_bsdf = nodes.get("Principled BSDF")
    if not principled_bsdf:
        print(f"Warning: Material '{material.name}' has no Principled BSDF node.")
        return

    # Find or create an Image Texture node
    image_node = None
    for node in nodes:
        if node.type == 'TEX_IMAGE':
            image_node = node
            break

    if not image_node:
        image_node = nodes.new(type='ShaderNodeTexImage')
        image_node.location = principled_bsdf.location[0] - 400, principled_bsdf.location[1]
        # Link Image Texture to Principled BSDF Base Color
        links = material.node_tree.links
        links.new(image_node.outputs['Color'], principled_bsdf.inputs['Base Color'])

    # Load the image
    if os.path.exists(texture_path):
        try:
            img = bpy.data.images.load(texture_path, check_existing=True)
            image_node.image = img
            print(f"Successfully loaded image: {texture_path}")
        except Exception as e:
            print(f"Error loading image '{texture_path}': {e}")
    else:
        print(f"Error: Texture file not found at '{texture_path}'")


# --- Core Relinking Logic ---
def perform_relinking(context, export_json_path, inventory_json_path):
    """Loads JSON data and relinks textures based on material names and texture hashes."""
    try:
        with open(export_json_path, 'r') as f:
            export_data = json.load(f)
        with open(inventory_json_path, 'r') as f:
            inventory_data = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError) as e:
        print(f"Error loading JSON files: {e}")
        return

    print("Starting texture relinking process...")
    texture_base_path = context.scene.texture_base_path
    if not texture_base_path:
        print("Warning: Texture Base Path is not set. Relative paths might not resolve correctly.")
    print(f"Using base path: {texture_base_path}")

    # Build a lookup dictionary for inventory hashes -> relative sourcePath
    texture_reg = {}
    for texture_entry in inventory_data.get("textures", []):
        print(f"Processing texture entry: {texture_entry}")
        file_hash = texture_entry.get("fileHash")
        print(f"File hash: {file_hash}")
        relative_source_path = os.path.join(texture_entry.get("path", ""), texture_entry.get("filename", ""))
        print(f"Relative source path: {relative_source_path}")
        if file_hash and relative_source_path:
            texture_reg[file_hash] = relative_source_path
            print(f"Added to hash map: {file_hash} -> {relative_source_path}")
        else:
            print(f"Warning: Missing file hash or source path in inventory entry: {texture_entry}")

    # Loop through export_data to drive the process
    mesh_material_map = export_data.get("mesh_material_texture_map", {})

    for mesh_name, materials in mesh_material_map.items():
        # Get the mesh object
        mesh_obj = bpy.data.objects.get(mesh_name)
        if not mesh_obj:
            print(f"Warning: Mesh '{mesh_name}' not found in the scene. Skipping.")
            continue

        for material_name, texture_info_list in materials.items():
            print(f"Processing material: {material_name}")

            # Check if the material already exists
            material = bpy.data.materials.get(material_name)
            if not material and CREATE_MATERIALS_IF_NEEDED:
                material = bpy.data.materials.new(name=material_name)
                material.use_nodes = True
                print(f"Created new material: {material_name}")

            if material is None:
                print(f"Skipping missing material: {material_name}")
                continue

            # Check if texture_info_list is empty before accessing
            if not texture_info_list:
                print(f"Warning: No texture info found for material '{material_name}'. Skipping.")
                continue

            # Assume first texture in the list
            texture_info = texture_info_list[0]
            texture_hash = texture_info.get("texture_file_hash_disk")
            if not texture_hash:
                print(f"No texture hash for material {material_name}")
                continue

            print(f"Material '{material_name}' uses texture hash: {texture_hash}")

            # Find matching texture in inventory
            relative_texture_path = texture_reg.get(texture_hash)
            if relative_texture_path:
                print(f"Found relative texture path: {relative_texture_path} for hash: {texture_hash}")
                # Construct absolute path using the user-provided base path
                abs_texture_path = os.path.normpath(os.path.join(texture_base_path, relative_texture_path))
                print(f"Constructed absolute texture path: {abs_texture_path}")
                setup_image_texture_node(material, abs_texture_path)
            else:
                print(f"Texture hash {texture_hash} not found in inventory!")

            # Assign the material to the mesh
            if material.name not in mesh_obj.data.materials:
                mesh_obj.data.materials.append(material)
                print(f"Assigned material '{material_name}' to mesh '{mesh_name}'.")

    print("Texture relinking process finished.")

# --- New Operators for clean 2-step selection ---

class SelectExportJsonOperator(bpy.types.Operator, ImportHelper):
    """Select the Texture Export JSON File"""
    bl_idname = "texture.select_export_json"
    bl_label = "Select Export JSON"

    filename_ext = ".json"
    filter_glob: StringProperty(default="*.json", options={'HIDDEN'})

    def execute(self, context):
        context.scene.texture_export_json_path = self.filepath
        self.report({'INFO'}, f"Selected Export JSON: {self.filepath}")
        return {'FINISHED'}

class SelectInventoryJsonOperator(bpy.types.Operator, ImportHelper):
    """Select the Texture Inventory JSON File"""
    bl_idname = "texture.select_inventory_json"
    bl_label = "Select Inventory JSON"

    filename_ext = ".json"
    filter_glob: StringProperty(default="*.json", options={'HIDDEN'})

    def execute(self, context):
        context.scene.texture_inventory_json_path = self.filepath
        self.report({'INFO'}, f"Selected Inventory JSON: {self.filepath}")
        return {'FINISHED'}

class SelectBasePathOperator(bpy.types.Operator, ImportHelper):
    """Select the Texture Base Path"""
    bl_idname = "texture.select_base_path"
    bl_label = "Select Base Path"

    filter_glob: StringProperty(default="*", options={'HIDDEN'})

    def execute(self, context):
        # Extract only the directory path
        context.scene.texture_base_path = os.path.dirname(self.filepath)
        self.report({'INFO'}, f"Selected Base Path: {context.scene.texture_base_path}")
        return {'FINISHED'}

class PerformRelinkingOperator(bpy.types.Operator):
    """Perform Texture Relinking"""
    bl_idname = "texture.perform_relinking"
    bl_label = "Relink Textures"

    def execute(self, context):
        export_path = context.scene.texture_export_json_path
        inventory_path = context.scene.texture_inventory_json_path
        base_path = context.scene.texture_base_path

        if not export_path or not inventory_path:
            self.report({'ERROR'}, "Both Export and Inventory JSON files must be selected.")
            return {'CANCELLED'}
        if not base_path:
            self.report({'WARNING'}, "Texture Base Path is not set. Proceeding with potentially relative paths.")

        perform_relinking(context, export_path, inventory_path)
        self.report({'INFO'}, "Texture Relinking Complete.")
        return {'FINISHED'}

# --- UI Panel ---

class TEXTURE_PT_relinker_panel(bpy.types.Panel):
    """Texture Relinker UI"""
    bl_label = "Texture Relinker"
    bl_idname = "TEXTURE_PT_relinker_panel"
    bl_space_type = 'TEXT_EDITOR'
    bl_region_type = 'UI'
    bl_category = 'Texture Tools'

    def draw(self, context):
        layout = self.layout
        scene = context.scene

        layout.label(text="Select JSON Files:")
        layout.prop(scene, "texture_export_json_path")
        layout.operator("texture.select_export_json", text="Select Export JSON")

        layout.prop(scene, "texture_inventory_json_path")
        layout.operator("texture.select_inventory_json", text="Select Inventory JSON")

        layout.separator()
        layout.label(text="Set Texture Base Path:")
        layout.prop(scene, "texture_base_path", text="Base Path")
        layout.operator("texture.select_base_path", text="Select Base Path")

        layout.separator()
        layout.operator("texture.perform_relinking", text="Relink Textures")

# --- Registration ---

def register():
    bpy.utils.register_class(SelectExportJsonOperator)
    bpy.utils.register_class(SelectInventoryJsonOperator)
    bpy.utils.register_class(SelectBasePathOperator)
    bpy.utils.register_class(PerformRelinkingOperator)
    bpy.utils.register_class(TEXTURE_PT_relinker_panel)

    bpy.types.Scene.texture_export_json_path = StringProperty(
        name="Export JSON Path",
        description="Path to the exported texture JSON file",
        subtype='FILE_PATH'
    )
    bpy.types.Scene.texture_inventory_json_path = StringProperty(
        name="Inventory JSON Path",
        description="Path to the texture inventory JSON file",
        subtype='FILE_PATH'
    )
    bpy.types.Scene.texture_base_path = StringProperty(
        name="Texture Base Path",
        description="Base directory containing the texture files referenced in the inventory",
        subtype='DIR_PATH'
    )

def unregister():
    bpy.utils.unregister_class(SelectExportJsonOperator)
    bpy.utils.unregister_class(SelectInventoryJsonOperator)
    bpy.utils.unregister_class(PerformRelinkingOperator)
    bpy.utils.unregister_class(TEXTURE_PT_relinker_panel)

    del bpy.types.Scene.texture_export_json_path
    del bpy.types.Scene.texture_inventory_json_path
    del bpy.types.Scene.texture_base_path

if __name__ == "__main__":
    register()

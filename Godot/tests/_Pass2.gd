@tool
extends SceneTree

# ---- NEW HELPER FUNCTION START ----
# This function applies configuration data from the JSON to a node.
# Currently, it only handles setting the transform for Node3D types.
func _apply_node_config(node: Node, config_data: Dictionary):
    # Check if a transform configuration exists
    if not config_data.has("transform"):
        return

    # Ensure the node is a 3D node that has a transform
    var node_3d = node as Node3D
    if not node_3d:
        printerr("  Warning: 'transform' config found for non-Node3D child '", node.name, "'.")
        return

    var transform_data = config_data["transform"]
    if typeof(transform_data) != TYPE_DICTIONARY:
        printerr("  Warning: 'transform' data for '", node.name, "' must be a Dictionary.")
        return

    # Apply position, using defaults if a value is not provided
    if transform_data.has("position"):
        var pos_data = transform_data["position"]
        if typeof(pos_data) == TYPE_DICTIONARY:
            node_3d.position = Vector3(
                pos_data.get("x", 0.0),
                pos_data.get("y", 0.0),
                pos_data.get("z", 0.0)
            )

    # Apply rotation (in degrees)
    if transform_data.has("rotation_degrees"):
        var rot_data = transform_data["rotation_degrees"]
        if typeof(rot_data) == TYPE_DICTIONARY:
            node_3d.rotation_degrees = Vector3(
                rot_data.get("x", 0.0),
                rot_data.get("y", 0.0),
                rot_data.get("z", 0.0)
            )

    # Apply scale
    if transform_data.has("scale"):
        var scale_data = transform_data["scale"]
        if typeof(scale_data) == TYPE_DICTIONARY:
            node_3d.scale = Vector3(
                scale_data.get("x", 1.0),
                scale_data.get("y", 1.0),
                scale_data.get("z", 1.0)
            )
# ---- NEW HELPER FUNCTION END ----


# ---- UPDATED RECURSIVE FUNCTION START ----
# This function processes a list of children and adds them to a parent node.
func _add_children_recursive(parent_node: Node, children_data: Array, scene_root: Node) -> bool:
    var children_were_added = false
    
    for child_info in children_data:
        if typeof(child_info) != TYPE_DICTIONARY or not child_info.has("name"):
            printerr("  Skipping invalid child entry (must be a Dictionary with a 'name'): ", child_info)
            continue

        var instance: Node = null

        # Step 1: Create the node instance.
        if child_info.has("path"):
            var child_scene_path = "res://" + child_info["path"]
            var resource = load(child_scene_path)
            if resource:
                instance = resource.instantiate()
            if not instance:
                printerr("  Failed to load or instantiate child resource: ", child_scene_path)
                continue
        elif child_info.has("class"):
            var node_class = child_info["class"]
            instance = ClassDB.instantiate(node_class)
            if not instance:
                printerr("  Failed to instantiate class: '", node_class, "'")
                continue
        else:
            printerr("  Skipping child '", child_info["name"], "' because it has no 'path' or 'class'.")
            continue

        # Step 2: Configure and add the node to the scene.
        instance.name = child_info["name"]
        
        # --- MODIFICATION START ---
        # Apply configuration from JSON, such as setting the transform.
        if child_info.has("config"):
            _apply_node_config(instance, child_info["config"])
        # --- MODIFICATION END ---
        
        parent_node.add_child(instance)
        instance.owner = scene_root
        
        print("  Added child '", instance.name, "' to '", parent_node.name, "'")
        children_were_added = true
        
        # Step 3: Recursively add any nested children.
        if child_info.has("children"):
            _add_children_recursive(instance, child_info["children"], scene_root)
            
    return children_were_added
# ---- UPDATED RECURSIVE FUNCTION END ----

func _init():
    print("Pass 2: Adding children...")

    var file = FileAccess.open("res://scene_config.json", FileAccess.READ)
    if not file:
        printerr("Failed to open scene_config.json")
        return
    var text = file.get_as_text()
    file.close()
    var data = JSON.parse_string(text)
    if typeof(data) != TYPE_ARRAY:
        printerr("Invalid JSON data in scene_config.json")
        return
        
    # --- Second Pass: Add children ---
    for scene_info in data:
        if typeof(scene_info) != TYPE_DICTIONARY or not scene_info.has("path"):
            continue

        var scene_path = "res://" + scene_info["path"]
        var children_to_add = scene_info.get("children", [])

        if children_to_add.is_empty():
            continue

        var existing_packed_scene = load(scene_path) as PackedScene
        if not existing_packed_scene:
            printerr("Failed to load base scene for adding children: ", scene_path)
            continue

        var root_node = existing_packed_scene.instantiate()
        if not root_node:
            printerr("Failed to instantiate base scene: ", scene_path)
            continue

        var children_added = _add_children_recursive(root_node, children_to_add, root_node)

        if children_added:
            var updated_packed_scene = PackedScene.new()
            var pack_err = updated_packed_scene.pack(root_node)
            if pack_err != OK:
                printerr("Failed to pack updated scene: ", scene_path, " Error code: ", pack_err)
            else:
                var save_err = ResourceSaver.save(updated_packed_scene, scene_path)
                if save_err != OK:
                    printerr("Failed to save updated scene: ", scene_path, " Error code: ", save_err)
                else:
                    print("  Successfully updated scene with children: ", scene_path)

        root_node.free()

    print("Second pass: Adding children complete.")
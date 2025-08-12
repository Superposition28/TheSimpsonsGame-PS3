# RemakeRegistry\Games\TheSimpsonsGame PS3\Godot\Scripts\_Ready.gd
@tool
extends SceneTree

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
            # Simplified check as invalid entries are already handled/skipped in pass 1
            # Only need to check if it *should* have children
            if scene_info.has("children") and not scene_info["children"].is_empty():
                printerr("Skipping potentially invalid scene entry for adding children: ", scene_info)
            continue # Skip if no path or no children defined

        var scene_path = "res://" + scene_info["path"]
        var children_to_add = scene_info.get("children", [])

        if children_to_add.is_empty():
            continue

        # Load the base scene created in the first pass
        var existing_packed_scene = load(scene_path) as PackedScene
        if not existing_packed_scene:
            printerr("Failed to load base scene for adding children: ", scene_path)
            continue

        var root_node = existing_packed_scene.instantiate()
        if not root_node:
            printerr("Failed to instantiate base scene: ", scene_path)
            continue

        var children_added = false # Flag to track if any *new* children were added in this pass
        # Add children
        for child_info in children_to_add:
            if typeof(child_info) != TYPE_DICTIONARY or not child_info.has("path") or not child_info.has("name"):
                printerr("Skipping invalid child entry for scene ", scene_path, ": ", child_info)
                continue

            var child_name = child_info["name"]

            # Check if child already exists
            if root_node.find_child(child_name, false):
                print("  Child '", child_name, "' already exists in scene '", scene_path, "'. Skipping.")
                continue

            var child_scene_path = "res://" + child_info["path"]

            # Check if the child is a .blend file
            if child_scene_path.ends_with(".blend"):
                # This means it's a .blend file
                var blend_object_name = child_info.get("object_name", "")  # Object name to load from the .blend file
                
                # Construct the path for the specific object inside the .blend file
                var full_blend_path = child_scene_path + "::" + blend_object_name
                var child_scene = load(full_blend_path) as PackedScene
                if not child_scene:
                    printerr("Failed to load child scene from .blend: ", full_blend_path, " for parent: ", scene_path)
                    continue

                var instance = child_scene.instantiate()
                if not instance:
                    printerr("Failed to instantiate child scene from .blend: ", full_blend_path)
                    continue

                instance.name = child_name # Use the pre-fetched name
                root_node.add_child(instance)
                # Set the owner for the child instance to ensure it's saved with the parent scene
                instance.owner = root_node
                children_added = true # Mark that a new child was added
                print("  Added child '", instance.name, "' (", full_blend_path, ") to '", root_node.name, "' (", scene_path, ")")
            else:
                # Handle non-.blend child (assuming it's a standard PackedScene)
                var child_scene = load(child_scene_path) as PackedScene
                if not child_scene:
                    printerr("Failed to load child scene: ", child_scene_path, " for parent: ", scene_path)
                    continue

                var instance = child_scene.instantiate()
                if not instance:
                    printerr("Failed to instantiate child scene: ", child_scene_path)
                    continue

                instance.name = child_name # Use the pre-fetched name
                root_node.add_child(instance)
                # Set the owner for the child instance to ensure it's saved with the parent scene
                instance.owner = root_node
                children_added = true # Mark that a new child was added
                print("  Added child '", instance.name, "' (", child_scene_path, ") to '", root_node.name, "' (", scene_path, ")")

        # Pack and save scene ONLY if *new* children were actually added
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
                    print("  Updated scene with children: ", scene_path)
		else:
			print("  No new children added for scene: ", scene_path)

        # Clean up the instantiated root node from this pass
        root_node.free()

    print("Second pass: Adding children complete")

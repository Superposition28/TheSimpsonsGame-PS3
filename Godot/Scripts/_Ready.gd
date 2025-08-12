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

        var children_added = false
        for child_info in children_to_add:
            if typeof(child_info) != TYPE_DICTIONARY or not child_info.has("path") or not child_info.has("name"):
                printerr("Skipping invalid child entry for scene ", scene_path, ": ", child_info)
                continue

            var child_name = child_info["name"]

            if root_node.find_child(child_name, false):
                print("  Child '", child_name, "' already exists in scene '", scene_path, "'. Skipping.")
                continue

            var child_scene_path = "res://" + child_info["path"]

            # This single block now correctly handles both .tscn and .glb files
            # The old if/else for .blend files has been removed.
            var child_scene = load(child_scene_path) as PackedScene
            if not child_scene:
                printerr("Failed to load child scene: ", child_scene_path, " for parent: ", scene_path)
                continue

            var instance = child_scene.instantiate()
            if not instance:
                printerr("Failed to instantiate child scene: ", child_scene_path)
                continue

            instance.name = child_name
            root_node.add_child(instance)
            instance.owner = root_node # This is crucial for saving the child
            children_added = true
            print("  Added child '", instance.name, "' (", child_scene_path, ") to '", root_node.name, "' (", scene_path, ")")

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

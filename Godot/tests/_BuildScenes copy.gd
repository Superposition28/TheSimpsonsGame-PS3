# _BuildScenes.gd
@tool
extends SceneTree

#-----------------------------------------------------------------------------
# HELPER FUNCTIONS
#-----------------------------------------------------------------------------

# Recursively processes a list of children and adds them to a parent node.
func _add_children_recursive(parent_node: Node, children_data: Array, scene_root: Node) -> bool:
	var children_were_added = false
	
	for child_info in children_data:
		if typeof(child_info) != TYPE_DICTIONARY or not child_info.has("name"):
			printerr("  Skipping invalid child entry: ", child_info)
			continue

		var instance: Node = null

		# Create the node instance, either from a scene path or a class name.
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

		# Configure and add the node to the scene.
		instance.name = child_info["name"]
		
		# Apply configuration from JSON (e.g., transform).
		if child_info.has("config"):
			_apply_node_config(instance, child_info["config"])
		
		parent_node.add_child(instance)
		instance.owner = scene_root # Set owner to save the child with the scene.
		
		print("    Added child '", instance.name, "' to '", parent_node.name, "'")
		children_were_added = true
		
		# Recursively add any nested children.
		if child_info.has("children"):
			_add_children_recursive(instance, child_info["children"], scene_root)
			
	return children_were_added


# Applies configuration data from the JSON to a node (e.g., transform for Node3D).
func _apply_node_config(node: Node, config_data: Dictionary):
	if not config_data.has("transform"):
		return

	var node_3d = node as Node3D
	if not node_3d:
		printerr("  Warning: 'transform' config found for non-Node3D child '", node.name, "'.")
		return

	var transform_data = config_data["transform"]
	if typeof(transform_data) != TYPE_DICTIONARY:
		return

	# Apply position, rotation (in degrees), and scale.
	if transform_data.has("position"):
		var pos = transform_data["position"]
		node_3d.position = Vector3(pos.get("x", 0.0), pos.get("y", 0.0), pos.get("z", 0.0))
	if transform_data.has("rotation_degrees"):
		var rot = transform_data["rotation_degrees"]
		node_3d.rotation_degrees = Vector3(rot.get("x", 0.0), rot.get("y", 0.0), rot.get("z", 0.0))
	if transform_data.has("scale"):
		var scl = transform_data["scale"]
		node_3d.scale = Vector3(scl.get("x", 1.0), scl.get("y", 1.0), scl.get("z", 1.0))


#-----------------------------------------------------------------------------
# MAIN EXECUTION
#-----------------------------------------------------------------------------

func _init():
	print("--- Scene Builder Initialized ---")
	
	# --- Load Configuration ---
	var file = FileAccess.open("res://scene_config.json", FileAccess.READ)
	if not file:
		printerr("FATAL: Failed to open scene_config.json")
		return

	var data = JSON.parse_string(file.get_as_text())
	file.close()
	
	if typeof(data) != TYPE_ARRAY:
		printerr("FATAL: Invalid JSON data in scene_config.json")
		return

	# --- Pass 1: Create all base scenes ---
	print("\n--- Running Pass 1: Creating Base Scenes ---")
	for scene_info in data:
		if typeof(scene_info) != TYPE_DICTIONARY or not scene_info.has("path") or not scene_info.has("name"):
			printerr("Skipping invalid scene entry: ", scene_info)
			continue
		
		if scene_info.get("type", "") != "scene": # Only process entries marked as scenes
			continue

		var scene_path = scene_info["path"]
		var save_path = "res://" + scene_path
		
		# Ensure the target directory exists.
		var folder = scene_path.get_base_dir()
		if folder != ".":
			DirAccess.make_dir_recursive_absolute("res://" + folder)
		
		# Create the root node for the scene.
		var node_class = scene_info.get("class", "Node")
		var root_node = ClassDB.instantiate(node_class)
		if not root_node is Node:
			printerr("  Failed to instantiate class '", node_class, "'. Falling back to Node.")
			root_node = Node.new()
		root_node.name = scene_info["name"]

		# Pack and save the empty scene.
		var packed_scene = PackedScene.new()
		packed_scene.pack(root_node)
		
		var save_err = ResourceSaver.save(packed_scene, save_path)
		if save_err == OK:
			print("  Created base scene: ", save_path)
		else:
			printerr("  Failed to save scene: ", save_path, " (Error: ", save_err, ")")
	
	print("--- Pass 1 Complete ---")

	# --- Pass 2: Populate scenes with children ---
	print("\n--- Running Pass 2: Populating Scenes ---")
	for scene_info in data:
		var children_to_add = scene_info.get("children", [])
		if children_to_add.is_empty():
			continue

		var scene_path = "res://" + scene_info["path"]
		print("Processing scene for population: ", scene_path)
		
		var packed_scene = load(scene_path) as PackedScene
		if not packed_scene:
			printerr("  Failed to load base scene for population.")
			continue

		var root_node = packed_scene.instantiate()
		var children_added = _add_children_recursive(root_node, children_to_add, root_node)

		# If children were added, re-pack and save the updated scene.
		if children_added:
			var updated_packed_scene = PackedScene.new()
			updated_packed_scene.pack(root_node)
			var save_err = ResourceSaver.save(updated_packed_scene, scene_path)
			if save_err == OK:
				print("  Successfully updated scene with children.")
			else:
				printerr("  Failed to save updated scene: ", scene_path, " (Error: ", save_err, ")")

		root_node.free()

	print("--- Pass 2 Complete ---")
	print("\n✅✅✅ Scene building finished! ✅✅✅")

	print("\nWaiting before exiting...")
	await create_timer(100.0).timeout

	quit() # Exit Godot automatically
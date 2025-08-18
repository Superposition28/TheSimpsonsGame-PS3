@tool
extends SceneTree

#-----------------------------------------------------------------------------
# HELPER FUNCTIONS
#-----------------------------------------------------------------------------

func _generate_collision_for_node(node_to_scan: Node, collision_parent: Node3D, scene_root: Node):
	var mesh_instance = node_to_scan as MeshInstance3D
	if mesh_instance and mesh_instance.mesh:
		var static_body = StaticBody3D.new()
		var shape_node = CollisionShape3D.new()
		shape_node.shape = mesh_instance.mesh.create_trimesh_shape()
		if not shape_node.shape:
			printerr("      -> Failed to create shape for mesh: ", mesh_instance.name)
			return
		static_body.add_child(shape_node)
		collision_parent.add_child(static_body)
		static_body.owner = scene_root
		shape_node.owner = scene_root
		static_body.global_transform = mesh_instance.global_transform
		static_body.rotate_x(deg_to_rad(90))
		print("      -> Generated collision body for '", mesh_instance.name, "'")
	for child in node_to_scan.get_children():
		_generate_collision_for_node(child, collision_parent, scene_root)


func _add_children_recursive(parent_node: Node, children_data: Array, scene_root: Node) -> bool:
	var children_were_added = false
	for child_info in children_data:
		if typeof(child_info) != TYPE_DICTIONARY or not child_info.has("name"):
			printerr("    Skipping invalid child entry: ", child_info)
			continue
		var instance: Node = null
		if child_info.has("path"):
			var child_scene_path = "res://" + child_info["path"]
			var resource = load(child_scene_path)
			if resource:
				instance = resource.instantiate()
			if not instance:
				printerr("    Failed to load or instantiate child resource: ", child_scene_path)
				continue
		elif child_info.has("class"):
			var node_class = child_info["class"]
			instance = ClassDB.instantiate(node_class)
			if not instance:
				printerr("    Failed to instantiate class: '", node_class, "'")
				continue
		else:
			printerr("    Skipping child '", child_info["name"], "' because it has no 'path' or 'class'.")
			continue
		instance.name = child_info["name"]
		
		# MODIFIED: Apply config immediately after instantiating.
		# The new _apply_node_config now handles transforms and mesh_overrides.
		if child_info.has("config"):
			_apply_node_config(instance, child_info["config"])
			
		parent_node.add_child(instance)
		instance.owner = scene_root
		print("      Added child '", instance.name, "' to '", parent_node.name, "'")
		children_were_added = true
		
		if child_info.has("collision"):
			var collision_config = child_info["collision"]
			if collision_config is Dictionary and collision_config.get("enabled", false):
				print("    Collision generation enabled for '", instance.name, "'. Creating container.")
				var collision_container = Node3D.new()
				collision_container.name = instance.name + "_Collision"
				parent_node.add_child(collision_container)
				collision_container.owner = scene_root
				_generate_collision_for_node(instance, collision_container, scene_root)

		if child_info.has("children"):
			_add_children_recursive(instance, child_info["children"], scene_root)
	return children_were_added


# MODIFIED: Replaced the old function with your improved version.
func _apply_node_config(node: Node, config_data: Dictionary):
	# --- Transform ---
	if config_data.has("transform"):
		var node_3d = node as Node3D
		if node_3d:
			var transform_data = config_data["transform"]
			if typeof(transform_data) == TYPE_DICTIONARY:
				if transform_data.has("position"):
					var pos = transform_data["position"]
					node_3d.position = Vector3(pos.get("x", 0.0), pos.get("y", 0.0), pos.get("z", 0.0))
				if transform_data.has("rotation_degrees"):
					var rot = transform_data["rotation_degrees"]
					node_3d.rotation_degrees = Vector3(rot.get("x", 0.0), rot.get("y", 0.0), rot.get("z", 0.0))
				if transform_data.has("scale"):
					var scl = transform_data["scale"]
					node_3d.scale = Vector3(scl.get("x", 1.0), scl.get("y", 1.0), scl.get("z", 1.0))
		else:
			printerr("    Warning: 'transform' config found for non-Node3D child '", node.name, "'.")

	# --- Mesh-specific overrides inside an imported asset ---
	if config_data.has("mesh_overrides"):
		var overrides = config_data["mesh_overrides"]
		if typeof(overrides) == TYPE_ARRAY:
			print("    Applying mesh overrides for '", node.name, "'")
			for mesh_cfg in overrides:
				if mesh_cfg is Dictionary and mesh_cfg.has("path"):
					# Use find_child for a more robust recursive search
					var target = node.find_child(mesh_cfg["path"], true, false)
					if target:
						if mesh_cfg.has("visible") and target is Node3D:
							target.visible = mesh_cfg["visible"]
							print("      -> Set visibility for '", mesh_cfg["path"], "' to ", mesh_cfg["visible"])
					else:
						printerr("      -> ERROR: Could not find mesh with path '", mesh_cfg["path"], "'")

#-----------------------------------------------------------------------------
# MAIN EXECUTION
#-----------------------------------------------------------------------------

func _init():
	print("--- Scene Builder Initialized ---")
	var file = FileAccess.open("res://scene_config.json", FileAccess.READ)
	if not file:
		printerr("FATAL: Failed to open scene_config.json")
		return
	var data = JSON.parse_string(file.get_as_text())
	file.close()
	if typeof(data) != TYPE_ARRAY:
		printerr("FATAL: Invalid JSON data in scene_config.json")
		return
	print("\n--- Running Pass 1: Creating Base Scenes ---")
	for scene_info in data:
		if typeof(scene_info) != TYPE_DICTIONARY or not scene_info.has("path") or not scene_info.has("name"):
			printerr("Skipping invalid scene entry: ", scene_info)
			continue
		if scene_info.get("type", "") != "scene":
			continue
		var scene_path = scene_info["path"]
		var save_path = "res://" + scene_path
		var folder = scene_path.get_base_dir()
		if folder != ".":
			DirAccess.make_dir_recursive_absolute("res://" + folder)
		var node_class = scene_info.get("class", "Node")
		var root_node = ClassDB.instantiate(node_class)
		if not root_node is Node:
			printerr("    Failed to instantiate class '", node_class, "'. Falling back to Node.")
			root_node = Node.new()
		root_node.name = scene_info["name"]
		var packed_scene = PackedScene.new()
		packed_scene.pack(root_node)
		var save_err = ResourceSaver.save(packed_scene, save_path)
		if save_err == OK:
			print("    Created base scene: ", save_path)
		else:
			printerr("    Failed to save scene: ", save_path, " (Error: ", save_err, ")")
	print("--- Pass 1 Complete ---")
	print("\n--- Running Pass 2: Populating Scenes ---")
	for scene_info in data:
		var children_to_add = scene_info.get("children", [])
		if children_to_add.is_empty():
			continue
		if scene_info.get("type", "") != "scene":
			continue
		var scene_path = "res://" + scene_info["path"]
		print("Processing scene for population: ", scene_path)
		var packed_scene = load(scene_path) as PackedScene
		if not packed_scene:
			printerr("    Failed to load base scene for population.")
			continue
		var root_node = packed_scene.instantiate()
		var children_added = _add_children_recursive(root_node, children_to_add, root_node)
		if children_added:
			var updated_packed_scene = PackedScene.new()
			updated_packed_scene.pack(root_node)
			var save_err = ResourceSaver.save(updated_packed_scene, scene_path)
			if save_err == OK:
				print("    Successfully updated scene with children.")
			else:
				printerr("    Failed to save updated scene: ", scene_path, " (Error: ", save_err, ")")
		root_node.free()
	print("--- Pass 2 Complete ---")
	print("\n✅✅✅ Scene building finished! ✅✅✅")

	if OS.get_cmdline_args().has("--no-exit"):
		print("\n'--no-exit' flag detected. Godot will remain open.")
	else:
		print("\nWaiting before exiting...")
		await create_timer(3.0).timeout
		quit()
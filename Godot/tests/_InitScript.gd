# RemakeRegistry\Games\TheSimpsonsGame PS3\Godot\_InitScript.gd
@tool
extends SceneTree

func _init():
	print("Building scenes...")
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
		
	# --- First Pass: Create all base scenes ---
	print("Pass 1: Creating base scenes...")
	for scene_info in data:
		if typeof(scene_info) != TYPE_DICTIONARY or not scene_info.has("path") or not scene_info.has("name"):
			printerr("Skipping invalid scene entry: ", scene_info)
			continue
			
		var scene_path = scene_info["path"]
		var folder = scene_path.get_base_dir()
		var save_path = "res://" + scene_path
		print("Processing scene: ", save_path)

		# Ensure folder exists
		if folder != ".":
			var full_folder_path = "res://" + folder
			if not DirAccess.dir_exists_absolute(full_folder_path):
				var err = DirAccess.make_dir_recursive_absolute(full_folder_path)
				if err != OK:
					printerr("  Failed to create directory: ", full_folder_path, " Error code: ", err)
					continue
		
		# ---- MODIFICATION START ----
		# Create root node using the 'class' property from JSON
		var node_class = scene_info.get("class", "Node")
		var root_node = ClassDB.instantiate(node_class)
		if not root_node is Node:
			printerr("  Failed to instantiate class: '", node_class, "'. Falling back to Node.")
			root_node = Node.new()
		# ---- MODIFICATION END ----
		
		root_node.name = scene_info["name"]

		# Pack and save scene
		var packed_scene = PackedScene.new()
		var pack_err = packed_scene.pack(root_node)
		if pack_err != OK:
			printerr("  Failed to pack scene: ", scene_path, " Error code: ", pack_err)
			root_node.free()
			continue

		if not FileAccess.file_exists(save_path):
			var save_err = ResourceSaver.save(packed_scene, save_path)
			if save_err != OK:
				printerr("  Failed to save scene: ", save_path, " Error code: ", save_err)
			else:
				print("  Successfully created base scene: ", save_path)
		else:
			print("  Scene already exists, skipping creation: ", save_path)

	print("First pass: Scene creation complete")
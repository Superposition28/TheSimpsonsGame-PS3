# ----------------------------------------------------------------------------
# IMPORT
# Godot EditorScript to import a previously exported scene (and its resources)
#
#
# -----------------------------------------------------------------------------

@tool
extends SceneTree # Needed to run from command line with --script
#extends EditorScript # Needed to run from the editor

const CONFIG_ROOT := "res://Json/"
const ASSET_ROOT  := "res://assets/"
const INDEX_JSON_ROOT := "res://index_json/"

# --- NEW --- Hold the loaded asset indexes
var glb_index: Array = []
var png_index: Array = []


# Entry file can be overridden with: --config=res://scene_config/Whatever.json
func _get_entry_config_path() -> String:
	var entry := CONFIG_ROOT + "Node4D.json"
	for arg in OS.get_cmdline_args():
		if arg.begins_with("--config="):
			var v := arg.substr(len("--config="), arg.length())
			if v != "":
				entry = v
	return entry

# ----------------------------------------------------------------------------
# JSON IO
# ----------------------------------------------------------------------------
func _load_json_array(abs_path: String) -> Array:
	var f := FileAccess.open(abs_path, FileAccess.READ)
	if not f:
		printerr("FATAL: Cannot open JSON: ", abs_path)
		return []
	var txt := f.get_as_text()
	f.close()
	var data: Variant = JSON.parse_string(txt)
	if typeof(data) == TYPE_ARRAY:
		return data as Array
	printerr("FATAL: Invalid JSON (expected array): ", abs_path)
	return []

# --- NEW HELPERS ---
func _json_to_vec2(d: Dictionary) -> Vector2:
	if d == null: return Vector2.ZERO
	return Vector2(float(d.get("x", 0.0)), float(d.get("y", 0.0)))

func _json_to_rect2(d: Dictionary) -> Rect2:
	if d == null: return Rect2()
	var pos := Vector2.ZERO
	var size := Vector2.ZERO
	if d.has("position") and d["position"] is Dictionary:
		pos = _json_to_vec2(d["position"])
	if d.has("size") and d["size"] is Dictionary:
		size = _json_to_vec2(d["size"])
	return Rect2(pos, size)

func _json_to_color(d: Dictionary) -> Color:
	if d == null: return Color.BLACK # Default to black if data is missing
	return Color(
		float(d.get("r", 0.0)),
		float(d.get("g", 0.0)),
		float(d.get("b", 0.0)),
		float(d.get("a", 1.0))
	)
# --- END NEW HELPERS ---


# ----------------------------------------------------------------------------
# --- NEW: ASSET INDEX LOOKUP ---
# ----------------------------------------------------------------------------

# Helper to find the real asset path from the loaded indexes
# 'lookup_key' is the value from the level JSON (e.g., index_data["index_source_path"])
# It searches against the "source_path" in the master indexes.
# Returns the full "res://assets/..." path if found, or an empty string if not.
func _find_indexed_path(lookup_key: String) -> String:
	var index_to_search: Array = []
	var file_type: String = ""
	
	if lookup_key.ends_with(".glb"):
		index_to_search = glb_index
		file_type = "GLB"
	elif lookup_key.ends_with(".png"):
		index_to_search = png_index
		file_type = "PNG"
	else:
		# Not a file type we're indexing
		return ""

	for entry in index_to_search:
		if entry.has("source_path") and entry["source_path"] == lookup_key:
			if entry.has("original_path") and entry["original_path"] != "":
				# Construct the final path, e.g., "res://assets/" + "path/from/index.png"
				return ASSET_ROOT + entry["original_path"]
			else:
				printerr("    ERROR: ", file_type, " index entry found for '", lookup_key, "' but 'original_path' is missing or empty.")
				return ""
	
	printerr("    ERROR: Could not find ", file_type, " indexed path for: ", lookup_key)
	return "" # Not found

# ----------------------------------------------------------------------------
# COLLISION
# ----------------------------------------------------------------------------
enum CollisionPlacement { STATIC_BODY_CHILD, STATIC_BODY_SIBLING, COLLISION_CONTAINER }

func _parse_collision_placement(s: String) -> int:
	match s:
		"StaticBodyChild":    return CollisionPlacement.STATIC_BODY_CHILD
		"StaticBodySibling":  return CollisionPlacement.STATIC_BODY_SIBLING
		"CollisionContainer": return CollisionPlacement.COLLISION_CONTAINER
		_: return CollisionPlacement.STATIC_BODY_CHILD

func _make_shape_for_mesh(mesh: Mesh, shape_type: String) -> Shape3D:
	if mesh == null:
		printerr("    Cannot create collision shape: mesh is null")
		return null

	if shape_type == "Trimesh":
		print("    Creating Trimesh collision shape")
		return mesh.create_trimesh_shape()
	elif shape_type == "Convex":
		print("    Creating Convex collision shape")
		return mesh.create_convex_shape()
	
	printerr("    Unknown collision shape type: ", shape_type)
	return null

func _is_ancestor_of(ancestor: Node, node: Node) -> bool:
	var n := node.get_parent()
	while n:
		if n == ancestor:
			return true
		n = n.get_parent()
	return false

func _transform_relative_to(node_3d: Node3D, ancestor: Node) -> Transform3D:
	var t := node_3d.transform
	var p := node_3d.get_parent()
	while p and p != ancestor:
		if p is Node3D:
			t = p.transform * t
		p = p.get_parent()
	return t

func _add_collision_to_mesh_instance(mesh_instance: MeshInstance3D, col_info: Dictionary, parent_node: Node) -> void:
	var shape_type := String(col_info.get("ShapeType", "Trimesh"))
	var shape: Shape3D = _make_shape_for_mesh(mesh_instance.mesh, shape_type)
	if shape == null:
		return

	var placement_str := String(col_info.get("shapePlacement", "StaticBodyChild"))
	var placement: int = _parse_collision_placement(placement_str)
	var static_body := StaticBody3D.new()
	static_body.name = "Collision"
	
	match placement:
		CollisionPlacement.STATIC_BODY_CHILD:
			print("    Attaching StaticBody3D as child.")
			mesh_instance.add_child(static_body)
		
		CollisionPlacement.STATIC_BODY_SIBLING:
			print("    Attaching StaticBody3D as sibling.")
			parent_node.add_child(static_body)
			# Copy the mesh's transform to its sibling body
			static_body.transform = mesh_instance.transform
		
		CollisionPlacement.COLLISION_CONTAINER:
			var container_name := String(col_info.get("containerName", "Collisions"))
			var container_node := parent_node.find_child(container_name, false, false)
			if not container_node:
				print("    Creating collision container: '", container_name, "'")
				container_node = Node3D.new()
				container_node.name = container_name
				parent_node.add_child(container_node)
			
			print("    Attaching StaticBody3D to container '", container_name, "'")
			container_node.add_child(static_body)
			
			var relative_transform := _transform_relative_to(mesh_instance, container_node.get_parent())
			static_body.transform = relative_transform

	var col_shape := CollisionShape3D.new()
	col_shape.shape = shape
	static_body.add_child(col_shape)


# ----------------------------------------------------------------------------
# SCENE NODES
# ----------------------------------------------------------------------------

# Apply properties from a 'config' dictionary to a node
func _apply_config_to_node(node: Node, config_data: Dictionary) -> void:
	if config_data.is_empty():
		return

	# --- 3D TRANSFORM ---
	if node is Node3D and config_data.has("transform"):
		var t_data: Dictionary = config_data["transform"]
		if t_data.has("position"):
			node.position = _json_to_vec3(t_data["position"])
		if t_data.has("rotation_degrees"):
			node.rotation_degrees = _json_to_vec3(t_data["rotation_degrees"])
		if t_data.has("scale"):
			node.scale = _json_to_vec3(t_data["scale"])

	# --- 2D TRANSFORM (for Control nodes) ---
	if node is Control:
		if config_data.has("layout_mode"):
			node.layout_mode = int(config_data["layout_mode"])
		if config_data.has("offsets"):
			var o: Dictionary = config_data["offsets"]
			node.set_offset(SIDE_LEFT, float(o.get("offset_left", 0.0)))
			node.set_offset(SIDE_TOP, float(o.get("offset_top", 0.0)))
			node.set_offset(SIDE_RIGHT, float(o.get("offset_right", 0.0)))
			node.set_offset(SIDE_BOTTOM, float(o.get("offset_bottom", 0.0)))
	
	# --- 2D TRANSFORM (for Node2D nodes) ---
	if node is Node2D:
		if config_data.has("position"):
			node.position = _json_to_vec2(config_data["position"])
		if config_data.has("rotation_degrees"):
			node.rotation_degrees = float(config_data["rotation_degrees"])
		if config_data.has("scale"):
			node.scale = _json_to_vec2(config_data["scale"])

	# --- Sprite2D properties ---
	if node is Sprite2D:
		if config_data.has("texture_path"):
			var path := _path_to_res(String(config_data["texture_path"]))
			var tex: Variant = load(path)
			if tex and (tex is Texture2D):
				node.texture = tex
			else:
				printerr("    Failed to load texture for '", node.name, "': ", path)
		if config_data.has("region_enabled"):
			node.region_enabled = bool(config_data["region_enabled"])
		if config_data.has("region_rect"):
			node.region_rect = _json_to_rect2(config_data["region_rect"])

	# --- Label properties ---
	if node is Label:
		if config_data.has("text"):
			node.text = String(config_data["text"])
		if config_data.has("horizontal_alignment"):
			node.horizontal_alignment = int(config_data["horizontal_alignment"])
		if config_data.has("vertical_alignment"):
			node.vertical_alignment = int(config_data["vertical_alignment"])

	# --- Panel properties ---
	if node is Panel:
		# Panels can have style overrides
		if config_data.has("style_override_panel"):
			var style_data: Dictionary = config_data["style_override_panel"]
			var stylebox := StyleBoxFlat.new()
			if style_data.has("bg_color"):
				stylebox.bg_color = _json_to_color(style_data["bg_color"])
			# Add other StyleBox properties here if needed (borders, etc.)
			node.add_theme_stylebox_override("panel", stylebox)

# Create a new, empty scene
func _create_base_scene(scene_info: Dictionary) -> Node:
	var scene_class := String(scene_info.get("class", "Node"))
	var base_node: Node
	
	if ClassDB.class_exists(scene_class):
		base_node = ClassDB.instantiate(scene_class) as Node
	else:
		printerr("  Cannot create scene, class '", scene_class, "' does not exist. Defaulting to Node.")
		base_node = Node.new()

	base_node.name = scene_info.get("name", "SceneRoot")
	
	# Apply 'editable_children_default' if it exists
	if scene_info.has("editable_children_default"):
		if bool(scene_info["editable_children_default"]):
			base_node.editable_children = true
	
	return base_node

# Save a scene to a .tscn file
func _save_scene(scene_root: Node, scene_path: String) -> void:
	var packed := PackedScene.new()
	var err := packed.pack(scene_root)
	if err == OK:
		err = ResourceSaver.save(packed, scene_path)
		if err == OK:
			print("  Created base scene: ", scene_path)
		else:
			printerr("  Failed to save scene: ", scene_path, " (", err, ")")

# Instantiate a child given its descriptor. Returns the created Node, or null.
func _instantiate_child(child_info: Dictionary, scene_root: Node) -> Node:
	var instance: Node = null
	
	# --- MODIFIED: Check for 'index' block to load resource ---
	if child_info.has("index"):
		var index_data: Dictionary = child_info["index"]
		var lookup_key: String = ""
		
		# Check for 'index_source_path' or 'source_path' as the key
		if index_data.has("index_source_path"):
			lookup_key = index_data["index_source_path"]
		elif index_data.has("source_path"):
			lookup_key = index_data["source_path"]
		
		if lookup_key != "":
			var indexed_path: String = _find_indexed_path(lookup_key)
			
			if indexed_path != "" and FileAccess.file_exists(indexed_path):
				print("    Found indexed path for '", lookup_key, "': '", indexed_path, "'")
				var res: Resource = load(indexed_path)
				
				if res is PackedScene:
					instance = res.instantiate()
				elif res is Mesh:
					var mesh_instance := MeshInstance3D.new()
					mesh_instance.mesh = res
					instance = mesh_instance
				elif res is Texture2D:
					var sprite_instance := Sprite2D.new()
					sprite_instance.texture = res
					instance = sprite_instance
				else:
					printerr("    ERROR: Indexed resource '", indexed_path, "' is not a valid type (PackedScene, Mesh, Texture2D).")
			elif indexed_path != "":
				printerr("    ERROR: Indexed path '", indexed_path, "' not found! (Key: '", lookup_key, "')")
			else:
				printerr("    ERROR: Failed to find indexed path for '", lookup_key, "'. Node '", child_info.get("name", "Unnamed"), "' will be null.")
		else:
			printerr("    ERROR: Node '", child_info.get("name", "Unnamed"), "' has 'index' block but no 'index_source_path' or 'source_path'.")
	# --- END MODIFIED LOGIC ---

	# 1) Nested config trees (ensure they are built first)
	if instance == null and child_info.has("config_file"): # --- MODIFIED ---
		var cfg_path := CONFIG_ROOT + child_info["config_file"]
		print("  Found nested config: ", cfg_path)
		var sub_scene_node: Node = _build_from_config(cfg_path)
		if sub_scene_node:
			instance = sub_scene_node
		else:
			printerr("  Failed to build nested config: ", cfg_path)
			
	# 2) Instantiated sub-scenes (e.g. "path": "res://MyScene.tscn")
	elif instance == null and child_info.has("path") and String(child_info["path"]).ends_with(".tscn"): # --- MODIFIED ---
		var scene_path: String = child_info["path"]
		if _scene_exists(scene_path):
			var packed: PackedScene = load(scene_path)
			if packed:
				instance = packed.instantiate()
			else:
				printerr("  Failed to load sub-scene: ", scene_path)
		else:
			printerr("  Sub-scene does not exist (may not be built yet): ", scene_path)

	# 3) A simple, built-in node (e.g. "class": "Node3D")
	elif instance == null and child_info.has("class"): # --- MODIFIED ---
		var class_name := String(child_info["class"])
		if ClassDB.class_exists(class_name):
			instance = ClassDB.instantiate(class_name) as Node
		else:
			printerr("  Cannot create node, class '", class_name, "' does not exist.")
			
	if instance:
		instance.name = child_info.get("name", "UnnamedNode")
	
	return instance

# Build a scene (and its children) from a config array
func _build_scene_from_array(scene_array: Array) -> Node:
	if scene_array.is_empty():
		return null
		
	# Assume first entry is the root
	var root_info: Dictionary = scene_array[0]
	var scene_path := String(root_info.get("path", ""))
	if scene_path == "":
		printerr("FATAL: Scene root info has no 'path' field.")
		return null
	
	print("\nBuilding Scene: ", scene_path)
	var scene_root: Node = _create_base_scene(root_info)
	
	# Apply root's own config
	if root_info.has("config"):
		_apply_config_to_node(scene_root, root_info["config"])
	
	# --- Build Children ---
	if root_info.has("children"):
		var children_array: Array = root_info["children"]
		for child_info_var in children_array:
			if not (child_info_var is Dictionary):
				printerr("  Skipping invalid child (not a Dictionary)")
				continue
				
			var child_info: Dictionary = child_info_var
			var child_node: Node = _instantiate_child(child_info, scene_root)
			
			if child_node:
				scene_root.add_child(child_node)
				
				# Apply config (if any)
				if child_info.has("config"):
					_apply_config_to_node(child_node, child_info["config"])
				
				# Attach script (if any)
				_attach_script_if_requested(child_node, child_info, "child")
				
				# Mark as editable
				var editable := bool(root_info.get("editable_children_default", false))
				if (child_info as Dictionary).has("editable_children"):
					editable = bool((child_info as Dictionary)["editable_children"])
				
				if editable:
					scene_root.set_editable_instance(child_node, true)
					print("    -> Marked '", child_node.name, "' as editable")
				
				# NEW: collision generation
				if child_node is MeshInstance3D and child_info.has("collision"):
					var col_info: Dictionary = child_info["collision"]
					if col_info.get("enabled", false):
						print("    Collision requested for '", child_node.name, "'")
						_add_collision_to_mesh_instance(child_node, col_info, scene_root)
			else:
				printerr("  Failed to instantiate child: ", child_info.get("name", "Unnamed"))

	_save_scene(scene_root, scene_path)
	return scene_root


# Entry point. Loads a config *file* and triggers the build.
func _build_from_config(abs_path: String) -> Node:
	var scene_array := _load_json_array(abs_path)
	if scene_array.is_empty():
		printerr("FATAL: Config file is empty or invalid: ", abs_path)
		return null
	return _build_scene_from_array(scene_array)


# ----------------------------------------------------------------------------
# HELPERS
# ----------------------------------------------------------------------------
func _path_to_res(p: String) -> String:
	return p if p.begins_with("res://") else "res://" + p

func _json_to_vec3(d: Dictionary) -> Vector3:
	if d == null: return Vector3.ZERO
	return Vector3(float(d.get("x", 0.0)), float(d.get("y", 0.0)), float(d.get("z", 0.0)))

func _attach_script_if_requested(node: Node, info: Dictionary, context: String) -> void:
	if info.has("script"):
		var s_path := String(info["script"])
		var abs := _path_to_res(s_path)
		var res: Variant = load(abs)
		if res and (res is Script):
			node.set_script(res)
			print("    Attached script '", abs, "' to ", context, " '", node.name, "'")
		else:
			printerr("    Failed to load script '", abs, "' for ", context, " '", node.name, "'")

func _scene_exists(scene_path: String) -> bool:
	return FileAccess.file_exists(scene_path)
# ----------------------------------------------------------------------------
# MAIN
# ----------------------------------------------------------------------------
func _init():
	print("--- Scene Builder Initialized ---")
	
	# --- NEW --- Load asset indexes
	print("Loading asset indexes...")
	glb_index = _load_json_array(INDEX_JSON_ROOT + "glb_index.json")
	png_index = _load_json_array(INDEX_JSON_ROOT + "png_index.json")
	print("  GLB index loaded: ", glb_index.size(), " entries")
	print("  PNG index loaded: ", png_index.size(), " entries")
	# --- END NEW ---
	
	var entry_cfg := _get_entry_config_path()
	print("Entry config: ", entry_cfg)
	_build_from_config(entry_cfg)
	print("\n✅✅✅ Scene building finished! ✅✅✅")

	if OS.get_cmdline_args().has("--no-exit"):
		print("\n'--no-exit' flag detected. Godot will remain open.")
	else:
		print("\nWaiting before exiting, to give Godot time to import...")
		# This timer is a bit of a hack, but --script exits immediately,
		# often before the editor has finished importing the new assets.
		var timer := get_tree().create_timer(5.0)
		await timer.timeout
		print("Exiting.")
		get_tree().quit()
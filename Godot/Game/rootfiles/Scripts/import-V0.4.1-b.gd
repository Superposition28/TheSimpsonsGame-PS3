# -----------------------------------------------------------------------------
# IMPORT
# Godot EditorScript to import a previously exported scene (and its resources)
#
# UPDATED V0.4.1-b: Added support for Shapes, Physics Layers, Generic Props, and Bones.
# -----------------------------------------------------------------------------

@tool
extends SceneTree

const CONFIG_ROOT := "res://Json/"
const ASSET_ROOT  := "res://assets/"

# Entry file can be overridden with: --config=res://scene_config/Whatever.json
func _get_entry_config_path() -> String:
	var entry := CONFIG_ROOT + "Node4D.json"
	for arg in OS.get_cmdline_args():
		if arg.begins_with("--config="):
			var v := arg.substr(len("--config="), arg.length())
			if v != "":
				entry = v
	return entry

# -----------------------------------------------------------------------------
# JSON IO & TYPE CONVERSION
# -----------------------------------------------------------------------------
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

func _json_to_vec2(d: Dictionary) -> Vector2:
	if d.is_empty(): return Vector2.ZERO
	return Vector2(float(d.get("x", 0.0)), float(d.get("y", 0.0)))

func _json_to_vec3(d: Dictionary) -> Vector3:
	if d.is_empty(): return Vector3.ZERO
	return Vector3(float(d.get("x", 0.0)), float(d.get("y", 0.0)), float(d.get("z", 0.0)))

func _json_to_quat(d: Dictionary) -> Quaternion:
	if d.is_empty(): return Quaternion.IDENTITY
	# Supports both xyzw and euler (optional expansion)
	return Quaternion(
		float(d.get("x", 0.0)),
		float(d.get("y", 0.0)),
		float(d.get("z", 0.0)),
		float(d.get("w", 1.0))
	)

func _json_to_rect2(d: Dictionary) -> Rect2:
	if d.is_empty(): return Rect2()
	var pos := _json_to_vec2(d.get("position", {}))
	var size := _json_to_vec2(d.get("size", {}))
	return Rect2(pos, size)

func _json_to_color(d: Dictionary) -> Color:
	if d.is_empty(): return Color.BLACK
	return Color(
		float(d.get("r", 0.0)),
		float(d.get("g", 0.0)),
		float(d.get("b", 0.0)),
		float(d.get("a", 1.0))
	)

# -----------------------------------------------------------------------------
# RESOURCE GENERATORS (Shapes, etc.)
# -----------------------------------------------------------------------------
func _create_shape_from_config(cfg: Dictionary) -> Shape3D:
	var type := String(cfg.get("type", "Box")) # Default to Box
	var shape: Shape3D = null

	match type:
		"Capsule", "CapsuleShape3D":
			shape = CapsuleShape3D.new()
			if cfg.has("radius"): shape.radius = float(cfg["radius"])
			if cfg.has("height"): shape.height = float(cfg["height"])
		"Box", "BoxShape3D":
			shape = BoxShape3D.new()
			if cfg.has("size"): shape.size = _json_to_vec3(cfg["size"])
		"Sphere", "SphereShape3D":
			shape = SphereShape3D.new()
			if cfg.has("radius"): shape.radius = float(cfg["radius"])
		"Cylinder", "CylinderShape3D":
			shape = CylinderShape3D.new()
			if cfg.has("radius"): shape.radius = float(cfg["radius"])
			if cfg.has("height"): shape.height = float(cfg["height"])
		"SeparationRay", "SeparationRayShape3D":
			shape = SeparationRayShape3D.new()
			if cfg.has("length"): shape.length = float(cfg["length"])
			if cfg.has("slide_on_slope"): shape.slide_on_slope = bool(cfg["slide_on_slope"])
		_:
			printerr("    Unknown shape type: ", type)

	return shape

# -----------------------------------------------------------------------------
# COLLISION GENERATION (Static Geometry)
# -----------------------------------------------------------------------------
enum CollisionPlacement { STATIC_BODY_CHILD, STATIC_BODY_SIBLING, COLLISION_CONTAINER }
var _collision_containers := {}

func _parse_collision_placement(s: String) -> int:
	match s:
		"StaticBodyChild":    return CollisionPlacement.STATIC_BODY_CHILD
		"StaticBodySibling":  return CollisionPlacement.STATIC_BODY_SIBLING
		"CollisionContainer": return CollisionPlacement.COLLISION_CONTAINER
		_: return CollisionPlacement.STATIC_BODY_CHILD

func _get_or_create_container(under_parent: Node, name: String, scene_root: Node) -> Node3D:
	var key := String(under_parent.get_path()) + "|" + name
	if _collision_containers.has(key):
		return _collision_containers[key]
	var c := Node3D.new()
	c.name = name
	under_parent.add_child(c)
	c.owner = scene_root
	_collision_containers[key] = c
	return c

func _generate_static_collision(node: Node, container_parent: Node3D, shape_type: String, placement: int, scene_root: Node) -> void:
	# This function generates collision from MESH DATA (Trimesh/Convex) automatically.
	# It is distinct from explicit CollisionShape3D nodes handled in _apply_node_config.
	var mesh_inst := node as MeshInstance3D
	if mesh_inst and mesh_inst.mesh:
		var shape: Shape3D
		if shape_type == "Convex": shape = mesh_inst.mesh.create_convex_shape()
		else: shape = mesh_inst.mesh.create_trimesh_shape()

		if shape:
			var body := StaticBody3D.new()
			body.name = mesh_inst.name + "_Body"

			# Determine parent based on placement strategy
			var target_parent: Node = container_parent
			if placement == CollisionPlacement.STATIC_BODY_CHILD: target_parent = mesh_inst
			elif placement == CollisionPlacement.STATIC_BODY_SIBLING: target_parent = mesh_inst.get_parent()

			target_parent.add_child(body)
			body.owner = scene_root
			body.transform = Transform3D.IDENTITY # Simplified assumption for child/container placement

			var col_node := CollisionShape3D.new()
			col_node.shape = shape
			body.add_child(col_node)
			col_node.owner = scene_root

			print("      -> Auto-Collision (", shape_type, ") created for '", mesh_inst.name, "'")

	for child in node.get_children():
		_generate_static_collision(child, container_parent, shape_type, placement, scene_root)

# -----------------------------------------------------------------------------
# CONFIG APPLICATION (MODULAR)
# -----------------------------------------------------------------------------

# 1. Transforms
func _apply_transform_config(node: Node, cfg: Dictionary) -> void:
	if not cfg.has("transform"): return
	var t_cfg: Dictionary = cfg["transform"]

	if node is Node3D:
		if t_cfg.has("position"): node.position = _json_to_vec3(t_cfg["position"])
		if t_cfg.has("rotation_degrees"): node.rotation_degrees = _json_to_vec3(t_cfg["rotation_degrees"])
		if t_cfg.has("scale"): node.scale = _json_to_vec3(t_cfg["scale"])
	elif node is Node2D:
		if t_cfg.has("position"): node.position = _json_to_vec2(t_cfg["position"])
		if t_cfg.has("rotation_degrees"): node.rotation_degrees = float(t_cfg["rotation_degrees"])
		if t_cfg.has("scale"): node.scale = _json_to_vec2(t_cfg["scale"])
	elif node is Control:
		_apply_control_layout(node, t_cfg) # Use specialized control handler

func _apply_control_layout(ctrl: Control, cfg: Dictionary) -> void:
	# Controls often use offsets/anchors rather than raw position/scale
	if cfg.has("layout_mode"): ctrl.layout_mode = int(cfg["layout_mode"])
	# Add more control-specific rect logic here if needed

# 2. Physics & Shapes
func _apply_physics_config(node: Node, cfg: Dictionary) -> void:
	# A. Collision Layers/Masks (CollisionObject3D)
	if node is CollisionObject3D: # StaticBody3D, CharacterBody3D, Area3D, etc.
		if cfg.has("collision_layer"): node.collision_layer = int(cfg["collision_layer"])
		if cfg.has("collision_mask"):  node.collision_mask = int(cfg["collision_mask"])

	# B. Explicit Shape Resources (CollisionShape3D, SpringArm3D)
	if cfg.has("shape") and cfg["shape"] is Dictionary:
		var shape_res := _create_shape_from_config(cfg["shape"])
		if shape_res:
			if node is CollisionShape3D:
				node.shape = shape_res
			elif node is SpringArm3D:
				node.shape = shape_res
			# Area3D doesn't hold a shape directly, it uses children

# 3. Generic Properties (SpringLength, Script Vars, etc.)
func _apply_generic_properties(node: Node, cfg: Dictionary) -> void:
	# "properties": { "spring_length": 3.0, "my_script_var": 10 }
	if cfg.has("properties") and cfg["properties"] is Dictionary:
		var props: Dictionary = cfg["properties"]
		for key in props:
			var val = props[key]
			# Check if property exists to avoid errors, or set_deferred if needed
			node.set(key, val)
			# Note: set() works for exported script variables too!

# 4. Visuals (Mesh/UI specific)
func _apply_visual_config(node: Node, cfg: Dictionary) -> void:
	if node is Sprite2D:
		if cfg.has("texture_path") and cfg["texture_path"] != "null":
			var tex = load(cfg["texture_path"])
			if tex: node.texture = tex
		if cfg.has("region_enabled"): node.region_enabled = bool(cfg["region_enabled"])
		if cfg.has("region_rect"): node.region_rect = _json_to_rect2(cfg["region_rect"])

	if node is Label or node is RichTextLabel:
		if cfg.has("text"): node.text = String(cfg["text"])

	if node is ColorRect and cfg.has("color"):
		node.color = _json_to_color(cfg["color"])

# 5. Scene/Mesh Overrides (Bones, Visibility)
func _apply_overrides(node: Node, cfg: Dictionary) -> void:
	# Mesh Overrides (Visibility)
	if cfg.has("mesh_overrides") and cfg["mesh_overrides"] is Array:
		for override in cfg["mesh_overrides"]:
			var path: String = override.get("path", "")
			var target := node.find_child(path, true, false)
			if target and target is Node3D and override.has("visible"):
				target.visible = bool(override["visible"])

	# Bone Overrides (Skeleton3D)
	# JSON Format: "bone_overrides": { "skeleton_path": "playermodel/Skeleton3D", "poses": { "BoneNameOrIndex": { "rotation": {...} } } }
	if cfg.has("bone_overrides") and cfg["bone_overrides"] is Dictionary:
		var bo: Dictionary = cfg["bone_overrides"]
		var skel_path: String = bo.get("skeleton_path", "")
		var skel_node := node.find_child(skel_path, true, false) as Skeleton3D

		if skel_node and bo.has("poses"):
			var poses: Dictionary = bo["poses"]
			for bone_id in poses:
				var pose_data: Dictionary = poses[bone_id]
				var idx := -1

				# Resolve Index (Handle string names or int indices)
				if str(bone_id).is_valid_int():
					idx = int(bone_id)
				else:
					idx = skel_node.find_bone(str(bone_id))

				if idx != -1:
					if pose_data.has("rotation"):
						var q := _json_to_quat(pose_data["rotation"])
						skel_node.set_bone_pose_rotation(idx, q)
					if pose_data.has("position"):
						var p := _json_to_vec3(pose_data["position"])
						skel_node.set_bone_pose_position(idx, p)
					# Add scale if needed

# --- MASTER CONFIG APPLICATION FUNCTION ---
func _apply_node_config(node: Node, config_data: Dictionary):
	if config_data.is_empty(): return

	_apply_transform_config(node, config_data)
	_apply_physics_config(node, config_data)
	_apply_visual_config(node, config_data)
	_apply_generic_properties(node, config_data)
	_apply_overrides(node, config_data)

# -----------------------------------------------------------------------------
# CHILD CREATION & RECURSION
# -----------------------------------------------------------------------------
func _ensure_dir_for(save_path: String) -> void:
	var folder := save_path.get_base_dir()
	if folder != "." and not DirAccess.dir_exists_absolute("res://" + folder.trim_prefix("res://")):
		DirAccess.make_dir_recursive_absolute("res://" + folder.trim_prefix("res://"))

func _attach_script_if_requested(node: Node, info: Dictionary) -> void:
	if info.has("script"):
		var s_path := String(info["script"])
		if not s_path.begins_with("res://"): s_path = "res://" + s_path

		var res = load(s_path)
		if res and (res is Script):
			node.set_script(res)
			print("    Attached script: ", s_path)
		else:
			printerr("    Failed to load script: ", s_path)

func _instantiate_child(child_info: Dictionary, scene_root: Node) -> Node:
	var instance: Node = null

	# 1. Config File (Nested)
	if child_info.has("config_file"):
		var sub_cfg: String = CONFIG_ROOT + String(child_info["config_file"])
		_build_from_config(sub_cfg)

	# 2. Scene Path (Preferred)
	if child_info.has("path"):
		var path: String = "res://" + String(child_info["path"])
		var res = load(path)
		if res is PackedScene:
			instance = res.instantiate()
		else:
			printerr("    Failed to load scene: ", path)
			return null

	# 3. Class Instantiation (Fallback)
	elif child_info.has("class"):
		var cls_name: String = String(child_info["class"])
		if ClassDB.class_exists(cls_name):
			instance = ClassDB.instantiate(cls_name)
		else:
			printerr("    Class not found: ", cls_name)
			return null

	# 4. GLB via Index
	elif child_info.has("index") and child_info["index"].has("index_source_path"):
		var glb_path: String = ASSET_ROOT + String(child_info["index"]["index_source_path"])
		var res = load(glb_path)
		if res is PackedScene:
			instance = res.instantiate()
		else:
			printerr("    Failed to load GLB: ", glb_path)
			return null
	else:
		return null # Skip invalid

	# Basic Setup
	if child_info.has("name"): instance.name = String(child_info["name"])

	# Attach Script BEFORE config (so we can set script variables)
	_attach_script_if_requested(instance, child_info)

	# Apply Config
	if child_info.has("config") and child_info["config"] is Dictionary:
		_apply_node_config(instance, child_info["config"])

	return instance

func _add_children_recursive(parent_node: Node, children_data: Array, scene_root: Node, editable_default: bool) -> void:
	for child_info in children_data:
		if typeof(child_info) != TYPE_DICTIONARY: continue

		var instance := _instantiate_child(child_info, scene_root)
		if not instance: continue

		parent_node.add_child(instance)
		instance.owner = scene_root
		print("      Added child '", instance.name, "'")

		# Editable Children
		var editable := editable_default
		if child_info.has("editable_children"): editable = bool(child_info["editable_children"])
		if editable: parent_node.set_editable_instance(instance, true)

		# Auto-Generate Static Collision (Optional Mesh Processing)
		if child_info.has("collision") and child_info["collision"] is Dictionary:
			var c: Dictionary = child_info["collision"]
			if c.get("enabled", false):
				var shape_type := String(c.get("ShapeType", "Trimesh"))
				var container_name := String(c.get("containerName", "Mesh_Collisions"))
				var container := _get_or_create_container(instance, container_name, scene_root)
				_generate_static_collision(instance, container, shape_type, CollisionPlacement.COLLISION_CONTAINER, scene_root)

		# Recurse
		if child_info.has("children") and child_info["children"] is Array:
			_add_children_recursive(instance, child_info["children"], scene_root, editable_default)

# -----------------------------------------------------------------------------
# BUILD PASSES
# -----------------------------------------------------------------------------
func _scene_exists(path: String) -> bool:
	return FileAccess.file_exists(path)

func _pass_create_base_scenes(cfg_items: Array) -> void:
	print("\n--- Pass 1: Creating Base Scenes ---")
	for info in cfg_items:
		if info.get("type") != "scene": continue
		if not (info.has("name") and info.has("path")): continue

		var path: String = "res://" + String(info["path"])
		var overwrite: bool = info.get("overwrite", true)

		if _scene_exists(path) and not overwrite:
			print("    Skipping existing: ", path)
			continue

		_ensure_dir_for(path)

		var cls: String = info.get("class", "Node")
		var root: Node = ClassDB.instantiate(cls)
		if not root: root = Node.new()
		root.name = String(info["name"])

		_attach_script_if_requested(root, info)

		var packed := PackedScene.new()
		packed.pack(root)
		ResourceSaver.save(packed, path)
		print("    Created base: ", path)
	print("--- Pass 1 Complete ---")

func _pass_populate_scenes(cfg_items: Array) -> void:
	print("\n--- Pass 2: Populating Scenes ---")
	for info in cfg_items:
		if info.get("type") != "scene": continue

		var path: String = "res://" + String(info["path"])
		var overwrite: bool = info.get("overwrite", true)
		if _scene_exists(path) and not overwrite: continue

		var children: Array = info.get("children", [])
		if children.is_empty(): continue

		print("Populating: ", path)
		var packed := load(path) as PackedScene
		if not packed: continue

		var root := packed.instantiate()
		var editable_default: bool = info.get("editable_children_default", true)

		# Apply root config if present (e.g. root position/layers)
		if info.has("config"): _apply_node_config(root, info["config"])

		_add_children_recursive(root, children, root, editable_default)

		var updated := PackedScene.new()
		updated.pack(root)
		ResourceSaver.save(updated, path)
		root.free()
	print("--- Pass 2 Complete ---")

func _build_from_config(abs_path: String) -> void:
	print("\n=== BUILD FROM CONFIG: ", abs_path, " ===")
	var items := _load_json_array(abs_path)
	if items.is_empty(): return

	_pass_create_base_scenes(items)
	_pass_populate_scenes(items)

# -----------------------------------------------------------------------------
# MAIN
# -----------------------------------------------------------------------------
func _init():
	print("--- Importer V0.5 Initialized ---")
	var entry := _get_entry_config_path()
	_build_from_config(entry)
	print("\n✅ Build Finished ✅")

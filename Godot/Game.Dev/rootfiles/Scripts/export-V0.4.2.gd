# -----------------------------------------------------------------------------
# EXPORT (Round-Trip Version)
#
# This script reads an existing JSON file as the "source of truth"
# and merges it with live data from the currently open Godot scene
# (e.g., transforms, text).
#
# It preserves all data from the original JSON (like "index", "collision")
# that doesn't exist in the Godot scene.
#
# READS FROM: res://Json/
# WRITES TO:  res://export-json/
# -----------------------------------------------------------------------------

@tool
extends EditorScript # Needed to run from the editor

# -------------------------------------------------------------------
# CONFIG
# -------------------------------------------------------------------
# Path to READ old JSON files from (The Source of Truth)
const JSON_IMPORT_ROOT: String = "res://Json/"
# Path to WRITE new JSON files to
const JSON_EXPORT_ROOT: String = "res://export-json/"

const DEFAULT_CONFIG_FILE: String = "Node4D.json"

const SHOULD_EMIT_VISIBILITY_FOR_ALL_MESHES: bool = true
const DEFAULT_COLLISION_CONTAINER_NAME: String = "Mesh_Collisions"

# -------------------------------------------------------------------
# STATE / HELPERS (tree-mirrored output)
# -------------------------------------------------------------------
var _exported_scene_jsons: Dictionary = {}  # acts like a Set: abs json res path -> true

func _rel_json_for_stack(stack: Array) -> String:
	# ["Root","Child"] -> "Root/Child.json"
	var joined: String = "/".join(stack)
	return joined + ".json"

func _abs_json_res(rel_json: String) -> String:
	# "Root/Child.json" -> "res://export-json/Root/Child.json"
	# NOTE: This now points to the EXPORT root
	return JSON_EXPORT_ROOT.path_join(rel_json)

func _rel_tscn_for_stack(stack: Array, source_scene_path: String) -> String:
	# Mirrors the JSON folder path, but keeps original scene filename (casing) from source_scene_path
	# e.g. ["Node","Node3D","Control"], "res://scenes/control.tscn" -> "Node/Node3D/Control/control.tscn"
	var joined: String = "/".join(stack)
	var file_name: String = _trim_res(source_scene_path).get_file()
	return joined + "/" + file_name

func _ensure_dir_for_res(res_path: String) -> void:
	# res_path is a res:// file path; make dirs recursively
	var folder: String = res_path.get_base_dir()
	if folder == "" or folder == ".":
		return
	if not DirAccess.dir_exists_absolute(folder):
		var ok: int = DirAccess.make_dir_recursive_absolute(folder)
		if ok != OK:
			push_error("Failed to create: %s" % folder)

func _write_json(abs_res_path: String, data: Variant) -> void:
	_ensure_dir_for_res(abs_res_path)
	var f: FileAccess = FileAccess.open(abs_res_path, FileAccess.WRITE)
	if not f:
		push_error("Cannot open for write: %s" % abs_res_path)
		return
	var json: String = JSON.stringify(data, "  ")
	f.store_string(json)
	f.close()

func _trim_res(p: String) -> String:
	if p.begins_with("res://"):
		return p.substr(6, p.length())
	return p

# --- NEW: JSON Loading Helpers (from import.gd) ---
func _load_json_array(abs_path: String) -> Array:
	var f := FileAccess.open(abs_path, FileAccess.READ)
	if not f:
		printerr("Cannot open JSON: ", abs_path)
		return []
	var txt := f.get_as_text()
	f.close()
	var data: Variant = JSON.parse_string(txt)
	if typeof(data) == TYPE_ARRAY:
		return data as Array
	printerr("Invalid JSON (expected array): ", abs_path)
	return []

# --- NEW: Helper to find old data for a child by name ---
func _find_child_json_by_name(parent_json: Dictionary, child_name: String) -> Dictionary:
	if parent_json.has("children") and parent_json["children"] is Array:
		for child_data in parent_json["children"]:
			if child_data is Dictionary and child_data.get("name", "") == child_name:
				return child_data
	return {} # Return empty dict if not found


# -------------------------------------------------------------------
# ENVIRONMENT (WorldEnvironment <-> Environment + Sky) EXPORT HELPERS
# (These are unchanged from export-V0.4.gd)
# -------------------------------------------------------------------
const _ENV_EXPORT_KEYS := [
	"background_mode", "background_color", "background_energy",
	"ambient_light_source", "ambient_light_color", "ambient_light_energy",
	"ambient_light_sky_contribution", "exposure_multiplier", "glow_enabled",
	"ssao_enabled", "ssil_enabled", "volumetric_fog_enabled", "fog_enabled",
	"tonemap_mode"
]

const _SKY_EXPORT_KEYS := [
	"sun_energy", "energy", "rayleigh", "mie", "mie_eccentricity",
	"exposure", "ground_color", "horizon_color", "sky_top_color",
	"sky_horizon_color", "texture", "rotation"
]

func _color_to_json(c: Color) -> Dictionary:
	return {"r": c.r, "g": c.g, "b": c.b, "a": c.a}

func _vec2_to_json(v: Vector2) -> Dictionary:
	return {"x": v.x, "y": v.y}

func _rect2_to_json(r: Rect2) -> Dictionary:
	return {
		"position": _vec2_to_json(r.position),
		"size": _vec2_to_json(r.size)
	}

func _serialize_props_from_keys(obj: Object, keys: Array) -> Dictionary:
	var out: Dictionary = {}
	for k in keys:
		if not obj:
			continue
		var v = obj.get(k) if obj.has_method("get") else null
		if v == null:
			continue
		if typeof(v) == TYPE_COLOR:
			out[k] = _color_to_json(v)
		else:
			out[k] = v
	return out

func _serialize_environment(env: Environment) -> Dictionary:
	var out: Dictionary = {}
	if env == null:
		return out
	out["props"] = _serialize_props_from_keys(env, _ENV_EXPORT_KEYS)
	if env.sky:
		var sky_dict: Dictionary = {}
		var mat: Resource = env.sky.sky_material
		if mat:
			var m: Dictionary = {}
			m["type"] = mat.get_class()
			m["props"] = _serialize_props_from_keys(mat, _SKY_EXPORT_KEYS)
			sky_dict["material"] = m
		out["sky"] = sky_dict
	return out

# -------------------------------------------------------------------
# COLLISION export helpers
# (These are unchanged from export-V0.4.gd)
# -------------------------------------------------------------------
func _collect_static_bodies(root: Node) -> Array:
	var out: Array = []
	var stack: Array = [root]
	while not stack.is_empty():
		var cur: Node = stack.pop_back()
		for c in cur.get_children():
			stack.push_back(c)
		if cur is StaticBody3D:
			out.append(cur)
	return out

func _find_collision_container(node: Node) -> Node3D:
	for c in node.get_children():
		if c is Node3D and (c.name.ends_with("_Collision") or c.name == DEFAULT_COLLISION_CONTAINER_NAME):
			return c as Node3D
	return null

func _infer_shape_type_from_bodies(bodies: Array) -> String:
	var saw_convex: bool = false
	var saw_concave: bool = false
	for b in bodies:
		for c in (b as Node).get_children():
			if c is CollisionShape3D:
				var shape: Shape3D = (c as CollisionShape3D).shape
				if shape is ConvexPolygonShape3D:
					saw_convex = true
				elif shape is ConcavePolygonShape3D:
					saw_concave = true
	if saw_concave:
		return "Trimesh"
	if saw_convex:
		return "Convex"
	return "Trimesh"

func _detect_collision_config(node: Node) -> Dictionary:
	var info: Dictionary = {}
	var container: Node3D = _find_collision_container(node)
	var bodies: Array = []
	if container:
		bodies = _collect_static_bodies(container)
	else:
		bodies = _collect_static_bodies(node)
	if bodies.is_empty():
		return info
	info["enabled"] = true
	info["containerName"] = container.name if container else DEFAULT_COLLISION_CONTAINER_NAME
	info["ShapeType"] = _infer_shape_type_from_bodies(bodies)
	return info

# -------------------------------------------------------------------
# NODE CONFIG (Live Data Gatherer)
# (This is unchanged from export-V0.4.gd and is compatible
#  with import-V0.4.gd)
# -------------------------------------------------------------------
func _gather_node_config(node: Node) -> Dictionary:
	var cfg: Dictionary = {}

	# 3D transforms
	if node is Node3D:
		var n3: Node3D = node as Node3D
		cfg["transform"] = {
			"position": {"x": n3.position.x, "y": n3.position.y, "z": n3.position.z},
			"rotation_degrees": {"x": n3.rotation_degrees.x, "y": n3.rotation_degrees.y, "z": n3.rotation_degrees.z},
			"scale": {"x": n3.scale.x, "y": n3.scale.y, "z": n3.scale.z}
		}

	# 2D transforms (for non-Control Node2D)
	if node is Node2D and not (node is Control):
		var n2 := node as Node2D
		if n2.position != Vector2.ZERO:
			cfg["position"] = _vec2_to_json(n2.position)
		if n2.rotation_degrees != 0.0:
			cfg["rotation_degrees"] = n2.rotation_degrees
		if n2.scale != Vector2.ONE:
			cfg["scale"] = _vec2_to_json(n2.scale)

	# 2D Control layout/offsets
	if node is Control:
		var c: Control = node as Control
		cfg["layout_mode"] = c.layout_mode
		cfg["offsets"] = {
			"offset_left": c.offset_left,
			"offset_top": c.offset_top,
			"offset_right": c.offset_right,
			"offset_bottom": c.offset_bottom
		}

	# Sprite2D properties
	if node is Sprite2D:
		var s := node as Sprite2D
		if s.texture:
			cfg["texture_path"] = s.texture.resource_path
		if s.region_enabled:
			cfg["region_enabled"] = true
			cfg["region_rect"] = _rect2_to_json(s.region_rect)

	# Label properties
	if node is Label:
		var l := node as Label
		if l.text != "":
			cfg["text"] = l.text

	# RichTextLabel properties
	if node is RichTextLabel:
		var rtl := node as RichTextLabel
		if rtl.text != "":
			cfg["bbcode_text"] = rtl.text

	# ColorRect properties
	if node is ColorRect:
		var cr := node as ColorRect
		cfg["color"] = _color_to_json(cr.color)

	# Mesh visibility overrides under this scope node
	var mesh_overrides: Array = _collect_mesh_visibility_overrides(node)
	if not mesh_overrides.is_empty():
		cfg["mesh_overrides"] = mesh_overrides

	# WorldEnvironment -> Environment dump
	if node is WorldEnvironment:
		var we: WorldEnvironment = node as WorldEnvironment
		if we.environment:
			cfg["environment"] = _serialize_environment(we.environment)

	return cfg

func _collect_mesh_visibility_overrides(scope_node: Node) -> Array:
	var arr: Array = []
	var stack: Array = [scope_node]
	while not stack.is_empty():
		var cur: Node = stack.pop_back()
		for c in cur.get_children():
			stack.push_back(c)
		if cur == scope_node:
			continue
		if cur is MeshInstance3D:
			var mi: MeshInstance3D = cur as MeshInstance3D
			if SHOULD_EMIT_VISIBILITY_FOR_ALL_MESHES or not mi.visible:
				arr.append({
					"path": String(scope_node.get_path_to(mi)),
					"visible": mi.visible
				})
	return arr

# -------------------------------------------------------------------
# CORE SERIALIZATION (MODIFIED FOR ROUND-TRIP MERGE)
# -------------------------------------------------------------------

# --- MODIFIED: Accepts 'old_data' to merge with ---
func _serialize_scene(scene_root: Node, scene_path_opt: String = "", path_stack: Array = [], old_data: Dictionary = {}) -> Dictionary:
	
	var scene_path: String = scene_path_opt
	if scene_path == "" and scene_root is Node:
		scene_path = scene_root.scene_file_path

	# --- MERGE ---
	# 1. Start with the old data as the base.
	#    This preserves "index", "collision", "overwrite", "editable_children_default"
	#    and any other custom keys from the "source of truth" JSON.
	var entry: Dictionary = old_data.duplicate(true)

	# 2. Overwrite with live data from the Godot scene.
	entry["type"] = "scene"
	entry["name"] = scene_root.name
	entry["path"] = _trim_res(scene_path)
	entry["class"] = scene_root.get_class()

	# mirror .tscn path into JSON folder structure when we have a stack
	if scene_path != "" and not path_stack.is_empty():
		entry["path"] = _rel_tscn_for_stack(path_stack, scene_path)

	# Root script (if any)
	var root_script: Script = scene_root.get_script()
	if root_script and root_script.resource_path != "":
		entry["script"] = _trim_res(root_script.resource_path)
	else:
		entry.erase("script") # Remove old script if it's gone

	# 3. Children (Recursive Merge)
	var children_arr: Array = []
	# Iterate over LIVE children in the Godot scene
	for c in scene_root.get_children():
		# Find the corresponding old data for this child
		var old_child_data = _find_child_json_by_name(old_data, c.name)
		children_arr.append(_serialize_child(c as Node, scene_root, path_stack, old_child_data))
	
	if not children_arr.is_empty():
		entry["children"] = children_arr
	else:
		entry.erase("children") # Remove if no live children

	return entry

# --- MODIFIED: Accepts 'old_data' to merge with ---
func _serialize_child(node: Node, scene_root: Node, path_stack: Array, old_data: Dictionary = {}) -> Dictionary:
	
	# --- MERGE ---
	# 1. Start with the old data as the base.
	#    This preserves "index", "collision", "config_file", etc.
	var d: Dictionary = old_data.duplicate(true)
	
	var child_scene_path: String = node.scene_file_path

	if child_scene_path != "":
		# --- Instanced subscene ---
		var new_stack: Array = path_stack.duplicate()
		new_stack.append(node.name)

		# Use the old config_file path if it exists, otherwise generate one.
		var rel_json: String = String(old_data.get("config_file", _rel_json_for_stack(new_stack)))
		# The NEW export path
		var abs_json_res_path: String = _abs_json_res(rel_json)

		# Export once per mirrored path
		if not _exported_scene_jsons.has(abs_json_res_path):
			_exported_scene_jsons[abs_json_res_path] = true
			var packed: PackedScene = load(child_scene_path) as PackedScene
			if packed:
				# --- MODIFIED: Load OLD sub-scene data for recursive merge ---
				var old_sub_json_path = JSON_IMPORT_ROOT + rel_json
				var old_sub_data_array = _load_json_array(old_sub_json_path)
				var old_sub_scene_data = {}
				if not old_sub_data_array.is_empty() and old_sub_data_array[0] is Dictionary:
					old_sub_scene_data = old_sub_data_array[0]
				else:
					push_warning("No old sub-scene JSON found at: %s" % old_sub_json_path)
				
				var inst: Node = packed.instantiate()
				# Pass the old sub-scene data into the serializer
				var arr: Array = [_serialize_scene(inst, child_scene_path, new_stack, old_sub_scene_data)]
				inst.free()
				_write_json(abs_json_res_path, arr) # Write to NEW export folder
				print("[Roundtrip] Exported subscene → ", abs_json_res_path)
			else:
				push_warning("Could not load subscene for export: %s" % child_scene_path)

		# 2. Overwrite parent-side reference with live data
		d["name"] = node.name
		d["config_file"] = rel_json
		d["path"] = _rel_tscn_for_stack(new_stack, child_scene_path) # mirrored .tscn path

		# 3. Merge instance-local config (e.g., transform overrides)
		var live_config: Dictionary = _gather_node_config(node)
		var old_config: Dictionary = d.get("config", {}).duplicate(true)
		old_config.merge(live_config, true) # Overwrite old with live
		if not old_config.is_empty():
			d["config"] = old_config
		else:
			d.erase("config")

		# editable flag if set
		if node.get_parent():
			var parent: Node = node.get_parent()
			if parent.has_method("is_editable_instance") and parent.is_editable_instance(node):
				d["editable_children"] = true
			else:
				d.erase("editable_children")

		return d  # no children inlined for instanced scenes

	# --- Non-instanced node (raw class): inline recurse ---
	
	# 2. Overwrite with live data
	d["class"] = node.get_class()
	d["name"] = node.name

	var sc: Script = node.get_script()
	if sc and sc.resource_path != "":
		d["script"] = _trim_res(sc.resource_path)
	else:
		d.erase("script")

	# 3. Merge config
	var live_cfg2: Dictionary = _gather_node_config(node)
	var old_cfg2: Dictionary = d.get("config", {}).duplicate(true)
	old_cfg2.merge(live_cfg2, true) # Overwrite old with live
	if not old_cfg2.is_empty():
		d["config"] = old_cfg2
	else:
		d.erase("config")

	if node.get_parent():
		var parent2: Node = node.get_parent()
		if parent2.has_method("is_editable_instance") and parent2.is_editable_instance(node):
			d["editable_children"] = true
		else:
			d.erase("editable_children")

	# 4. Children (Recursive Merge)
	var nested: Array = []
	var child_stack: Array = path_stack.duplicate()
	child_stack.append(node.name)
	# Iterate over LIVE children
	for c in node.get_children():
		# Find this child's old data within the current 'd' dictionary
		var old_child_data = _find_child_json_by_name(d, c.name)
		nested.append(_serialize_child(c, scene_root, child_stack, old_child_data))
		
	if not nested.is_empty():
		d["children"] = nested
	else:
		d.erase("children")

	return d

# -------------------------------------------------------------------
# ENTRY POINTS (MODIFIED)
# -------------------------------------------------------------------
func _run() -> void:
	var root: Node = get_editor_interface().get_edited_scene_root()
	if root:
		# Use the scene's name to find the matching JSON file
		# e.g. "TheLandOfChocolate" root node -> "TheLandOfChocolate.json"
		_export_single(root, root.name + ".json")
	else:
		push_error("No scene is open. Open a scene or call _export_scene_path/_export_folder from this script.")

# --- MODIFIED: Loads old JSON before exporting ---
func _export_single(scene_root: Node, json_name: String = DEFAULT_CONFIG_FILE) -> void:
	if scene_root == null:
		push_error("Export aborted: scene_root is null.")
		return
		
	# 1. Load the OLD root JSON file from the IMPORT path
	var old_json_path = JSON_IMPORT_ROOT + json_name
	var old_data_array = _load_json_array(old_json_path)
	
	# 2. Find the old data for THIS specific scene
	var old_scene_data := {}
	for item in old_data_array:
		if item is Dictionary and item.get("name", "") == scene_root.name:
			old_scene_data = item
			break
			
	if old_scene_data.is_empty():
		push_warning("No matching old JSON data found for scene: %s at %s" % [scene_root.name, old_json_path])
		push_warning("A new JSON will be created from scratch.")

	# 3. Pass old data to the serializer
	var config_items: Array = []
	config_items.append(_serialize_scene(scene_root, "", [scene_root.name], old_scene_data))
	
	# 4. Write to the NEW EXPORT path
	var new_json_path = JSON_EXPORT_ROOT + json_name
	_write_json(new_json_path, config_items)
	print("[Roundtrip] Exported current scene → ", new_json_path)

# (Optional convenience - MODIFIED)
func _export_scene_path(scene_path: String, json_name: String) -> void:
	var packed: PackedScene = load(scene_path) as PackedScene
	if not packed:
		push_error("Failed to load scene: %s" % scene_path)
		return
	var inst: Node = packed.instantiate()

	# 1. Load OLD JSON
	var old_json_path = JSON_IMPORT_ROOT + json_name
	var old_data_array = _load_json_array(old_json_path)
	var old_scene_data := {}
	for item in old_data_array:
		if item is Dictionary and item.get("name", "") == inst.name:
			old_scene_data = item
			break
	if old_scene_data.is_empty():
		push_warning("No matching old JSON data found for scene: %s at %s" % [inst.name, old_json_path])

	# 2. Serialize with old data
	var arr: Array = [_serialize_scene(inst, scene_path, [inst.name], old_scene_data)]
	inst.free()
	
	# 3. Write to NEW path
	var new_json_path = JSON_EXPORT_ROOT + json_name
	_write_json(new_json_path, arr)
	print("[Roundtrip] Exported %s → %s" % [scene_path, new_json_path])

# (Optional convenience - Unchanged, just a finder)
func _find_scenes_recursive(root_res: String) -> Array:
	var out: Array = []
	var dir: DirAccess = DirAccess.open(root_res)
	if dir == null:
		push_error("Cannot open dir: %s" % root_res)
		return out
	dir.list_dir_begin()
	while true:
		var name: String = dir.get_next()
		if name == "":
			break
		if dir.current_is_dir():
			if name.begins_with("."):
				continue
			out += _find_scenes_recursive(root_res.path_join(name))
		else:
			if name.ends_with(".tscn"):
				out.append(root_res.path_join(name))
	dir.list_dir_end()
	return out
}
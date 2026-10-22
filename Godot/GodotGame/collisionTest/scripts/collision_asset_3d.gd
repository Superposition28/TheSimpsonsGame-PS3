@tool
class_name CollisionAsset3D
extends Node3D
## Original collision bytes -> editor-visible meshes and real Godot static shapes.
## Supported layout is the inspected PS3 Havok 4 build; this is not a Havok runtime.

const HavokReader = preload("res://scripts/tsg_havok_reader.gd")
const CharacterReader = preload("res://scripts/tsg_character_reader.gd")

const PRESETS: Array[Dictionary] = [
	{"name": "Land of Chocolate / zone01", "source": "zone01.hkt.PS3", "visual": "zone01.glb"},
	{"name": "Cake breakaway / prop", "source": "cake.hkt.PS3", "visual": "cake.glb"},
	{"name": "Zone03 / mesh + convex", "source": "zone03.hkt.PS3", "visual": "zone03.glb"},
	{"name": "Shared character / HKO", "source": "shared_character.hko.PS3"},
	{"name": "Bunny / ACS binding gallery", "source": "bunny.acs.PS3", "visual": "bunny.glb", "bbn": "npc_default.bbn.PS3", "model": "bunny.preinstanced"},
	{"name": "Weapon / ACS kind 2", "source": "weapon.acs.PS3", "visual": "baton.glb", "bbn": "player_default.bbn.PS3", "model": "baton.preinstanced"},
	{"name": "Homer / ACS kind 3", "source": "homer.acs.PS3", "bbn": "player_default.bbn.PS3"},
]

signal rebuilt

@export_enum("Custom", "Land of Chocolate / zone01", "Cake breakaway / prop", "Zone03 / mesh + convex", "Shared character / HKO", "Bunny / ACS binding gallery", "Weapon / ACS kind 2", "Homer / ACS kind 3") var sample_preset: int = 0:
	set(value):
		sample_preset = value
		if value > 0 and value <= PRESETS.size():
			var preset: Dictionary = PRESETS[value - 1]
			source_file = "res://samples/raw/" + str(preset["source"])
			visual_file = "res://samples/models/" + str(preset["visual"]) if preset.has("visual") else ""
			bbn_file = "res://samples/raw/" + str(preset["bbn"]) if preset.has("bbn") else ""
			skeleton_model_file = "res://samples/raw/" + str(preset["model"]) if preset.has("model") else ""
@export_file("*.PS3", "*.ps3", "*.hkt", "*.hko", "*.acs") var source_file: String = "":
	set(value):
		source_file = value
		_request_rebuild()
@export_file("*.PS3", "*.ps3") var bbn_file: String = "":
	set(value):
		bbn_file = value
		_request_rebuild()
@export_file("*.preinstanced") var skeleton_model_file: String = "":
	set(value):
		skeleton_model_file = value
		_request_rebuild()
@export_file("*.glb", "*.gltf", "*.tscn") var visual_file: String = "":
	set(value):
		visual_file = value
		_request_rebuild()

@export_group("Preview")
@export var show_visual: bool = true:
	set(value):
		show_visual = value
		_request_rebuild()
@export var show_collision: bool = true:
	set(value):
		show_collision = value
		_request_rebuild()
@export var show_labels: bool = false:
	set(value):
		show_labels = value
		_request_rebuild()
@export var solid_collision: bool = false:
	set(value):
		solid_collision = value
		_request_rebuild()
@export var apply_body_transforms: bool = true:
	set(value):
		apply_body_transforms = value
		_request_rebuild()
@export_enum("Stored XYZ", "Reflect Z", "Reflect X") var coordinate_mode: int = 0:
	set(value):
		coordinate_mode = value
		_request_rebuild()
@export_range(0.001, 100.0, 0.001) var unit_scale: float = 1.0:
	set(value):
		unit_scale = maxf(value, 0.001)
		_request_rebuild()
@export var build_physics: bool = true:
	set(value):
		build_physics = value
		_request_rebuild()
@export var triangle_backfaces: bool = true:
	set(value):
		triangle_backfaces = value
		_request_rebuild()

@export_group("Actions")
@export_tool_button("Rebuild collision preview") var rebuild_action: Callable = rebuild
@export_file("*.tscn") var bake_path: String = "res://generated/selection.tscn"
@export_tool_button("Bake meshes and physics to scene") var bake_action: Callable = bake_scene
@export_multiline var status: String = "Choose a collision file or run tools/prepare_samples.py."

var report: Dictionary = {}
var preview_bounds: AABB = AABB()
var _has_bounds: bool = false
var _queued: bool = false
var _building: bool = false
var _generated: Node3D
var _physics_count: int = 0


func _ready() -> void:
	_request_rebuild()


func _request_rebuild() -> void:
	if not is_inside_tree() or _queued or _building:
		return
	_queued = true
	_rebuild_deferred.call_deferred()


func _rebuild_deferred() -> void:
	_queued = false
	if is_inside_tree():
		rebuild()


func rebuild() -> bool:
	if _building:
		return false
	_building = true
	_clear_generated()
	report = {}
	_has_bounds = false
	preview_bounds = AABB()
	_physics_count = 0
	if source_file.is_empty():
		status = "Choose a collision file. Prepare bundled examples with tools/prepare_samples.py."
		_building = false
		rebuilt.emit()
		return false
	var is_acs: bool = source_file.to_lower().contains(".acs")
	if is_acs:
		report = CharacterReader.read_file(source_file, bbn_file, skeleton_model_file)
	else:
		report = HavokReader.read_file(source_file)
	if not bool(report.get("ok", false)):
		status = "Cannot load %s\n%s" % [source_file, report.get("error", "Unknown format error")]
		_building = false
		rebuilt.emit()
		return false
	_generated = Node3D.new()
	_generated.name = "GeneratedCollision"
	_generated.set_meta("tsg_generated", true)
	add_child(_generated)
	if is_acs:
		_build_character()
	else:
		_build_havok()
	_add_visual(is_acs)
	report["physics_shape_count"] = _physics_count
	status = "%s\n%s\nGodot static shapes: %d" % [source_file.get_file(), str(report.get("stats", {})), _physics_count]
	for warning in report.get("warnings", []):
		status += "\n" + str(warning)
	if Engine.is_editor_hint() and is_inside_tree():
		var edited: Node = get_tree().edited_scene_root
		if edited != null:
			_set_owners(_generated, edited)
	_building = false
	rebuilt.emit()
	return true


func _clear_generated() -> void:
	for child in get_children():
		if bool(child.get_meta("tsg_generated", false)):
			remove_child(child)
			child.free()
	_generated = null


func _conversion() -> Basis:
	match coordinate_mode:
		1:
			return Basis.from_scale(Vector3(1, 1, -1))
		2:
			return Basis.from_scale(Vector3(-1, 1, 1))
	return Basis.IDENTITY


func _convert_pose(raw: Transform3D) -> Transform3D:
	var conversion: Basis = _conversion()
	return Transform3D(conversion * raw.basis * conversion.inverse(), conversion * raw.origin * unit_scale)


func _convert_points(raw: PackedVector3Array) -> PackedVector3Array:
	var converted := PackedVector3Array()
	converted.resize(raw.size())
	var conversion: Basis = _conversion()
	for i in raw.size():
		converted[i] = conversion * raw[i] * unit_scale
	return converted


func _build_havok() -> void:
	var shapes: Dictionary = {}
	for shape_info: Dictionary in report.get("shapes", []):
		shapes[int(shape_info["offset"])] = shape_info
	for body_info: Dictionary in report.get("bodies", []):
		var offset: int = int(body_info["shape_offset"])
		if not shapes.has(offset):
			continue
		var raw_pose: Transform3D = body_info.get("transform", Transform3D.IDENTITY)
		var pose: Transform3D = _convert_pose(raw_pose) if apply_body_transforms else Transform3D.IDENTITY
		var shape_info: Dictionary = shapes[offset]
		var physics_shape: Shape3D = _make_shape(shape_info)
		if physics_shape == null:
			continue
		var body := StaticBody3D.new()
		body.name = "Body_%06X" % int(body_info["offset"])
		body.transform = pose
		body.set_meta("source_name", str(body_info.get("name", "")))
		body.set_meta("shape_offset", offset)
		body.set_meta("raw_transform", raw_pose)
		body.set_meta("source_margin", shape_info.get("margin", 0.0))
		_generated.add_child(body)
		_add_shape_nodes(body, physics_shape, shape_info, true)
		if show_labels:
			_add_label(body, str(body_info.get("name", "")).get_slice("|", 0) + " / " + str(shape_info["kind"]), Vector3(0, 0.25, 0))


func _make_shape(info: Dictionary) -> Shape3D:
	match str(info["kind"]):
		"mesh":
			var points: PackedVector3Array = _convert_points(info["vertices"])
			var indices: PackedInt32Array = info["indices"]
			var faces := PackedVector3Array()
			for i in range(0, indices.size(), 3):
				var a: Vector3 = points[indices[i]]
				var b: Vector3 = points[indices[i + 1]]
				var c: Vector3 = points[indices[i + 2]]
				if (b - a).cross(c - a).length_squared() < 1e-14:
					continue
				if _conversion().determinant() < 0:
					faces.append_array(PackedVector3Array([a, c, b]))
				else:
					faces.append_array(PackedVector3Array([a, b, c]))
			if faces.is_empty():
				return null
			var shape := ConcavePolygonShape3D.new()
			shape.backface_collision = triangle_backfaces
			shape.set_faces(faces)
			return shape
		"box":
			var shape := BoxShape3D.new()
			shape.size = Vector3(info["half_extents"]).abs() * unit_scale * 2.0
			return shape
		"sphere":
			var shape := SphereShape3D.new()
			shape.radius = float(info["radius"]) * unit_scale
			return shape
		"convex":
			var shape := ConvexPolygonShape3D.new()
			shape.points = _convert_points(info["vertices"])
			return shape
	return null


func _add_shape_nodes(parent: Node3D, shape: Shape3D, info: Dictionary, physical: bool) -> void:
	if build_physics and physical:
		var collider := CollisionShape3D.new()
		collider.name = "CollisionShape3D"
		collider.shape = shape
		parent.add_child(collider)
		_physics_count += 1
	var display_mesh: Mesh = shape.get_debug_mesh()
	if solid_collision:
		if shape is ConcavePolygonShape3D:
			display_mesh = _triangle_mesh(shape.get_faces())
		elif shape is SphereShape3D:
			var sphere := SphereMesh.new()
			sphere.radius = shape.radius
			sphere.height = shape.radius * 2.0
			display_mesh = sphere
		elif shape is BoxShape3D:
			var box := BoxMesh.new()
			box.size = shape.size
			display_mesh = box
		elif shape is CapsuleShape3D:
			var capsule := CapsuleMesh.new()
			capsule.radius = shape.radius
			capsule.height = shape.height
			display_mesh = capsule
	var preview := MeshInstance3D.new()
	preview.name = "CollisionPreview"
	preview.mesh = display_mesh
	preview.visible = show_collision
	preview.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	var color := Color.from_hsv(float(int(info.get("offset", 0)) % 311) / 311.0, 0.5, 1.0)
	preview.material_override = _material(color, solid_collision)
	parent.add_child(preview)
	_include_bounds(parent.transform * display_mesh.get_aabb())


func _triangle_mesh(faces: PackedVector3Array) -> ArrayMesh:
	var surface := SurfaceTool.new()
	surface.begin(Mesh.PRIMITIVE_TRIANGLES)
	for vertex: Vector3 in faces:
		surface.add_vertex(vertex)
	surface.generate_normals()
	return surface.commit()


func _material(color: Color, translucent: bool = false) -> StandardMaterial3D:
	var material := StandardMaterial3D.new()
	material.shading_mode = BaseMaterial3D.SHADING_MODE_UNSHADED
	material.cull_mode = BaseMaterial3D.CULL_DISABLED
	material.albedo_color = color
	if translucent:
		material.transparency = BaseMaterial3D.TRANSPARENCY_ALPHA
		material.albedo_color.a = 0.32
	return material


func _build_character() -> void:
	var gallery_count: int = 0
	for record: Dictionary in report.get("records", []):
		var resolved: bool = bool(record.get("attachment_resolved", false))
		var item := Node3D.new()
		item.name = "Record_%03d" % gallery_count
		var local_pose: Transform3D = record.get("local_transform", Transform3D.IDENTITY)
		if resolved:
			var bone_pose: Transform3D = record["bone_transform"]
			item.transform = _convert_pose(bone_pose * local_pose)
		else:
			# A separated diagnostic gallery: never invent bone poses at model origin.
			item.position = Vector3(float(gallery_count % 3) * 4.0, 2.0, float(gallery_count / 3) * 4.0)
		_generated.add_child(item)
		item.set_meta("record", record)
		var params: PackedFloat32Array = record.get("parameters", PackedFloat32Array())
		var kind: int = int(record.get("kind", 0))
		if kind == 1 and not params.is_empty():
			var sphere := SphereShape3D.new()
			sphere.radius = params[0] * unit_scale
			# Sphere semantics remain inferred. Diagnostic ACS records never become blockers.
			_add_shape_nodes(item, sphere, {"offset": int(record["offset"]), "kind": "candidate sphere"}, false)
		elif (kind == 2 or kind == 3) and params.size() >= 2 and params[0] > 0.0 and params[1] > 0.0:
			var capsule := CapsuleShape3D.new()
			var r: float = minf(params[0], params[1]) * unit_scale
			var h: float = maxf(params[0], params[1]) * unit_scale
			capsule.radius = r
			capsule.height = maxf(h, r * 2.0)
			# Two-parameter ACS geometry remains a preview hypothesis and never becomes a blocker.
			_add_shape_nodes(item, capsule, {"offset": int(record["offset"]), "kind": "candidate 2-param"}, false)
		else:
			var marker := MeshInstance3D.new()
			var sphere := SphereMesh.new()
			sphere.radius = 0.06
			sphere.height = 0.12
			marker.mesh = sphere
			marker.material_override = _material(Color.ORANGE)
			marker.visible = show_collision
			item.add_child(marker)
			_include_bounds(AABB(item.position - Vector3.ONE, Vector3.ONE * 2))
		var bone_name: String = str(record.get("bone_name", ""))
		if bone_name.is_empty():
			bone_name = "unresolved %08X" % int(record.get("binding_id", 0))
		var suffix: String = "pose resolved" if resolved else "pose unavailable / gallery"
		_add_label(item, "%s\nkind %d %s\n%s" % [bone_name, kind, str(params), suffix], Vector3(0, -0.9, 0))
		gallery_count += 1
	report["gallery_record_count"] = gallery_count


func _add_visual(character_gallery: bool) -> void:
	if visual_file.is_empty() or not ResourceLoader.exists(visual_file):
		return
	var packed: PackedScene = load(visual_file) as PackedScene
	if packed == null:
		return
	var visual: Node3D = packed.instantiate() as Node3D
	if visual == null:
		return
	visual.name = "VisualModel"
	visual.visible = show_visual
	visual.transform = Transform3D(_conversion().scaled(Vector3.ONE * unit_scale), Vector3.ZERO)
	if character_gallery:
		visual.position.x = -4.0
	_generated.add_child(visual)
	_visual_bounds(visual, visual.transform)


func _visual_bounds(node: Node, relative: Transform3D) -> void:
	if node is MeshInstance3D and node.mesh != null:
		_include_bounds(relative * node.mesh.get_aabb())
	for child in node.get_children():
		if child is Node3D:
			_visual_bounds(child, relative * child.transform)


func _include_bounds(box: AABB) -> void:
	if not _has_bounds:
		preview_bounds = box
		_has_bounds = true
	else:
		preview_bounds = preview_bounds.merge(box)


func _add_label(parent: Node3D, text: String, at: Vector3) -> void:
	var label := Label3D.new()
	label.name = "SourceLabel"
	label.text = text
	label.position = at
	label.font_size = 24
	label.pixel_size = 0.006
	label.billboard = BaseMaterial3D.BILLBOARD_ENABLED
	label.no_depth_test = true
	parent.add_child(label)


func _set_owners(node: Node, scene_owner: Node) -> void:
	node.owner = scene_owner
	if not node.scene_file_path.is_empty():
		return
	for child in node.get_children():
		_set_owners(child, scene_owner)


func bake_scene() -> int:
	if _generated == null:
		return ERR_UNCONFIGURED
	DirAccess.make_dir_recursive_absolute(bake_path.get_base_dir())
	var snapshot: Node = _generated.duplicate()
	snapshot.name = "CollisionAsset"
	snapshot.set_meta("source_file", source_file)
	snapshot.set_meta("research_preview", true)
	for child in snapshot.get_children():
		_set_owners(child, snapshot)
	var packed := PackedScene.new()
	var error: int = packed.pack(snapshot)
	if error == OK:
		error = ResourceSaver.save(packed, bake_path)
	snapshot.free()
	status += "\nBake: %s (%s)" % [bake_path, error_string(error)]
	return error

extends SceneTree
## Integration tests use real copied source samples and Godot's physics server.

const Asset = preload("res://scripts/collision_asset_3d.gd")
const Havok = preload("res://scripts/tsg_havok_reader.gd")
const Character = preload("res://scripts/tsg_character_reader.gd")
const Lab = preload("res://scripts/collision_lab.gd")

var failures: PackedStringArray = PackedStringArray()
var results: Array[Dictionary] = []


func _initialize() -> void:
	_run.call_deferred()


func _check(condition: bool, description: String) -> void:
	if not condition:
		failures.append(description)
		printerr("FAIL: ", description)


func _run() -> void:
	var asset: Node3D = Asset.new()
	root.add_child(asset)
	await process_frame
	for index in Lab.PRESETS.size():
		var preset: Dictionary = Lab.PRESETS[index]
		asset.source_file = "res://samples/raw/" + str(preset["source"])
		asset.visual_file = "res://samples/models/" + str(preset["visual"]) if preset.has("visual") else ""
		asset.bbn_file = "res://samples/raw/" + str(preset["bbn"]) if preset.has("bbn") else ""
		asset.skeleton_model_file = "res://samples/raw/" + str(preset["model"]) if preset.has("model") else ""
		await process_frame
		_check(asset.rebuild(), "Build " + str(preset["name"]))
		var count: int = asset.find_children("*", "CollisionShape3D", true, false).size()
		_check(count == int(asset.report.get("physics_shape_count", -1)), "Tree/physics count agrees: " + str(preset["name"]))
		if str(preset["source"]) == "zone01.hkt.PS3":
			_check(count == 4, "zone01 produces four physical mesh bodies")
			_check(int(asset.report.stats.triangle_count) == 654, "zone01 source triangle count 654")
			await _ray_test(asset)
			await _fall_test(asset)
			asset.coordinate_mode = 1
			await process_frame
			_check(asset.rebuild(), "Reflected-Z rebuild")
			await _ray_test(asset)
			asset.coordinate_mode = 0
			asset.unit_scale = 0.5
			await process_frame
			_check(asset.rebuild(), "Unit-scale rebuild")
			await _ray_test(asset)
			asset.unit_scale = 1.0
			asset.apply_body_transforms = false
			await process_frame
			_check(asset.rebuild(), "Raw shape-space rebuild")
			await _ray_test(asset)
			asset.apply_body_transforms = true
			await process_frame
			asset.rebuild()
		elif str(preset["source"]) == "shared_character.hko.PS3":
			_check(count == 16, "HKO produces16actualGodotshapes")
			_check(int(asset.report.stats.box_count) == 13 and int(asset.report.stats.sphere_count) == 3, "HKO box/sphere types")
		elif str(preset["source"]) == "bunny.acs.PS3":
			_check(count == 0, "Unposed ACS does not generate fabricated blocking shapes")
			_check(int(asset.report.stats.binding_name_count) == 9, "All nine bunny bindings named")
			_check(int(asset.report.stats.model_hierarchy_node_count) == 100, "Bunny HAnim100nodes")
			_check(int(asset.report.stats.attachment_resolved_count) == 0, "Missing bunny poses remain unresolved")
			_check(asset.find_children("SourceLabel", "Label3D", true, false).size() == 9, "Nine labeled bunny gallery records")
		elif str(preset["source"]) == "cake.hkt.PS3":
			await _ray_test(asset)
			await _fall_test(asset)
			_visual_diagnostic(asset)
		elif str(preset["source"]) == "zone03.hkt.PS3":
			_check(int(asset.report.stats.convex_count) == 1, "Convex source decoded")
			_check(asset.find_child("VisualModel", true, false) != null, "Matching zone03 GLB is loaded")
			var convex_count: int = 0
			for node in asset.find_children("*", "CollisionShape3D", true, false):
				if node.shape is ConvexPolygonShape3D:
					convex_count += 1
			_check(convex_count == 1, "ConvexPolygonShape3D instantiated")
			await _ray_test(asset)
		elif str(preset["source"]) == "homer.acs.PS3":
			_check(int(asset.report.stats.binding_name_count) == 9, "Nine Homer bindings named via player_default.bbn")
		asset.bake_path = "res://generated/%s.tscn" % str(preset["source"]).split(".")[0]
		_check(asset.bake_scene() == OK, "Bake " + str(preset["name"]))
		var packed: PackedScene = load(asset.bake_path) as PackedScene
		_check(packed != null, "Reload packed scene " + asset.bake_path)
		if packed != null:
			var restored: Node = packed.instantiate()
			_check(restored.find_children("*", "CollisionShape3D", true, false).size() == count, "Physics survives scene round trip " + str(preset["name"]))
			restored.free()
		results.append({"preset": preset["name"], "physics_shapes": count, "stats": asset.report.get("stats", {})})
		print("PASS preset ", preset["name"], " : ", count, " static shapes")
	_malformed_inputs()
	root.remove_child(asset)
	asset.free()
	await process_frame
	await process_frame
	DirAccess.make_dir_recursive_absolute("res://test-output")
	var out: FileAccess = FileAccess.open("res://test-output/results.json", FileAccess.WRITE)
	out.store_string(JSON.stringify({"engine": Engine.get_version_info(), "presets": results, "failures": failures}, "\t"))
	out.close()
	print("COLLISION_TESTS: ", "PASS" if failures.is_empty() else "FAIL", " (", failures.size(), " failures)")
	quit(0 if failures.is_empty() else 1)


func _triangle(asset: Node3D, horizontal: bool = false) -> PackedVector3Array:
	for info: Dictionary in asset.report.get("shapes", []):
		var pose: Transform3D = Transform3D.IDENTITY
		if asset.apply_body_transforms:
			for body: Dictionary in asset.report["bodies"]:
				if int(body["shape_offset"]) == int(info["offset"]):
					pose = asset._convert_pose(body["transform"])
					break
		var kind: String = str(info["kind"])
		if kind == "mesh":
			var points: PackedVector3Array = asset._convert_points(info["vertices"])
			var indices: PackedInt32Array = info["indices"]
			for i in range(0, indices.size(), 3):
				var a: Vector3 = pose * points[indices[i]]
				var b: Vector3 = pose * points[indices[i + 1]]
				var c: Vector3 = pose * points[indices[i + 2]]
				var cross: Vector3 = (b - a).cross(c - a)
				if cross.length_squared() < 0.01:
					continue
				if horizontal and absf(cross.normalized().dot(Vector3.UP)) < 0.95:
					continue
				return PackedVector3Array([a, b, c])
		elif kind == "box":
			var extents: Vector3 = Vector3(info["half_extents"]).abs() * asset.unit_scale
			var a: Vector3 = pose * Vector3(-extents.x * 0.5, extents.y, -extents.z * 0.5)
			var b: Vector3 = pose * Vector3(0.0, extents.y, extents.z * 0.5)
			var c: Vector3 = pose * Vector3(extents.x * 0.5, extents.y, -extents.z * 0.5)
			var cross: Vector3 = (b - a).cross(c - a)
			if cross.length_squared() < 0.0001:
				continue
			if horizontal and absf(cross.normalized().dot(Vector3.UP)) < 0.95:
				continue
			return PackedVector3Array([a, b, c])
	return PackedVector3Array()


func _ray_test(asset: Node3D) -> void:
	await physics_frame
	await physics_frame
	var triangle: PackedVector3Array = _triangle(asset)
	_check(triangle.size() == 3, "Physical mesh has a nondegenerate test triangle")
	if triangle.size() != 3:
		return
	var center: Vector3 = (triangle[0] + triangle[1] + triangle[2]) / 3.0
	var normal: Vector3 = (triangle[1] - triangle[0]).cross(triangle[2] - triangle[0]).normalized()
	var query := PhysicsRayQueryParameters3D.create(center + normal * 0.08, center - normal * 0.08, 1)
	var hit: Dictionary = asset.get_world_3d().direct_space_state.intersect_ray(query)
	_check(not hit.is_empty(), "Ray intersects generated original mesh: " + asset.source_file)
	if not hit.is_empty():
		_check(Vector3(hit["position"]).distance_to(center) < 0.01, "Ray hit agrees with source triangle position")


func _fall_test(asset: Node3D) -> void:
	var triangle: PackedVector3Array = _triangle(asset, true)
	_check(triangle.size() == 3, "Cake has a horizontal physical surface")
	if triangle.size() != 3:
		return
	var center: Vector3 = (triangle[0] + triangle[1] + triangle[2]) / 3.0
	var sphere := RigidBody3D.new()
	sphere.collision_layer = 2
	sphere.collision_mask = 1
	sphere.continuous_cd = true
	var shape := SphereShape3D.new()
	shape.radius = 0.12
	var collider := CollisionShape3D.new()
	collider.shape = shape
	sphere.add_child(collider)
	root.add_child(sphere)
	sphere.global_position = center + Vector3.UP * 0.8
	for frame in 150:
		await physics_frame
	var height: float = sphere.global_position.y - center.y
	_check(height > 0.04 and height < 0.25, "Falling sphere rests on imported cake collision (height %.5f)" % height)
	_check(absf(sphere.linear_velocity.y) < 0.2, "Falling sphere vertical velocity settles")
	sphere.queue_free()
	await physics_frame


func _visual_diagnostic(asset: Node3D) -> void:
	var visual: Node3D = asset.find_child("VisualModel", true, false) as Node3D
	_check(visual != null, "Matching cake GLB is loaded")
	var collider: CollisionShape3D = asset.find_child("CollisionShape3D", true, false) as CollisionShape3D
	if visual != null and collider != null:
		print("Cake collider AABB: ", collider.shape.get_debug_mesh().get_aabb())
		print("Combined collider/visual AABB: ", asset.preview_bounds)


func _malformed_inputs() -> void:
	DirAccess.make_dir_recursive_absolute("res://test-output")
	var out: FileAccess = FileAccess.open("res://test-output/truncated.PS3", FileAccess.WRITE)
	out.store_buffer(PackedByteArray([1, 2, 3]))
	out.close()
	_check(not bool(Havok.read_file("res://test-output/truncated.PS3")["ok"]), "Truncated Havok rejected")
	_check(not bool(Character.read_file("res://test-output/truncated.PS3")["ok"]), "Truncated ACS rejected")
	_check(not bool(Havok.read_file("res://test-output/absent.PS3")["ok"]), "Missing collision file rejected")
	DirAccess.remove_absolute("res://test-output/truncated.PS3")

extends SceneTree
## Reload every generated scene, verify counts, and exercise Godot physics.

var failures: Array[String] = []
var scene_count: int = 0
var body_count: int = 0
const Builder = preload("res://.variant_tools/physics_builder.gd")


func _initialize() -> void:
	_run.call_deferred()


func _check(condition: bool, description: String) -> void:
	if not condition:
		failures.append(description)
		printerr(description)


func _scenes(directory: String) -> Array[String]:
	var result: Array[String] = []
	var dir: DirAccess = DirAccess.open(directory)
	if dir == null:
		return result
	for filename: String in dir.get_files():
		if filename.ends_with(".tscn"):
			result.append(directory.path_join(filename))
	for child: String in dir.get_directories():
		if child not in [".godot", "assets", ".variant_tools"]:
			result.append_array(_scenes(directory.path_join(child)))
	return result


func _run() -> void:
	await _primitive_tests()
	var scenes: Array[String] = _scenes("res://")
	print("VARIANT_PROGRESS 0 %d Validate scenes" % scenes.size())
	for path: String in scenes:
		var scene: PackedScene = load(path) as PackedScene
		_check(scene != null, "Cannot reload scene: " + path)
		if scene == null:
			continue
		var instance: Node = scene.instantiate()
		_check(instance != null, "Cannot instantiate scene: " + path)
		if instance != null:
			instance.free()
		scene_count += 1
		print("VARIANT_PROGRESS %d %d %s" % [scene_count, scenes.size(), path])
	var jobs: Dictionary = JSON.parse_string(FileAccess.get_file_as_string("res://variant_jobs.json"))
	var baked: Dictionary = JSON.parse_string(FileAccess.get_file_as_string("res://variant_bake_results.json"))
	var successful: Dictionary = {}
	for job: Dictionary in baked.get("jobs", []):
		if bool(job.get("ok", false)):
			successful[str(job["uid"])] = job
	var collision_jobs: Array = jobs.get("jobs", [])
	var processed: int = 0
	print("VARIANT_PROGRESS 0 %d Validate collision physics" % collision_jobs.size())
	for job: Dictionary in collision_jobs:
		processed += 1
		if not successful.has(str(job["uid"])):
			print("VARIANT_PROGRESS %d %d %s (skipped)" % [processed, collision_jobs.size(), job["uid"]])
			continue
		var scene: PackedScene = load(str(job["output"])) as PackedScene
		_check(scene != null, "Cannot reload baked collision " + str(job["uid"]))
		if scene == null:
			continue
		var instance: Node3D = scene.instantiate() as Node3D
		var colliders: Array[Node] = instance.find_children("*", "CollisionShape3D", true, false)
		_check(colliders.size() == int(successful[str(job["uid"])]["physics_shapes"]), "Baked body count changed: " + str(job["uid"]))
		body_count += colliders.size()
		root.add_child(instance)
		# World-space tests also cover a rotated, translated owner placement.
		instance.transform = Transform3D(Basis(Vector3.UP, 0.37), Vector3(23, 7, -19))
		await physics_frame
		await physics_frame
		await _physical_test(instance, colliders, str(job["uid"]))
		root.remove_child(instance)
		instance.free()
		await physics_frame
		print("VARIANT_PROGRESS %d %d %s" % [processed, collision_jobs.size(), job["uid"]])
	var output: FileAccess = FileAccess.open("res://variant_validation.json", FileAccess.WRITE)
	output.store_string(JSON.stringify({"failures": failures, "scenes": scene_count, "physics_bodies": body_count}, "\t"))
	output.close()
	print("VARIANT_VALIDATION: ", scene_count, " scenes, ", body_count, " collision bodies, ", failures.size(), " failures")
	quit(0 if failures.is_empty() else 1)


func _physical_test(instance: Node3D, colliders: Array[Node], uid: String) -> void:
	var tested_ray: bool = false
	var floor_triangle := PackedVector3Array()
	for node: Node in colliders:
		var collider: CollisionShape3D = node as CollisionShape3D
		if not collider.shape is ConcavePolygonShape3D:
			continue
		var faces: PackedVector3Array = collider.shape.get_faces()
		for i: int in range(0, faces.size(), 3):
			var a: Vector3 = collider.global_transform * faces[i]
			var b: Vector3 = collider.global_transform * faces[i + 1]
			var c: Vector3 = collider.global_transform * faces[i + 2]
			var normal: Vector3 = (b - a).cross(c - a).normalized()
			if not tested_ray:
				var center: Vector3 = (a + b + c) / 3.0
				var query := PhysicsRayQueryParameters3D.create(center + normal * 0.04, center - normal * 0.04, 1)
				var hit: Dictionary = instance.get_world_3d().direct_space_state.intersect_ray(query)
				_check(not hit.is_empty(), "Source surface ray misses: " + uid)
				if not hit.is_empty():
					_check(Vector3(hit["position"]).distance_to(center) < 0.01, "Ray position changed: " + uid)
				tested_ray = true
			if absf(normal.dot(Vector3.UP)) > 0.99 and (b - a).cross(c - a).length() > 0.5:
				floor_triangle = PackedVector3Array([a, b, c])
			if tested_ray and not floor_triangle.is_empty():
				break
		if tested_ray and not floor_triangle.is_empty():
			break
	# One known fixture supplies a deterministic falling-body surface. Other
	# environments can have ceilings overlapping a selected triangle.
	if uid == "cfeaf1":
		_check(not floor_triangle.is_empty(), "Known EU terrain has no horizontal test surface")
	if uid == "cfeaf1" and not floor_triangle.is_empty():
		var center: Vector3 = (floor_triangle[0] + floor_triangle[1] + floor_triangle[2]) / 3.0
		var sphere := RigidBody3D.new()
		sphere.collision_layer = 2
		sphere.collision_mask = 1
		sphere.continuous_cd = true
		var collider := CollisionShape3D.new()
		var shape := SphereShape3D.new()
		shape.radius = 0.12
		collider.shape = shape
		sphere.add_child(collider)
		root.add_child(sphere)
		sphere.global_position = center + Vector3.UP * 0.8
		for frame: int in 150:
			await physics_frame
		var height: float = sphere.global_position.y - center.y
		_check(height > 0.04 and height < 0.25, "Falling body did not settle on original terrain")
		_check(absf(sphere.linear_velocity.y) < 0.2, "Falling body did not settle")
		sphere.free()


func _primitive_tests() -> void:
	# Authored synthetic geometry verifies the builder independently of game data.
	var corners := PackedVector3Array()
	for x: float in [-1.0, 1.0]:
		for y: float in [-1.0, 1.0]:
			for z: float in [-1.0, 1.0]:
				corners.append(Vector3(x, y, z))
	var shapes: Array[Dictionary] = [
		{"offset": 1, "kind": "box", "half_extents": Vector3.ONE, "margin": 0.03},
		{"offset": 2, "kind": "sphere", "radius": 1.0},
		{"offset": 3, "kind": "convex", "vertices": corners},
	]
	var bodies: Array[Dictionary] = []
	for i: int in 3:
		bodies.append({"offset": i, "shape_offset": i + 1, "transform": Transform3D(Basis(Vector3.UP, 0.2), Vector3(i * 5.0, 0, 0))})
	var node: Node3D = Builder.build({"shapes": shapes, "bodies": bodies})
	root.add_child(node)
	node.transform = Transform3D(Basis(Vector3.UP, 0.4), Vector3(11, 5, -7))
	await physics_frame
	await physics_frame
	for body: Node in node.get_children():
		var physical: StaticBody3D = body as StaticBody3D
		var start: Vector3 = physical.global_transform * Vector3(0, 2, 0)
		var end: Vector3 = physical.global_transform * Vector3(0, -2, 0)
		var hit: Dictionary = node.get_world_3d().direct_space_state.intersect_ray(PhysicsRayQueryParameters3D.create(start, end, 1))
		_check(not hit.is_empty(), "Synthetic primitive ray misses " + str(physical.name))
		if not hit.is_empty():
			_check(Vector3(hit["position"]).distance_to(physical.global_transform * Vector3.UP) < 0.01, "Synthetic primitive dimension or transform changed")
	root.remove_child(node)
	node.free()
	await physics_frame

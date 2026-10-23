extends RefCounted
## Physics-only conversion of collisionTest's verified shape-building behavior.
## No authored coordinate changes, render-mesh collision, or ACS hypotheses.


static func make_shape(info: Dictionary) -> Shape3D:
	match str(info["kind"]):
		"mesh":
			var points: PackedVector3Array = info["vertices"]
			var indices: PackedInt32Array = info["indices"]
			var faces := PackedVector3Array()
			for i: int in range(0, indices.size(), 3):
				var a: Vector3 = points[indices[i]]
				var b: Vector3 = points[indices[i + 1]]
				var c: Vector3 = points[indices[i + 2]]
				if (b - a).cross(c - a).length_squared() >= 1e-14:
					faces.append_array(PackedVector3Array([a, b, c]))
			if faces.is_empty():
				return null
			var shape := ConcavePolygonShape3D.new()
			shape.backface_collision = true
			shape.set_faces(faces)
			return shape
		"box":
			var shape := BoxShape3D.new()
			shape.size = Vector3(info["half_extents"]).abs() * 2.0
			return shape
		"sphere":
			var shape := SphereShape3D.new()
			shape.radius = float(info["radius"])
			return shape
		"convex":
			var shape := ConvexPolygonShape3D.new()
			shape.points = info["vertices"]
			return shape
	return null


static func build(report: Dictionary) -> Node3D:
	var root := Node3D.new()
	root.name = "OriginalGameCollision"
	root.set_meta("variant_generated_collision", true)
	var shapes: Dictionary[int, Shape3D] = {}
	var margins: Dictionary[int, float] = {}
	for info: Dictionary in report.get("shapes", []):
		var shape: Shape3D = make_shape(info)
		if shape != null:
			shapes[int(info["offset"])] = shape
			margins[int(info["offset"])] = float(info.get("margin", 0.0))
	for body_info: Dictionary in report.get("bodies", []):
		var offset: int = int(body_info["shape_offset"])
		if not shapes.has(offset):
			continue
		var body := StaticBody3D.new()
		body.name = "Body_%06X" % int(body_info["offset"])
		body.transform = body_info.get("transform", Transform3D.IDENTITY)
		body.collision_layer = 1
		body.collision_mask = 0
		body.set_meta("source_name", str(body_info.get("name", "")))
		body.set_meta("source_margin", margins[offset])
		body.set_meta("shape_offset", offset)
		root.add_child(body)
		body.owner = root
		var collider := CollisionShape3D.new()
		collider.name = "CollisionShape3D"
		collider.shape = shapes[offset]
		body.add_child(collider)
		collider.owner = root
	return root

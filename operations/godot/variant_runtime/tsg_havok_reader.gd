@tool
class_name TSGHavokReader extends RefCounted
## Bounded reader for the inspected PS3 Hkx / Havok 4.1 collision layout.
## Values stay in the game's authored coordinates. MOPP bytecode is not executed.

const WRAPPER_SIZE: int = 0x10
const MAX_FILE_BYTES: int = 512 * 1024 * 1024
const MAX_WARNINGS: int = 64

var _data: PackedByteArray = PackedByteArray()
var _stream: StreamPeerBuffer = StreamPeerBuffer.new()
var _error: String = ""
var _warnings: PackedStringArray = PackedStringArray()
var _sections: Array[Dictionary] = []
var _class_names: Dictionary[int, String] = {}
var _objects: Dictionary[int, String] = {}
var _local_fixups: Dictionary[int, int] = {}
var _global_fixups: Dictionary[int, Vector2i] = {}
var _shapes: Array[Dictionary] = []
var _bodies: Array[Dictionary] = []
var _supported_offsets: Dictionary[int, bool] = {}
var _stats: Dictionary = {}
var _base: int = 0
var _data_size: int = 0


static func read_file(path: String) -> Dictionary:
	var reader: RefCounted = new()
	return reader._read(path)


func _read(path: String) -> Dictionary:
	var file: FileAccess = FileAccess.open(path, FileAccess.READ)
	if file == null:
		_fail("Cannot open collision file: %s (error %d)." % [path, FileAccess.get_open_error()])
		return _result()
	var file_size: int = file.get_length()
	if file_size < 0xE0 or file_size > MAX_FILE_BYTES:
		_fail("Unsupported Havok file size: %d bytes." % file_size)
		return _result()
	_data = file.get_buffer(file_size)
	if _data.size() != file_size:
		_fail("Could not read the complete collision file.")
		return _result()
	_stream.data_array = _data
	_stream.big_endian = true
	_stats = {
		"file_size": file_size, "shape_count": 0, "body_count": 0,
		"source_body_count": 0, "unsupported_body_count": 0,
		"mesh_count": 0, "box_count": 0, "sphere_count": 0,
		"convex_count": 0, "vertex_count": 0, "triangle_count": 0,
	}
	if not _read_header() or not _read_class_names() or not _read_fixups():
		return _result()
	for object_offset: int in _objects:
		var object_class: String = _objects[object_offset]
		var shape: Dictionary = {}
		match object_class:
			"EAStorageMeshShape":
				shape = _read_mesh(object_offset)
			"hkBoxShape":
				shape = _read_box(object_offset)
			"hkSphereShape":
				shape = _read_sphere(object_offset)
			"hkConvexVerticesShape":
				shape = _read_convex(object_offset)
		if not _error.is_empty():
			return _result()
		if not shape.is_empty():
			_shapes.append(shape)
			_supported_offsets[object_offset] = true
	for object_offset: int in _objects:
		if _objects[object_offset] == "hkRigidBody":
			_read_body(object_offset)
			if not _error.is_empty():
				return _result()
	_stats["shape_count"] = _shapes.size()
	_stats["body_count"] = _bodies.size()
	if _shapes.is_empty():
		_warn("No supported collision shapes were found in this Havok packfile.")
	return _result()


func _result() -> Dictionary:
	# Failed reads return no partial geometry: callers cannot accidentally preview it.
	var empty_records: Array[Dictionary] = []
	return {
		"ok": _error.is_empty(), "error": _error,
		"shapes": _shapes if _error.is_empty() else empty_records,
		"bodies": _bodies if _error.is_empty() else empty_records,
		"stats": _stats, "warnings": _warnings,
	}


func _fail(message: String) -> void:
	if _error.is_empty():
		_error = message


func _warn(message: String) -> void:
	if _warnings.size() < MAX_WARNINGS:
		_warnings.append(message)
	elif _warnings.size() == MAX_WARNINGS:
		_warnings.append("Further warnings omitted.")


func _range(position: int, size: int, label: String) -> bool:
	if position < 0 or size < 0 or position > _data.size() or size > _data.size() - position:
		_fail("%s exceeds the file bounds (offset 0x%x, size %d)." % [label, position, size])
		return false
	return true


func _data_range(offset: int, size: int, label: String) -> bool:
	if offset < 0 or size < 0 or offset > _data_size or size > _data_size - offset:
		_fail("%s exceeds the data section (offset 0x%x, size %d)." % [label, offset, size])
		return false
	return true


func _u32(position: int) -> int:
	if not _range(position, 4, "UInt32"):
		return 0
	return (int(_data[position]) << 24) | (int(_data[position + 1]) << 16) | (int(_data[position + 2]) << 8) | int(_data[position + 3])


func _word(offset: int) -> int:
	if not _data_range(offset, 4, "Object word"):
		return 0
	return _u32(_base + offset)


func _float(offset: int) -> float:
	if not _data_range(offset, 4, "Object float"):
		return 0.0
	_stream.seek(_base + offset)
	var value: float = _stream.get_float()
	if not is_finite(value):
		_fail("Non-finite float at data offset 0x%x." % offset)
	return value


func _vector(offset: int) -> Vector3:
	return Vector3(_float(offset), _float(offset + 4), _float(offset + 8))


func _ascii(position: int, end: int, label: String) -> String:
	if position < 0 or end < position or not _range(position, end - position, label):
		_fail("Invalid %s string range." % label)
		return ""
	var cursor: int = position
	while cursor < end and _data[cursor] != 0:
		if _data[cursor] < 0x20 or _data[cursor] > 0x7E:
			_fail("Non-ASCII byte in %s at file offset 0x%x." % [label, cursor])
			return ""
		cursor += 1
	if cursor == end:
		_fail("Unterminated %s string." % label)
		return ""
	return _data.slice(position, cursor).get_string_from_ascii()


func _read_header() -> bool:
	var wrapper: PackedByteArray = PackedByteArray([0x48, 0x6B, 0x78, 0x10, 9, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0])
	if _data.slice(0, 16) != wrapper or _u32(0x10) != 0x57E0E057 or _u32(0x14) != 0x10C0C010:
		_fail("Not a supported Hkx-wrapped Havok packfile.")
		return false
	if _u32(0x1C) != 4 or _data.slice(0x20, 0x24) != PackedByteArray([4, 0, 1, 1]):
		_fail("Unsupported Havok version/layout; expected version 4, 32-bit big-endian PS3 layout.")
		return false
	if _u32(0x24) != 3:
		_fail("Unsupported Havok section count; expected three sections.")
		return false
	var version: String = _ascii(0x38, 0x48, "Havok content version")
	if version != "Havok-4.1.0-r1":
		_fail("Unsupported Havok content version: %s." % version)
		return false
	var expected_tags: Array[String] = ["__classnames__", "__data__", "__types__"]
	for section_index: int in range(3):
		var descriptor: int = 0x50 + section_index * 48
		if not _range(descriptor, 48, "Section descriptor"):
			return false
		var tag: String = _ascii(descriptor, descriptor + 19, "section tag")
		if tag != expected_tags[section_index]:
			_fail("Unsupported Havok section ordering: %s." % tag)
			return false
		var start: int = WRAPPER_SIZE + _u32(descriptor + 20)
		var bounds: PackedInt64Array = PackedInt64Array()
		for field_index: int in range(6):
			bounds.append(_u32(descriptor + 24 + field_index * 4))
		for field_index: int in range(1, bounds.size()):
			if bounds[field_index] < bounds[field_index - 1]:
				_fail("Non-monotonic section boundaries in %s." % tag)
				return false
		if start < 0xE0 or not _range(start, bounds[5], "Section %s" % tag):
			_fail("Invalid section start for %s." % tag)
			return false
		_sections.append({"tag": tag, "start": start, "bounds": bounds})
	_base = int(_sections[1]["start"])
	var data_bounds: PackedInt64Array = _sections[1]["bounds"]
	_data_size = data_bounds[0]
	if _u32(0x28) != 1 or _u32(0x2C) != 0 or _u32(0x30) != 0:
		_fail("Unsupported Havok root-object section or offset.")
		return false
	_stats["contents_version"] = version
	_stats["data_section_offset"] = _base
	return _error.is_empty()


func _read_class_names() -> bool:
	var section: Dictionary = _sections[0]
	var bounds: PackedInt64Array = section["bounds"]
	var start: int = int(section["start"])
	var end: int = start + bounds[0]
	var cursor: int = start
	while cursor < end:
		if _data[cursor] == 0xFF and _padding(cursor, end):
			break
		if cursor + 5 > end or _data[cursor + 4] != 9:
			_fail("Malformed Havok class-name record at file offset 0x%x." % cursor)
			return false
		var value: String = _ascii(cursor + 5, end, "class name")
		if not _error.is_empty() or value.is_empty():
			_fail("Empty or malformed Havok class name.")
			return false
		_class_names[cursor + 5 - start] = value
		cursor += 5 + value.length() + 1
	return _error.is_empty()


func _padding(start: int, end: int) -> bool:
	for position: int in range(start, end):
		if _data[position] != 0xFF:
			return false
	return true


func _read_fixups() -> bool:
	var bounds: PackedInt64Array = _sections[1]["bounds"]
	var widths: Array[int] = [8, 12, 12]
	for region: int in range(3):
		var cursor: int = bounds[region]
		var end: int = bounds[region + 1]
		var record_count: int = 0
		while cursor < end:
			if _data[_base + cursor] == 0xFF and _padding(_base + cursor, _base + end):
				break
			if widths[region] > end - cursor:
				_fail("Truncated Havok fixup record in region %d." % region)
				return false
			var source: int = _u32(_base + cursor)
			if not _data_range(source, 4, "Fixup source"):
				return false
			var second: int = _u32(_base + cursor + 4)
			if region == 0:
				if not _data_range(second, 1, "Local fixup target") or _local_fixups.has(source):
					_fail("Duplicate or invalid local fixup at 0x%x." % source)
					return false
				_local_fixups[source] = second
			elif region == 1:
				var target: int = _u32(_base + cursor + 8)
				if second >= _sections.size() or _global_fixups.has(source) or _local_fixups.has(source):
					_fail("Invalid or duplicate global fixup at 0x%x." % source)
					return false
				var target_bounds: PackedInt64Array = _sections[second]["bounds"]
				if target >= target_bounds[0]:
					_fail("Global fixup target outside its section.")
					return false
				_global_fixups[source] = Vector2i(second, target)
			else:
				var class_offset: int = _u32(_base + cursor + 8)
				if second != 0 or not _class_names.has(class_offset) or _objects.has(source):
					_fail("Unknown class or duplicate virtual fixup at 0x%x." % source)
					return false
				_objects[source] = _class_names[class_offset]
			if region < 2 and _word(source) != 0:
				_fail("Expected an unresolved zero pointer at data offset 0x%x." % source)
				return false
			cursor += widths[region]
			record_count += 1
		_stats[["local_fixup_count", "global_fixup_count", "virtual_fixup_count"][region]] = record_count
	if _objects.is_empty():
		_fail("Havok file has no instantiated objects.")
		return false
	_stats["source_object_count"] = _objects.size()
	return _error.is_empty()


func _pointer(source: int, required: bool = true) -> int:
	if _local_fixups.has(source):
		return _local_fixups[source]
	if _global_fixups.has(source):
		var target: Vector2i = _global_fixups[source]
		if target.x == 1:
			return target.y
		if required:
			_fail("Object pointer at 0x%x targets unsupported section %d." % [source, target.x])
		return -1
	if required:
		_fail("Missing pointer fixup at data offset 0x%x." % source)
	return -1


func _read_mesh(offset: int) -> Dictionary:
	if not _data_range(offset, 0xD0, "EAStorageMeshShape header"):
		return {}
	var vertex_count: int = _word(offset + 0x18)
	var triangle_count: int = _word(offset + 0x24)
	var vertex_start: int = _pointer(offset + 0x14)
	var triangle_start: int = _pointer(offset + 0x20)
	if not _error.is_empty():
		return {}
	if vertex_count == 0 or triangle_count == 0:
		_fail("Empty EAStorageMeshShape at data offset 0x%x." % offset)
		return {}
	if not _data_range(vertex_start, vertex_count * 16, "Mesh vertices") or not _data_range(triangle_start, triangle_count * 12, "Mesh triangles"):
		return {}
	var vertices: PackedVector3Array = PackedVector3Array()
	vertices.resize(vertex_count)
	for index: int in range(vertex_count):
		vertices[index] = _vector(vertex_start + index * 16)
		_float(vertex_start + index * 16 + 12)
	var indices: PackedInt32Array = PackedInt32Array()
	indices.resize(triangle_count * 3)
	for index: int in range(triangle_count * 3):
		var vertex_index: int = _word(triangle_start + index * 4)
		if vertex_index >= vertex_count:
			_fail("Mesh triangle index %d exceeds vertex count %d." % [vertex_index, vertex_count])
			return {}
		indices[index] = vertex_index
	var margin: float = _float(offset + 0x38)
	if margin < 0.0:
		_fail("Negative mesh convex margin at data offset 0x%x." % offset)
	_stats["mesh_count"] = int(_stats["mesh_count"]) + 1
	_stats["vertex_count"] = int(_stats["vertex_count"]) + vertex_count
	_stats["triangle_count"] = int(_stats["triangle_count"]) + triangle_count
	return {"offset": offset, "kind": "mesh", "vertices": vertices, "indices": indices, "margin": margin}


func _read_box(offset: int) -> Dictionary:
	if not _data_range(offset, 32, "hkBoxShape"):
		return {}
	var margin: float = _float(offset + 12)
	var extents: Vector3 = _vector(offset + 16)
	_float(offset + 28)
	if margin < 0.0 or extents.x < 0.0 or extents.y < 0.0 or extents.z < 0.0:
		_fail("Negative box half-extent or margin at data offset 0x%x." % offset)
	_stats["box_count"] = int(_stats["box_count"]) + 1
	return {"offset": offset, "kind": "box", "half_extents": extents, "margin": margin}


func _read_sphere(offset: int) -> Dictionary:
	if not _data_range(offset, 16, "hkSphereShape"):
		return {}
	var radius: float = _float(offset + 12)
	if radius <= 0.0:
		_fail("Non-positive sphere radius at data offset 0x%x." % offset)
	_stats["sphere_count"] = int(_stats["sphere_count"]) + 1
	return {"offset": offset, "kind": "sphere", "radius": radius}


func _read_convex(offset: int) -> Dictionary:
	if not _data_range(offset, 0x50, "hkConvexVerticesShape header"):
		return {}
	var margin: float = _float(offset + 12)
	var group_count: int = _word(offset + 0x34)
	var vertex_count: int = _word(offset + 0x3C)
	var plane_count: int = _word(offset + 0x44)
	var vertex_start: int = _pointer(offset + 0x30)
	var plane_start: int = _pointer(offset + 0x40)
	if not _error.is_empty():
		return {}
	if margin < 0.0 or vertex_count == 0 or vertex_count > group_count * 4:
		_fail("Invalid convex shape count or margin at data offset 0x%x." % offset)
		return {}
	if not _data_range(vertex_start, group_count * 48, "Convex packed vertices") or not _data_range(plane_start, plane_count * 16, "Convex planes"):
		return {}
	var vertices: PackedVector3Array = PackedVector3Array()
	vertices.resize(vertex_count)
	for index: int in range(vertex_count):
		var group_offset: int = vertex_start + (index / 4) * 48
		var lane: int = (index % 4) * 4
		vertices[index] = Vector3(_float(group_offset + lane), _float(group_offset + 16 + lane), _float(group_offset + 32 + lane))
	for index: int in range(plane_count * 4):
		_float(plane_start + index * 4)
	_stats["convex_count"] = int(_stats["convex_count"]) + 1
	_stats["vertex_count"] = int(_stats["vertex_count"]) + vertex_count
	return {"offset": offset, "kind": "convex", "vertices": vertices, "margin": margin}


func _read_body(offset: int) -> void:
	_stats["source_body_count"] = int(_stats["source_body_count"]) + 1
	if not _data_range(offset, 0xF0, "hkRigidBody header"):
		return
	var name_start: int = _pointer(offset + 0x10, false)
	var body_name: String = "body_0x%x" % offset
	if name_start >= 0:
		body_name = _ascii(_base + name_start, _base + _data_size, "body name")
	var shape_offset: int = _pointer(offset + 0x1C, false)
	var visited: Dictionary[int, bool] = {}
	while _objects.get(shape_offset, "") == "hkMoppBvTreeShape":
		if visited.has(shape_offset):
			_fail("Cyclic MOPP child-shape pointers for %s." % body_name)
			return
		visited[shape_offset] = true
		if not _data_range(shape_offset, 0x18, "hkMoppBvTreeShape"):
			return
		shape_offset = _pointer(shape_offset + 0x10, false)
	if not _supported_offsets.has(shape_offset):
		_stats["unsupported_body_count"] = int(_stats["unsupported_body_count"]) + 1
		var object_class: String = _objects.get(shape_offset, "missing shape/fixup")
		_warn("Skipped body %s: unsupported shape %s at 0x%x." % [body_name, object_class, shape_offset])
		return
	var x_axis: Vector3 = _vector(offset + 0xB0)
	var y_axis: Vector3 = _vector(offset + 0xC0)
	var z_axis: Vector3 = _vector(offset + 0xD0)
	var position: Vector3 = _vector(offset + 0xE0)
	for padding_offset: int in [0xBC, 0xCC, 0xDC, 0xEC]:
		_float(offset + padding_offset)
	var body_transform: Transform3D = Transform3D(Basis(x_axis, y_axis, z_axis), position)
	_bodies.append({"offset": offset, "name": body_name, "shape_offset": shape_offset, "transform": body_transform})

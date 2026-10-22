@tool
class_name TSGCharacterReader
extends RefCounted
## Bounded reader for the observed PS3 ACS/BBN and RenderWare FrameList layouts.
## Identifiers can resolve without a usable pose. In particular, the inspected
## bunny has 100 HAnim nodes but only two FrameList transforms. Those transforms
## are never substituted for the missing bone poses.

const MAX_AUXILIARY_BYTES: int = 16 * 1024 * 1024
const MAX_MODEL_BYTES: int = 512 * 1024 * 1024
const MAX_ITEMS: int = 100000


static func read_file(path: String, bbn_path: String = "", model_path: String = "") -> Dictionary:
	var records: Array[Dictionary] = []
	var skeleton: Array[Dictionary] = []
	var warnings := PackedStringArray()
	var stats: Dictionary = {
		"record_count": 0, "kind_counts": {1: 0, 2: 0, 3: 0},
		"attachment_resolved_count": 0, "attachment_unresolved_count": 0,
		"binding_name_count": 0, "bbn_alias_count": 0, "bbn_rig_count": 0,
		"model_frame_count": 0, "model_hierarchy_node_count": 0, "model_pose_count": 0,
	}
	var result: Dictionary = {
		"ok": false, "error": "", "records": records, "warnings": warnings,
		"stats": stats, "skeleton": skeleton,
	}
	var loaded: Dictionary = _load_file(path, MAX_AUXILIARY_BYTES)
	if not loaded.ok:
		result.error = loaded.error
		return result
	var data: PackedByteArray = loaded.bytes
	stats["bytes"] = data.size()
	if data.size() < 4 or data[0] != 1 or data[2] != 0 or data[3] != 0:
		result.error = "Unsupported ACS header; expected 01 count 00 00."
		return result
	var offset: int = 4
	for ordinal in range(int(data[1])):
		if not _in_range(data, offset, 76):
			result.error = "ACS record %d has a truncated common header." % ordinal
			return result
		var size: int = _u32(data, offset, true)
		var kind: int = int(data[offset + 72])
		var expected_size: int = 80 if kind == 1 else 84
		if kind < 1 or kind > 3:
			result.error = "ACS record %d has unsupported kind %d." % [ordinal, kind]
			return result
		if size != expected_size or not _in_range(data, offset, size):
			result.error = "ACS record %d has invalid size %d for kind %d." % [ordinal, size, kind]
			return result
		var matrix_values := PackedFloat32Array()
		for component in range(12):
			var value: float = _f32(data, offset + 24 + component * 4, true)
			if not is_finite(value):
				result.error = "ACS record %d contains a non-finite matrix value." % ordinal
				return result
			matrix_values.append(value)
		var parameters := PackedFloat32Array()
		for component in range(1 if kind == 1 else 2):
			var value: float = _f32(data, offset + 76 + component * 4, true)
			if not is_finite(value):
				result.error = "ACS record %d contains a non-finite shape parameter." % ordinal
				return result
			parameters.append(value)
		var kind_padding: int = (int(data[offset + 73]) << 16) | (int(data[offset + 74]) << 8) | int(data[offset + 75])
		if kind_padding != 0:
			_add_warning(warnings, "Nonzero ACS kind padding is retained but has no established meaning.")
		if _u32(data, offset + 16, true) != 0x00730000:
			_add_warning(warnings, "An ACS +0x10 word differs from the observed 0x00730000 value.")
		for parameter in parameters:
			if parameter <= 0.0:
				_add_warning(warnings, "Nonpositive ACS shape parameters require inspection before constructing physics shapes.")
		records.append({
			"offset": offset, "size": size, "identifier": _u32(data, offset + 4, true),
			"binding_id": _u32(data, offset + 8, true), "kind": kind, "parameters": parameters,
			"local_transform": _matrix_transform(matrix_values), "matrix_values": matrix_values,
			"flags": _u32(data, offset + 12, true), "word_10": _u32(data, offset + 16, true),
			"secondary_id": _u32(data, offset + 20, true), "kind_padding": kind_padding,
			"bone_name": "", "bone_index": -1, "bone_transform": Transform3D.IDENTITY,
			"attachment_resolved": false, "binding_alias": "", "rig_hash": -1,
		})
		stats.kind_counts[kind] = int(stats.kind_counts[kind]) + 1
		offset += size
	if offset != data.size():
		result.error = "ACS has %d trailing bytes after its declared records." % (data.size() - offset)
		return result

	var bindings: Dictionary = {"aliases": {}, "rig_names": {}}
	if not bbn_path.is_empty():
		var bbn_file: Dictionary = _load_file(bbn_path, MAX_AUXILIARY_BYTES)
		if bbn_file.ok:
			var parsed_bbn: Dictionary = _parse_bbn(bbn_file.bytes)
			if parsed_bbn.ok:
				bindings = parsed_bbn
				stats.bbn_alias_count = parsed_bbn.aliases.size()
				stats.bbn_rig_count = parsed_bbn.rig_names.size()
			else:
				_add_warning(warnings, "BBN: " + str(parsed_bbn.error))
		else:
			_add_warning(warnings, "BBN: " + str(bbn_file.error))
	else:
		_add_warning(warnings, "No BBN supplied; alias-to-rig name resolution is unavailable.")

	var model: Dictionary = {"nodes": {}, "poses": {}, "frame_count": 0}
	if not model_path.is_empty():
		var model_file: Dictionary = _load_file(model_path, MAX_MODEL_BYTES)
		if model_file.ok:
			var parsed_model: Dictionary = _parse_model(model_file.bytes)
			if parsed_model.ok:
				model = parsed_model
				stats.model_frame_count = model.frame_count
				stats.model_hierarchy_node_count = model.nodes.size()
				stats.model_pose_count = model.poses.size()
			else:
				_add_warning(warnings, "Model: " + str(parsed_model.error))
		else:
			_add_warning(warnings, "Model: " + str(model_file.error))
	else:
		_add_warning(warnings, "No raw preinstanced model supplied; bone poses are unavailable.")

	for record in records:
		var binding_id: int = int(record.binding_id)
		var rig_hash: int = binding_id
		if bindings.aliases.has(binding_id):
			var alias: Dictionary = bindings.aliases[binding_id]
			rig_hash = int(alias.rig_hash)
			record.bone_name = alias.rig_name
			record.binding_alias = alias.name
			stats.binding_name_count = int(stats.binding_name_count) + 1
		elif bindings.rig_names.has(binding_id):
			record.bone_name = bindings.rig_names[binding_id]
			stats.binding_name_count = int(stats.binding_name_count) + 1
		record.rig_hash = rig_hash
		if model.nodes.has(rig_hash):
			record.bone_index = int(model.nodes[rig_hash].index)
		if model.nodes.has(rig_hash) and model.poses.has(rig_hash):
			record.bone_transform = model.poses[rig_hash]
			record.attachment_resolved = true
			stats.attachment_resolved_count = int(stats.attachment_resolved_count) + 1
		else:
			stats.attachment_unresolved_count = int(stats.attachment_unresolved_count) + 1
	for node_id in model.poses:
		if model.nodes.has(node_id):
			skeleton.append({
				"name": str(bindings.rig_names.get(node_id, "0x%08X" % int(node_id))),
				"hash": int(node_id), "index": int(model.nodes[node_id].index),
				"transform": model.poses[node_id],
			})
	if int(stats.attachment_unresolved_count) > 0:
		_add_warning(warnings, "%d ACS attachments have no verified FrameList bone pose; show these as a labeled record gallery, not positioned model collision." % int(stats.attachment_unresolved_count))
	if int(stats.model_hierarchy_node_count) > int(stats.model_frame_count):
		_add_warning(warnings, "The model has %d HAnim nodes but only %d FrameList transforms. HAnim node indices do not index those frames." % [int(stats.model_hierarchy_node_count), int(stats.model_frame_count)])
	_add_warning(warnings, "ACS basis triples are read as columns for preview; handedness, units and the original bone-space convention remain unvalidated.")
	if int(stats.kind_counts[2]) + int(stats.kind_counts[3]) > 0:
		_add_warning(warnings, "ACS kinds 2 and 3 retain two scalar parameters; capsule/cylinder geometry is a preview hypothesis.")
	stats.record_count = records.size()
	result.ok = true
	result.warnings = warnings
	return result


static func _parse_bbn(data: PackedByteArray) -> Dictionary:
	if data.size() < 40:
		return _failure("Truncated header.")
	var alias_count: int = _u32(data, 24, true)
	var rig_count: int = _u32(data, 28, true)
	var rig_offset: int = _u32(data, 32, true)
	var alias_offset: int = _u32(data, 36, true)
	if alias_count > MAX_ITEMS or rig_count > MAX_ITEMS:
		return _failure("Table counts exceed the reader limit.")
	if rig_offset < 40 or alias_offset < 40 or not _in_range(data, rig_offset, rig_count * 8) or not _in_range(data, alias_offset, alias_count * 16):
		return _failure("A name table lies outside the file.")
	var rig: Array[Dictionary] = []
	var rig_names: Dictionary = {}
	for index in range(rig_count):
		var offset: int = rig_offset + index * 8
		var name: Dictionary = _ascii_z(data, _u32(data, offset, true))
		if not name.ok:
			return _failure("Invalid rig name at index %d: %s" % [index, str(name.error)])
		var hash_value: int = _u32(data, offset + 4, true)
		if _sdbm(name.text) != hash_value:
			return _failure("Rig name/hash mismatch at index %d." % index)
		if rig_names.has(hash_value):
			return _failure("Duplicate rig hash; attachment would be ambiguous.")
		rig.append({"name": name.text, "hash": hash_value})
		rig_names[hash_value] = name.text
	var aliases: Dictionary = {}
	for index in range(alias_count):
		var offset: int = alias_offset + index * 16
		var name: Dictionary = _ascii_z(data, _u32(data, offset, true))
		if not name.ok:
			return _failure("Invalid alias name at index %d: %s" % [index, str(name.error)])
		var hash_value: int = _u32(data, offset + 4, true)
		var rig_index: int = _u32(data, offset + 8, true)
		if rig_index >= rig.size() or _sdbm(name.text) != hash_value:
			return _failure("Invalid alias rig index or name/hash at index %d." % index)
		if aliases.has(hash_value):
			return _failure("Duplicate alias hash; attachment would be ambiguous.")
		aliases[hash_value] = {
			"name": name.text, "rig_name": rig[rig_index].name, "rig_hash": rig[rig_index].hash,
			"rig_index": rig_index, "flags": _u32(data, offset + 12, true),
		}
	return {"ok": true, "error": "", "aliases": aliases, "rig_names": rig_names}


static func _parse_model(data: PackedByteArray) -> Dictionary:
	if data.size() < 12 or _u32(data, 0, false) != 0x10:
		return _failure("Expected a little-endian RenderWare CLUMP.")
	var clump_size: int = _u32(data, 4, false)
	if not _in_range(data, 12, clump_size):
		return _failure("CLUMP exceeds the model file.")
	var children: Dictionary = _chunks(data, 12, 12 + clump_size)
	if not children.ok:
		return children
	var frame_list: Dictionary = {}
	for chunk in children.chunks:
		if int(chunk.kind) == 0x0e:
			if not frame_list.is_empty():
				return _failure("Multiple FrameLists are not supported.")
			frame_list = chunk
	if frame_list.is_empty():
		return _failure("No FrameList found.")
	var parts: Dictionary = _chunks(data, int(frame_list.start), int(frame_list.end))
	if not parts.ok:
		return parts
	var frame_struct: Dictionary = {}
	var extensions: Array[Dictionary] = []
	for chunk in parts.chunks:
		if int(chunk.kind) == 1:
			if not frame_struct.is_empty():
				return _failure("Multiple FrameList structures are not supported.")
			frame_struct = chunk
		elif int(chunk.kind) == 3:
			extensions.append(chunk)
	if frame_struct.is_empty() or int(frame_struct.size) < 4:
		return _failure("Missing or truncated FrameList structure.")
	var count: int = _u32(data, int(frame_struct.start), false)
	if count > MAX_ITEMS or 4 + count * 56 != int(frame_struct.size) or extensions.size() != count:
		return _failure("FrameList count/size/extension count mismatch.")
	var transforms: Array[Transform3D] = []
	for index in range(count):
		var offset: int = int(frame_struct.start) + 4 + index * 56
		var values := PackedFloat32Array()
		for component in range(12):
			var value: float = _f32(data, offset + component * 4, false)
			if not is_finite(value):
				return _failure("Non-finite FrameList transform.")
			values.append(value)
		var parent_index: int = _u32(data, offset + 48, false)
		var local_transform: Transform3D = _matrix_transform(values)
		if parent_index == 0xffffffff:
			transforms.append(local_transform)
		elif parent_index < index:
			transforms.append(transforms[parent_index] * local_transform)
		else:
			return _failure("FrameList parent does not precede its child; pose resolution stopped.")
	var nodes: Dictionary = {}
	var frame_ids: Dictionary = {}
	for index in range(count):
		var plugins: Dictionary = _chunks(data, int(extensions[index].start), int(extensions[index].end))
		if not plugins.ok:
			return plugins
		for chunk in plugins.chunks:
			if int(chunk.kind) != 0x11e:
				continue
			if int(chunk.size) < 12:
				return _failure("Truncated HAnim plugin.")
			var start: int = int(chunk.start)
			if _u32(data, start, false) != 0x100:
				return _failure("Unsupported HAnim version.")
			var node_id: int = _u32(data, start + 4, false)
			if frame_ids.has(node_id):
				return _failure("Duplicate per-frame HAnim ID; pose is ambiguous.")
			frame_ids[node_id] = index
			var node_count: int = _u32(data, start + 8, false)
			if node_count == 0:
				continue
			if node_count > MAX_ITEMS or 20 + node_count * 12 != int(chunk.size):
				return _failure("HAnim node count/size mismatch.")
			for node_ordinal in range(node_count):
				var offset: int = start + 20 + node_ordinal * 12
				var hash_value: int = _u32(data, offset, false)
				var bone_index: int = _u32(data, offset + 4, false)
				if nodes.has(hash_value) or bone_index >= node_count:
					return _failure("Duplicate HAnim node ID or out-of-range index.")
				nodes[hash_value] = {"index": bone_index, "flags": _u32(data, offset + 8, false)}
	var poses: Dictionary = {}
	for node_id in nodes:
		if frame_ids.has(node_id):
			poses[node_id] = transforms[int(frame_ids[node_id])]
	return {"ok": true, "error": "", "nodes": nodes, "poses": poses, "frame_count": count}


static func _chunks(data: PackedByteArray, start: int, end: int) -> Dictionary:
	if start < 0 or end < start or end > data.size():
		return _failure("Invalid chunk container bounds.")
	var chunks: Array[Dictionary] = []
	var offset: int = start
	while offset < end:
		if chunks.size() >= MAX_ITEMS or offset > end - 12:
			return _failure("Truncated chunk header or excessive chunk count.")
		var size: int = _u32(data, offset + 4, false)
		if size > end - offset - 12:
			return _failure("Chunk payload exceeds its container.")
		chunks.append({"kind": _u32(data, offset, false), "start": offset + 12, "end": offset + 12 + size, "size": size})
		offset += 12 + size
	return {"ok": true, "error": "", "chunks": chunks}


static func _load_file(path: String, maximum: int) -> Dictionary:
	var file: FileAccess = FileAccess.open(path, FileAccess.READ)
	if file == null:
		return _failure("Cannot open %s (error %d)." % [path, FileAccess.get_open_error()])
	var length: int = file.get_length()
	if length < 0 or length > maximum:
		return _failure("File exceeds the %d-byte reader limit: %s" % [maximum, path])
	var bytes: PackedByteArray = file.get_buffer(length)
	if bytes.size() != length:
		return _failure("Short read: " + path)
	return {"ok": true, "error": "", "bytes": bytes}


static func _ascii_z(data: PackedByteArray, offset: int) -> Dictionary:
	if offset < 0 or offset >= data.size():
		return _failure("String offset is outside the file.")
	var end: int = offset
	while end < data.size() and end - offset <= 1024:
		if data[end] == 0:
			return {"ok": true, "error": "", "text": data.slice(offset, end).get_string_from_ascii()}
		if data[end] < 32 or data[end] > 126:
			return _failure("Name is not printable ASCII.")
		end += 1
	return _failure("Missing string terminator or name exceeds 1024 bytes.")


static func _matrix_transform(values: PackedFloat32Array) -> Transform3D:
	return Transform3D(
		Basis(Vector3(values[0], values[1], values[2]), Vector3(values[3], values[4], values[5]), Vector3(values[6], values[7], values[8])),
		Vector3(values[9], values[10], values[11])
	)


static func _u32(data: PackedByteArray, offset: int, big_endian: bool) -> int:
	if big_endian:
		return (int(data[offset]) << 24) | (int(data[offset + 1]) << 16) | (int(data[offset + 2]) << 8) | int(data[offset + 3])
	return int(data.decode_u32(offset))


static func _f32(data: PackedByteArray, offset: int, big_endian: bool) -> float:
	if not big_endian:
		return data.decode_float(offset)
	var reversed := PackedByteArray([data[offset + 3], data[offset + 2], data[offset + 1], data[offset]])
	return reversed.decode_float(0)


static func _sdbm(value: String) -> int:
	var hash_value: int = 0
	for byte in value.to_lower().to_ascii_buffer():
		hash_value = (hash_value * 65599 + int(byte)) & 0xffffffff
	return hash_value


static func _in_range(data: PackedByteArray, offset: int, count: int) -> bool:
	return offset >= 0 and count >= 0 and offset <= data.size() and count <= data.size() - offset


static func _failure(message: String) -> Dictionary:
	return {"ok": false, "error": message}


static func _add_warning(warnings: PackedStringArray, message: String) -> void:
	if not warnings.has(message):
		warnings.append(message)

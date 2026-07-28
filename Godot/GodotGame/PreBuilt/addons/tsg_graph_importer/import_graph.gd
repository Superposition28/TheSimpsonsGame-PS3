@tool
extends EditorImportPlugin

func _get_importer_name():
	return "tsg.graph.importer"

func _get_visible_name():
	return "TSG NavGraph"

func _get_recognized_extensions():
	return ["graph"]

func _get_save_extension():
	return "res"

func _get_resource_type():
	return "Resource" # Changed from AStar3D to Resource

func _get_preset_count():
	return 1

func _get_preset_name(preset_index):
	return "Default"

func _get_import_options(path, preset_index):
	return []

# Helper for signed 16-bit integers
func _get_16_signed(file: FileAccess) -> int:
	var val = file.get_16()
	if val > 32767:
		val -= 65536
	return val

# --- THE ACTUAL IMPORT LOGIC ---
func _import(source_file, save_path, options, platform_variants, gen_files):
	var file = FileAccess.open(source_file, FileAccess.READ)
	if file == null:
		printerr("Failed to open .graph file: ", source_file)
		return FAILED
		
	# CRITICAL: The PS3 format is strictly Big-Endian
	file.big_endian = true

	var size = file.get_length()
	if size < 0x80:
		printerr("File too small to be a valid .graph")
		return ERR_FILE_CORRUPT

	# Read GUID
	file.seek(0x10)
	var guid_bytes = file.get_buffer(16)
	var guid = guid_bytes.hex_encode().to_upper()
	# Format to match python: 8-4-4-4-12
	var formatted_guid = "{%s-%s-%s-%s-%s}" % [
		guid.substr(0,8), guid.substr(8,4), guid.substr(12,4), guid.substr(16,4), guid.substr(20,12)
	]

	# Read Header Values
	file.seek(0x0C)
	var raw0C = file.get_32()
	var node_count = raw0C >> 16

	file.seek(0x20)
	var node_offset = file.get_32()
	
	# Read layout offsets for heuristics
	file.seek(0x24); var node_end_24 = file.get_32()
	file.seek(0x40); var off40 = file.get_32()
	file.seek(0x44); var off44 = file.get_32()
	file.seek(0x48); var off48 = file.get_32()
	file.seek(0x60); var off60 = file.get_32()
	file.seek(0x64); var count_64 = file.get_32()
	file.seek(0x68); var off68 = file.get_32()
	file.seek(0x70); var off70 = file.get_32()

	if node_offset == 0 or node_offset >= size:
		node_offset = 0

	# Calculate expected node end
	var expected_node_end = node_offset + (node_count * 0x20)
	var node_end = expected_node_end

	var valid_node_end = func(v):
		if v == 0 or v < node_offset or v > size: return false
		return ((v - node_offset) % 0x20) == 0

	if valid_node_end.call(node_end_24):
		node_end = node_end_24
	elif valid_node_end.call(off68):
		node_end = off68

	if node_end > size: node_end = size
	if node_end < node_offset: node_end = node_offset

	# Create our Custom Resource Container
	var nav_graph = TSGNavGraph.new()
	nav_graph.guid = formatted_guid

	# Parse Nodes
	if node_offset != 0 and node_count > 0:
		file.seek(node_offset)
		for i in range(node_count):
			if file.get_position() + 0x20 > size:
				break
				
			var x = file.get_float()
			var y = file.get_float()
			var z = file.get_float()
			var radius = file.get_float()
			var node_id = file.get_16()
			var area_id = _get_16_signed(file)
			var flags = file.get_32()
			
			file.seek(file.get_position() + 8) # Skip unk1 and unk2
			
			nav_graph.nodes.append({
				"pos": Vector3(x, y, z), # Godot is Y-Up natively
				"radius": radius,
				"node_id": node_id,
				"area": area_id,
				"flags": flags
			})

	# Determine where edge block could be (Heuristic)
	var potential_blocks = []
	var check_blocks = [off40, off44, off48, off60 if count_64 > 0 else 0, off68, off70]
	for v in check_blocks:
		if v > 0 and v >= node_end and v < size:
			if not potential_blocks.has(v):
				potential_blocks.append(v)
	
	potential_blocks.sort()
	var next_block_after_nodes = size
	if potential_blocks.size() > 0:
		next_block_after_nodes = potential_blocks[0]

	# Parse Edges
	var off = node_end
	if node_count > 0:
		while off + 16 <= next_block_after_nodes:
			file.seek(off)
			var cost = file.get_float()
			var a = file.get_16()
			var b = file.get_16()
			var tag_c = _get_16_signed(file)
			var tag_d = file.get_16()
			var zero = file.get_32()

			# Validate
			if a >= node_count or b >= node_count or a == b:
				break
			if is_nan(cost) or abs(cost) > 1e6:
				break

			nav_graph.edges.append({
				"a": a,
				"b": b,
				"cost": cost,
				"tag_c": tag_c,
				"tag_d": tag_d
			})
			off += 16

	# Save the Custom Resource
	var filename = save_path + "." + _get_save_extension()
	var err = ResourceSaver.save(nav_graph, filename)
	
	if err != OK:
		printerr("Failed to save imported graph: ", filename)
		return err
		
	return OK

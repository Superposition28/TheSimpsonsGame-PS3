@tool
extends EditorImportPlugin

# --- BASIC IMPORTER INFO ---

func _get_importer_name() -> String:
    return "tsg_graph_importer"

func _get_visible_name() -> String:
    return "The Simpsons Game NavGraph (.graph)"

func _get_recognized_extensions() -> PackedStringArray:
    return ["graph"]

func _get_save_extension() -> String:
    # We'll save as a PackedScene (.tscn)
    return "tscn"

func _get_resource_type() -> String:
    return "PackedScene"

func _get_preset_count() -> int:
    return 1

func _get_preset_name(preset: int) -> String:
    return "Default"

# --- LOW-LEVEL BINARY HELPERS (BIG-ENDIAN, LIKE YOUR BLENDER SCRIPT) ---

static func _u32_be(bytes: PackedByteArray, offset: int) -> int:
    return (int(bytes[offset]) << 24) \
        | (int(bytes[offset + 1]) << 16) \
        | (int(bytes[offset + 2]) << 8) \
        | int(bytes[offset + 3])

static func _f32_be(bytes: PackedByteArray, offset: int) -> float:
    # Godot floats are little-endian; swap bytes first.
    var b := PackedByteArray()
    b.resize(4)
    b[0] = bytes[offset + 3]
    b[1] = bytes[offset + 2]
    b[2] = bytes[offset + 1]
    b[3] = bytes[offset + 0]
    return b.decode_float(0)

static func _tsg_to_godot(x: float, y: float, z: float) -> Vector3:
    # Same mapping you used in Blender: (x, -z, y)
    # This should line up with terrain exported from Blender → GLB → Godot.
    return Vector3(x, -z, y)

static func _parse_graph_points(bytes: PackedByteArray) -> Array:
    var size := bytes.size()
    var points: Array[Vector3] = []

    if size < 0x80:
        push_error("Graph file too small to be valid.")
        return points

    var raw0C := _u32_be(bytes, 0x0C)
    var node_offset := _u32_be(bytes, 0x20)
    var node_count := raw0C >> 16  # upper 16 bits

    if node_offset == 0 or node_offset >= size or node_count <= 0:
        push_warning("No valid node block found in .graph file.")
        return points

    var off := node_offset
    for i in node_count:
        if off + 0x20 > size:
            break

        var x := _f32_be(bytes, off + 0x00)
        var y := _f32_be(bytes, off + 0x04)
        var z := _f32_be(bytes, off + 0x08)
        # radius := _f32_be(bytes, off + 0x0C)      # available if you want it later
        # node_id := _u16_be(...) etc…             # not needed for simple view

        var p := _tsg_to_godot(x, y, z)
        points.append(p)

        off += 0x20

    return points

# --- MAIN IMPORT FUNCTION ---

func _import(
        source_file: String,
        save_path: String,
        options: Dictionary,
        platform_variants: Array,
        gen_files: Array
    ) -> int:

    var bytes := FileAccess.get_file_as_bytes(source_file)
    if bytes.is_empty():
        push_error("Failed to read .graph file: %s" % source_file)
        return ERR_FILE_CANT_OPEN

    var points: Array = _parse_graph_points(bytes)
    if points.is_empty():
        push_warning("No points parsed from .graph: %s" % source_file)

    # Root node that will appear when you instance the imported scene
    var root := Node3D.new()
    root.name = source_file.get_file().get_basename()

    # Store all positions in metadata so you can also grab them as an array if you want
    root.set_meta("graph_points", points)

    # Simple shared debug mesh used for all point instances
    var sphere := SphereMesh.new()
    sphere.radius = 0.3
    sphere.height = 0.6
    sphere.radial_segments = 8
    sphere.rings = 4

    # Create one child per point, with a visible sphere
    for i in points.size():
        var p := points[i] as Vector3

        var node := Node3D.new()
        node.name = "Point_%04d" % i
        node.position = p

        var mi := MeshInstance3D.new()
        mi.mesh = sphere
        mi.name = "Marker"
        node.add_child(mi)

        root.add_child(node)

    # Pack as a scene
    var scene := PackedScene.new()
    if not scene.pack(root):
        push_error("Failed to pack scene from .graph: %s" % source_file)
        return ERR_CANT_CREATE

    var out_path := "%s.%s" % [save_path, _get_save_extension()]
    var err := ResourceSaver.save(out_path, scene)
    if err != OK:
        push_error("Failed to save imported .graph scene: %s" % out_path)
        return err

    return OK

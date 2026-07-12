@tool
extends EditorImportPlugin

func _get_importer_name():
    return "tsg.graph.importer"

func _get_visible_name():
    return "TSG NavGraph"

func _get_recognized_extensions():
    return ["graph"]

func _get_save_extension():
    return "res" # We will save this as a Resource file (.res)

func _get_resource_type():
    return "AStar3D" # Or PackedScene if you want a visual node tree

func _get_preset_count():
    return 1

func _get_preset_name(preset_index):
    return "Default"

func _get_import_options(path, preset_index):
    return []

# --- THE ACTUAL IMPORT LOGIC ---
func _import(source_file, save_path, options, platform_variants, gen_files):
    # 1. Open the file
    var file = FileAccess.open(source_file, FileAccess.READ)
    if file == null:
        printerr("Failed to open .graph file: ", source_file)
        return FAILED
        
    # CRITICAL: The PS3 format is strictly Big-Endian
    file.big_endian = true

    # 2. Check File Size (Sanity Check)
    var size = file.get_length()
    if size < 0x80:
        printerr("File too small to be a valid .graph")
        return ERR_FILE_CORRUPT

    # 3. Read Header Values (Translating your Python script)
    file.seek(0x0C)
    var raw0C = file.get_32()
    var node_count = raw0C >> 16
    var other_count = raw0C & 0xFFFF

    file.seek(0x20)
    var node_offset = file.get_32()
    
    # Optional: Read GUID (Godot handles byte arrays easily)
    file.seek(0x10)
    var guid_bytes = file.get_buffer(16)
    var guid = guid_bytes.hex_encode().to_upper() # e.g. "91CD1F91..."

    # 4. Create the Godot Resource
    var astar = AStar3D.new()
    
    # 5. Parse Nodes
    if node_offset != 0 and node_count > 0:
        file.seek(node_offset)
        for i in range(node_count):
            if file.get_position() + 0x20 > size:
                break
                
            # Read Node Data
            var x = file.get_float()
            var y = file.get_float()
            var z = file.get_float()
            var radius = file.get_float()
            var node_id = file.get_16()
            var area_id = file.get_16() # Assuming signed isn't strictly needed for the ID right now
            var flags = file.get_32()
            
            # Skip unk1 and unk2
            file.seek(file.get_position() + 8) 
            
            # Note on Coordinates: The game is Y-Up and Godot is Y-Up. 
            # You likely just need Vector3(x, y, z). You might need to flip Z to -z depending on handedness.
            var pos = Vector3(x, y, z) 
            
            # Add to AStar (using node_id as the AStar ID)
            astar.add_point(node_id, pos)
            
            # Note: You can store the area_id, radius, and flags inside 
            # a separate Dictionary resource or script attached to this AStar if needed.

    # 6. Parse Edges (Simplified version of your heuristic loop)
    # You will need to implement the 'expected_node_end' logic here to find the edge offset
    # ...
    # var edge_cost = file.get_float()
    # var a = file.get_16()
    # var b = file.get_16()
    # astar.connect_points(a, b, false) # false for unidirectional, check the game logic!

    # 7. Save the final resource
    var filename = save_path + "." + _get_save_extension()
    var err = ResourceSaver.save(astar, filename)
    
    if err != OK:
        printerr("Failed to save imported graph: ", filename)
        return err
        
    return OK
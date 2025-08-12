# RemakeRegistry\Games\TheSimpsonsGame PS3\Godot\_InitScript.gd
@tool
extends SceneTree

func _init():
    print("Building scenes...")
    var file = FileAccess.open("res://scene_config.json", FileAccess.READ)
    if not file:
        printerr("Failed to open scene_config.json")
        return
    var text = file.get_as_text()
    file.close()
    var data = JSON.parse_string(text)
    if typeof(data) != TYPE_ARRAY:
        printerr("Invalid JSON data in scene_config.json")
        return
        
    var dir = DirAccess.open("res://")
    if not dir:
        printerr("Failed to open res:// directory")
        return

    # --- First Pass: Create all base scenes ---
    print("Pass 1: Creating base scenes...")
    for scene_info in data:
        if typeof(scene_info) != TYPE_DICTIONARY or not scene_info.has("path") or not scene_info.has("name"):
            printerr("Skipping invalid scene entry: ", scene_info)
            continue
            
        var scene_path = scene_info["path"]
        var folder = scene_path.get_base_dir()
        var save_path = "res://" + scene_path
        print("Processing scene: ", save_path)

        # Ensure folder exists
        if folder != ".":
            var full_folder_path = "res://" + folder
            print("  Checking directory: ", full_folder_path)
            if not DirAccess.dir_exists_absolute(full_folder_path):
                print("  Directory does not exist. Attempting to create...")
                # Use DirAccess static method for potentially better reliability in tool scripts
                var err = DirAccess.make_dir_recursive_absolute(full_folder_path)
                if err != OK:
                    printerr("  Failed to create directory: ", full_folder_path, " Error code: ", err)
                    continue # Skip this scene if dir creation fails
                else:
                    print("  Successfully created directory: ", full_folder_path)
            else:
                print("  Directory already exists.")
        else:
            print("  Scene is in root directory (res://). No directory creation needed.")

        # Create root node
        var root_node = Node.new() # Use generic Node for now, can be changed later if needed
        root_node.name = scene_info["name"]

        # Assign script if specified
        if scene_info.has("script"):
            var script_path = "res://" + scene_info["script"]
            if FileAccess.file_exists(script_path):
                var script = load(script_path)
                if script:
                    root_node.set_script(script)
                    print("  Script assigned: ", script_path)
                else:
                    printerr("  Failed to load script: ", script_path)
            else:
                printerr("  Script file does not exist: ", script_path)

        # Pack and save scene
        var packed_scene = PackedScene.new()
        var pack_err = packed_scene.pack(root_node)
        if pack_err != OK:
            printerr("  Failed to pack scene: ", scene_path, " Error code: ", pack_err)
            root_node.free() # Clean up node if packing failed
            continue
            
        print("  Checking if scene exists: ", save_path)
        if not FileAccess.file_exists(save_path):
            print("  Scene does not exist. Attempting to save...")
            # Ensure ResourceSaver flags allow overwriting if needed, though it should by default
            var save_err = ResourceSaver.save(packed_scene, save_path)
            if save_err != OK:
                printerr("  Failed to save scene: ", save_path, " Error code: ", save_err)
            else:
                print("  Successfully created base scene: ", save_path)
        else:
            print("  Scene already exists, skipping creation: ", save_path)
            
        # root_node is packed, no need to free manually unless pack fails

    # Mark the end of the initialization process
    print("First pass: Scene creation complete")

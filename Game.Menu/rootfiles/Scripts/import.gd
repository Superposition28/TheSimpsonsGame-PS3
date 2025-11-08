@tool
extends EditorScript

const CONFIG_ROOT := "res://Json/"
const ASSET_ROOT  := "res://assets/"

# Entry file can be overridden with: --config=res://scene_config/Whatever.json
func _get_entry_config_path() -> String:
    var entry := CONFIG_ROOT + "Node4D.json"
    for arg in OS.get_cmdline_args():
        if arg.begins_with("--config="):
            var v := arg.substr(len("--config="), arg.length())
            if v != "":
                entry = v
    return entry

# -----------------------------------------------------------------------------
# JSON IO
# -----------------------------------------------------------------------------
func _load_json_array(abs_path: String) -> Array:
    var f := FileAccess.open(abs_path, FileAccess.READ)
    if not f:
        printerr("FATAL: Cannot open JSON: ", abs_path)
        return []
    var txt := f.get_as_text()
    f.close()
    var data: Variant = JSON.parse_string(txt)
    if typeof(data) == TYPE_ARRAY:
        return data as Array
    printerr("FATAL: Invalid JSON (expected array): ", abs_path)
    return []

# -----------------------------------------------------------------------------
# COLLISION
# -----------------------------------------------------------------------------
enum CollisionPlacement { STATIC_BODY_CHILD, STATIC_BODY_SIBLING, COLLISION_CONTAINER }

func _parse_collision_placement(s: String) -> int:
    match s:
        "StaticBodyChild":    return CollisionPlacement.STATIC_BODY_CHILD
        "StaticBodySibling":  return CollisionPlacement.STATIC_BODY_SIBLING
        "CollisionContainer": return CollisionPlacement.COLLISION_CONTAINER
        _: return CollisionPlacement.STATIC_BODY_CHILD

func _make_shape_for_mesh(mesh: Mesh, shape_type: String) -> Shape3D:
    if not mesh:
        return null
    match shape_type:
        "Convex":
            return mesh.create_convex_shape()
        _, "Trimesh":
            return mesh.create_trimesh_shape()

# Collision containers cache
var _collision_containers := {} # Dictionary: String (parent_path + "|" + name) -> Node3D

# Prefer a parent whose owner == scene_root; fall back upwards until we find one.
func _find_saveable_parent(start: Node, scene_root: Node) -> Node:
    var n := start
    while n and n != scene_root:
        if n.owner == scene_root:
            return n
        n = n.get_parent()
    return scene_root

# NEW: is ancestor helper
func _is_ancestor_of(ancestor: Node, node: Node) -> bool:
    var n := node.get_parent()
    while n:
        if n == ancestor:
            return true
        n = n.get_parent()
    return false

# Compose local transforms up to 'ancestor' (no global_transform off-tree).
func _transform_relative_to(node_3d: Node3D, ancestor: Node) -> Transform3D:
    var t := node_3d.transform
    var p := node_3d.get_parent()
    while p and p != ancestor:
        if p is Node3D:
            t = (p as Node3D).transform * t
        else:
            break
        p = p.get_parent()
    return t

func _get_or_create_container(under_parent: Node, name: String, scene_root: Node) -> Node3D:
    var key := String(under_parent.get_path()) + "|" + name
    if _collision_containers.has(key):
        return _collision_containers[key]
    var c := Node3D.new()
    c.name = name
    under_parent.add_child(c)
    c.owner = scene_root
    _collision_containers[key] = c
    return c

func _place_static_body(
    target_for_placement: Node3D,
    sibling_parent: Node,
    container_parent: Node,
    place: int,
    scene_root: Node
) -> StaticBody3D:
    var desired_parent: Node = null
    match place:
        CollisionPlacement.STATIC_BODY_CHILD:
            desired_parent = target_for_placement
            if desired_parent == null:
                desired_parent = sibling_parent
        CollisionPlacement.STATIC_BODY_SIBLING:
            desired_parent = sibling_parent
        CollisionPlacement.COLLISION_CONTAINER:
            desired_parent = container_parent

    if desired_parent == null:
        desired_parent = sibling_parent if sibling_parent != null else container_parent
    if desired_parent == null:
        desired_parent = scene_root

    # Ensure we parent under something that will actually serialize (owner == scene_root).
    var save_parent := _find_saveable_parent(desired_parent, scene_root)

    # If requested CHILD would put us under a non-saveable target, use a container under the saveable parent.
    if place == CollisionPlacement.STATIC_BODY_CHILD and save_parent != desired_parent:
        save_parent = _get_or_create_container(save_parent, String(target_for_placement.name) + "_Collision", scene_root)

    # If explicit COLLISION_CONTAINER was requested but none provided, make one under the saveable parent.
    if place == CollisionPlacement.COLLISION_CONTAINER and container_parent == null:
        save_parent = _get_or_create_container(save_parent, String(target_for_placement.name) + "_Collision", scene_root)

    var body := StaticBody3D.new()
    save_parent.add_child(body)
    body.owner = scene_root
    return body

func _generate_collision_for_node(
    node_to_scan: Node,
    container_parent: Node3D,
    shape_type: String,
    placement: int,
    scene_root: Node
) -> void:
    var mesh_instance := node_to_scan as MeshInstance3D
    if mesh_instance and mesh_instance.mesh:
        var shape := _make_shape_for_mesh(mesh_instance.mesh, shape_type)
        if not shape:
            printerr("      -> Failed to create ", shape_type, " shape for mesh: ", mesh_instance.name)
        else:
            var static_body := _place_static_body(
                mesh_instance,
                mesh_instance.get_parent(),
                container_parent,
                placement,
                scene_root
            )
            if static_body == null:
                printerr("      -> Failed to place StaticBody for '", mesh_instance.name, "'")
            else:
                var shape_node := CollisionShape3D.new()
                shape_node.shape = shape
                static_body.add_child(shape_node)
                static_body.owner = scene_root
                shape_node.owner = scene_root

                # Body is under some parent; compute the correct relative transform
                var body_parent := static_body.get_parent()

                if body_parent == mesh_instance:
                    # Child-of-mesh case: identity
                    static_body.transform = Transform3D.IDENTITY
                else:
                    # If the body parent is NOT an ancestor (e.g., a sibling container),
                    # compute relative to the container's parent instead.
                    var base_parent := body_parent
                    if not _is_ancestor_of(body_parent, mesh_instance):
                        base_parent = body_parent.get_parent()  # typically ZoneXX_Terrain

                    static_body.transform = _transform_relative_to(mesh_instance, base_parent)

                # Optional legacy correction:
                # static_body.rotate_x(deg_to_rad(90))

                print("      -> Collision (", shape_type, ") for '", mesh_instance.name, "'")

    for child in node_to_scan.get_children():
        _generate_collision_for_node(child, container_parent, shape_type, placement, scene_root)

# -----------------------------------------------------------------------------
# APPLY CONFIG
# -----------------------------------------------------------------------------
func _apply_control_offsets(ctrl: Control, cfg: Dictionary) -> void:
    if cfg.has("layout_mode"):
        # 0 = anchors, 1 = position
        ctrl.layout_mode = int(cfg["layout_mode"])

    if cfg.has("offsets"):
        var o_v: Variant = cfg["offsets"]
        if typeof(o_v) == TYPE_DICTIONARY:
            var o: Dictionary = o_v as Dictionary
            if o.has("offset_left"):   ctrl.offset_left   = float(o["offset_left"])
            if o.has("offset_top"):    ctrl.offset_top    = float(o["offset_top"])
            if o.has("offset_right"):  ctrl.offset_right  = float(o["offset_right"])
            if o.has("offset_bottom"): ctrl.offset_bottom = float(o["offset_bottom"])

func _apply_node_config(node: Node, config_data: Dictionary):
    # Transform
    if config_data.has("transform"):
        var node_3d := node as Node3D
        if node_3d:
            var t: Variant = config_data["transform"]
            if typeof(t) == TYPE_DICTIONARY:
                var td: Dictionary = t as Dictionary
                if td.has("position"):
                    var p: Variant = td["position"]
                    if typeof(p) == TYPE_DICTIONARY:
                        var pd: Dictionary = p as Dictionary
                        node_3d.position = Vector3(
                            float(pd.get("x", 0.0)),
                            float(pd.get("y", 0.0)),
                            float(pd.get("z", 0.0))
                        )
                if td.has("rotation_degrees"):
                    var r: Variant = td["rotation_degrees"]
                    if typeof(r) == TYPE_DICTIONARY:
                        var rd: Dictionary = r as Dictionary
                        node_3d.rotation_degrees = Vector3(
                            float(rd.get("x", 0.0)),
                            float(rd.get("y", 0.0)),
                            float(rd.get("z", 0.0))
                        )
                if td.has("scale"):
                    var s: Variant = td["scale"]
                    if typeof(s) == TYPE_DICTIONARY:
                        var sd: Dictionary = s as Dictionary
                        node_3d.scale = Vector3(
                            float(sd.get("x", 1.0)),
                            float(sd.get("y", 1.0)),
                            float(sd.get("z", 1.0))
                        )
        else:
            printerr("    Warning: 'transform' on non-Node3D: ", node.name)

    # NEW: Control (2D) offsets & layout_mode
    if node is Control:
        _apply_control_offsets(node as Control, config_data)

    # Mesh overrides
    if config_data.has("mesh_overrides"):
        var overrides: Variant = config_data["mesh_overrides"]
        if typeof(overrides) == TYPE_ARRAY:
            var arr: Array = overrides as Array
            print("    Applying mesh overrides for '", node.name, "'")
            for mesh_cfg in arr:
                if mesh_cfg is Dictionary and (mesh_cfg as Dictionary).has("path"):
                    var path_str: String = String((mesh_cfg as Dictionary)["path"])
                    var target: Node = node.find_child(path_str, true, false)
                    if target:
                        if (mesh_cfg as Dictionary).has("visible") and target is Node3D:
                            (target as Node3D).visible = bool((mesh_cfg as Dictionary)["visible"])
                            print("      -> Set visibility for '", path_str, "' = ", (mesh_cfg as Dictionary)["visible"])
                    else:
                        printerr("      -> Could not find mesh path '", path_str, "' under '", node.name, "'")

# -----------------------------------------------------------------------------
# CHILD CREATION
# -----------------------------------------------------------------------------
func _ensure_dir_for(save_path: String) -> void:
    var folder := save_path.get_base_dir()
    if folder != ".":
        DirAccess.make_dir_recursive_absolute("res://" + folder.trim_prefix("res://"))

# Create base .tscn for a "scene" entry (Pass 1)
func _create_base_scene(scene_info: Dictionary) -> void:
    if scene_info.get("type", "") != "scene":
        return
    if not (scene_info.has("name") and scene_info.has("path")):
        return

    var node_class: String = String(scene_info.get("class", "Node"))
    var scene_path: String = "res://" + String(scene_info["path"])
    var overwrite := bool(scene_info.get("overwrite", true))  # <--- new

    # If the scene already exists and overwrite == false, skip creating it.
    if _scene_exists(scene_path) and not overwrite:
        print("    Skipping base scene (exists, overwrite=false): ", scene_path)
        return

    _ensure_dir_for(scene_path)

    var root: Node = ClassDB.instantiate(node_class)
    if not (root is Node):
        printerr("    Failed to instantiate '", node_class, "', falling back to Node.")
        root = Node.new()
    root.name = String(scene_info["name"])

    _attach_script_if_requested(root, scene_info, "scene root")

    var packed: PackedScene = PackedScene.new()
    var pack_err: int = packed.pack(root)
    if pack_err != OK:
        printerr("    Failed to pack scene: ", scene_path, " (", pack_err, ")")
        return

    var err: int = ResourceSaver.save(packed, scene_path)
    if err == OK:
        print("    Created base scene: ", scene_path)
    else:
        printerr("    Failed to save scene: ", scene_path, " (", err, ")")

# Instantiate a child given its descriptor. Returns the created Node, or null.
func _instantiate_child(child_info: Dictionary, scene_root: Node) -> Node:
    var instance: Node = null

    # 1) Nested config trees (ensure they are built first)
    if child_info.has("config_file"):
        var sub_cfg_rel: String = String(child_info["config_file"])
        var sub_cfg_abs: String = CONFIG_ROOT + sub_cfg_rel
        _build_from_config(sub_cfg_abs)  # recursively build child tree before instantiating

    # 2) Scene path (preferred)
    if child_info.has("path"):
        var child_scene_path: String = "res://" + String(child_info["path"])
        var res: Variant = load(child_scene_path)
        if res and (res is PackedScene):
            instance = (res as PackedScene).instantiate()
        if not instance:
            printerr("    Failed to load/instantiate child scene: ", child_scene_path)
            return null

    # 3) Class instantiation (fallback / lights, environment, etc.)
    elif child_info.has("class"):
        var cls: String = String(child_info["class"])
        instance = ClassDB.instantiate(cls)
        if not instance:
            printerr("    Failed to instantiate class: ", cls)
            return null

    # 4) GLB asset via index (no 'path'/'class')
    elif child_info.has("index"):
        var idx: Variant = child_info["index"]
        if typeof(idx) == TYPE_DICTIONARY and (idx as Dictionary).has("index_source_path"):
            var glb_abs: String = ASSET_ROOT + String((idx as Dictionary)["index_source_path"])
            var glb_res: Variant = load(glb_abs)
            if glb_res and (glb_res is PackedScene):
                instance = (glb_res as PackedScene).instantiate()
            else:
                printerr("    Failed to load GLB as scene: ", glb_abs)
                return null
        else:
            printerr("    'index' block missing 'index_source_path' for child: ", child_info.get("name", "<unnamed>"))
            return null
    else:
        printerr("    Skipping child '", child_info.get("name", "<unnamed>"), "' (needs 'path', 'class', or 'index').")
        return null

    # Name
    if child_info.has("name"):
        instance.name = String(child_info["name"])

    # Apply config immediately
    if child_info.has("config") and (child_info["config"] is Dictionary):
        _apply_node_config(instance, child_info["config"] as Dictionary)

    # NEW: attach script if requested on the child instance
    _attach_script_if_requested(instance, child_info, "child")

    # Collision generation removed from here - now happens in _add_children_recursive

    return instance

# Recursively add children defined in "children" arrays
func _add_children_recursive(parent_node: Node, children_data: Array, scene_root: Node, editable_default: bool) -> void:
    for child_info in children_data:
        if typeof(child_info) != TYPE_DICTIONARY:
            printerr("    Skipping invalid child entry: ", child_info)
            continue
        var instance := _instantiate_child(child_info, scene_root)
        if not instance:
            continue
        parent_node.add_child(instance)
        instance.owner = scene_root
        print("      Added child '", instance.name, "' to '", parent_node.name, "'")

        # NEW: per-scene default, with optional per-child override
        var editable := editable_default
        if (child_info as Dictionary).has("editable_children"):
            editable = bool((child_info as Dictionary)["editable_children"])

        # Mark as editable children in the editor (safe to call even if not a sub-scene)
        if editable:
            parent_node.set_editable_instance(instance, true)
            print("      -> Marked '", instance.name, "' as editable")

        # NEW: collision generation happens here (instance is now under scene_root)
        if child_info.has("collision") and (child_info["collision"] is Dictionary):
            var c := child_info["collision"] as Dictionary
            if bool(c.get("enabled", false)):
                var shape_type := String(c.get("ShapeType", "Trimesh"))

                # Always put collisions under a per-asset container (allow override via JSON)
                var container_name := String(c.get("containerName", "Mesh_Collisions"))
                var container := _get_or_create_container(instance, container_name, scene_root)

                # Force container placement so everything lands under the asset's Mesh_Collisions
                var placement := CollisionPlacement.COLLISION_CONTAINER

                _generate_collision_for_node(instance, container, shape_type, placement, scene_root)

        # Nested children (inline) – pass the same default down
        if (child_info as Dictionary).has("children") and ((child_info as Dictionary)["children"] is Array):
            _add_children_recursive(instance, (child_info as Dictionary)["children"] as Array, scene_root, editable_default)

# -----------------------------------------------------------------------------
# BUILD PASSES (for any config file)
# -----------------------------------------------------------------------------
func _pass_create_base_scenes(cfg_items: Array) -> void:
    print("\n--- Pass 1: Creating Base Scenes ---")
    for scene_info in cfg_items:
        if typeof(scene_info) == TYPE_DICTIONARY:
            _create_base_scene(scene_info as Dictionary)
    print("--- Pass 1 Complete ---")

func _pass_populate_scenes(cfg_items: Array) -> void:
    print("\n--- Pass 2: Populating Scenes ---")
    for scene_info in cfg_items:
        if typeof(scene_info) != TYPE_DICTIONARY:
            continue
        if (scene_info as Dictionary).get("type", "") != "scene":
            continue

        var scene_path: String = "res://" + String((scene_info as Dictionary)["path"])
        var overwrite := bool((scene_info as Dictionary).get("overwrite", true))  # <--- new

        # If the scene exists and overwrite=false, do NOT modify/repack it.
        if _scene_exists(scene_path) and not overwrite:
            print("    Skipping population (exists, overwrite=false): ", scene_path)
            continue

        var children_to_add_v: Variant = (scene_info as Dictionary).get("children", [])
        if typeof(children_to_add_v) != TYPE_ARRAY:
            continue
        var children_to_add: Array = children_to_add_v as Array
        if children_to_add.is_empty():
            continue

        var editable_default := bool((scene_info as Dictionary).get("editable_children_default", true))

        print("Processing scene for population: ", scene_path)
        var packed := load(scene_path) as PackedScene
        if not packed:
            printerr("    Failed to load base scene for population: ", scene_path)
            continue

        var root := packed.instantiate()
        _add_children_recursive(root, children_to_add, root, editable_default)

        var updated := PackedScene.new()
        updated.pack(root)
        var save_err := ResourceSaver.save(updated, scene_path)
        if save_err == OK:
            print("    Successfully updated scene: ", scene_path)
        else:
            printerr("    Failed to save updated scene: ", scene_path, " (", save_err, ")")
        root.free()
    print("--- Pass 2 Complete ---")

# Build a single config file (recursively called when encountering 'config_file')
func _build_from_config(abs_path: String) -> void:
    print("\n=== BUILD FROM CONFIG ===\n", abs_path)
    var items_v: Variant = _load_json_array(abs_path)
    if typeof(items_v) != TYPE_ARRAY:
        return
    var items: Array = items_v as Array
    if items.is_empty():
        return
    _pass_create_base_scenes(items)
    _pass_populate_scenes(items)

# -----------------------------------------------------------------------------
# HELPERS
# -----------------------------------------------------------------------------
func _path_to_res(p: String) -> String:
    return p if p.begins_with("res://") else "res://" + p

func _attach_script_if_requested(node: Node, info: Dictionary, context: String) -> void:
    if info.has("script"):
        var s_path := String(info["script"])
        var abs := _path_to_res(s_path)
        var res: Variant = load(abs)
        if res and (res is Script):
            node.set_script(res)
            print("    Attached script '", abs, "' to ", context, " '", node.name, "'")
        else:
            printerr("    Failed to load script '", abs, "' for ", context, " '", node.name, "'")

func _scene_exists(scene_path: String) -> bool:
    return FileAccess.file_exists(scene_path)
# -----------------------------------------------------------------------------
# MAIN
# -----------------------------------------------------------------------------
func _init():
    print("--- Scene Builder Initialized ---")
    var entry_cfg := _get_entry_config_path()
    print("Entry config: ", entry_cfg)
    _build_from_config(entry_cfg)
    print("\n✅✅✅ Scene building finished! ✅✅✅")

    if OS.get_cmdline_args().has("--no-exit"):
        print("\n'--no-exit' flag detected. Godot will remain open.")
    else:
        print("\nWaiting before exiting, to give Godot time to process the scenes...")
        #await create_timer(10.0).timeout
        #quit()

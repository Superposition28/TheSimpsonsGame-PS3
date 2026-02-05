# -----------------------------------------------------------------------------
# IMPORT V0.5
#
# -----------------------------------------------------------------------------

@tool
extends SceneTree

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
# JSON IO & TYPE CONVERSION
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

func _path_to_res(p: String) -> String:
    return p if p.begins_with("res://") else "res://" + p

func _json_to_vec2(d: Dictionary) -> Vector2:
    if d.is_empty(): return Vector2.ZERO
    return Vector2(float(d.get("x", 0.0)), float(d.get("y", 0.0)))

func _json_to_vec3(d: Dictionary) -> Vector3:
    if d.is_empty(): return Vector3.ZERO
    return Vector3(float(d.get("x", 0.0)), float(d.get("y", 0.0)), float(d.get("z", 0.0)))

func _json_to_quat(d: Dictionary) -> Quaternion:
    if d.is_empty(): return Quaternion.IDENTITY
    return Quaternion(
        float(d.get("x", 0.0)),
        float(d.get("y", 0.0)),
        float(d.get("z", 0.0)),
        float(d.get("w", 1.0))
    )

func _json_to_rect2(d: Dictionary) -> Rect2:
    if d.is_empty(): return Rect2()
    var pos := Vector2.ZERO
    var size := Vector2.ZERO
    if d.has("position") and d["position"] is Dictionary:
        pos = _json_to_vec2(d["position"])
    if d.has("size") and d["size"] is Dictionary:
        size = _json_to_vec2(d["size"])
    return Rect2(pos, size)

func _json_to_color(d: Dictionary) -> Color:
    if d.is_empty(): return Color.BLACK
    return Color(
        float(d.get("r", 0.0)),
        float(d.get("g", 0.0)),
        float(d.get("b", 0.0)),
        float(d.get("a", 1.0))
    )

# -----------------------------------------------------------------------------
# RESOURCE GENERATORS (Primitive Shapes)
# -----------------------------------------------------------------------------
func _create_primitive_shape(cfg: Dictionary) -> Shape3D:
    var type := String(cfg.get("type", "Box"))
    var shape: Shape3D = null

    match type:
        "Capsule", "CapsuleShape3D":
            shape = CapsuleShape3D.new()
            if cfg.has("radius"): shape.radius = float(cfg["radius"])
            if cfg.has("height"): shape.height = float(cfg["height"])
        "Box", "BoxShape3D":
            shape = BoxShape3D.new()
            if cfg.has("size"): shape.size = _json_to_vec3(cfg["size"])
        "Sphere", "SphereShape3D":
            shape = SphereShape3D.new()
            if cfg.has("radius"): shape.radius = float(cfg["radius"])
        "Cylinder", "CylinderShape3D":
            shape = CylinderShape3D.new()
            if cfg.has("radius"): shape.radius = float(cfg["radius"])
            if cfg.has("height"): shape.height = float(cfg["height"])
        "SeparationRay", "SeparationRayShape3D":
            shape = SeparationRayShape3D.new()
            if cfg.has("length"): shape.length = float(cfg["length"])
            if cfg.has("slide_on_slope"): shape.slide_on_slope = bool(cfg["slide_on_slope"])
        _:
            printerr("    Unknown shape type: ", type)
    return shape

# -----------------------------------------------------------------------------
# COLLISION GENERATION (Mesh Auto-Gen)
# -----------------------------------------------------------------------------
enum CollisionPlacement { STATIC_BODY_CHILD, STATIC_BODY_SIBLING, COLLISION_CONTAINER }

func _parse_collision_placement(s: String) -> int:
    match s:
        "StaticBodyChild":    return CollisionPlacement.STATIC_BODY_CHILD
        "StaticBodySibling":  return CollisionPlacement.STATIC_BODY_SIBLING
        "CollisionContainer": return CollisionPlacement.COLLISION_CONTAINER
        _: return CollisionPlacement.STATIC_BODY_CHILD

func _transform_relative_to(node_3d: Node3D, ancestor: Node) -> Transform3D:
    var t := node_3d.transform
    var p := node_3d.get_parent()
    while p and p != ancestor:
        if p is Node3D:
            t = p.transform * t
        p = p.get_parent()
    return t

func _add_mesh_collision(mesh_instance: MeshInstance3D, col_info: Dictionary, parent_node: Node) -> void:
    # 1. Create Shape from Mesh
    var shape_type := String(col_info.get("ShapeType", "Trimesh"))
    var shape: Shape3D = null

    if mesh_instance.mesh:
        if shape_type == "Convex": shape = mesh_instance.mesh.create_convex_shape()
        else: shape = mesh_instance.mesh.create_trimesh_shape()

    if not shape:
        printerr("    Failed to create collision shape for: ", mesh_instance.name)
        return

    # 2. Create Body
    var static_body := StaticBody3D.new()
    static_body.name = "Collision"

    var placement_str := String(col_info.get("shapePlacement", "StaticBodyChild"))
    var placement: int = _parse_collision_placement(placement_str)

    # 3. Placement Logic
    match placement:
        CollisionPlacement.STATIC_BODY_CHILD:
            mesh_instance.add_child(static_body)

        CollisionPlacement.STATIC_BODY_SIBLING:
            parent_node.add_child(static_body)
            static_body.transform = mesh_instance.transform

        CollisionPlacement.COLLISION_CONTAINER:
            var container_name := String(col_info.get("containerName", "Collisions"))
            var container_node := parent_node.find_child(container_name, false, false)
            if not container_node:
                container_node = Node3D.new()
                container_node.name = container_name
                parent_node.add_child(container_node)

            container_node.add_child(static_body)
            # Calculate relative transform so collision stays aligned with mesh
            static_body.transform = _transform_relative_to(mesh_instance, container_node.get_parent())

    # 4. Add Shape
    var col_shape := CollisionShape3D.new()
    col_shape.shape = shape
    static_body.add_child(col_shape)
    print("    -> Auto-Collision (", shape_type, ") created for '", mesh_instance.name, "'")

# -----------------------------------------------------------------------------
# CONFIG APPLICATION
# -----------------------------------------------------------------------------

func _apply_node_config(node: Node, cfg: Dictionary) -> void:
    if cfg.is_empty(): return

    # 1. Transforms (Combined V0.4.1 + V0.4.2 logic)
    if node is Node3D and cfg.has("transform"):
        var t: Dictionary = cfg["transform"]
        if t.has("position"): node.position = _json_to_vec3(t["position"])
        if t.has("rotation_degrees"): node.rotation_degrees = _json_to_vec3(t["rotation_degrees"])
        if t.has("scale"): node.scale = _json_to_vec3(t["scale"])

    elif node is Node2D:
        if cfg.has("position"): node.position = _json_to_vec2(cfg["position"])
        if cfg.has("rotation_degrees"): node.rotation_degrees = float(cfg["rotation_degrees"])
        if cfg.has("scale"): node.scale = _json_to_vec2(cfg["scale"])

    elif node is Control:
        if cfg.has("layout_mode"): node.layout_mode = int(cfg["layout_mode"])
        if cfg.has("offsets") and cfg["offsets"] is Dictionary:
            var o: Dictionary = cfg["offsets"]
            node.set_offset(SIDE_LEFT, float(o.get("offset_left", 0.0)))
            node.set_offset(SIDE_TOP, float(o.get("offset_top", 0.0)))
            node.set_offset(SIDE_RIGHT, float(o.get("offset_right", 0.0)))
            node.set_offset(SIDE_BOTTOM, float(o.get("offset_bottom", 0.0)))

    # 2. Physics Layers & Explicit Shapes (V0.4.1 feature)
    if node is CollisionObject3D:
        if cfg.has("collision_layer"): node.collision_layer = int(cfg["collision_layer"])
        if cfg.has("collision_mask"):  node.collision_mask = int(cfg["collision_mask"])

    if cfg.has("shape") and cfg["shape"] is Dictionary:
        var shape_res := _create_primitive_shape(cfg["shape"])
        if shape_res:
            if node is CollisionShape3D: node.shape = shape_res
            elif node is SpringArm3D: node.shape = shape_res

    # 3. Visuals & UI (Combined V0.4.1 + V0.4.2)
    if node is Sprite2D:
        if cfg.has("texture_path"):
            var path := _path_to_res(String(cfg["texture_path"]))
            var tex = load(path)
            if tex: node.texture = tex
        if cfg.has("region_enabled"): node.region_enabled = bool(cfg["region_enabled"])
        if cfg.has("region_rect"): node.region_rect = _json_to_rect2(cfg["region_rect"])

    if node is Label or node is RichTextLabel:
        if cfg.has("text"): node.text = String(cfg["text"])
        if node is Label:
            if cfg.has("horizontal_alignment"): node.horizontal_alignment = int(cfg["horizontal_alignment"])
            if cfg.has("vertical_alignment"): node.vertical_alignment = int(cfg["vertical_alignment"])

    if node is Panel and cfg.has("style_override_panel"):
        var style_data: Dictionary = cfg["style_override_panel"]
        var stylebox := StyleBoxFlat.new()
        if style_data.has("bg_color"): stylebox.bg_color = _json_to_color(style_data["bg_color"])
        node.add_theme_stylebox_override("panel", stylebox)

    if node is ColorRect and cfg.has("color"):
        node.color = _json_to_color(cfg["color"])

    # 4. Overrides: Bones & Mesh Visibility (V0.4.1 feature)
    # Bone Overrides
    if cfg.has("bone_overrides") and cfg["bone_overrides"] is Dictionary:
        var bo: Dictionary = cfg["bone_overrides"]
        var skel_path: String = bo.get("skeleton_path", "")
        var skel_node := node.find_child(skel_path, true, false) as Skeleton3D

        if skel_node and bo.has("poses"):
            var poses: Dictionary = bo["poses"]
            for bone_id in poses:
                var pose_data: Dictionary = poses[bone_id]
                var idx := -1
                if str(bone_id).is_valid_int(): idx = int(bone_id)
                else: idx = skel_node.find_bone(str(bone_id))

                if idx != -1:
                    if pose_data.has("rotation"):
                        skel_node.set_bone_pose_rotation(idx, _json_to_quat(pose_data["rotation"]))
                    if pose_data.has("position"):
                        skel_node.set_bone_pose_position(idx, _json_to_vec3(pose_data["position"]))

    # Mesh Visibility Overrides
    if cfg.has("mesh_overrides") and cfg["mesh_overrides"] is Array:
        for override in cfg["mesh_overrides"]:
            var path: String = override.get("path", "")
            var target := node.find_child(path, true, false)
            if target and target is Node3D and override.has("visible"):
                target.visible = bool(override["visible"])

    # 5. Generic Properties (Scripts)
    if cfg.has("properties") and cfg["properties"] is Dictionary:
        var props: Dictionary = cfg["properties"]
        for key in props:
            node.set(key, props[key])

# -----------------------------------------------------------------------------
# BUILDER (Recursive Single-Pass)
# -----------------------------------------------------------------------------

func _attach_script_if_requested(node: Node, info: Dictionary) -> void:
    if info.has("script"):
        var s_path := String(info["script"])
        var abs_path := _path_to_res(s_path)
        var res = load(abs_path)
        if res and (res is Script):
            node.set_script(res)
            print("    Attached script: ", abs_path)
        else:
            printerr("    Failed to load script: ", abs_path)

func _instantiate_child(child_info: Dictionary, _scene_root: Node) -> Node:
    var instance: Node = null
    var path_ref: String = String(child_info.get("path", ""))

    # 1. Nested Config
    if child_info.has("config_file"):
        var cfg_path := CONFIG_ROOT + String(child_info["config_file"])

        # Build the child scene recursively
        var built_root = _build_from_config(cfg_path)

        # If the config built successfully and we have a target path ending in .tscn...
        if built_root and path_ref.ends_with(".tscn"):
            var abs_path := _path_to_res(path_ref)

            # The build process has already saved the scene to disk.
            # We treat the raw 'built_root' as a temporary artifact and free it.
            built_root.free()

            # Now we load the file we just saved to get a proper "Instance" connection.
            if FileAccess.file_exists(abs_path):
                var res = load(abs_path)
                if res is PackedScene:
                    instance = res.instantiate()
                    print("    -> Instantiated saved scene: ", abs_path)
                else:
                    printerr("    Failed to load built scene: ", abs_path)
            else:
                printerr("    Error: Build appeared successful but file missing: ", abs_path)
        else:
            # Fallback: If no path was provided, use the raw node (won't be a linked instance)
            instance = built_root

    # 2. Scene or Model Path (Preferred)
    # UPDATED: Allows .glb/.gltf files found in 'path' to be loaded directly.
    elif path_ref.ends_with(".tscn") or path_ref.ends_with(".glb") or path_ref.ends_with(".gltf"):
        var abs_path := _path_to_res(path_ref)

        # We build if the file is missing OR if the JSON defines children (Inline Definition).
        var file_missing := not FileAccess.file_exists(abs_path)
        var is_inline_def := child_info.has("children")

        if file_missing or is_inline_def:
            print("    Detected Inline Scene Definition for: ", abs_path)
            # Treat this child_info as the root of a new scene and build it.
            var built_root = _build_scene_from_array([child_info])

            if built_root:
                built_root.free()
                if FileAccess.file_exists(abs_path):
                    instance = load(abs_path).instantiate()
                    print("    -> Generated & Instantiated inline scene: ", abs_path)
        else:
            # Standard behavior: Load existing file
            var res = load(abs_path)
            if res is PackedScene:
                instance = res.instantiate()
            else:
                printerr("    Failed to load scene: ", abs_path)

    # 3. Simple GLB Loading (Fallback / Index style)
    elif child_info.has("index") and child_info["index"].has("index_source_path"):
        var glb_path: String = ASSET_ROOT + String(child_info["index"]["index_source_path"])
        if FileAccess.file_exists(glb_path):
            var res = load(glb_path)
            if res is PackedScene:
                instance = res.instantiate()
            else:
                printerr("    Failed to load GLB: ", glb_path)
        else:
            printerr("    GLB not found: ", glb_path)

    # 4. Class Instantiation
    elif child_info.has("class"):
        var cls_name: String = String(child_info["class"])
        if ClassDB.class_exists(cls_name):
            instance = ClassDB.instantiate(cls_name)
        else:
            printerr("    Class not found: ", cls_name)

    if instance:
        if child_info.has("name"): instance.name = String(child_info["name"])
        _attach_script_if_requested(instance, child_info)

        # Apply merged config
        if child_info.has("config") and child_info["config"] is Dictionary:
            _apply_node_config(instance, child_info["config"])

    # [PATCH] 5. Recursion for Nested Children (Class-based nodes like LOC3D)
    if instance and child_info.has("children") and child_info["children"] is Array:
        for sub_data in child_info["children"]:
            if not (sub_data is Dictionary): continue

            # Recursive call to create the sub-child (e.g. Zone01_Terrain)
            var sub_node := _instantiate_child(sub_data, _scene_root)

            if sub_node:
                instance.add_child(sub_node)

                # Ensure it gets saved to the scene
                if _scene_root:
                    sub_node.owner = _scene_root

                # Apply Collision (Copied from main loop logic)
                if sub_node is MeshInstance3D and sub_data.has("collision"):
                    var c: Dictionary = sub_data["collision"]
                    if c.get("enabled", false):
                        _add_mesh_collision(sub_node, c, instance)

    return instance

func _create_base_scene(scene_info: Dictionary) -> Node:
    var cls := String(scene_info.get("class", "Node"))
    var base: Node
    if ClassDB.class_exists(cls):
        base = ClassDB.instantiate(cls)
    else:
        base = Node.new()

    base.name = scene_info.get("name", "SceneRoot")

    return base

func _save_scene(scene_root: Node, scene_path: String) -> void:
    var packed := PackedScene.new()
    var err := packed.pack(scene_root)
    if err == OK:
        # Ensure directory exists
        var folder := scene_path.get_base_dir()
        if not DirAccess.dir_exists_absolute(folder):
            DirAccess.make_dir_recursive_absolute(folder)

        ResourceSaver.save(packed, scene_path)
        print("  Saved scene: ", scene_path)
    else:
        printerr("  Failed to pack scene: ", scene_path)

func _build_scene_from_array(scene_array: Array) -> Node:
    if scene_array.is_empty(): return null

    var root_info: Dictionary = scene_array[0]
    var scene_path := _path_to_res(root_info.get("path", ""))

    print("\nBuilding Scene: ", scene_path)
    var this_root := _create_base_scene(root_info)

    if not this_root:
        printerr("FATAL: Failed to create root node for: ", scene_path)
        return null

    # Apply Root Config
    if root_info.has("config"):
        _apply_node_config(this_root, root_info["config"])
    _attach_script_if_requested(this_root, root_info)

    # Process Children
    if root_info.has("children"):
        for child_data in root_info["children"]:
            if not (child_data is Dictionary): continue

            var child_node := _instantiate_child(child_data, this_root)
            if child_node:
                this_root.add_child(child_node)
                child_node.owner = this_root # Important for saving

                # Editable Children
                var editable := bool(root_info.get("editable_children_default", false))
                #var editable := bool(root_info.get("editable_children_default", true))
                if child_data.has("editable_children"):
                    editable = bool(child_data["editable_children"])
                if editable:
                    this_root.set_editable_instance(child_node, true)

                # Mesh Collision Generation (V0.4.2 logic integration)
                if child_node is MeshInstance3D and child_data.has("collision"):
                    var c: Dictionary = child_data["collision"]
                    if c.get("enabled", false):
                        _add_mesh_collision(child_node, c, this_root)

    # If path is provided, save it. If not, it might be a nested config returning a node.
    if scene_path != "res://":
        _save_scene(this_root, scene_path)

    return this_root

func _build_from_config(abs_path: String) -> Node:
    var items := _load_json_array(abs_path)
    if items.is_empty(): return null
    return _build_scene_from_array(items)

# -----------------------------------------------------------------------------
# MAIN
# -----------------------------------------------------------------------------
func _init():
    print("--- Importer V0.5 Initialized ---")
    var entry := _get_entry_config_path()
    print("Config Entry: ", entry)

    _build_from_config(entry)

    print("\n✅ Build Finished ✅")

    if OS.get_cmdline_args().has("--no-exit"):
        print("Keeping editor open (--no-exit).")
    else:
        print("Waiting 5s for asset import stabilization...")
        #var timer := get_tree().create_timer(15.0)
        #await timer.timeout
        print("Exiting.")
        #get_tree().quit()

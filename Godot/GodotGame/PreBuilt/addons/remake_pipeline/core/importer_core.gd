@tool
extends RefCounted
class_name RemakeImporterCore

const DEFAULT_CONFIG_ROOT := "res://Json/"
const ASSET_ROOT := "res://assets/"
const ASSET_MAP_PATH := "res://assets/normalized_map.json"

var _asset_map: Dictionary = {}
var _config_root: String = DEFAULT_CONFIG_ROOT

func run_import(entry_config: String = "Node4D.json", config_root: String = "") -> bool:
    _config_root = config_root if config_root != "" else DEFAULT_CONFIG_ROOT
    _load_asset_map()

    var entry := _resolve_config_path(entry_config)
    print("Config Entry: ", entry)

    var built := _build_from_config(entry)
    return built != null

func _resolve_config_path(entry_config: String) -> String:
    if entry_config.begins_with("res://") or entry_config.begins_with("user://"):
        return entry_config
    return _config_root + entry_config

# -----------------------------------------------------------------------------
# ASSET RESOLUTION (Normalized Map & Fallbacks)
# -----------------------------------------------------------------------------

func _load_asset_map() -> void:
    if not FileAccess.file_exists(ASSET_MAP_PATH):
        print("    No asset map found at: ", ASSET_MAP_PATH)
        return

    var data = RemakePipelineUtils.load_json_array(ASSET_MAP_PATH)
    for entry in data:
        if entry is Dictionary and entry.has("uid") and entry.has("new_path"):
            _asset_map[entry["uid"]] = entry["new_path"]

    print("    Loaded ", _asset_map.size(), " asset mappings.")

func _resolve_asset_path(item_info: Dictionary) -> String:
    var path_out := ""

    # 1. Try Mapping (via asset_id)
    if item_info.has("asset") and item_info["asset"] is Dictionary:
        var asset_cfg: Dictionary = item_info["asset"]
        var aid = asset_cfg.get("asset_id", "")
        var a_type = asset_cfg.get("asset_type", "")

        if aid != "" and _asset_map.has(aid):
            var mapped_path: String = _asset_map[aid]

            # If the JSON specifies an asset_type, swap the extension
            if a_type != "":
                mapped_path = mapped_path.get_basename() + "." + a_type

            var full_path = ASSET_ROOT + mapped_path

            if FileAccess.file_exists(full_path):
                return full_path
            else:
                print("    [Map Miss] File not found at swapped path: ", full_path)

        # 2. Try Fallback Paths
        if asset_cfg.has("paths") and asset_cfg["paths"] is Array:
            for p in asset_cfg["paths"]:
                var candidate := ASSET_ROOT + String(p)
                if FileAccess.file_exists(candidate):
                    return candidate

    # 3. Default: Use top-level path property
    var p_ref = String(item_info.get("path", ""))
    if p_ref != "":
        return RemakePipelineUtils.path_to_res(p_ref)

    return ""

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
            if cfg.has("size"): shape.size = RemakePipelineUtils.json_to_vec3(cfg["size"])
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
            static_body.transform = _transform_relative_to(mesh_instance, container_node.get_parent())

    # 4. Add Shape
    var col_shape := CollisionShape3D.new()
    col_shape.shape = shape
    static_body.add_child(col_shape)
    print("    -> Auto-Collision (", shape_type, ") created for '", mesh_instance.name, "'")

# -----------------------------------------------------------------------------
# CONFIG APPLICATION
# -----------------------------------------------------------------------------

func _apply_node_config(node: Node, cfg: Dictionary, node_info: Dictionary = {}) -> void:
    if cfg.is_empty(): return

    # 1. Transforms
    if node is Node3D and cfg.has("transform"):
        var t: Dictionary = cfg["transform"]
        if t.has("position"): node.position = RemakePipelineUtils.json_to_vec3(t["position"])
        if t.has("rotation_degrees"): node.rotation_degrees = RemakePipelineUtils.json_to_vec3(t["rotation_degrees"])
        if t.has("scale"): node.scale = RemakePipelineUtils.json_to_vec3(t["scale"])

    elif node is Node2D:
        if cfg.has("position"): node.position = RemakePipelineUtils.json_to_vec2(cfg["position"])
        if cfg.has("rotation_degrees"): node.rotation_degrees = float(cfg["rotation_degrees"])
        if cfg.has("scale"): node.scale = RemakePipelineUtils.json_to_vec2(cfg["scale"])

    elif node is Control:
        if cfg.has("layout_mode"): node.layout_mode = int(cfg["layout_mode"])
        if cfg.has("offsets") and cfg["offsets"] is Dictionary:
            var o: Dictionary = cfg["offsets"]
            node.set_offset(SIDE_LEFT, float(o.get("offset_left", 0.0)))
            node.set_offset(SIDE_TOP, float(o.get("offset_top", 0.0)))
            node.set_offset(SIDE_RIGHT, float(o.get("offset_right", 0.0)))
            node.set_offset(SIDE_BOTTOM, float(o.get("offset_bottom", 0.0)))

    # 2. Physics Layers & Explicit Shapes
    if node is CollisionObject3D:
        if cfg.has("collision_layer"): node.collision_layer = int(cfg["collision_layer"])
        if cfg.has("collision_mask"):  node.collision_mask = int(cfg["collision_mask"])

    if cfg.has("shape") and cfg["shape"] is Dictionary:
        var shape_res := _create_primitive_shape(cfg["shape"])
        if shape_res:
            if node is CollisionShape3D: node.shape = shape_res
            elif node is SpringArm3D: node.shape = shape_res

    # 3. Visuals & UI
    if node is Sprite2D:
        var tex_path := ""
        if not node_info.is_empty():
            tex_path = _resolve_asset_path(node_info)

        if tex_path == "" and cfg.has("texture_path"):
            tex_path = RemakePipelineUtils.path_to_res(String(cfg["texture_path"]))

        if tex_path != "":
            var tex = load(tex_path)
            if tex: node.texture = tex

        if cfg.has("region_enabled"): node.region_enabled = bool(cfg["region_enabled"])
        if cfg.has("region_rect"): node.region_rect = RemakePipelineUtils.json_to_rect2(cfg["region_rect"])

    if node is Label or node is RichTextLabel:
        if cfg.has("text"): node.text = String(cfg["text"])
        if node is Label:
            if cfg.has("horizontal_alignment"): node.horizontal_alignment = int(cfg["horizontal_alignment"])
            if cfg.has("vertical_alignment"): node.vertical_alignment = int(cfg["vertical_alignment"])

    if node is Panel and cfg.has("style_override_panel"):
        var style_data: Dictionary = cfg["style_override_panel"]
        var stylebox := StyleBoxFlat.new()
        if style_data.has("bg_color"): stylebox.bg_color = RemakePipelineUtils.json_to_color(style_data["bg_color"])
        node.add_theme_stylebox_override("panel", stylebox)

    if node is ColorRect and cfg.has("color"):
        node.color = RemakePipelineUtils.json_to_color(cfg["color"])

    # 4. Overrides: Bones & Mesh Visibility
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
                        skel_node.set_bone_pose_rotation(idx, RemakePipelineUtils.json_to_quat(pose_data["rotation"]))
                    if pose_data.has("position"):
                        skel_node.set_bone_pose_position(idx, RemakePipelineUtils.json_to_vec3(pose_data["position"]))

    if cfg.has("mesh_overrides") and cfg["mesh_overrides"] is Array:
        for override in cfg["mesh_overrides"]:
            var path: String = override.get("path", "")
            var target := node.find_child(path, true, false)
            if target and target is Node3D and override.has("visible"):
                target.visible = bool(override["visible"])

    # 5. Generic Properties
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
        var abs_path := RemakePipelineUtils.path_to_res(s_path)
        var res = load(abs_path)
        if res and (res is Script):
            node.set_script(res)
            print("    Attached script: ", abs_path)
        else:
            printerr("    Failed to load script: ", abs_path)

func _instantiate_child(child_info: Dictionary, _scene_root: Node) -> Node:
    var instance: Node = null
    var path_ref: String = _resolve_asset_path(child_info)
    var children_processed := false

    # 1. Nested Config
    if child_info.has("config_file"):
        var cfg_path := _config_root + String(child_info["config_file"])

        var built_root = _build_from_config(cfg_path)

        if built_root and path_ref.ends_with(".tscn"):
            var abs_path := path_ref

            built_root.free()

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
            instance = built_root

    # 2. Scene or Model Path (Preferred)
    elif path_ref.ends_with(".tscn") or path_ref.ends_with(".glb") or path_ref.ends_with(".gltf"):
        var abs_path := path_ref

        var file_missing := not FileAccess.file_exists(abs_path)
        var is_inline_def := child_info.has("children")

        if file_missing or is_inline_def:
            print("    Detected Inline Scene Definition for: ", abs_path)
            var built_root = _build_scene_from_array([child_info])
            children_processed = true

            if built_root:
                built_root.free()
                if FileAccess.file_exists(abs_path):
                    instance = load(abs_path).instantiate()
                    print("    -> Generated & Instantiated inline scene: ", abs_path)
        else:
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

        if child_info.has("config") and child_info["config"] is Dictionary:
            _apply_node_config(instance, child_info["config"], child_info)

    if instance and child_info.has("children") and child_info["children"] is Array and not children_processed:
        for sub_data in child_info["children"]:
            if not (sub_data is Dictionary): continue

            var sub_node := _instantiate_child(sub_data, _scene_root)

            if sub_node:
                instance.add_child(sub_node)

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
        var folder := scene_path.get_base_dir()
        if not DirAccess.dir_exists_absolute(folder):
            DirAccess.make_dir_recursive_absolute(folder)

        ResourceSaver.save(packed, scene_path)
        print("  Saved scene: ", scene_path)
    else:
        printerr("  Failed to pack scene: ", scene_path)

func _assign_owner(node: Node, target_owner: Node) -> void:
    if node != target_owner and node.owner == null:
        node.owner = target_owner

    for child in node.get_children():
        _assign_owner(child, target_owner)

func _build_scene_from_array(scene_array: Array) -> Node:
    if scene_array.is_empty(): return null

    var root_info: Dictionary = scene_array[0]
    var scene_path := RemakePipelineUtils.path_to_res(root_info.get("path", ""))

    print("\nBuilding Scene: ", scene_path)
    var this_root := _create_base_scene(root_info)

    if not this_root:
        printerr("FATAL: Failed to create root node for: ", scene_path)
        return null

    if root_info.has("config"):
        _apply_node_config(this_root, root_info["config"], root_info)
    _attach_script_if_requested(this_root, root_info)

    if root_info.has("children"):
        for child_data in root_info["children"]:
            if not (child_data is Dictionary): continue

            var child_node := _instantiate_child(child_data, this_root)
            if child_node:
                this_root.add_child(child_node)
                _assign_owner(child_node, this_root)

                var editable := bool(root_info.get("editable_children", false))
                if child_data.has("editable_children"):
                    editable = bool(child_data["editable_children"])
                if editable:
                    this_root.set_editable_instance(child_node, true)

                if child_node is MeshInstance3D and child_data.has("collision"):
                    var c: Dictionary = child_data["collision"]
                    if c.get("enabled", false):
                        _add_mesh_collision(child_node, c, this_root)

    if scene_path != "res://":
        _save_scene(this_root, scene_path)

    return this_root

func _build_from_config(abs_path: String) -> Node:
    var items := RemakePipelineUtils.load_json_array(abs_path)
    if items.is_empty(): return null
    return _build_scene_from_array(items)

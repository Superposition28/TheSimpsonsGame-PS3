@tool
extends RefCounted
class_name RemakeExporterCore

func export_scene(root: Node, save_path: String) -> bool:
    if not root:
        printerr("Export failed: no scene root.")
        return false

    var data: Array = []
    data.append(_serialize_node(root, root))

    return RemakePipelineUtils.save_json_array(save_path, data)

func _serialize_node(node: Node, root: Node) -> Dictionary:
    var dict := {
        "name": node.name,
        "class": node.get_class(),
    }

    if node != root and node.scene_file_path != "":
        dict["type"] = "scene"
        dict["path"] = node.scene_file_path
        _apply_metadata(dict, node)
        _apply_script(dict, node)
        return dict

    var cfg: Dictionary = {}
    _apply_transforms(cfg, node)
    _apply_visuals(cfg, node)
    _apply_ui(cfg, node)
    _apply_physics(cfg, node)

    if not cfg.is_empty():
        dict["config"] = cfg

    _apply_metadata(dict, node)
    _apply_script(dict, node)

    var children_data: Array = []
    for child in node.get_children():
        if not (child is Node):
            continue
        var child_dict := _serialize_node(child, root)
        if not child_dict.is_empty():
            children_data.append(child_dict)

    if not children_data.is_empty():
        dict["children"] = children_data

    return dict

func _apply_transforms(cfg: Dictionary, node: Node) -> void:
    if node is Node3D:
        cfg["transform"] = {
            "position": RemakePipelineUtils.vec3_to_json(node.position),
            "rotation_degrees": RemakePipelineUtils.vec3_to_json(node.rotation_degrees),
            "scale": RemakePipelineUtils.vec3_to_json(node.scale),
        }
    elif node is Node2D:
        cfg["position"] = RemakePipelineUtils.vec2_to_json(node.position)
        cfg["rotation_degrees"] = node.rotation_degrees
        cfg["scale"] = RemakePipelineUtils.vec2_to_json(node.scale)

func _apply_ui(cfg: Dictionary, node: Node) -> void:
    if node is Control:
        cfg["layout_mode"] = node.layout_mode
        cfg["offsets"] = {
            "offset_left": node.get_offset(SIDE_LEFT),
            "offset_top": node.get_offset(SIDE_TOP),
            "offset_right": node.get_offset(SIDE_RIGHT),
            "offset_bottom": node.get_offset(SIDE_BOTTOM),
        }

    if node is Label:
        cfg["text"] = node.text
        cfg["horizontal_alignment"] = node.horizontal_alignment
        cfg["vertical_alignment"] = node.vertical_alignment

    if node is RichTextLabel:
        cfg["text"] = node.text

    if node is ColorRect:
        cfg["color"] = RemakePipelineUtils.color_to_json(node.color)

func _apply_visuals(cfg: Dictionary, node: Node) -> void:
    if node is Sprite2D:
        if node.texture and node.texture.resource_path != "":
            cfg["texture_path"] = node.texture.resource_path
        cfg["region_enabled"] = node.region_enabled
        cfg["region_rect"] = RemakePipelineUtils.rect2_to_json(node.region_rect)

func _apply_physics(cfg: Dictionary, node: Node) -> void:
    if node is CollisionObject3D:
        cfg["collision_layer"] = node.collision_layer
        cfg["collision_mask"] = node.collision_mask

    if node is CollisionShape3D and node.shape:
        cfg["shape"] = _serialize_shape(node.shape)

func _serialize_shape(shape: Shape3D) -> Dictionary:
    if shape is BoxShape3D:
        return {"type": "Box", "size": RemakePipelineUtils.vec3_to_json(shape.size)}
    if shape is CapsuleShape3D:
        return {"type": "Capsule", "radius": shape.radius, "height": shape.height}
    if shape is SphereShape3D:
        return {"type": "Sphere", "radius": shape.radius}
    if shape is CylinderShape3D:
        return {"type": "Cylinder", "radius": shape.radius, "height": shape.height}
    if shape is SeparationRayShape3D:
        return {"type": "SeparationRay", "length": shape.length, "slide_on_slope": shape.slide_on_slope}
    return {}

func _apply_metadata(dict: Dictionary, node: Node) -> void:
    if node.has_meta("asset_id"):
        var asset: Dictionary = {"asset_id": node.get_meta("asset_id")}
        if node.has_meta("asset_type"):
            asset["asset_type"] = node.get_meta("asset_type")
        if node.has_meta("asset_paths"):
            asset["paths"] = node.get_meta("asset_paths")
        dict["asset"] = asset

func _apply_script(dict: Dictionary, node: Node) -> void:
    var s = node.get_script()
    if s and s is Script:
        if s.resource_path != "":
            dict["script"] = s.resource_path

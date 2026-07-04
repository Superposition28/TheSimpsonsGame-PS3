@tool
extends RefCounted
class_name RemakePipelineUtils

static func path_to_res(p: String) -> String:
    if p == "":
        return ""
    return p if p.begins_with("res://") else "res://" + p

static func load_json_array(abs_path: String) -> Array:
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

static func save_json_array(abs_path: String, data: Array) -> bool:
    var f := FileAccess.open(abs_path, FileAccess.WRITE)
    if not f:
        printerr("FATAL: Cannot write JSON: ", abs_path)
        return false
    var txt := JSON.stringify(data, "\t")
    f.store_string(txt)
    f.close()
    return true

static func json_to_vec2(d: Dictionary) -> Vector2:
    if d.is_empty():
        return Vector2.ZERO
    return Vector2(float(d.get("x", 0.0)), float(d.get("y", 0.0)))

static func json_to_vec3(d: Dictionary) -> Vector3:
    if d.is_empty():
        return Vector3.ZERO
    return Vector3(float(d.get("x", 0.0)), float(d.get("y", 0.0)), float(d.get("z", 0.0)))

static func json_to_quat(d: Dictionary) -> Quaternion:
    if d.is_empty():
        return Quaternion.IDENTITY
    return Quaternion(
        float(d.get("x", 0.0)),
        float(d.get("y", 0.0)),
        float(d.get("z", 0.0)),
        float(d.get("w", 1.0))
    )

static func json_to_rect2(d: Dictionary) -> Rect2:
    if d.is_empty():
        return Rect2()
    var pos := Vector2.ZERO
    var size := Vector2.ZERO
    if d.has("position") and d["position"] is Dictionary:
        pos = json_to_vec2(d["position"])
    if d.has("size") and d["size"] is Dictionary:
        size = json_to_vec2(d["size"])
    return Rect2(pos, size)

static func json_to_color(d: Dictionary) -> Color:
    if d.is_empty():
        return Color.BLACK
    return Color(
        float(d.get("r", 0.0)),
        float(d.get("g", 0.0)),
        float(d.get("b", 0.0)),
        float(d.get("a", 1.0))
    )

static func vec2_to_json(v: Vector2) -> Dictionary:
    return {"x": v.x, "y": v.y}

static func vec3_to_json(v: Vector3) -> Dictionary:
    return {"x": v.x, "y": v.y, "z": v.z}

static func quat_to_json(q: Quaternion) -> Dictionary:
    return {"x": q.x, "y": q.y, "z": q.z, "w": q.w}

static func rect2_to_json(r: Rect2) -> Dictionary:
    return {
        "position": vec2_to_json(r.position),
        "size": vec2_to_json(r.size),
    }

static func color_to_json(c: Color) -> Dictionary:
    return {"r": c.r, "g": c.g, "b": c.b, "a": c.a}

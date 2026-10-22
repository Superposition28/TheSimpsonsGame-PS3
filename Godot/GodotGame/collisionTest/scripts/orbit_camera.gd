extends Camera3D

var target: Vector3 = Vector3.ZERO
var distance: float = 18.0
var yaw: float = 0.65
var pitch: float = 0.45


func _ready() -> void:
	_update_camera()


func frame_bounds(bounds: AABB) -> void:
	target = bounds.get_center()
	distance = maxf(bounds.size.length() * 0.85, 3.0)
	far = maxf(distance * 20.0, 2000.0)
	_update_camera()


func _unhandled_input(event: InputEvent) -> void:
	if event is InputEventMouseMotion:
		if Input.is_mouse_button_pressed(MOUSE_BUTTON_RIGHT):
			yaw -= event.relative.x * 0.007
			pitch = clampf(pitch + event.relative.y * 0.007, -1.45, 1.45)
			_update_camera()
		elif Input.is_mouse_button_pressed(MOUSE_BUTTON_MIDDLE):
			target += (-global_basis.x * event.relative.x + global_basis.y * event.relative.y) * distance * 0.0015
			_update_camera()
	if event is InputEventMouseButton and event.pressed:
		if event.button_index == MOUSE_BUTTON_WHEEL_UP:
			distance = maxf(distance * 0.85, 0.1)
		elif event.button_index == MOUSE_BUTTON_WHEEL_DOWN:
			distance *= 1.15
		_update_camera()


func _update_camera() -> void:
	position = target + Vector3(sin(yaw) * cos(pitch), sin(pitch), cos(yaw) * cos(pitch)) * distance
	look_at(target, Vector3.UP)

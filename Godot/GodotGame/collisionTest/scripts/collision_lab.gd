extends Node3D

const PRESETS: Array[Dictionary] = [
	{"name": "Land of Chocolate / zone01", "source": "zone01.hkt.PS3", "visual": "zone01.glb"},
	{"name": "Cake breakaway / prop", "source": "cake.hkt.PS3", "visual": "cake.glb"},
	{"name": "Zone03 / mesh + convex", "source": "zone03.hkt.PS3", "visual": "zone03.glb"},
	{"name": "Shared character / HKO", "source": "shared_character.hko.PS3"},
	{"name": "Bunny / ACS binding gallery", "source": "bunny.acs.PS3", "visual": "bunny.glb", "bbn": "npc_default.bbn.PS3", "model": "bunny.preinstanced"},
	{"name": "Weapon / ACS kind 2", "source": "weapon.acs.PS3", "visual": "baton.glb", "bbn": "player_default.bbn.PS3", "model": "baton.preinstanced"},
	{"name": "Homer / ACS kind 3", "source": "homer.acs.PS3", "bbn": "player_default.bbn.PS3"},
]

@onready var asset: CollisionAsset3D = $CollisionAsset
@onready var camera: Camera3D = $Camera3D
var _status_label: Label
var _file_dialog: FileDialog
var _probe_count: int = 0


func _ready() -> void:
	_build_ui()
	asset.rebuilt.connect(_on_rebuilt)
	_on_rebuilt()


func _unhandled_key_input(event: InputEvent) -> void:
	if event is InputEventKey and event.pressed and not event.echo:
		if event.keycode == KEY_F:
			camera.frame_bounds(asset.preview_bounds)
		elif event.keycode == KEY_SPACE:
			_drop_probe()


func _build_ui() -> void:
	var layer := CanvasLayer.new()
	add_child(layer)
	var panel := PanelContainer.new()
	panel.position = Vector2(12, 12)
	panel.custom_minimum_size = Vector2(660, 0)
	layer.add_child(panel)
	var rows := VBoxContainer.new()
	panel.add_child(rows)
	var title := Label.new()
	title.text = "TSG COLLISION LAB  ·  PS3 research preview"
	title.add_theme_font_size_override("font_size", 20)
	rows.add_child(title)
	var choices := HBoxContainer.new()
	rows.add_child(choices)
	var presets := OptionButton.new()
	for preset in PRESETS:
		presets.add_item(str(preset["name"]))
	presets.item_selected.connect(_select_preset)
	choices.add_child(presets)
	_add_button(choices, "Load original…", _choose_file)
	_add_button(choices, "Frame [F]", func() -> void: camera.frame_bounds(asset.preview_bounds))
	var toggles := HBoxContainer.new()
	rows.add_child(toggles)
	_add_toggle(toggles, "Visual", asset.show_visual, func(value: bool) -> void: asset.show_visual = value)
	_add_toggle(toggles, "Collision", asset.show_collision, func(value: bool) -> void: asset.show_collision = value)
	_add_toggle(toggles, "Solid", asset.solid_collision, func(value: bool) -> void: asset.solid_collision = value)
	_add_toggle(toggles, "Labels", asset.show_labels, func(value: bool) -> void: asset.show_labels = value)
	_add_toggle(toggles, "Body transforms", asset.apply_body_transforms, func(value: bool) -> void: asset.apply_body_transforms = value)
	var actions := HBoxContainer.new()
	rows.add_child(actions)
	var axes := OptionButton.new()
	for text: String in ["Stored XYZ", "Reflect Z", "Reflect X"]:
		axes.add_item(text)
	axes.item_selected.connect(func(index: int) -> void: asset.coordinate_mode = index)
	actions.add_child(axes)
	_add_button(actions, "Drop probe [Space]", _drop_probe)
	_add_button(actions, "Bake .tscn", _bake)
	var help := Label.new()
	help.text = "RMB orbit · MMB pan · Wheel zoom   |   Original units; axis/placement verification remains experimental."
	rows.add_child(help)
	_status_label = Label.new()
	_status_label.custom_minimum_size = Vector2(650, 0)
	_status_label.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	_status_label.add_theme_font_size_override("font_size", 13)
	rows.add_child(_status_label)
	_file_dialog = FileDialog.new()
	_file_dialog.access = FileDialog.ACCESS_FILESYSTEM
	_file_dialog.file_mode = FileDialog.FILE_MODE_OPEN_FILE
	_file_dialog.filters = PackedStringArray(["*.PS3,*.ps3,*.hkt,*.hko,*.acs ; Original collision resources"])
	_file_dialog.file_selected.connect(_load_external)
	layer.add_child(_file_dialog)


func _add_button(parent: Node, text: String, action: Callable) -> void:
	var button := Button.new()
	button.text = text
	button.pressed.connect(action)
	parent.add_child(button)


func _add_toggle(parent: Node, text: String, value: bool, action: Callable) -> void:
	var toggle := CheckButton.new()
	toggle.text = text
	toggle.button_pressed = value
	toggle.toggled.connect(action)
	parent.add_child(toggle)


func _select_preset(index: int) -> void:
	var preset: Dictionary = PRESETS[index]
	asset.source_file = "res://samples/raw/" + str(preset["source"])
	asset.visual_file = "res://samples/models/" + str(preset["visual"]) if preset.has("visual") else ""
	asset.bbn_file = "res://samples/raw/" + str(preset["bbn"]) if preset.has("bbn") else ""
	asset.skeleton_model_file = "res://samples/raw/" + str(preset["model"]) if preset.has("model") else ""


func _on_rebuilt() -> void:
	if _status_label != null:
		_status_label.text = asset.status
	if bool(asset.report.get("ok", false)):
		camera.frame_bounds(asset.preview_bounds)


func _choose_file() -> void:
	_file_dialog.popup_centered_ratio(0.7)


func _load_external(path: String) -> void:
	asset.visual_file = ""
	asset.bbn_file = ""
	asset.skeleton_model_file = ""
	asset.source_file = path


func _bake() -> void:
	asset.bake_scene()
	_status_label.text = asset.status


func _drop_probe() -> void:
	if int(asset.report.get("physics_shape_count", 0)) == 0:
		_status_label.text = asset.status + "\nNo physical shapes: ACS is a diagnostic gallery."
		return
	var center: Vector2 = get_viewport().get_visible_rect().size * 0.5
	var from: Vector3 = camera.project_ray_origin(center)
	var direction: Vector3 = camera.project_ray_normal(center)
	var query := PhysicsRayQueryParameters3D.create(from, from + direction * camera.far, 1)
	var hit: Dictionary = get_world_3d().direct_space_state.intersect_ray(query)
	if hit.is_empty():
		_status_label.text = asset.status + "\nCenter ray missed. Orbit until a collision surface is centered."
		return
	var probe := RigidBody3D.new()
	probe.name = "PhysicsProbe_%d" % _probe_count
	_probe_count += 1
	probe.collision_layer = 2
	probe.collision_mask = 1
	probe.continuous_cd = true
	var radius: float = clampf(asset.preview_bounds.size.length() * 0.005, 0.08, 0.3)
	var shape := SphereShape3D.new()
	shape.radius = radius
	var collider := CollisionShape3D.new()
	collider.shape = shape
	probe.add_child(collider)
	var mesh := SphereMesh.new()
	mesh.radius = radius
	mesh.height = radius * 2
	var display := MeshInstance3D.new()
	display.mesh = mesh
	var material := StandardMaterial3D.new()
	material.albedo_color = Color(1, 0.3, 0.1)
	display.material_override = material
	probe.add_child(display)
	add_child(probe)
	probe.global_position = Vector3(hit["position"]) + Vector3.UP * maxf(radius * 5.0, 0.5)
	_status_label.text = asset.status + "\nProbe dropped onto a ray-tested original collision surface."

@tool
extends EditorPlugin
## Authoring commands only. Build/import work runs off the editor's main thread.

const MENU: PackedStringArray = ["Variant: Build/Refresh Local Variant", "Variant: Open Local Variant", "Variant: Build Without Collision", "Variant: Remove Local Variant"]
var _thread: Thread
var _dialog: ConfirmationDialog
var _assets: LineEdit
var _source: LineEdit
var _collision: bool = true
var _module: String


func _enter_tree() -> void:
	_module = ProjectSettings.globalize_path("res://").path_join("../../..").simplify_path()
	add_tool_menu_item(MENU[0], _show_build.bind(true))
	add_tool_menu_item(MENU[1], _open_variant)
	add_tool_menu_item(MENU[2], _show_build.bind(false))
	add_tool_menu_item(MENU[3], _execute.bind(PackedStringArray(["--clean"])))
	_dialog = ConfirmationDialog.new()
	_dialog.title = "Build isolated local variant"
	_dialog.ok_button_text = "Build"
	var fields := VBoxContainer.new()
	_dialog.add_child(fields)
	var help := Label.new()
	help.text = "Canonical EU scenes stay unchanged. Outputs replace the ignored LocalVariant project."
	fields.add_child(help)
	var assets_label := Label.new()
	assets_label.text = "Converted assets directory (with normalization maps):"
	fields.add_child(assets_label)
	_assets = LineEdit.new()
	_assets.text = str(EditorInterface.get_editor_settings().get_project_metadata("local_variant", "assets", ProjectSettings.globalize_path("res://assets")))
	fields.add_child(_assets)
	var source_label := Label.new()
	source_label.text = "Matching raw collision dataset (blank uses module config.toml):"
	fields.add_child(source_label)
	_source = LineEdit.new()
	_source.text = str(EditorInterface.get_editor_settings().get_project_metadata("local_variant", "source", ""))
	fields.add_child(_source)
	_dialog.confirmed.connect(_start_build)
	add_child(_dialog)


func _exit_tree() -> void:
	for item: String in MENU:
		remove_tool_menu_item(item)
	if _thread != null:
		_thread.wait_to_finish()
	_dialog.queue_free()


func _show_build(collision: bool) -> void:
	_collision = collision
	_dialog.popup_centered(Vector2i(750, 220))


func _start_build() -> void:
	var settings: EditorSettings = EditorInterface.get_editor_settings()
	settings.set_project_metadata("local_variant", "assets", _assets.text)
	settings.set_project_metadata("local_variant", "source", _source.text)
	var args := PackedStringArray(["--assets", _assets.text, "--godot", OS.get_executable_path()])
	if not _source.text.strip_edges().is_empty():
		args.append_array(PackedStringArray(["--source", _source.text]))
	if not _collision:
		args.append("--no-collision")
	_execute(args)


func _execute(arguments: PackedStringArray) -> void:
	if _thread != null:
		push_warning("A local variant command is already running.")
		return
	print("Local variant: running. Logs: ", _module.path_join("Godot/GodotGame/.local_variant_work/process.log"))
	_thread = Thread.new()
	_thread.start(_run_cli.bind(arguments))
	set_process(true)


func _run_cli(arguments: PackedStringArray) -> Dictionary:
	var output: Array = []
	var args := PackedStringArray(["-B", _module.path_join("operations/godot/build_local_variant.py")])
	args.append_array(arguments)
	var code: int = OS.execute("python", args, output, true)
	return {"code": code, "output": output}


func _process(_delta: float) -> void:
	if _thread == null or _thread.is_alive():
		return
	var result: Dictionary = _thread.wait_to_finish()
	_thread = null
	for line: Variant in result["output"]:
		print(str(line))
	if int(result["code"]) != 0:
		push_error("Local variant failed. Existing canonical and active projects were preserved. See output above.")
	set_process(false)


func _open_variant() -> void:
	var path: String = _module.path_join("Godot/GodotGame/LocalVariant")
	if not FileAccess.file_exists(path.path_join("project.godot")):
		push_warning("Build a local variant first.")
		return
	OS.create_process(OS.get_executable_path(), PackedStringArray(["--editor", "--path", path]))

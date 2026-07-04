@tool
extends EditorPlugin

const IMPORTER_CORE = preload("res://addons/remake_pipeline/core/importer_core.gd")
const EXPORTER_CORE = preload("res://addons/remake_pipeline/core/exporter_core.gd")

var _export_dialog: EditorFileDialog
var _import_dialog: EditorFileDialog

func _enter_tree() -> void:
    add_tool_menu_item("Remake: Export Scene to JSON", _on_export_pressed)
    add_tool_menu_item("Remake: Import JSON Scene", _on_import_pressed)

    _export_dialog = EditorFileDialog.new()
    _export_dialog.access = EditorFileDialog.ACCESS_RESOURCES
    _export_dialog.file_mode = EditorFileDialog.FILE_MODE_SAVE_FILE
    _export_dialog.filters = PackedStringArray(["*.json ; JSON"])
    _export_dialog.file_selected.connect(_on_export_path_selected)
    add_child(_export_dialog)

    _import_dialog = EditorFileDialog.new()
    _import_dialog.access = EditorFileDialog.ACCESS_RESOURCES
    _import_dialog.file_mode = EditorFileDialog.FILE_MODE_OPEN_FILE
    _import_dialog.filters = PackedStringArray(["*.json ; JSON"])
    _import_dialog.file_selected.connect(_on_import_path_selected)
    add_child(_import_dialog)

func _exit_tree() -> void:
    remove_tool_menu_item("Remake: Export Scene to JSON")
    remove_tool_menu_item("Remake: Import JSON Scene")

func _on_export_pressed() -> void:
    _export_dialog.popup_centered_ratio(0.7)

func _on_import_pressed() -> void:
    _import_dialog.popup_centered_ratio(0.7)

func _on_export_path_selected(path: String) -> void:
    var root := get_editor_interface().get_edited_scene_root()
    if not root:
        printerr("Remake export failed: no open scene.")
        return

    var exporter = EXPORTER_CORE.new()
    var ok := exporter.export_scene(root, path)
    if ok:
        print("Remake export complete: ", path)
    else:
        printerr("Remake export failed: ", path)

func _on_import_path_selected(path: String) -> void:
    var importer = IMPORTER_CORE.new()
    var ok := importer.run_import(path, "")
    if ok:
        print("Remake import complete: ", path)
        get_editor_interface().get_resource_filesystem().scan()
    else:
        printerr("Remake import failed: ", path)

extends SceneTree
## Rename-only publication. Run in the work project after the staging engine exits.

func _owned(path: String) -> bool:
	var marker: Variant = JSON.parse_string(FileAccess.get_file_as_string(path.path_join(".local_variant_owned.json")))
	return marker is Dictionary and marker.get("tool") == "local_variant"

func _initialize() -> void:
	var data: Variant = JSON.parse_string(FileAccess.get_file_as_string("res://publication.json"))
	if not data is Dictionary:
		printerr("Invalid publication manifest")
		quit(1)
		return
	var work := ProjectSettings.globalize_path("res://").simplify_path().trim_suffix("/")
	var stage: String = data.get("stage", "")
	var previous: String = data.get("previous", "")
	var output: String = data.get("output", "")
	if stage != work.path_join("staging") or previous != work.path_join("previous") or output != work.get_base_dir().path_join("LocalVariant"):
		printerr("Refusing unsafe publication paths")
		quit(1)
		return
	if not _owned(stage) or DirAccess.dir_exists_absolute(previous):
		printerr("Staging is unowned or previous output still exists")
		quit(1)
		return
	var had_output := DirAccess.dir_exists_absolute(output)
	if had_output:
		if not _owned(output) or DirAccess.rename_absolute(output, previous) != OK:
			printerr("Cannot move the previous local project; close its editor/game")
			quit(1)
			return
	if DirAccess.rename_absolute(stage, output) != OK:
		if had_output and DirAccess.rename_absolute(previous, output) != OK:
			printerr("Publication failed; restore the preserved project from ", previous)
		else:
			printerr("Publication failed; previous project restored")
		quit(1)
		return
	quit(0)

extends SceneTree
## Build-time only: read supplied originals and serialize local Godot resources.

const Reader = preload("res://.variant_tools/tsg_havok_reader.gd")
const Builder = preload("res://.variant_tools/physics_builder.gd")


func _initialize() -> void:
	var input: Variant = JSON.parse_string(FileAccess.get_file_as_string("res://variant_jobs.json"))
	if not input is Dictionary:
		printerr("Invalid variant job manifest")
		quit(1)
		return
	var results: Array[Dictionary] = []
	for job: Dictionary in input.get("jobs", []):
		var report: Dictionary = Reader.read_file(str(job["source"]))
		var result: Dictionary = {"uid": job["uid"], "source_hash": job["source_hash"],
			"ok": false, "stats": report.get("stats", {}), "warnings": report.get("warnings", [])}
		if not bool(report.get("ok", false)):
			result["error"] = report.get("error", "Unsupported or malformed collision")
			results.append(result)
			continue
		var node: Node3D = Builder.build(report)
		node.set_meta("collision_uid", str(job["uid"]))
		node.set_meta("source_hash", str(job["source_hash"]))
		var count: int = node.find_children("*", "CollisionShape3D", true, false).size()
		result["physics_shapes"] = count
		if count == 0:
			result["error"] = "No supported nondegenerate collision bodies"
		elif count != int(report.get("stats", {}).get("source_body_count", 0)):
			# Do not quietly publish partially supported collision for an asset.
			result["error"] = "Incomplete collision: %d of %d source bodies" % [count, int(report.stats.source_body_count)]
		else:
			var packed := PackedScene.new()
			var error: Error = packed.pack(node)
			if error == OK:
				DirAccess.make_dir_recursive_absolute(str(job["output"]).get_base_dir())
				error = ResourceSaver.save(packed, str(job["output"]))
			if error != OK:
				printerr("Cannot save collision: ", error_string(error))
				node.free()
				quit(1)
				return
			result["ok"] = true
		node.free()
		results.append(result)
		print("Collision ", job["uid"], ": ", count, " bodies; ", result["ok"])
	var output: FileAccess = FileAccess.open("res://variant_bake_results.json", FileAccess.WRITE)
	if output == null:
		quit(1)
		return
	output.store_string(JSON.stringify({"jobs": results}, "\t"))
	output.close()
	quit(0)

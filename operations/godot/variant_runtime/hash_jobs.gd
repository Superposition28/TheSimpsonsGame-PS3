extends SceneTree
## Native batch hashing for the Lua builder; persisted job hashes remain SHA-256.

func _initialize() -> void:
	var input: Variant = JSON.parse_string(FileAccess.get_file_as_string("res://variant_jobs.json"))
	if not input is Dictionary or not input.get("jobs") is Array:
		printerr("Invalid variant job manifest")
		quit(1)
		return
	var total: int = input["jobs"].size()
	var processed: int = 0
	print("VARIANT_PROGRESS 0 %d Hash collision inputs" % total)
	for job: Dictionary in input["jobs"]:
		var digest := FileAccess.get_sha256(str(job["source"]))
		if digest.is_empty():
			printerr("Cannot hash collision source: ", job["source"])
			quit(1)
			return
		job["source_hash"] = digest
		processed += 1
		print("VARIANT_PROGRESS %d %d %s" % [processed, total, job["uid"]])
	var output := FileAccess.open("res://variant_jobs.json", FileAccess.WRITE)
	if output == null:
		quit(1)
		return
	output.store_string(JSON.stringify(input, "\t"))
	output.close()
	quit(0)

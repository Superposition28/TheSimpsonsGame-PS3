@tool
extends SceneTree

const IMPORTER_CORE = preload("res://addons/remake_pipeline/core/importer_core.gd")

func _init() -> void:
    print("--- Remake Pipeline CLI ---")

    var args := OS.get_cmdline_args()
    var entry := "Node4D.json"
    var config_root := ""
    var keep_open := args.has("--no-exit")

    for i in range(args.size()):
        if args[i] == "--entry" and i + 1 < args.size():
            entry = args[i + 1]
        if args[i] == "--config-root" and i + 1 < args.size():
            config_root = args[i + 1]

    var importer = IMPORTER_CORE.new()
    var ok := importer.run_import(entry, config_root)

    if ok:
        print("Headless build finished successfully.")
        if not keep_open:
            quit(0)
    else:
        printerr("Headless build failed.")
        quit(1)

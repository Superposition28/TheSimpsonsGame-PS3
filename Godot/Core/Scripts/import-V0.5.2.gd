# -----------------------------------------------------------------------------
# IMPORT V0.5.3
# godot version 4.5
# -----------------------------------------------------------------------------
@tool
extends SceneTree

const IMPORTER_CORE = preload("res://addons/remake_pipeline/core/importer_core.gd")

const CONFIG_ROOT := "res://Json/"
const ASSET_ROOT  := "res://assets/"
const ASSET_MAP_PATH := "res://assets/normalized_map.json"

func _init():
    print("--- Importer V0.5 Initialized ---")
    var args := OS.get_cmdline_args()
    var entry := "Node4D.json"
    var config_root := ""

    for i in range(args.size()):
        if args[i] == "--entry" and i + 1 < args.size():
            entry = args[i + 1]
        if args[i] == "--config-root" and i + 1 < args.size():
            config_root = args[i + 1]

    var importer = IMPORTER_CORE.new()
    var ok := importer.run_import(entry, config_root)
    if ok:
        print("\n✅ Build Finished ✅")
    else:
        printerr("\nBuild Failed")

    if OS.get_cmdline_args().has("--no-exit"):
        print("Keeping editor open (--no-exit).")
    else:
        print("Exiting.")

## Path: Node4D/Node3D/Characters/mouse_lock.gd
## Binding, bound to 4D/Node3D/Characters/mouse_lock.tscn
##
## Mouse lock management for player character
##
##
##


extends Node

@onready var debug := bool(Console.get_cvar("debug"))

func _ready() -> void:
    if Engine.has_singleton("Console"):
        # Listen for CVar changes to update mouse state. [cite: 100]
        Console.cvar_changed.connect(_on_cvar_changed)
    _apply_mouse_mode() # Set initial state.
    if debug: print("mouse_lock: ready, initial mouse mode applied")

func _exit_tree() -> void:
    Input.mouse_mode = Input.MOUSE_MODE_VISIBLE
    if debug: print("mouse_lock: exited, mouse mode set to visible")

func _on_cvar_changed(cvar_name: String, _new_value: Variant) -> void:
    if cvar_name == "ui.in_pause" or cvar_name == "ui.console_open" or cvar_name == "mouse.lock":
        _apply_mouse_mode()
        if debug: print("mouse_lock: CVar changed, mouse mode updated")
    else:
        if debug: print("mouse_lock: CVar changed (%s), no action taken" % cvar_name)

func _apply_mouse_mode() -> void:
    var console_open = bool(Console.get_cvar("ui.console_open"))
    var in_pause = bool(Console.get_cvar("ui.in_pause"))
    var want_lock = bool(Console.get_cvar("mouse.lock"))

    if console_open or in_pause:
        Input.mouse_mode = Input.MOUSE_MODE_VISIBLE
        if debug: print("mouse_lock: applied mouse mode visible")
    elif want_lock:
        Input.mouse_mode = Input.MOUSE_MODE_CAPTURED
        if debug: print("mouse_lock: applied mouse mode captured")
    else:
        Input.mouse_mode = Input.MOUSE_MODE_VISIBLE
        if debug: print("mouse_lock: applied mouse mode visible")

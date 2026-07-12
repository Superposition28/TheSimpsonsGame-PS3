## Path: Node4D/Node2D/Terminal_ControlNode.gd
## Binding, bound to 4D/Node2D/Terminal_ControlNode.tscn
##
## Terminal UI (control node) for in-game console
#
##
##
##

extends Control

@onready var _panel: Panel = $CanvasLayer/Panel
@onready var _out: RichTextLabel = $CanvasLayer/Panel/OutputField
@onready var _in: LineEdit = $CanvasLayer/Panel/InputField
@onready var _vp: VideoStreamPlayer = $CanvasLayer/Panel/VideoPlayer

func _ready() -> void:
    process_mode = Node.PROCESS_MODE_ALWAYS
    _panel.visible = false
    _out.bbcode_enabled = true
    _in.text_submitted.connect(_on_InputField_text_submitted)
    _in.editable = false

    # Wire console signals, including the new cvar_changed signal.
    Console.printed.connect(_on_console_print)
    Console.cleared.connect(_on_console_clear)
    Console.cvar_changed.connect(_on_cvar_changed)

    # Set initial state from CVar.
    _update_visibility(bool(Console.get_cvar("ui.console_open")))
    ConsoleCommands.register_ui_commands(self)

func _on_cvar_changed(cvar_name: String, new_value: Variant) -> void:
    # React to state changes, rather than controlling them.
    if cvar_name == "ui.console_open":
        _update_visibility(bool(new_value))

func _update_visibility(is_visible: bool) -> void:
    _panel.visible = is_visible
    _in.editable = is_visible
    if is_visible:
        _in.grab_focus()
    else:
        _in.clear()


func _open_console() -> void:
    _panel.visible = true
    _in.editable = true
    _in.grab_focus()
    Console.set_visible(true)
    Console.set_cvar("ui.console_open", true)

    # Pause the game via console command so pause state is handled centrally.
    Console.execute_command("pause_game on")

    # Release mouse so user can interact with UI.
    Input.mouse_mode = Input.MOUSE_MODE_VISIBLE

func _close_console() -> void:
    _panel.visible = false
    _in.editable = false
    _in.clear()
    Console.set_visible(false)
    Console.set_cvar("ui.console_open", false)

    # Restore paused state only if the pause menu is NOT active.
    var in_pause: Variant = Console.get_cvar("ui.in_pause")
    if in_pause == null or not bool(in_pause):
        Console.execute_command("pause_game off")

    var want_lock: Variant = Console.get_cvar("mouse.lock")
    if want_lock == null or bool(want_lock):
        Input.mouse_mode = Input.MOUSE_MODE_CAPTURED

func _on_console_toggled(visible: Variant = null) -> void:
    # Keep UI in sync if some other system toggles the console.
    # Accepts a boolean (visible) or no args.
    if visible == null:
        # unknown, just flip to whatever Console.is_visible() reports if available
        # fallback to the panel state
        if Console.has_method("is_visible") and Console.is_visible():
            _open_console()
        else:
            _close_console()
        return
    if bool(visible):
        _open_console()
    else:
        _close_console()

# ----- Output & input plumbing -----
func _on_console_print(text: String) -> void:
    _out.append_text(text + "\n")
    _out.scroll_to_line(_out.get_line_count() - 1)

func _on_console_clear() -> void:
    _out.clear()

func _on_InputField_text_submitted(text: String) -> void:
    var debug := bool(Console.get_cvar("debug"))
    var line := text.strip_edges()
    if debug: print("Terminal_ControlNode: input submitted -> '%s'" % line)
    if line == "":
        Console.execute_command("//ui_console_toggle") # Use command to close
        return
    # Prepend the default prefix if the user doesn't provide one.
    if not (line.begins_with("/") or line.begins_with("//") or line.begins_with("///")):
        line = "//" + line

    var result := Console.execute_command(line)
    if result != "":
        Console.print_line(result)
    _in.clear()

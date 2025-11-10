## Path: Scripts/Console.gd
## Binding, Editor Autoload
## Console system
## Handles the developer console with command registration, CVar storage, input history, and output.
## all internal operations are performed using console commands that can be called from anywhere even by the user
##
##
##

extends Node

signal printed(text: String)
signal cleared()
signal toggled(visible: bool)
signal cvar_changed(cvar_name: String, new_value) # New signal

var _visible: bool = false
# The command data structure is now a single dictionary.
var _commands: Dictionary = {} # Stores: { "callable": Callable, "description": String, "hidden": bool }
var _cvars: Dictionary = {}
var _history: Array[String] = []
var _history_max := 200

func _ready() -> void:
    register_cvar("ui.in_pause", false, "True when pause menu is open; blocks console toggle")
    register_cvar("ui.console_open", false, "True when the developer console UI is visible")
    register_cvar("mouse.lock", true, "Capture mouse when gameplay is active")
    register_cvar("debug", true, "Enable debug print statements (Godot print)") # new CVar, enabled by default
    # Commands are registered in the dedicated ConsoleCommands module.
    ConsoleCommands.register_core_commands()

func set_visible(v: bool) -> void:
    if _visible == v: return
    _visible = v
    emit_signal("toggled", _visible)

func is_visible() -> bool:
    return _visible

func print_line(text: String) -> void:
    emit_signal("printed", text)

func clear_output() -> void:
    emit_signal("cleared")

func execute_command(line: String) -> String:
    # Delegate execution to ConsoleCommands which centralises command logic.
    return ConsoleCommands.execute_command(line)

# Updated to accept a 'hidden' flag.
func register_command(cmd_name: String, func_ref: Callable, description: String = "", hidden: bool = false) -> void:
    _commands[cmd_name] = {
        "callable": func_ref,
        "description": description,
        "hidden": hidden
    }

# NOTE: "CVar" = Console Variable.
# A CVar is a named runtime configuration value exposed via the developer console.
# Use register_cvar() to create a togglable / configurable setting (stored in _cvars).
# CVars are accessible by the "cvar" console command and via get_cvar()/set_cvar().
# Typical uses: feature toggles, debug flags, input/gameplay settings, etc.

func register_cvar(cvar_name: String, default_value, description: String="") -> void:
    # Register a new console variable (CVar).
    # - cvar_name: unique key used by the console and get/set functions.
    # - default_value: initial runtime value (type is preserved).
    # - description: optional human-readable description shown by tools.
    _cvars[cvar_name] = {"value": default_value, "desc": description}

func set_cvar(cvar_name: String, value) -> void:
    # Set an existing CVar's value, or create it if missing.
    # This affects the runtime value only (no automatic persistence).
    if not _cvars.has(cvar_name):
        _cvars[cvar_name] = {"value": value, "desc": ""}
    else:
        # Avoid emitting signal if the value hasn't changed.
        if _cvars[cvar_name]["value"] == value:
            return
        _cvars[cvar_name]["value"] = value
    
    # Emit the new signal so other nodes can react.
    emit_signal("cvar_changed", cvar_name, value)

func get_cvar(cvar_name: String):
    # Return the current value of a CVar, or null if it doesn't exist.
    if not _cvars.has(cvar_name):
        return null
    return _cvars[cvar_name]["value"]


# --- helpers ---
func _tokenize(line: String) -> Array[String]:
    var parts: Array[String] = []
    var current := ""
    var in_quotes := false
    for i in range(line.length()):
        var ch := line[i]
        if ch == "\"":
            in_quotes = !in_quotes
        elif ch == " " and not in_quotes:
            if current != "":
                parts.append(current)
                current = ""
        else:
            current += ch
    if current != "":
        parts.append(current)
    return parts

func _collect_flags(tokens: Array) -> Dictionary:
    var flags := {}
    var i := 0
    while i < tokens.size():
        var t := str(tokens[i])
        if t.begins_with("--"):
            flags[t.substr(2, t.length())] = true
            tokens.remove_at(i)
        else:
            i += 1
    return flags

func _parse_value(s: String):
    if s == "true": return true
    if s == "false": return false
    if s.is_valid_int(): return int(s)
    if s.is_valid_float(): return float(s)
    return s

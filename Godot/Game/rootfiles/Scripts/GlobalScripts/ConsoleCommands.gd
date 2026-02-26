## Path: Scripts/ConsoleCommands.gd
## Centralized command registration and execution
## Autoload singleton: ConsoleCommands
##
## - register_core_commands(): binds built-in commands
## - register_ui_commands(term_node): binds UI-related commands (needs terminal node)
## - execute_command(line): runs a command via Console registry
##
## Each registered command delegates to a private helper (_cmd_*).
class_name ConsoleCommands
extends Node

var _term_node: Node = null  # set by register_ui_commands()

func register_core_commands() -> void:
    # / -> Basic user-facing commands
    Console.register_command("help", _cmd_help, "List commands or help <name>")
    Console.register_command("history", _cmd_history, "Show input history")
    Console.register_command("clear", _cmd_clear, "Clear console output")
    Console.register_command("jump", _cmd_jump, "Makes the player jump.")
    
    # // -> Advanced gameplay/UI commands
    Console.register_command("cvar", _cmd_cvar, "cvar <name> [value] — get/set cvar")
    Console.register_command("cvars", _cmd_cvars, "List all CVars")
    Console.register_command("ui_pause_toggle", _cmd_ui_pause_toggle, "Toggles the pause menu.")
    Console.register_command("ui_console_toggle", _cmd_ui_console_toggle, "Toggles the developer console.")

    # /// -> Hidden, internal, or debug commands (hidden = true)
    Console.register_command("_internal_pause_game", _cmd_pause_game, "Pauses or unpauses the game tree.", true)

static func register_ui_commands(term_node: Node) -> void:
    # Keep a reference so helpers can use the terminal resources (e.g., video player)
    ConsoleCommands._term_node = term_node
    Console.register_command("echo", ConsoleCommands._cmd_echo, "echo <text>")
    Console.register_command("play_video", ConsoleCommands._cmd_play_video, "play_video <resource>")
    Console.register_command("stop_video", ConsoleCommands._cmd_stop_video, "Stop video playback")

static func execute_command(line: String) -> String:
    var processed_line := line.strip_edges()
    if processed_line.is_empty(): return ""

    # 1. Check for a valid prefix and strip it.
    var prefix_len := 0
    if processed_line.begins_with("///"):
        prefix_len = 3
    elif processed_line.begins_with("//"):
        prefix_len = 2
    elif processed_line.begins_with("/"):
        prefix_len = 1
    else:
        return "[color=red]Invalid format. Commands must start with /, //, or ///[/color]"

    var command_body := processed_line.substr(prefix_len)
    if command_body.strip_edges() == "": return ""

    # 2. History
    Console._history.append(line)
    if Console._history.size() > Console._history_max:
        Console._history.pop_front()

    # 3. Tokenize and flags
    var tokens: Array = Console._tokenize(command_body)
    if tokens.is_empty(): return ""
    var cmd_name: String = tokens.pop_front()
    var flags: Dictionary = Console._collect_flags(tokens)

    # 4. Fetch the command's info dictionary.
    var cmd_info = Console._commands.get(cmd_name, null)
    if cmd_info == null:
        return "[color=red]Unknown command:[/color] %s" % cmd_name

    # 5. Enforce hidden-command access: require /// for hidden commands.
    var is_hidden := bool(cmd_info.get("hidden", false))
    if is_hidden and prefix_len < 3:
        return "[color=red]Unknown command:[/color] %s" % cmd_name

    # 6. Execute callable
    var fn = cmd_info["callable"]
    var result = fn.call(tokens, flags)
    return str(result) if result != null else ""


# -------------------------------------------------------------------
#                     Private command helpers
# -------------------------------------------------------------------

func _cmd_help(args: Array, _flags: Dictionary) -> String:
    if args.size() == 0:
        var visible_command_names: Array[String] = []
        for cmd_name in Console._commands:
            var cmd_info = Console._commands[cmd_name]
            # Only list commands that are NOT hidden.
            if not cmd_info.get("hidden", false):
                visible_command_names.append(cmd_name)
        
        visible_command_names.sort()
        return "[b]Commands:[/b]\n" + "\n".join(PackedStringArray(visible_command_names))

    var cmd_name := str(args[0])
    var cmd_info = Console._commands.get(cmd_name, null)
    if not cmd_info: return "No such command: %s" % cmd_name
    return cmd_info.get("description", "No description")

func _cmd_history(_args: Array, _flags: Dictionary) -> String:
    var lines: Array[String] = []
    for i in range(Console._history.size()):
        lines.append("%3d: %s" % [i + 1, Console._history[i]])
    return "[code]%s[/code]" % "\n".join(PackedStringArray(lines))

func _cmd_clear(_args: Array, _flags: Dictionary) -> String:
    Console.clear_output()
    return ""

func _cmd_cvar(args: Array, _flags: Dictionary) -> String:
    if args.size() == 0:
        return "Usage: cvar <name> [value]"
    var cvar_name := str(args[0])
    if args.size() == 1:
        if not Console._cvars.has(cvar_name):
            return "No such cvar: %s" % cvar_name
        return "%s = %s" % [cvar_name, str(Console._cvars[cvar_name]["value"])]
    var val_str := str(args[1])
    var parsed = Console._parse_value(val_str)
    Console.set_cvar(cvar_name, parsed)
    return "%s = %s" % [cvar_name, str(parsed)]

func _cmd_cvars(_args: Array, _flags: Dictionary) -> String:
    var lines: Array[String] = []
    for k in Console._cvars.keys():
        lines.append("%s = %s" % [k, str(Console._cvars[k]["value"])])
    lines.sort()
    return "[code]%s[/code]" % "\n".join(PackedStringArray(lines))

func _cmd_jump(_args: Array, _flags: Dictionary) -> String:
    var player = get_tree().get_first_node_in_group("player")
    if player and player.is_on_floor():
        # This command now directly manipulates the player node.
        player.velocity.y = player.jump_velocity
        return "Jumped."
    return "Cannot jump."

func _cmd_ui_console_toggle(_args: Array, _flags: Dictionary) -> String:
    # This command now owns the logic for opening/closing the console.
    var is_open = bool(Console.get_cvar("ui.console_open"))
    var new_state = not is_open
    
    Console.set_cvar("ui.console_open", new_state)
    Console.execute_command("///_internal_pause_game %s" % ("on" if new_state else "off"))
    
    return "Console opened." if new_state else "Console closed."

func _cmd_ui_pause_toggle(_args: Array, _flags: Dictionary) -> String:
    if bool(Console.get_cvar("ui.console_open")):
        return "Cannot open pause menu while console is open."
        
    var is_paused = bool(Console.get_cvar("ui.in_pause"))
    var new_state = not is_paused
    
    Console.set_cvar("ui.in_pause", new_state)
    Console.execute_command("///_internal_pause_game %s" % ("on" if new_state else "off"))

    return "Game paused." if new_state else "Game resumed."

# Renamed to be an internal command.
func _cmd_pause_game(args: Array, _flags: Dictionary) -> String:
    var current := get_tree().paused
    var target := current
    if args.size() == 0:
        target = not current
    else:
        var a := str(args[0]).to_lower()
        match a:
            "on", "true", "1":
                target = true
            "off", "false", "0":
                target = false
            "toggle":
                target = not current
            _:
                return "Usage: pause_game [on|off|toggle]"
    get_tree().paused = target
    return "Game paused" if target else "Game unpaused"

func _cmd_echo(args: Array, _flags: Dictionary) -> String:
    return " ".join(PackedStringArray(args))

func _cmd_play_video(args: Array, _flags: Dictionary) -> String:
    if args.is_empty():
        return "Usage: play_video <resource path>"
    if _term_node == null or not _term_node.has_node("_vp"):
        return "Terminal video player not available"
    var path := str(args[0])
    var stream := load(path)
    if stream == null:
        return "Could not load: %s" % path
    var vp := _term_node.get_node("_vp")
    vp.stream = stream
    vp.play()
    return "Playing: %s" % path

func _cmd_stop_video(_args: Array, _flags: Dictionary) -> String:
    if _term_node == null or not _term_node.has_node("_vp"):
        return "Terminal video player not available"
    var vp := _term_node.get_node("_vp")
    vp.stop()
    return "Stopped video"

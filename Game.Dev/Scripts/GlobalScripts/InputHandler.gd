## Path: Scripts/InputHandler.gd
## New autoload singleton.
## Captures all player input and translates it into console commands or CVar updates.

extends Node

func _ready() -> void:
    # never pause this node; it must always capture input.
    process_mode = Node.PROCESS_MODE_ALWAYS

    # Register CVars that this handler will control.
    Console.register_cvar("player.move.forward", 0.0, "Forward/backward movement axis [-1, 1]")
    Console.register_cvar("player.move.right", 0.0, "Right/left movement axis [-1, 1]")
    Console.register_cvar("player.look.dx", 0.0, "Mouse X delta for looking")
    Console.register_cvar("player.look.dy", 0.0, "Mouse Y delta for looking")

func _unhandled_input(event: InputEvent) -> void:
    var debug := bool(Console.get_cvar("debug"))

    # Handle discrete, single-press actions.
    if event.is_action_pressed("jump"):
        if debug: print("InputHandler: action 'jump' pressed")
        Console.execute_command("/jump")
        get_viewport().set_input_as_handled()

    if event.is_action_pressed("ui_console"):
        if debug: print("InputHandler: action 'ui_console' pressed")
        Console.execute_command("//ui_console_toggle")
        get_viewport().set_input_as_handled()

    if event.is_action_pressed("ui_cancel"):
        # The pause menu will only respond if the console is not open.
        if debug: print("InputHandler: action 'ui_cancel' pressed")
        if !bool(Console.get_cvar("ui.console_open")):
            Console.execute_command("//ui_pause_toggle")
        get_viewport().set_input_as_handled()

    # Handle continuous mouse look.
    if event is InputEventMouseMotion and Input.mouse_mode == Input.MOUSE_MODE_CAPTURED:
        if debug: print("InputHandler: mouse motion dx=%s dy=%s" % [event.relative.x, event.relative.y])
        Console.set_cvar("player.look.dx", event.relative.x)
        Console.set_cvar("player.look.dy", event.relative.y)

func _process(_delta: float) -> void:
    # Handle continuous movement axes every frame.
    var forward_axis := Input.get_axis("down", "up")
    var right_axis := Input.get_axis("left", "right")
    Console.set_cvar("player.move.forward", forward_axis)
    Console.set_cvar("player.move.right", right_axis)

    # Reset mouse look deltas each frame so rotation stops if the mouse stops.
    Console.set_cvar("player.look.dx", 0.0)
    Console.set_cvar("player.look.dy", 0.0)

extends Control

# --- setup ---
func _ready() -> void:
    process_mode = Node.PROCESS_MODE_ALWAYS
    # Connect to the CVar signal to react to state changes.
    Console.cvar_changed.connect(_on_cvar_changed)
    # Set initial visibility based on the CVar.
    visible = bool(Console.get_cvar("ui.in_pause"))

func _on_cvar_changed(cvar_name: String, new_value: Variant) -> void:
    if cvar_name == "ui.in_pause":
        visible = bool(new_value)

# Input is no longer handled here; it's managed by InputHandler.gd
# The button signals now just execute commands.
func _on_ResumeButton_pressed():
    if bool(Console.get_cvar("debug")):
        print("Pause_Control: Resume button pressed")
    Console.execute_command("//ui_pause_toggle")

func _on_QuitButton_pressed():
    if bool(Console.get_cvar("debug")):
        print("Pause_Control: Quit button pressed")
    Console.execute_command("/quit") # Assumes /quit is registered elsewhere

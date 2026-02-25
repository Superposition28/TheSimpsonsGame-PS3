# SPDX-License-Identifier: MIT
import bpy

# --- Global Settings ---
global debug_mode
debug_mode = False  # Default value, can be set in the addon preferences


def printc(message: str, colour: str | None = None) -> None:
    """
    Print a message to the console with optional ANSI color coding.
    """
    colours = {
        'red': '\033[91m', 'green': '\033[92m', 'yellow': '\033[93m',
        'blue': '\033[94m', 'magenta': '\033[95m', 'cyan': '\033[96m',
        'white': '\033[97m', 'darkcyan': '\033[36m', 'darkyellow': '\033[33m',
        'darkred': '\033[31m', 'reset': '\033[0m'
    }
    endc = '\033[0m'
    if colour and colour.lower() in colours:
        print(f"{colours['magenta']}EXTENSION:{endc} {colours[colour.lower()]}{message}{endc}")
    else:
        print(f"{colours['magenta']}EXTENSION:{endc} {colours['blue']}{message}{endc}")


def bPrinter(
    text: str,
    block_name: str = "SimpGame_Importer_Log",
    to_blender_editor: bool = False,
    print_to_console: bool = True,
    console_colour: str = "blue",
    require_debug_mode: bool = False,
    log_as_metadata: bool = False,
    metadata_key: str = "log_metadata"
) -> None:
    """Robust logging function that can print to console with colors, write to a Blender text block, and/or store logs as metadata on the scene. Respects a global debug_mode flag and can be configured to only log when debug_mode is True."""
    global debug_mode
    addon_name = __package__.split('.')[0] if __package__ else None
    
    try:
        if addon_name and addon_name in bpy.context.preferences.addons:
            debug_mode = bpy.context.preferences.addons[addon_name].preferences.debugmode
        elif __name__ in bpy.context.preferences.addons:
            debug_mode = bpy.context.preferences.addons[__name__].preferences.debugmode
    except Exception as e:
        printc(f"[Log Error] Could not access addon preferences for '{addon_name or __name__}': {e}. Assuming debug_mode=False.")
        debug_mode = False

    if not require_debug_mode or debug_mode:
        if print_to_console:
            printc(text, colour=console_colour)
        if log_as_metadata:
            try:
                scene = bpy.context.scene
                key_to_use = get_unique_metadata_key(scene, metadata_key)
                scene[key_to_use] = text
                printc(f"[Log] Stored log at metadata key: {key_to_use}", colour="green")
            except Exception as e:
                printc(f"[Log Error] Failed to store log as metadata: {e}")
        if to_blender_editor and hasattr(bpy.data, "texts"):
            try:
                if block_name not in bpy.data.texts:
                    text_block = bpy.data.texts.new(block_name)
                    # Use printc directly here to avoid infinite recursion if bPrinter failed.
                    printc(f"[Log] Created new text block: '{block_name}'")
                else:
                    text_block = bpy.data.texts[block_name]
                text_block.write(text + "\n")
            except Exception as e:
                printc(f"[Log Error] Failed to write to Blender text block '{block_name}': {e}")


def get_unique_metadata_key(container: dict, base_key: str) -> str:
    """
    generate a unique key for storing metadata in the given container (e.g. bpy.types.Scene) by appending a numeric suffix if needed to avoid overwriting existing keys.
    """
    if base_key not in container.keys():
        return base_key
    i = 1
    while True:
        new_key = f"{base_key}.{i:03d}"
        if new_key not in container.keys():
            return new_key
        i += 1

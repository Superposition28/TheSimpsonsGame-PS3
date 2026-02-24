
# blender imports
import math

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
    try:
        if __name__ in bpy.context.preferences.addons:
            debug_mode = bpy.context.preferences.addons[__name__].preferences.debugmode
    except Exception as e:
        printc(f"[Log Error] Could not access addon preferences for '{__name__}': {e}. Assuming debug_mode=False.")
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
                    bPrinter(f"[Log] Created new text block: '{block_name}'")
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


# --- Utility Functions ---

def sanitize_uvs(uv_layer: bpy.types.MeshUVLoopLayer) -> None:
    """Sanitize UV coordinates by replacing non-finite values with (0.0, 0.0) and logging any occurrences."""
    bPrinter(f"[Sanitize] Checking UV layer: {uv_layer.name}")
    if not uv_layer.data:
        bPrinter(f"[Sanitize] Warning: UV layer '{uv_layer.name}' has no data.")
        return
    sanitized_count = 0
    for uv_loop in uv_layer.data:
        if not all(math.isfinite(c) for c in uv_loop.uv):
            bPrinter(f"[Sanitize] Non-finite UV replaced with (0.0, 0.0): {uv_loop.uv[:]}", require_debug_mode=True)
            uv_loop.uv.x = 0.0
            uv_loop.uv.y = 0.0
            sanitized_count += 1
    if sanitized_count > 0:
        bPrinter(f"[Sanitize] Sanitized {sanitized_count} non-finite UV coordinates in layer '{uv_layer.name}'.")

def utils_set_mode(mode: str) -> None:
    """Utility function to set the current mode in Blender, with error handling and logging."""
    bPrinter(f"[SetMode] Setting mode to {mode}")
    if bpy.ops.object.mode_set.poll():
        bpy.ops.object.mode_set(mode=mode, toggle=False)

def strip2face(strip: list) -> list:
    """Convert a triangle strip (list of vertex indices) into a list of faces (triplets of vertex indices), handling the winding order correctly and skipping degenerate faces."""
    #bPrinter(f"[Strip2Face] Converting strip of length {len(strip)} to faces", require_debug_mode=True)
    flipped = False
    tmp_table = []
    if len(strip) < 3:
        #bPrinter(f"[Strip2Face] Strip too short ({len(strip)}) to form faces. Skipping.")
        return []
    for x in range(len(strip)-2):
        v1 = strip[x]
        v2 = strip[x+1]
        v3 = strip[x+2]
        if v1 == v2 or v1 == v3 or v2 == v3:
            #bPrinter(f"[Strip2Face] Skipping degenerate face in strip at index {x} with indices ({v1}, {v2}, {v3})", require_debug_mode=True)
            flipped = not flipped
            continue
        if flipped:
            tmp_table.append((v3, v2, v1))
        else:
            tmp_table.append((v2, v3, v1))
        flipped = not flipped
    #bPrinter(f"[Strip2Face] Generated {len(tmp_table)} faces from strip.", require_debug_mode=True)
    return tmp_table



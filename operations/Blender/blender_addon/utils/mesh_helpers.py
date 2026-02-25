# SPDX-License-Identifier: MIT
import math
import bpy
from .logger import bPrinter

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

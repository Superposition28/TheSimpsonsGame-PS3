# SPDX-License-Identifier: MIT
# Blender addon for importing The Simpsons Game 3D assets with texture↔mesh linking

bl_info = {
    "name": "The Simpsons Game 3d Asset Importer",
    "author": "Turk & Mister_Nebula & Samarixum",
    "version": (1, 5, 6),
    "blender": (4, 0, 0),  # highest supportable version
    "location": "File > Import-Export",
    "description": "Import .rws.preinstanced, .dff.preinstanced mesh files from The Simpsons Game (PS3), detect embedded strings, and link textures to meshes.",
    "warning": "",
    "category": "Import-Export",
}

import bpy
import bmesh
import struct
import re
import io
import math
import mathutils
from pathlib import Path
import numpy as np
import string
import tempfile
import sqlite3
import sys

from bpy.props import (
    StringProperty,
    CollectionProperty
)
from bpy_extras.io_utils import ImportHelper

# --- Global Settings ---
global debug_mode
debug_mode = True  # Default value, can be set in the addon preferences

# --- Utility Functions ---

def printc(message: str, colour: str | None = None) -> None:
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

def get_unique_metadata_key(container: dict, base_key: str) -> str:
    if base_key not in container.keys():
        return base_key
    i = 1
    while True:
        new_key = f"{base_key}.{i:03d}"
        if new_key not in container.keys():
            return new_key
        i += 1

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

def sanitize_uvs(uv_layer: bpy.types.MeshUVLoopLayer) -> None:
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
    bPrinter(f"[SetMode] Setting mode to {mode}")
    if bpy.ops.object.mode_set.poll():
        bpy.ops.object.mode_set(mode=mode, toggle=False)

def strip2face(strip: list) -> list:
    bPrinter(f"[Strip2Face] Converting strip of length {len(strip)} to faces", require_debug_mode=True)
    flipped = False
    tmp_table = []
    if len(strip) < 3:
        bPrinter(f"[Strip2Face] Strip too short ({len(strip)}) to form faces. Skipping.")
        return []
    for x in range(len(strip)-2):
        v1 = strip[x]
        v2 = strip[x+1]
        v3 = strip[x+2]
        if v1 == v2 or v1 == v3 or v2 == v3:
            bPrinter(f"[Strip2Face] Skipping degenerate face in strip at index {x} with indices ({v1}, {v2}, {v3})", require_debug_mode=True)
            flipped = not flipped
            continue
        if flipped:
            tmp_table.append((v3, v2, v1))
        else:
            tmp_table.append((v2, v3, v1))
        flipped = not flipped
    bPrinter(f"[Strip2Face] Generated {len(tmp_table)} faces from strip.", require_debug_mode=True)
    return tmp_table

# --- String Detection (original) ---

ALLOWED_CHARS = string.ascii_letters + string.digits + '_-.'
ALLOWED_CHARS_BYTES = ALLOWED_CHARS.encode('ascii')

FIXED_SIGNATURES_TO_CHECK = [
    {'signature': bytes.fromhex('0211010002000000'), 'relative_string_offset': 16, 'description': 'String Block Header (General, 8 bytes)'},
    {'signature': bytes.fromhex('0211010002000000140000002d00021c'), 'relative_string_offset': 16, 'description': 'String Block Header (Subtype A, 16 bytes)'},
    {'signature': bytes.fromhex('0211010002000000180000002d00021c'), 'relative_string_offset': 16, 'description': 'String Block Header (Subtype B, 16 bytes) - Hypothesized'},
    {'signature': bytes.fromhex('905920010000803f0000803f0000803f'), 'relative_string_offset': 16, 'description': 'Another Block Type Header (16 bytes, Common Float Pattern)'}
]

MAX_POTENTIAL_STRING_LENGTH = 64
MIN_EXTRACTED_STRING_LENGTH = 4
CONTEXT_SIZE = 16
STRING_CONTEXT_SIZE = 5

def find_strings_by_signature_in_data(data: bytes, signatures_info: list, max_string_length: int, min_string_length: int, context_bytes: int, string_context_bytes: int) -> list:
    results = []
    data_len = len(data)
    bPrinter("[String Search] Starting search for configured fixed signatures...")
    for sig_info in signatures_info:
        signature = sig_info['signature']
        relative_string_offset = sig_info['relative_string_offset']
        signature_len = len(signature)
        current_offset = 0
        bPrinter(f"[String Search] Searching for signature: {signature.hex()} ('{sig_info['description']}')")
        while current_offset < data_len:
            signature_offset = data.find(signature, current_offset)
            if signature_offset == -1:
                break
            string_start_offset = signature_offset + relative_string_offset
            if string_start_offset < 0 or string_start_offset >= data_len:
                bPrinter(f"Warning: Calculated string offset {string_start_offset:08X} for signature at {signature_offset:08X} is out of data bounds.")
                current_offset = signature_offset + signature_len
                continue
            extracted_string_bytes = b""
            string_search_end = min(data_len, string_start_offset + max_string_length)
            string_end_offset = string_start_offset
            if string_start_offset < data_len:
                for i in range(string_start_offset, string_search_end):
                    if i >= data_len:
                        break
                    byte = data[i]
                    if byte in ALLOWED_CHARS_BYTES:
                        extracted_string_bytes += bytes([byte])
                        string_end_offset = i + 1
                    else:
                        break
            extracted_string_text = None
            is_valid_string = False
            string_context_before_data = None
            string_context_after_data = None
            if extracted_string_bytes:
                try:
                    extracted_string_text = extracted_string_bytes.decode('ascii')
                    if len(extracted_string_text) >= min_string_length:
                        is_valid_string = True
                        string_context_before_start = max(0, string_start_offset - string_context_bytes)
                        string_context_after_end = min(data_len, string_end_offset + string_context_bytes)
                        string_context_before_data = data[string_context_before_start : string_start_offset]
                        string_context_after_data = data[string_end_offset : string_context_after_end]
                except UnicodeDecodeError:
                    bPrinter(f"Warning: UnicodeDecodeError at {string_start_offset:08X} trying to decode potential string.")
                    pass
            context_before_start = max(0, signature_offset - context_bytes)
            context_after_end = min(data_len, signature_offset + signature_len + context_bytes)
            context_before_data = data[context_before_start : signature_offset]
            context_after_data = data[signature_offset + signature_len : context_after_end]
            results.append({
                'type': 'fixed_signature_string',
                'signature_offset': signature_offset,
                'signature': signature.hex(),
                'signature_description': sig_info['description'],
                'context_before': context_before_data.hex(),
                'context_after': context_after_data.hex(),
                'string_found': is_valid_string,
                'string_offset': string_start_offset if is_valid_string else None,
                'string': extracted_string_text if is_valid_string else None,
                'string_context_before': string_context_before_data.hex() if string_context_before_data is not None else None,
                'string_context_after': string_context_after_data.hex() if string_context_after_data is not None else None
            })
            current_offset = signature_offset + signature_len
    bPrinter("[String Search] Fixed signature search complete.")
    return results

# --- New: Robust texture & mesh linking pass ---------------------------------

# Required header checks (fast sanity)
# SOF header constants (positions with stable constants from your spec)
SOF_HDR0_CONSTS = [
    (0x00, bytes.fromhex("10 00 00 00")),
    (0x08, bytes.fromhex("2D 00 02 1C")),
]
SOF_HDR1_CONSTS = [
    (0x38, bytes.fromhex("2D 00 02 1C")),
]

# Texture-name header variants (exact, as provided)
TEX_HDR_VARIANTS = [
    bytes.fromhex("02 11 01 00 02 00 00 00 14 00 00 00 2D 00 02 1C"),
    bytes.fromhex("02 11 01 00 02 00 00 00 18 00 00 00 2D 00 02 1C"),
    bytes.fromhex("02 11 01 00 02 00 00 00 10 00 00 00 2D 00 02 1C"),
]
REL_STRING_OFFSET_FROM_TEX_HDR = 16  # your spec

TLFD_MARKER = b"TLFD"
EOF_MARKER  = bytes.fromhex("16 EA 00 00 05 00 00 00 2D 00 02 1C 01 00 00 00 00")

# Mesh chunk regex (same as original)
MESH_REGEX = re.compile(b"\x33\xEA\x00\x00....\x2D\x00\x02\x1C", re.DOTALL)

def _check_required_headers(data: bytes) -> bool:
    ok = True
    for off, sig in SOF_HDR0_CONSTS:
        if len(data) < off + len(sig) or data[off:off+len(sig)] != sig:
            bPrinter(f"[Header Check] SOF main header mismatch at 0x{off:02X}.", console_colour="yellow")
            ok = False
    for off, sig in SOF_HDR1_CONSTS:
        if len(data) < off + len(sig) or data[off:off+len(sig)] != sig:
            bPrinter(f"[Header Check] SOF second header mismatch at 0x{off:02X}.", console_colour="yellow")
            ok = False
    if ok:
        bPrinter("[Header Check] Required SOF headers present (both).", console_colour="green")
    else:
        bPrinter("[Header Check] One or more required headers missing; continuing defensively.", console_colour="red")
    return ok

def _iter_all_occurrences(data: bytes, needle: bytes):
    start = 0
    nlen = len(needle)
    dlen = len(data)
    while True:
        idx = data.find(needle, start)
        if idx == -1:
            return
        yield idx
        start = idx + nlen

def _extract_ascii_from(data: bytes, start_off: int, max_len: int) -> str | None:
    dlen = len(data)
    if start_off >= dlen:
        return None
    out = bytearray()
    end = min(dlen, start_off + max_len)
    for i in range(start_off, end):
        b = data[i]
        if b in ALLOWED_CHARS_BYTES:
            out.append(b)
        else:
            break
    if len(out) >= MIN_EXTRACTED_STRING_LENGTH:
        try:
            return out.decode("ascii")
        except Exception:
            return None
    return None

def build_texture_mesh_links(data: bytes) -> tuple[dict[int, list[str]], dict[str, str], set[str]]:
    """
    Pass 1: scan file for texture headers→names, TLFD markers, mesh chunk headers.
    Pass 2: walk events in order and associate the last texture set (after TLFD if present)
            to the next mesh encountered.

    Returns tuple:
      - links: {mesh_chunk_offset: [tex_names]}
      - resolved_paths: {lower(tex_name): source_path from SQLite (if available)}
      - all_texture_names_found: {set of all unique texture names found}
    """
    links: dict[int, list[str]] = {}
    resolved_paths: dict[str, str] = {}
    all_texture_names_found: set[str] = set()
    events = []  # (offset, type, payload)

    # Required header sanity (non-fatal)
    _check_required_headers(data)

    # Texture headers → texture names
    tex_hits = 0
    for hdr in TEX_HDR_VARIANTS:
        for off in _iter_all_occurrences(data, hdr):
            name = _extract_ascii_from(data, off + REL_STRING_OFFSET_FROM_TEX_HDR, MAX_POTENTIAL_STRING_LENGTH)
            if name:
                tex_hits += 1
                events.append((off, "tex_name", name))
                all_texture_names_found.add(name)
                # Attempt to resolve to a full path via SQLite
                _maybe_cache_texture_path(name, resolved_paths)
    if tex_hits == 0:
        bPrinter("[TexScan] No texture strings found via header variants.", console_colour="yellow")
    else:
        bPrinter(f"[TexScan] Collected {tex_hits} texture name(s).", console_colour="green")

    # TLFD markers
    tlfd_hits = 0
    for off in _iter_all_occurrences(data, TLFD_MARKER):
        tlfd_hits += 1
        events.append((off, "tlfd", None))
    bPrinter(f"[TLFD] Found {tlfd_hits} TLFD marker(s).", console_colour="green" if tlfd_hits > 0 else "yellow")

    # Mesh chunks
    mesh_hits = 0
    for m in MESH_REGEX.finditer(data):
        events.append((m.start(), "mesh", None))
        mesh_hits += 1
    bPrinter(f"[MeshScan] Found {mesh_hits} mesh chunk header(s).", console_colour="green" if mesh_hits > 0 else "yellow")

    # EOF
    eof_off = data.find(EOF_MARKER)
    if eof_off != -1:
        events.append((eof_off, "eof", None))
        bPrinter(f"[EOF] EOF marker detected at {eof_off:08X}.", console_colour="green")
    else:
        bPrinter("[EOF] EOF marker not detected; file may still be valid.", console_colour="yellow")

    # Sort by offset
    events.sort(key=lambda x: x[0])

    # Association logic:
    # - accumulate pending texture names until TLFD
    # - when TLFD appears, snapshot the current pending set (if any)
    # - the NEXT mesh after TLFD gets that snapshot
    # - if TLFD is missing, associate the current pending set to the next mesh
    pending_textures: list[str] = []
    snapshot_after_tlfd: list[str] | None = None

    for off, etype, payload in events:
        if etype == "tex_name":
            pending_textures.append(payload)  # payload is name
        elif etype == "tlfd":
            # Snapshot current pending textures; they will apply to the next mesh
            snapshot_after_tlfd = pending_textures.copy() if pending_textures else []
        elif etype == "mesh":
            if snapshot_after_tlfd is not None:
                links[off] = snapshot_after_tlfd.copy()
                # clear only the snapshot; keep pending in case multiple TLFD→mesh groups exist
                snapshot_after_tlfd = None
                pending_textures.clear()
            elif pending_textures:
                # No TLFD seen: still associate most recent textures
                links[off] = pending_textures.copy()
                pending_textures.clear()
            else:
                # No textures seen: leave empty (no entry)
                pass
        elif etype == "eof":
            break

    # Log summary to Blender text editor
    bPrinter("\n--- Texture ↔ Mesh Links ---", to_blender_editor=True)
    if links:
        for moff, names in links.items():
            line = f"[Link] MeshChunk@{moff:08X} -> {', '.join(names) if names else '(no textures)'}"
            bPrinter(line, to_blender_editor=True)
    else:
        bPrinter("[Link] No mesh↔texture associations could be established.", to_blender_editor=True)
    return links, resolved_paths, all_texture_names_found

# --- SQLite texture index -----------------------------------------

USE_SQLITE_DB_LOOKUP = True
SQLITE_TABLE = "png_index"

_sqlite_conn = None

def _open_sqlite_if_configured() -> sqlite3.Connection | None:
    global _sqlite_conn
    if not USE_SQLITE_DB_LOOKUP:
        return None

    # Get path dynamically from the scene property set by the driver script
    try:
        # Check if we are in a context where bpy.context is available
        if bpy.context and bpy.context.scene:
            main_db_path = bpy.context.scene.get("tsg_db_path")
        else:
            bPrinter(f"[SQLite] bpy.context.scene is not available. DB lookup unavailable.", console_colour="red", to_blender_editor=True)
            main_db_path = None

    except Exception as e:
        bPrinter(f"[SQLite] Failed to access bpy.context.scene: {e}", console_colour="red", to_blender_editor=True)
        main_db_path = None

    if not main_db_path:
        bPrinter(f"[SQLite] 'tsg_db_path' custom property not found or empty on scene. DB lookup unavailable.", console_colour="red", to_blender_editor=True)
        return None

    try:
        if _sqlite_conn is None:
            db_path = Path(main_db_path)
            if not db_path.exists():
                bPrinter(f"[SQLite] DB not found at: {main_db_path}", console_colour="yellow", to_blender_editor=True)
                return None
            _sqlite_conn = sqlite3.connect(str(db_path))
            bPrinter(f"[SQLite] Opened DB at: {main_db_path}", console_colour="green", to_blender_editor=True)
        return _sqlite_conn
    except Exception as e:
        bPrinter(f"[SQLite] Failed to open DB at '{main_db_path}': {e}", console_colour="red", to_blender_editor=True)
        return None

def _normalize_tex_name(name: str) -> str:
    n = name.strip()
    if n.lower().endswith('.png'):
        n = n[: -4]
    return n.lower()

def _resolve_texture_path_from_db(tex_name: str) -> str | None:
    conn = _open_sqlite_if_configured()
    if conn is None:
        return None
    try:
        norm = _normalize_tex_name(tex_name)
        cur = conn.cursor()
        cur.execute(
            f"SELECT source_path FROM {SQLITE_TABLE} WHERE LOWER(REPLACE(source_file_name, '.png', '')) = ? LIMIT 1",
            (norm,)
        )
        row = cur.fetchone()
        bPrinter(f"[SQLite] Lookup for '{tex_name}' (normalized: '{norm}') returned: {row}", console_colour="green" if row else "yellow", to_blender_editor=True)
        return row[0] if row and row[0] else None
    except Exception as e:
        bPrinter(f"[SQLite] Lookup error for '{tex_name}': {e}", console_colour="yellow", to_blender_editor=True)
        return None

def _maybe_cache_texture_path(tex_name: str, cache: dict[str, str]) -> None:
    key = _normalize_tex_name(tex_name)
    if key in cache:
        bPrinter(f"[SQLite] Cache hit for '{tex_name}': {cache[key]}", console_colour="green", to_blender_editor=True)
        return
    path = _resolve_texture_path_from_db(tex_name)
    if path:
        cache[key] = path
    bPrinter(f"[SQLite] Cached path for '{tex_name}': {path if path else 'NOT_FOUND'}", console_colour="green" if path else "yellow", to_blender_editor=True)

# --- Material helpers ---------------------------------------------------------

_material_cache: dict[str, bpy.types.Material] = {}

def _ensure_material_for_texture(tex_name: str, resolved_paths: dict[str, str]) -> bpy.types.Material | None:
    try:
        key = _normalize_tex_name(tex_name)
        mat_name = f"TEX_{key}"
        if key in _material_cache:
            return _material_cache[key]
        mat = bpy.data.materials.get(mat_name)
        if mat is None:
            mat = bpy.data.materials.new(mat_name)
        mat.use_nodes = True
        nt = mat.node_tree
        nodes = nt.nodes
        links = nt.links
        # Keep Output node if present, clear others
        out = next((n for n in nodes if n.type == 'OUTPUT_MATERIAL'), None)
        for n in list(nodes):
            if n != out:
                nodes.remove(n)
        if out is None:
            out = nodes.new('ShaderNodeOutputMaterial')
            out.location = (400, 0)
        bsdf = nodes.new('ShaderNodeBsdfPrincipled')
        bsdf.location = (150, 0)
        img_node = nodes.new('ShaderNodeTexImage')
        img_node.location = (-200, 0)

        # Attempt to load image from resolved db path
        img = None
        relative_path = resolved_paths.get(key) # This is the 'db_source_path'

        if relative_path:
            gameroot_path = None
            try:
                # Check if we are in a context where bpy.context is available
                if bpy.context and bpy.context.scene:
                    gameroot_path = bpy.context.scene.get("tsg_gameroot_path")
                else:
                    bPrinter("[Material] bpy.context.scene not available.", console_colour="red")
            except Exception as e:
                    bPrinter(f"[Material] Error accessing scene or scene property 'tsg_gameroot_path': {e}", console_colour="red")

            if gameroot_path:
                # Construct the full absolute path as requested: gameroot + "GameFiles/STROUT/" + db_source_path
                absolute_path = Path(gameroot_path) / "GameFiles" / "STROUT" / relative_path

                # Prepend the long path prefix if on Windows
                if sys.platform == 'win32' and not str(absolute_path).startswith('\\\\?\\'):
                    absolute_path = Path(f"\\\\?\\{str(absolute_path)}")
                    bPrinter(f"[Material] Applied Windows long path prefix. Attempting load from: {absolute_path}", require_debug_mode=True)
                else:
                    bPrinter(f"[Material] Attempting to load '{tex_name}' from: {absolute_path}", require_debug_mode=True)

                if absolute_path.exists():
                    try:
                        img = bpy.data.images.load(str(absolute_path), check_existing=True)
                    except Exception as e:
                        bPrinter(f"[Material] Failed to load image for '{tex_name}' from '{absolute_path}': {e}", console_colour="yellow")
                else:
                    bPrinter(f"[Material] File not found at constructed path: {absolute_path}", console_colour="yellow")
            else:
                bPrinter(f"[Material] 'tsg_gameroot_path' not set in scene. Cannot resolve '{relative_path}'.", console_colour="red")
        else:
            bPrinter(f"[Material] No resolved DB path found for '{tex_name}' (key: '{key}').", console_colour="yellow")

        img_node.image = img
        # --- MODIFICATION END ---

        try:
            links.new(img_node.outputs.get('Color'), bsdf.inputs.get('Base Color'))
        except Exception:
            pass
        if 'Alpha' in img_node.outputs and 'Alpha' in bsdf.inputs:
            try:
                links.new(img_node.outputs['Alpha'], bsdf.inputs['Alpha'])
            except Exception:
                pass
        try:
            links.new(bsdf.outputs.get('BSDF'), out.inputs.get('Surface'))
        except Exception:
            pass
        _material_cache[key] = mat
        return mat
    except Exception as e:
        bPrinter(f"[Material] Error creating material for '{tex_name}': {e}", console_colour="red")
        return None

def _create_materials_for_all_textures(links: dict[int, list[str]], resolved_paths: dict[str, str]) -> None:
    all_names: set[str] = set()
    for names in links.values():
        all_names.update(names)
    if not all_names:
        return
    bPrinter(f"[Material] Creating materials for {len(all_names)} texture(s).")
    for n in sorted(all_names):
        _ensure_material_for_texture(n, resolved_paths)

# --- Blender Addon Components ---

class SimpGameImport(bpy.types.Operator, ImportHelper):
    """Blender Operator for importing The Simpsons Game files with texture↔mesh linking."""
    bl_idname = "custom_import_scene.simpgame"
    bl_label = "Import"
    bl_options = {'PRESET', 'UNDO'}
    filter_glob: StringProperty(
        default="*.preinstanced",
        options={'HIDDEN'},
    )
    filepath: StringProperty(subtype='FILE_PATH',)
    files: CollectionProperty(type=bpy.types.PropertyGroup)

    def draw(self, context: bpy.types.Context) -> None:
        pass

    def execute(self, context: bpy.types.Context) -> set:
        bPrinter("== The Simpsons Game Import Log ==", to_blender_editor=True, log_as_metadata=False)
        bPrinter("Importer Version: {}.{}.{}".format(*bl_info['version']), to_blender_editor=True, log_as_metadata=False)
        bPrinter(f"Importing file: {self.filepath}", to_blender_editor=True, log_as_metadata=True)
        file_path = Path(self.filepath)
        bPrinter(f"File size: {file_path.stat().st_size} bytes", to_blender_editor=True, log_as_metadata=False)
        bPrinter(f"File name: {file_path.name}", to_blender_editor=True, log_as_metadata=False)
        bPrinter(f"Output file: {file_path.stem}.blend", to_blender_editor=True, log_as_metadata=False)
        filename = file_path.stem
        bPrinter(f"{filename}", log_as_metadata=True, metadata_key="LOD")

        try:
            with open(self.filepath, "rb") as cur_file:
                tmpRead = cur_file.read()
        except FileNotFoundError:
            bPrinter(f"[Error] File not found: {self.filepath})")
            return {'CANCELLED'}
        except Exception as e:
            bPrinter(f"[Error] Failed to read file {self.filepath}: {e}")
            return {'CANCELLED'}

        # --- Dedicated texture pass ---
        bPrinter("\n--- Texture String Pass ---", to_blender_editor=True)
        texture_links_by_mesh_offset, texture_paths_by_name, all_found_tex_names = build_texture_mesh_links(tmpRead)
        # Create materials up-front for all discovered textures
        #_create_materials_for_all_textures(all_found_tex_names, texture_paths_by_name)

        # --- Log all found texture strings and their resolved paths ---
        bPrinter("\n--- All Found Texture Strings & DB Paths ---", to_blender_editor=True)
        if all_found_tex_names:
            sorted_names = sorted(list(all_found_tex_names), key=lambda s: s.lower())
            bPrinter(f"Found {len(sorted_names)} unique texture strings. Querying DB...", to_blender_editor=True)

            # Get gameroot path once
            gameroot_path = None
            try:
                if bpy.context and bpy.context.scene:
                    gameroot_path = bpy.context.scene.get("tsg_gameroot_path")
            except Exception:
                pass # Fail silently, will be handled in loop

            for name in sorted_names:
                key = _normalize_tex_name(name)
                relative_path = texture_paths_by_name.get(key)

                log_path = "NOT_FOUND_IN_DB"
                if relative_path:
                    if gameroot_path:
                        log_path = str(Path(gameroot_path) / "GameFiles" / "STROUT" / relative_path)
                    else:
                        log_path = f"{relative_path} (tsg_gameroot_path not set)"

                bPrinter(f"{name} -- {log_path}", to_blender_editor=True)
        else:
            bPrinter("No texture strings were found in the file.", to_blender_editor=True)


        # --- Perform original fixed signature detection (kept for extra visibility) ---
        bPrinter("\n--- Found Embedded Strings (Fixed Signature Scan) ---", to_blender_editor=True)
        string_results = find_strings_by_signature_in_data(
            tmpRead,
            FIXED_SIGNATURES_TO_CHECK,
            MAX_POTENTIAL_STRING_LENGTH,
            MIN_EXTRACTED_STRING_LENGTH,
            CONTEXT_SIZE,
            STRING_CONTEXT_SIZE
        )
        found_string_count = 0
        for item in string_results:
            if item['type'] == 'fixed_signature_string' and item['string_found']:
                found_string_count += 1
                bPrinter(f"{item['string_offset']:08X}: {item['string']}", to_blender_editor=True)

        if found_string_count == 0:
            bPrinter("[String Found] No valid strings found for configured signatures.", to_blender_editor=True)
        else:
            bPrinter(f"[String Found] Total {found_string_count} valid strings found.", to_blender_editor=True)

        # --- Mesh Import Process ---
        bPrinter("\n--- Mesh Import Process ---")
        cur_collection = bpy.data.collections.new("New Mesh")
        bpy.context.scene.collection.children.link(cur_collection)

        mshBytes = MESH_REGEX  # use the compiled regex
        mesh_iter = 0

        data_io = io.BytesIO(tmpRead)

        for x in mshBytes.finditer(tmpRead):
            mesh_chunk_off = x.start()

            data_io.seek(x.end() + 4)
            try:
                FaceDataOff = int.from_bytes(data_io.read(4), byteorder='little')
                MeshDataSize = int.from_bytes(data_io.read(4), byteorder='little')
                MeshChunkStart = data_io.tell()
                data_io.seek(0x14, 1)
                mDataTableCount = int.from_bytes(data_io.read(4), byteorder='big')
                mDataSubCount = int.from_bytes(data_io.read(4), byteorder='big')
                bPrinter(f"[Mesh {mesh_iter}] Found chunk at {x.start():08X}. FaceDataOff: {FaceDataOff}, MeshDataSize: {MeshDataSize}, mDataTableCount: {mDataTableCount}, mDataSubCount: {mDataSubCount}")

                # --- Log linked textures with their full paths ---
                linked_tex_names = texture_links_by_mesh_offset.get(mesh_chunk_off, [])

                # Get gameroot path once for this mesh's log
                gameroot_path = None
                try:
                    if bpy.context and bpy.context.scene:
                        gameroot_path = bpy.context.scene.get("tsg_gameroot_path")
                except Exception:
                    pass # Fail silently, will be handled in loop

                if linked_tex_names:
                    log_entries = []
                    for name in linked_tex_names:
                        # Use the same normalization as the DB cache to find the path
                        key = _normalize_tex_name(name)
                        relative_path = texture_paths_by_name.get(key) # Get path, default if not found

                        log_path = "N/A_IN_CACHE"
                        if relative_path:
                            if gameroot_path:
                                full_path = Path(gameroot_path) / "GameFiles" / "STROUT" / relative_path
                                if sys.platform == 'win32':
                                    full_path = Path(f"\\\\?\\{str(full_path)}")
                                log_path = str(full_path)
                                if not full_path.exists():
                                    log_path += " (ERROR: texture file not found)"
                                else:
                                    log_path += " (note: texture detected)"
                            else:
                                log_path = f"{relative_path} (tsg_gameroot_path not set)"

                        log_entries.append(f"{name} -- {log_path}")
                    bPrinter(f"[Mesh {mesh_iter}] Linked textures: {', '.join(log_entries)}", to_blender_editor=True)
                else:
                    bPrinter(f"[Mesh {mesh_iter}] Linked textures: (none)", to_blender_editor=True)
                # --- END ---

            except Exception as e:
                bPrinter(f"[Error] Failed to read mesh chunk header data at {x.start():08X}: {e}")
                continue

            for i in range(mDataTableCount):
                data_io.seek(4, 1)
                data_io.read(4)

            mDataSubStart = data_io.tell()

            for i in range(mDataSubCount):
                try:
                    data_io.seek(mDataSubStart + i * 0xC + 8)
                    offset = int.from_bytes(data_io.read(4), byteorder='big')
                    data_io.seek(offset + MeshChunkStart + 0xC)
                    VertCountDataOff = int.from_bytes(data_io.read(4), byteorder='big') + MeshChunkStart
                    data_io.seek(VertCountDataOff)
                    VertChunkTotalSize = int.from_bytes(data_io.read(4), byteorder='big')
                    VertChunkSize = int.from_bytes(data_io.read(4), byteorder='big')
                    if VertChunkSize <= 0:
                        bPrinter(f"[Mesh {mesh_iter}_{i}] Warning: VertChunkSize is non-positive ({VertChunkSize}). Skipping mesh part.")
                        continue
                    VertCount = int(VertChunkTotalSize / VertChunkSize)
                    data_io.seek(8, 1)
                    VertexStart = int.from_bytes(data_io.read(4), byteorder='big') + FaceDataOff + MeshChunkStart
                    data_io.seek(0x14, 1)
                    face_count_bytes_offset = data_io.tell()
                    if face_count_bytes_offset + 4 > len(tmpRead):
                        bPrinter(f"[Mesh {mesh_iter}_{i}] Error: Insufficient data to read FaceCount at offset {face_count_bytes_offset:08X}. Skipping mesh part.")
                        continue
                    FaceCount = int(int.from_bytes(data_io.read(4), byteorder='big') / 2)
                    data_io.seek(4, 1)
                    FaceStart = int.from_bytes(data_io.read(4), byteorder='big') + FaceDataOff + MeshChunkStart

                    bPrinter(f"[MeshPart {mesh_iter}_{i}] Reading data. VertCount: {VertCount}, FaceCount: {FaceCount}, VertexStart: {VertexStart:08X}, FaceStart: {FaceStart:08X}")

                except Exception as e:
                    bPrinter(f"[Error] Failed to read sub-mesh header data for part {mesh_iter}_{i}: {e}")
                    continue

                data_io.seek(FaceStart)
                StripList = []
                tmpList = []
                try:
                    if FaceStart < 0 or FaceStart >= len(tmpRead):
                        bPrinter(f"[MeshPart {mesh_iter}_{i}] Error: FaceStart offset {FaceStart:08X} is out of bounds. Skipping face data read.")
                        FaceCount = 0
                    else:
                        data_io.seek(FaceStart)
                        if FaceStart + FaceCount * 2 > len(tmpRead):
                            bPrinter(f"[MeshPart {mesh_iter}_{i}] Warning: Predicted face data size ({FaceCount * 2} bytes) exceeds file bounds from FaceStart {FaceStart:08X}. Reading available data.")
                            FaceCount = (len(tmpRead) - FaceStart) // 2
                            bPrinter(f"[MeshPart {mesh_iter}_{i}] Adjusted FaceCount to {FaceCount} based on available data.")

                    for f in range(FaceCount):
                        if data_io.tell() + 2 > len(tmpRead):
                            bPrinter(f"[MeshPart {mesh_iter}_{i}] Warning: Hit end of data while reading face index {f}. Stopping face index read.")
                            break
                        Indice = int.from_bytes(data_io.read(2), byteorder='big')
                        if Indice == 65535:
                            if tmpList:
                                StripList.append(tmpList.copy())
                            tmpList.clear()
                        else:
                            tmpList.append(Indice)
                    if tmpList:
                        StripList.append(tmpList.copy())
                except Exception as e:
                    bPrinter(f"[Error] Failed to read face indices for mesh part {mesh_iter}_{i}: {e}")
                    continue

                FaceTable = []
                for f in StripList:
                    FaceTable.extend(strip2face(f))

                VertTable = []
                UVTable = []
                CMTable = []
                try:
                    if VertexStart < 0 or VertexStart >= len(tmpRead):
                        bPrinter(f"[MeshPart {mesh_iter}_{i}] Error: VertexStart offset {VertexStart:08X} is out of bounds. Skipping vertex data read.")
                        VertCount = 0

                    for v in range(VertCount):
                        vert_data_start = VertexStart + v * VertChunkSize
                        if vert_data_start + VertChunkSize > len(tmpRead):
                            bPrinter(f"[MeshPart {mesh_iter}_{i}] Warning: Hit end of data while reading vertex {v}. Stopping vertex read.")
                            break

                        data_io.seek(vert_data_start)

                        if data_io.tell() + 12 > len(tmpRead):
                            bPrinter(f"[MeshPart {mesh_iter}_{i}] Warning: Insufficient data for vertex coords at {data_io.tell():08X} for vertex {v}. Skipping.")
                            continue

                        TempVert = struct.unpack('>fff', data_io.read(4 * 3))
                        VertTable.append(TempVert)

                        # Fixed layout discovered by analyzer
                        FIXED_U_OFFSET = 0x14  # 20 bytes (U)
                        FIXED_V_OFFSET = 0x18  # 24 bytes (V)
                        FIXED_CM_OFFSET = 0x1C # 28 bytes (CM U,V)

                        # Main UV (read U and V separately for robustness)
                        u_off = vert_data_start + FIXED_U_OFFSET
                        v_off = vert_data_start + FIXED_V_OFFSET
                        TempU = 0.0
                        TempV = 0.0
                        if u_off + 4 <= len(tmpRead):
                            data_io.seek(u_off)
                            TempU = struct.unpack('>f', data_io.read(4))[0]
                        else:
                            bPrinter(f"[MeshPart {mesh_iter}_{i}] Warning: Insufficient data for U at {u_off:08X} for vertex {v}.", require_debug_mode=True)
                        if v_off + 4 <= len(tmpRead):
                            data_io.seek(v_off)
                            TempV = struct.unpack('>f', data_io.read(4))[0]
                        else:
                            bPrinter(f"[MeshPart {mesh_iter}_{i}] Warning: Insufficient data for V at {v_off:08X} for vertex {v}.", require_debug_mode=True)
                        # Flip V per findings
                        UVTable.append((TempU, 1.0 - TempV))

                        # Secondary (CM) UV
                        cm_off = vert_data_start + FIXED_CM_OFFSET
                        if cm_off + 8 <= len(tmpRead):
                            data_io.seek(cm_off)
                            cm_u, cm_v = struct.unpack('>ff', data_io.read(8))
                        else:
                            bPrinter(f"[MeshPart {mesh_iter}_{i}] Warning: Insufficient data for CM at {cm_off:08X} for vertex {v}.", require_debug_mode=True)
                            cm_u, cm_v = (0.0, 0.0)
                        CMTable.append((cm_u, 1.0 - cm_v))

                    # Diagnostics: stride and UV uniqueness
                    try:
                        uniq_uvs = len({(round(u,5), round(v,5)) for (u,v) in UVTable})
                        bPrinter(f"[MeshPart {mesh_iter}_{i}] Read {len(VertTable)} vertices, {len(UVTable)} UVs, {len(CMTable)} CMs. Stride={VertChunkSize} (0x{VertChunkSize:X}) UniqueUV={uniq_uvs}")
                    except Exception:
                        bPrinter(f"[MeshPart {mesh_iter}_{i}] Read {len(VertTable)} vertices, {len(UVTable)} UVs, {len(CMTable)} CMs.")

                except Exception as e:
                    bPrinter(f"[Error] Failed to read vertex data for mesh part {mesh_iter}_{i}: {e}")
                    continue

                if not VertTable or not FaceTable:
                    bPrinter(f"[MeshPart {mesh_iter}_{i}] Warning: No valid vertices or faces read for mesh part. Skipping mesh creation.")
                    continue

                mesh1 = bpy.data.meshes.new(f"Mesh_{mesh_iter}_{i}")
                # check if mesh1 has .use_auto_smooth attribute before setting it
                if hasattr(mesh1, 'use_auto_smooth'):
                    mesh1.use_auto_smooth = True
                else:
                    bPrinter(f"[MeshPart {mesh_iter}_{i}] Warning: Mesh object does not support 'use_auto_smooth'. Skipping this setting.", require_debug_mode=True, console_colour="yellow", to_blender_editor=True)

                obj = bpy.data.objects.new(f"Mesh_{mesh_iter}_{i}", mesh1)

                cur_collection.objects.link(obj)
                bpy.context.view_layer.objects.active = obj
                obj.select_set(True)
                mesh = bpy.context.object.data
                bm = bmesh.new()

                for v_co in VertTable:
                    bm.verts.new(v_co)
                bm.verts.ensure_lookup_table()
                bm.verts.index_update()
                bPrinter(f"[MeshPart {mesh_iter}_{i}] Added {len(bm.verts)} vertices to BMesh.")

                faces_created_count = 0
                for f_indices in FaceTable:
                    try:
                        valid_face = True
                        face_verts = []
                        for idx in f_indices:
                            if idx < 0 or idx >= len(bm.verts):
                                bPrinter(f"[FaceError] Invalid vertex index {idx} in face {f_indices}. Skipping face.")
                                valid_face = False
                                break
                            face_verts.append(bm.verts[idx])
                        if valid_face:
                            try:
                                bm.faces.new(face_verts)
                                faces_created_count += 1
                            except ValueError as e:
                                bPrinter(f"[FaceWarning] Failed to create face {f_indices} ({len(face_verts)} verts): {e}. Skipping.")
                            except Exception as e:
                                bPrinter(f"[FaceError] Unexpected error creating face {f_indices}: {e}. Skipping.")
                    except Exception as e:
                        bPrinter(f"[FaceError] Unhandled error processing face indices {f_indices}: {e}")
                        continue

                bPrinter(f"[MeshPart {mesh_iter}_{i}] Attempted to create {len(FaceTable)} faces, successfully created {faces_created_count}.")
                # Ensure element indices are valid before using l.vert.index
                bm.verts.ensure_lookup_table()
                bm.faces.ensure_lookup_table()
                bm.verts.index_update()
                bm.edges.index_update()
                bm.faces.index_update()

                if not bm.faces:
                    bPrinter(f"[BMeshWarning] No faces created for mesh {mesh_iter}_{i}. Skipping UV assignment and further processing for this mesh part.")
                    bm.free()
                    if mesh1:
                        if mesh1.users == 1:
                            bpy.data.meshes.remove(mesh1)
                            bPrinter(f"[BMeshWarning] Removed unused mesh data block '{mesh1.name}'.")
                    if obj:
                        if obj.users == 1:
                            for col in bpy.data.collections:
                                if obj.name in col.objects:
                                    col.objects.unlink(obj)
                            bpy.data.objects.remove(obj)
                            bPrinter(f"[BMeshWarning] Removed unused object '{obj.name}'.")
                    continue

                uv_layer = bm.loops.layers.uv.get("uvmap")
                if uv_layer is None:
                    uv_layer = bm.loops.layers.uv.new("uvmap")
                    bPrinter("[Info] Created new 'uvmap' layer.")

                cm_layer = bm.loops.layers.uv.get("CM_uv")
                if cm_layer is None:
                    cm_layer = bm.loops.layers.uv.new("CM_uv")
                    bPrinter("[Info] Created new 'CM_uv' layer.")

                uv_layer_name = uv_layer.name
                cm_layer_name = cm_layer.name

                uv_assigned_count = 0
                cm_assigned_count = 0
                unique_loop_uvs = set()
                unique_loop_cmuvs = set()
                used_vert_indices = set()
                for f in bm.faces:
                    f.smooth = True
                    for l in f.loops:
                        vert_index = l.vert.index
                        used_vert_indices.add(vert_index)
                        if vert_index < 0 or vert_index >= len(UVTable) or vert_index >= len(CMTable):
                            bPrinter(f"[UVError] Vertex index {vert_index} out of range for UV/CM tables ({len(UVTable)}/{len(CMTable)}) during assignment for mesh part {mesh_iter}_{i}. Skipping UV assignment for this loop.")
                            l[uv_layer].uv = (0.0, 0.0)
                            l[cm_layer].uv = (0.0, 0.0)
                            continue
                        try:
                            uv_coords = UVTable[vert_index]
                            if all(math.isfinite(c) for c in uv_coords):
                                l[uv_layer].uv = uv_coords
                                uv_assigned_count += 1
                                unique_loop_uvs.add((round(uv_coords[0],5), round(uv_coords[1],5)))
                            else:
                                bPrinter(f"[Inline-Sanitize] Non-finite main UV for vertex {vert_index} in loop of mesh part {mesh_iter}_{i}. Assigning (0.0, 0.0).", require_debug_mode=True)
                                l[uv_layer].uv = (0.0, 0.0)
                                uv_assigned_count += 1
                            cm_coords = CMTable[vert_index]
                            if all(math.isfinite(c) for c in cm_coords):
                                l[cm_layer].uv = cm_coords
                                cm_assigned_count += 1
                                unique_loop_cmuvs.add((round(cm_coords[0],5), round(cm_coords[1],5)))
                            else:
                                bPrinter(f"[Inline-Sanitize] Non-finite CM UV for vertex {vert_index} in loop of mesh part {mesh_iter}_{i}. Assigning (0.0, 0.0).", require_debug_mode=True)
                                l[cm_layer].uv = (0.0, 0.0)
                                cm_assigned_count += 1
                        except Exception as e:
                            bPrinter(f"[UVError] Failed to assign UV/CM for vertex {vert_index} in loop of mesh part {mesh_iter}_{i}: {e}")
                            l[uv_layer].uv = (0.0, 0.0)
                            l[cm_layer].uv = (0.0, 0.0)
                            continue

                try:
                    bPrinter(f"[MeshPart {mesh_iter}_{i}] Assigned UVs to {uv_assigned_count} loops, CM UVs to {cm_assigned_count} loops. UniqueLoopUV={len(unique_loop_uvs)} UniqueLoopCMUV={len(unique_loop_cmuvs)} UsedVerts={len(used_vert_indices)}")
                except Exception:
                    bPrinter(f"[MeshPart {mesh_iter}_{i}] Assigned UVs to {uv_assigned_count} loops, CM UVs to {cm_assigned_count} loops.")
                bm.to_mesh(mesh)
                bm.free()
                bPrinter(f"[MeshPart {mesh_iter}_{i}] BMesh converted to mesh data.")

                # Ensure the intended UV layer is active for viewport/export
                try:
                    if uv_layer_name in mesh.uv_layers:
                        # Set active and active_render to main UV layer
                        main_idx = None
                        for idx, layer in enumerate(mesh.uv_layers):
                            if layer.name == uv_layer_name:
                                main_idx = idx
                                break
                        if main_idx is not None:
                            mesh.uv_layers.active = mesh.uv_layers[main_idx]
                            mesh.uv_layers.active_index = main_idx
                            mesh.uv_layers[main_idx].active_render = True

                        if cm_layer_name in mesh.uv_layers:
                            for layer in mesh.uv_layers:
                                if layer.name == cm_layer_name:
                                    layer.active_render = False
                                    break
                        bPrinter(f"[MeshPart {mesh_iter}_{i}] Set active UV layer to '{uv_layer_name}'.")
                except Exception as e:
                    bPrinter(f"[UV-Active] Failed to set active UV layer: {e}")

                if uv_layer_name in mesh.uv_layers:
                    sanitize_uvs(mesh.uv_layers[uv_layer_name])
                else:
                    bPrinter(f"[Sanitize] Warning: Main UV layer '{uv_layer_name}' not found on mesh data block after to_mesh for mesh {mesh_iter}_{i}.")

                if cm_layer_name in mesh.uv_layers:
                    sanitize_uvs(mesh.uv_layers[cm_layer_name])
                else:
                    bPrinter(f"[Sanitize] Warning: CM UV layer '{cm_layer_name}' not found on mesh data block after to_mesh for mesh {mesh_iter}_{i}.")

                # Apply the first linked texture's material to this object by default
                try:
                    # Use the original variable that just has names for material linking
                    linked_tex_for_mat = texture_links_by_mesh_offset.get(mesh_chunk_off, [])
                    first_mat_name = linked_tex_for_mat[0] if linked_tex_for_mat else None
                    if first_mat_name:
                        mat = _ensure_material_for_texture(first_mat_name, texture_paths_by_name)
                        if mat:
                            if len(obj.data.materials) == 0:
                                obj.data.materials.append(mat)
                            else:
                                obj.data.materials[0] = mat
                            obj.active_material = mat
                            bPrinter(f"[MeshPart {mesh_iter}_{i}] Assigned material '{mat.name}'.")
                except Exception as e:
                    bPrinter(f"[Material] Failed to assign material on mesh part {mesh_iter}_{i}: {e}", console_colour="yellow")

                obj.rotation_euler = (1.5707963705062866, 0, 0)
                bPrinter(f"[MeshPart {mesh_iter}_{i}] Object created '{obj.name}' and rotated.")

            mesh_iter += 1

        bPrinter("== Import Complete ==", to_blender_editor=True)
        return {'FINISHED'}

class MyAddonPreferences(bpy.types.AddonPreferences):
    bl_idname = __name__
    debugmode: bpy.props.BoolProperty(
        name="Debug Mode",
        description="Enable or disable debug mode",
        default=False
    )
    def draw(self, context: bpy.types.Context) -> None:
        layout = self.layout
        layout.prop(self, "debugmode")

def menu_func_import(self: bpy.types.Menu, context: bpy.types.Context) -> None:
    self.layout.operator(SimpGameImport.bl_idname, text="The Simpsons Game (.rws,dff)")

# --- Registration ---

classes = (
    SimpGameImport,
    MyAddonPreferences,
)

def register() -> None:
    bPrinter("[Register] Registering addon components")
    for cls in classes:
        bpy.utils.register_class(cls)
    bpy.types.TOPBAR_MT_file_import.append(menu_func_import)

def unregister() -> None:
    bPrinter("[Unregister] Unregistering addon components")
    try:
        bpy.types.TOPBAR_MT_file_import.remove(menu_func_import)
    except Exception as e:
        bPrinter(f"[Unregister] Warning removing menu item: {e}", to_blender_editor=True)
    for cls in reversed(classes):
        try:
            bpy.utils.unregister_class(cls)
        except RuntimeError as e:
            bPrinter(f"[Unregister] Warning unregistering class {cls.__name__}: {e}", to_blender_editor=True)

if __name__ == "__main__":
    bPrinter("[Main] Running as main script. Registering.")
    register()

"""Blender addon for importing The Simpsons Game 3D assets."""

bl_info = {
    "name": "The Simpsons Game 3d Asset Importer",
    "author": "Turk & Mister_Nebula & Samarixum",
    "version": (1, 2, 4), # Incremented version
    "blender": (4, 0, 0), # highest supportable version, 2.8 and above
    "location": "File > Import-Export",
    "description": "Import .rws.preinstanced, .dff.preinstanced mesh files from The Simpsons Game (PS3) and detect embedded strings.", # Updated description
    "warning": "",
    "category": "Import-Export",
}

import bpy
import bmesh
import os
import struct
import re
import io
import math
import mathutils
import numpy as np
import string

from bpy.props import (
    StringProperty,
    CollectionProperty
)
from bpy_extras.io_utils import ImportHelper

# --- Global Settings ---
global debug_mode
debug_mode = False # Default value, can be set in the addon preferences

# --- Utility Functions ---

def printc(message: str, colour: str | None = None) -> None:
    """Prints a message to the console with optional colour support."""
    # Simple colour support for Windows/cmd
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
    """Finds a unique metadata key by appending .001, .002, etc. if needed."""
    if base_key not in container.keys():
        return base_key  # Base key is free

    # Look for existing numbered variants
    i = 1
    while True:
        new_key = f"{base_key}.{i:03d}"  # e.g., log_metadata.001
        if new_key not in container.keys():
            return new_key
        i += 1

def bPrinter(
    text: str,
    block_name: str = "SimpGame_Importer_Log",
    to_blender_editor: bool = False,
    print_to_console: bool = True,   # Flag to print log to the console
    console_colour: str = "blue",
    require_debug_mode: bool = False, # Flag to require debug mode
    log_as_metadata: bool = False,   # Flag to store the log as metadata
    metadata_key: str = "log_metadata"   # Specify the key for metadata storage
) -> None:
    """Appends a message to a text block in Blender's text editor if requested,
    and optionally prints to console. Optionally stores log as metadata."""

    global debug_mode

    # Only try to write to Blender's text editor if requested and bpy.data has 'texts'
    try:
        if __name__ in bpy.context.preferences.addons:
            # Access preferences if the addon name is found
            debug_mode = bpy.context.preferences.addons[__name__].preferences.debugmode
    except Exception as e:
        # Catch any other potential errors during preference access
        printc(f"[Log Error] Could not access addon preferences for '{__name__}': {e}. Assuming debug_mode=False.")
        debug_mode = False # Fallback safely

    # Only proceed if debug mode is not required OR if it is required and enabled
    if not require_debug_mode or debug_mode:
        # Print to the console for immediate feedback, based on the flag
        if print_to_console:
            printc(text, colour=console_colour) # Use the printc function for coloured output
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
    """Checks for and sanitizes non-finite UV coordinates in a UV layer."""
    bPrinter(f"[Sanitize] Checking UV layer: {uv_layer.name}")

    # Check if uv_layer.data is accessible and has elements
    if not uv_layer.data:
        bPrinter(f"[Sanitize] Warning: UV layer '{uv_layer.name}' has no data.")
        return

    sanitized_count = 0
    for uv_loop in uv_layer.data:
        # Check for NaN or infinity
        if not all(math.isfinite(c) for c in uv_loop.uv):
            bPrinter(f"[Sanitize] Non-finite UV replaced with (0.0, 0.0): {uv_loop.uv[:]}", require_debug_mode=True)
            uv_loop.uv.x = 0.0
            uv_loop.uv.y = 0.0
            sanitized_count += 1
    if sanitized_count > 0:
        bPrinter(f"[Sanitize] Sanitized {sanitized_count} non-finite UV coordinates in layer '{uv_layer.name}'.")

def utils_set_mode(mode: str) -> None:
    """Safely sets the object mode."""
    bPrinter(f"[SetMode] Setting mode to {mode}")
    if bpy.ops.object.mode_set.poll():
        bpy.ops.object.mode_set(mode=mode, toggle=False)

def strip2face(strip: list) -> list:
    """Converts a triangle strip into a list of triangle faces."""
    bPrinter(f"[Strip2Face] Converting strip of length {len(strip)} to faces", require_debug_mode=True)
    flipped = False
    tmp_table = []
    # Need at least 3 indices to form a triangle strip
    if len(strip) < 3:
        bPrinter(f"[Strip2Face] Strip too short ({len(strip)}) to form faces. Skipping.")
        return []

    for x in range(len(strip)-2):
        v1 = strip[x]
        v2 = strip[x+1]
        v3 = strip[x+2]
        # Check for degenerate triangles (indices are the same)
        if v1 == v2 or v1 == v3 or v2 == v3:
            bPrinter(f"[Strip2Face] Skipping degenerate face in strip at index {x} with indices ({v1}, {v2}, {v3})", require_debug_mode=True)
            flipped = not flipped # Still flip for correct winding of subsequent faces
            continue # Skip this specific face

        if flipped:
            tmp_table.append((v3, v2, v1)) # Reversed winding for flipped faces
        else:
            tmp_table.append((v2, v3, v1)) # Standard winding
        flipped = not flipped # Toggle flipped state for the next iteration

    bPrinter(f"[Strip2Face] Generated {len(tmp_table)} faces from strip.", require_debug_mode=True)
    return tmp_table

# --- String Detection Logic ---

# Characters typically allowed in programmer-defined strings
ALLOWED_CHARS = string.ascii_letters + string.digits + '_-.'
ALLOWED_CHARS_BYTES = ALLOWED_CHARS.encode('ascii') # Convert allowed chars to bytes

# Configuration for String Detection
FIXED_SIGNATURES_TO_CHECK = [
    {'signature': bytes.fromhex('0211010002000000'), 'relative_string_offset': 16, 'description': 'String Block Header (General, 8 bytes)'},
    {'signature': bytes.fromhex('0211010002000000140000002d00021c'), 'relative_string_offset': 16, 'description': 'String Block Header (Subtype A, 16 bytes)'},
    {'signature': bytes.fromhex('0211010002000000180000002d00021c'), 'relative_string_offset': 16, 'description': 'String Block Header (Subtype B, 16 bytes) - Hypothesized'},
    {'signature': bytes.fromhex('905920010000803f0000803f0000803f'), 'relative_string_offset': 16, 'description': 'Another Block Type Header (16 bytes, Common Float Pattern)'} # Corrected based on common 803f pattern, PLACEHOLDER: Verify exact bytes and offset
]

# Analysis Settings for String Detection
MAX_POTENTIAL_STRING_LENGTH = 64
MIN_EXTRACTED_STRING_LENGTH = 4
CONTEXT_SIZE = 16 # Bytes around the SIGNATURE / START marker to show
STRING_CONTEXT_SIZE = 5 # Bytes around the STRING to show

def find_strings_by_signature_in_data(data: bytes, signatures_info: list, max_string_length: int, min_string_length: int, context_bytes: int, string_context_bytes: int) -> list:
    """
    Searches binary data for specific byte signatures and attempts to extract
    associated strings at a fixed relative offset.
    Outputs results including context around the signature and string.

    Args:
        data (bytes): The binary data to search within.
        signatures_info (list): A list of dictionaries, each containing 'signature'
                                ('bytes'), 'relative_string_offset' (int), and
                                'description' (str).
        max_string_length (int): Maximum number of bytes to check for a string.
        min_string_length (int): Minimum length for an extracted string to be
                                considered valid.
        context_bytes (int): Bytes of context around the signature.
        string_context_bytes (int): Bytes of context around the extracted string.

    Returns:
        list: A list of dictionaries for found patterns, containing details
            similar to the previous script's output.
    """
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
            # Search for the next occurrence of the signature
            signature_offset = data.find(signature, current_offset)

            if signature_offset == -1:
                # Signature not found further in the data
                break

            # Calculate the potential string start offset
            string_start_offset = signature_offset + relative_string_offset

            # Check if the potential string start is within data bounds
            if string_start_offset < 0 or string_start_offset >= data_len:
                bPrinter(f"Warning: Calculated string offset {string_start_offset:08X} for signature at {signature_offset:08X} is out of data bounds.")
                current_offset = signature_offset + signature_len
                continue


            # --- Attempt to extract string ---
            extracted_string_bytes = b""
            # Limit string search to not go past max_string_length OR data end
            string_search_end = min(data_len, string_start_offset + max_string_length)
            string_end_offset = string_start_offset # Initialize end offset to start

            # Ensure we don't read past the end of the data
            if string_start_offset < data_len:
                for i in range(string_start_offset, string_search_end):
                    if i >= data_len: # Extra safety check, though range should prevent this
                        break
                    byte = data[i]
                    if byte in ALLOWED_CHARS_BYTES:
                        extracted_string_bytes += bytes([byte])
                        string_end_offset = i + 1 # Update end offset (exclusive)
                    else:
                        # Non-allowed character ends the string
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
                        # --- Extract context bytes around the STRING ---
                        string_context_before_start = max(0, string_start_offset - string_context_bytes)
                        string_context_after_end = min(data_len, string_end_offset + string_context_bytes)
                        string_context_before_data = data[string_context_before_start : string_start_offset]
                        string_context_after_data = data[string_end_offset : string_context_after_end]

                except UnicodeDecodeError:
                    bPrinter(f"Warning: UnicodeDecodeError at {string_start_offset:08X} trying to decode potential string.")
                    pass # String is not valid if decoding fails


            # --- Extract context bytes around the SIGNATURE ---
            context_before_start = max(0, signature_offset - context_bytes)
            context_after_end = min(data_len, signature_offset + signature_len + context_bytes)

            context_before_data = data[context_before_start : signature_offset]
            context_after_data = data[signature_offset + signature_len : context_after_end]

            results.append({
                'type': 'fixed_signature_string', # Indicate result type
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

            # Continue search *after* the current signature occurrence
            current_offset = signature_offset + signature_len

    bPrinter("[String Search] Fixed signature search complete.")
    return results

# --- Blender Addon Components ---

class SimpGameImport(bpy.types.Operator, ImportHelper):
    """Blender Operator for importing The Simpsons Game files."""
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
        # No specific import options needed in the file browser.
        pass

    def execute(self, context: bpy.types.Context) -> set:
        """Executes the import process."""
        bPrinter("== The Simpsons Game Import Log ==", to_blender_editor=True, log_as_metadata=False) # Log header to editor
        bPrinter(f"Importing file: {self.filepath}", to_blender_editor=True, log_as_metadata=True)
        bPrinter(f"File size: {os.path.getsize(self.filepath)} bytes", to_blender_editor=True, log_as_metadata=False)
        bPrinter(f"File name: {os.path.basename(self.filepath)}", to_blender_editor=True, log_as_metadata=False)
        bPrinter(f"Output file: {os.path.splitext(os.path.basename(self.filepath))[0]}.blend", to_blender_editor=True, log_as_metadata=False)
        filename = os.path.basename(self.filepath).split('.')[0]
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

        # --- Perform String Detection ---
        bPrinter("\n--- Found Embedded Strings ---", to_blender_editor=True) # Log header to editor
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


        bPrinter("\n--- Mesh Import Process ---") # Log header to editor


        # --- Start Mesh Import (Existing Logic) ---
        cur_collection = bpy.data.collections.new("New Mesh")
        bpy.context.scene.collection.children.link(cur_collection)

        mshBytes = re.compile(b"\x33\xEA\x00\x00....\x2D\x00\x02\x1C", re.DOTALL)
        mesh_iter = 0

        data_io = io.BytesIO(tmpRead)

        for x in mshBytes.finditer(tmpRead):
            data_io.seek(x.end() + 4)
            try:
                FaceDataOff = int.from_bytes(data_io.read(4), byteorder='little')
                MeshDataSize = int.from_bytes(data_io.read(4), byteorder='little')
                MeshChunkStart = data_io.tell()
                data_io.seek(0x14, 1)
                mDataTableCount = int.from_bytes(data_io.read(4), byteorder='big')
                mDataSubCount = int.from_bytes(data_io.read(4), byteorder='big')
                bPrinter(f"[Mesh {mesh_iter}] Found chunk at {x.start():08X}. FaceDataOff: {FaceDataOff}, MeshDataSize: {MeshDataSize}, mDataTableCount: {mDataTableCount}, mDataSubCount: {mDataSubCount}")

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

                        uv_offset = vert_data_start + VertChunkSize - 16
                        if uv_offset < 0 or uv_offset + 8 > len(tmpRead):
                            bPrinter(f"[MeshPart {mesh_iter}_{i}] Warning: Insufficient data for UV coords at {uv_offset:08X} for vertex {v}. Skipping UV.")
                            TempUV = (0.0, 0.0)
                        else:
                            data_io.seek(uv_offset)
                            TempUV = struct.unpack('>ff', data_io.read(4 * 2))
                        UVTable.append((TempUV[0], 1 - TempUV[1]))

                        cm_offset = vert_data_start + VertChunkSize - 8
                        if cm_offset < 0 or cm_offset + 8 > len(tmpRead):
                            bPrinter(f"[MeshPart {mesh_iter}_{i}] Warning: Insufficient data for CM coords at {cm_offset:08X} for vertex {v}. Skipping CM.")
                            TempCM = (0.0, 0.0)
                        else:
                            data_io.seek(cm_offset)
                            TempCM = struct.unpack('>ff', data_io.read(4 * 2))
                        CMTable.append((TempCM[0], 1 - TempCM[1]))

                    bPrinter(f"[MeshPart {mesh_iter}_{i}] Read {len(VertTable)} vertices, {len(UVTable)} UVs, {len(CMTable)} CMs.")

                except Exception as e:
                    bPrinter(f"[Error] Failed to read vertex data for mesh part {mesh_iter}_{i}: {e}")
                    continue

                if not VertTable or not FaceTable:
                    bPrinter(f"[MeshPart {mesh_iter}_{i}] Warning: No valid vertices or faces read for mesh part. Skipping mesh creation.")
                    continue

                mesh1 = bpy.data.meshes.new(f"Mesh_{mesh_iter}_{i}")
                mesh1.use_auto_smooth = True
                obj = bpy.data.objects.new(f"Mesh_{mesh_iter}_{i}", mesh1)
                cur_collection.objects.link(obj)
                bpy.context.view_layer.objects.active = obj
                obj.select_set(True)
                mesh = bpy.context.object.data
                bm = bmesh.new()

                for v_co in VertTable:
                    bm.verts.new(v_co)
                bm.verts.ensure_lookup_table()
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
                for f in bm.faces:
                    f.smooth = True
                    for l in f.loops:
                        vert_index = l.vert.index
                        if vert_index >= len(UVTable) or vert_index >= len(CMTable):
                            bPrinter(f"[UVError] Vertex index {vert_index} out of range for UV/CM tables ({len(UVTable)}/{len(CMTable)}) during assignment for mesh part {mesh_iter}_{i}. Skipping UV assignment for this loop.")
                            l[uv_layer].uv = (0.0, 0.0)
                            l[cm_layer].uv = (0.0, 0.0)
                            continue

                        try:
                            uv_coords = UVTable[vert_index]
                            if all(math.isfinite(c) for c in uv_coords):
                                l[uv_layer].uv = uv_coords
                                uv_assigned_count += 1
                            else:
                                bPrinter(f"[Inline-Sanitize] Non-finite main UV for vertex {vert_index} in loop of mesh part {mesh_iter}_{i}. Assigning (0.0, 0.0).", require_debug_mode=True)
                                l[uv_layer].uv = (0.0, 0.0)
                                uv_assigned_count += 1

                            cm_coords = CMTable[vert_index]
                            if all(math.isfinite(c) for c in cm_coords):
                                l[cm_layer].uv = cm_coords
                                cm_assigned_count += 1
                            else:
                                bPrinter(f"[Inline-Sanitize] Non-finite CM UV for vertex {vert_index} in loop of mesh part {mesh_iter}_{i}. Assigning (0.0, 0.0).", require_debug_mode=True)
                                l[cm_layer].uv = (0.0, 0.0)
                                cm_assigned_count += 1

                        except Exception as e:
                            bPrinter(f"[UVError] Failed to assign UV/CM for vertex {vert_index} in loop of mesh part {mesh_iter}_{i}: {e}")
                            l[uv_layer].uv = (0.0, 0.0)
                            l[cm_layer].uv = (0.0, 0.0)
                            continue

                bPrinter(f"[MeshPart {mesh_iter}_{i}] Assigned UVs to {uv_assigned_count} loops, CM UVs to {cm_assigned_count} loops.")

                bm.to_mesh(mesh)
                bm.free()
                bPrinter(f"[MeshPart {mesh_iter}_{i}] BMesh converted to mesh data.")

                if uv_layer_name in mesh.uv_layers:
                    sanitize_uvs(mesh.uv_layers[uv_layer_name])
                else:
                    bPrinter(f"[Sanitize] Warning: Main UV layer '{uv_layer_name}' not found on mesh data block after to_mesh for mesh {mesh_iter}_{i}.")

                if cm_layer_name in mesh.uv_layers:
                    sanitize_uvs(mesh.uv_layers[cm_layer_name])
                else:
                    bPrinter(f"[Sanitize] Warning: CM UV layer '{cm_layer_name}' not found on mesh data block after to_mesh for mesh {mesh_iter}_{i}.")

                obj.rotation_euler = (1.5707963705062866, 0, 0)
                bPrinter(f"[MeshPart {mesh_iter}_{i}] Object created '{obj.name}' and rotated.")

            mesh_iter += 1

        bPrinter("== Import Complete ==", to_blender_editor=True)
        return {'FINISHED'}

class MyAddonPreferences(bpy.types.AddonPreferences):
    """Defines preferences for the addon."""
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
    """Adds the import option to the Blender file import menu."""
    self.layout.operator(SimpGameImport.bl_idname, text="The Simpsons Game (.rws,dff)")

# --- Registration ---

classes = (
    SimpGameImport,
    MyAddonPreferences,
)

def register() -> None:
    """Registers the addon classes and menu functions."""
    bPrinter("[Register] Registering addon components")
    for cls in classes:
        bpy.utils.register_class(cls)
    bpy.types.TOPBAR_MT_file_import.append(menu_func_import)

def unregister() -> None:
    """Unregisters the addon classes and menu functions."""
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

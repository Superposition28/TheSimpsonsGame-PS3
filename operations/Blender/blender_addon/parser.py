# SPDX-License-Identifier: MIT
"""
Parser module for The Simpsons Game binary files.
Contains logic for RenderWare chunk parsing, material extraction, signature scanning,
and mesh-texture linking.
"""
import re
import string
import struct
from typing import Any, Generator
from .utils.logger import bPrinter
from .materials import _maybe_cache_texture_path

_ALLOWED_CHARS = string.ascii_letters + string.digits + '_-.'
_ALLOWED_CHARS_BYTES = _ALLOWED_CHARS.encode('ascii')
_SOF_HDR0_CONSTS = [
    (0x00, bytes.fromhex("10 00 00 00")),
    (0x08, bytes.fromhex("2D 00 02 1C")),
]
_SOF_HDR1_CONSTS = [
    (0x38, bytes.fromhex("2D 00 02 1C")),
]
_RW_STRUCT_TYPE = bytes.fromhex("01 00 00 00")
_RW_STRING_TYPE = bytes.fromhex("02 00 00 00")
_RW_VERSION = bytes.fromhex("2D 00 02 1C")
_STRING_STRUCT_PAYLOAD_SIZE = 4
_MAX_TEXTURE_STRING_BYTES = 0x80
_TLFD_MARKER = b"TLFD"
_EOF_MARKER  = bytes.fromhex("16 EA 00 00 05 00 00 00 2D 00 02 1C 01 00 00 00 00")



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
MESH_REGEX = re.compile(b"\x33\xEA\x00\x00....\x2D\x00\x02\x1C", re.DOTALL)


def find_strings_by_signature_in_data(data: bytes, signatures_info: list, max_string_length: int, min_string_length: int, context_bytes: int, string_context_bytes: int) -> list:
    """
    Scans binary data for specified signatures and extracts associated ASCII strings.
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
                    if byte in _ALLOWED_CHARS_BYTES:
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


def _iter_texture_names(data: bytes) -> Generator[tuple[int, str], None, None]:
    """Yield names from a validated RenderWare STRUCT + STRING chunk pair."""
    search_offset = 0
    while True:
        string_chunk_offset = data.find(_RW_STRING_TYPE, search_offset)
        if string_chunk_offset == -1:
            return
        search_offset = string_chunk_offset + len(_RW_STRING_TYPE)

        struct_chunk_offset = string_chunk_offset - 16
        if struct_chunk_offset < 0 or string_chunk_offset + 12 > len(data):
            continue
        if data[struct_chunk_offset:struct_chunk_offset + 4] != _RW_STRUCT_TYPE:
            continue
        if int.from_bytes(data[struct_chunk_offset + 4:struct_chunk_offset + 8], "little") != _STRING_STRUCT_PAYLOAD_SIZE:
            continue
        if data[struct_chunk_offset + 8:struct_chunk_offset + 12] != _RW_VERSION:
            continue
        if data[string_chunk_offset + 8:string_chunk_offset + 12] != _RW_VERSION:
            continue

        string_size = int.from_bytes(data[string_chunk_offset + 4:string_chunk_offset + 8], "little")
        string_start = string_chunk_offset + 12
        string_end = string_start + string_size
        if string_size == 0 or string_size > _MAX_TEXTURE_STRING_BYTES or string_end > len(data):
            continue

        string_bytes = data[string_start:string_end].split(b"\x00", maxsplit=1)[0].rstrip(b"\xBF")
        name_end = 0
        while name_end < len(string_bytes) and string_bytes[name_end] in _ALLOWED_CHARS_BYTES:
            name_end += 1
        if name_end == 0:
            continue

        name = string_bytes[:name_end].decode("ascii")
        yield string_chunk_offset - 4, name


def extract_rw_mesh_materials(data: bytes) -> tuple[dict[int, list[str | None]], set[str]]:
    """
    Parses RenderWare clump geometry and material lists to map each EA_MESH (0x0000EA33) chunk offset
    to its exact list of material diffuse texture names (or None if untextured).
    """
    mesh_materials: dict[int, list[str | None]] = {}
    all_textures: set[str] = set()

    def parse_container(offset: int, end: int) -> None:
        curr = offset
        while curr + 12 <= end:
            cid, csize, _ = struct.unpack('<III', data[curr:curr+12])
            payload_start = curr + 12
            payload_end = payload_start + csize
            if payload_end > len(data):
                break

            if cid == 0x0F:  # rwID_GEOMETRY
                geom_mats: list[str | None] = []
                g_curr = payload_start
                while g_curr + 12 <= payload_end:
                    g_cid, g_csize, _ = struct.unpack('<III', data[g_curr:g_curr+12])
                    g_pstart = g_curr + 12
                    g_pend = g_pstart + g_csize
                    if g_pend > payload_end:
                        break

                    if g_cid == 0x08:  # rwID_MATLIST
                        m_curr = g_pstart
                        while m_curr + 12 <= g_pend:
                            m_cid, m_csize, _ = struct.unpack('<III', data[m_curr:m_curr+12])
                            m_pstart = m_curr + 12
                            m_pend = m_pstart + m_csize
                            if m_pend > g_pend:
                                break
                            if m_cid == 0x07:  # rwID_MATERIAL
                                tex_diffuse = None
                                t_curr = m_pstart
                                while t_curr + 12 <= m_pend:
                                    t_cid, t_csize, _ = struct.unpack('<III', data[t_curr:t_curr+12])
                                    t_pstart = t_curr + 12
                                    t_pend = t_pstart + t_csize
                                    if t_pend > m_pend:
                                        break
                                    if t_cid == 0x06:  # rwID_TEXTURE
                                        s_curr = t_pstart
                                        while s_curr + 12 <= t_pend:
                                            s_cid, s_csize, _ = struct.unpack('<III', data[s_curr:s_curr+12])
                                            s_pstart = s_curr + 12
                                            s_pend = s_pstart + s_csize
                                            if s_pend > t_pend:
                                                break
                                            if s_cid == 0x02:  # rwID_STRING (diffuse texture name)
                                                s_bytes = data[s_pstart:s_pend].split(b'\x00', 1)[0].rstrip(b'\xbf')
                                                try:
                                                    name = s_bytes.decode('ascii')
                                                    if name:
                                                        tex_diffuse = name
                                                except UnicodeDecodeError:
                                                    tex_diffuse = None
                                                break
                                            s_curr += 12 + s_csize
                                    t_curr += 12 + t_csize
                                geom_mats.append(tex_diffuse)
                                if tex_diffuse:
                                    all_textures.add(tex_diffuse)
                            m_curr += 12 + m_csize
                    elif g_cid == 0x03:  # rwID_EXTENSION
                        e_curr = g_pstart
                        while e_curr + 12 <= g_pend:
                            e_cid, e_csize, _ = struct.unpack('<III', data[e_curr:e_curr+12])
                            if e_cid == 0xEA33:  # EA_EARS_MESH
                                mesh_materials[e_curr] = list(geom_mats)
                            e_curr += 12 + e_csize
                    g_curr += 12 + g_csize
            elif cid in (0x10, 0x1A, 0x14, 0x03):  # Clump, GeoList, Atomic, Extension
                parse_container(payload_start, payload_end)
            curr += 12 + csize

    parse_container(0, len(data))
    return mesh_materials, all_textures


def build_texture_mesh_links(
    data: bytes, preinstanced_filepath: str | None = None
) -> tuple[dict[int, list[str]], dict[str, str], set[str], dict[int, list[str | None]]]:
    """
    Parses RenderWare chunk hierarchy for material lists and maps each mesh chunk
    to its exact list of material textures (1-to-1 submesh material mapping).
    Returns (links, resolved_paths, all_texture_names_found, mesh_materials_by_offset).
    """
    resolved_paths: dict[str, str] = {}
    _check_required_headers(data)

    mesh_materials_by_offset, all_texture_names_found = extract_rw_mesh_materials(data)

    # Fallback to scanning if chunk tree mapping produced no meshes
    if not mesh_materials_by_offset:
        for off, name in _iter_texture_names(data):
            all_texture_names_found.add(name)

    # Cache texture paths for discovered textures
    for name in all_texture_names_found:
        _maybe_cache_texture_path(name, resolved_paths, preinstanced_filepath)

    # Build legacy links mapping (non-None strings per mesh)
    links: dict[int, list[str]] = {
        moff: [m for m in mlist if m is not None]
        for moff, mlist in mesh_materials_by_offset.items()
    }

    # Diagnostics
    tlfd_hits = sum(1 for _ in _iter_all_occurrences(data, _TLFD_MARKER))
    bPrinter(f"[TLFD] Found {tlfd_hits} TLFD marker(s).", console_colour="green" if tlfd_hits > 0 else "yellow")

    mesh_hits = len(mesh_materials_by_offset)
    bPrinter(f"[MeshScan] Mapped {mesh_hits} mesh chunk(s) to material lists.", console_colour="green" if mesh_hits > 0 else "yellow")

    eof_off = data.find(_EOF_MARKER)
    if eof_off != -1:
        bPrinter(f"[EOF] Clump extension plugin (0xEA16) detected at {eof_off:08X}.", console_colour="green")

    bPrinter("\n--- Texture ↔ Mesh Links ---", to_blender_editor=True)
    if mesh_materials_by_offset:
        for moff, mlist in mesh_materials_by_offset.items():
            formatted = [f"[{i}]: {name if name else '(untextured)'}" for i, name in enumerate(mlist)]
            line = f"[Link] MeshChunk@{moff:08X} -> {', '.join(formatted) if formatted else '(no materials)'}"
            bPrinter(line, to_blender_editor=True)
    else:
        bPrinter("[Link] No mesh↔material associations could be established.", to_blender_editor=True)

    return links, resolved_paths, all_texture_names_found, mesh_materials_by_offset


def _check_required_headers(data: bytes) -> bool:
    """
    Checks if the data contains required SOF headers at expected offsets.
    """
    ok = True
    for off, sig in _SOF_HDR0_CONSTS:
        if len(data) < off + len(sig) or data[off:off+len(sig)] != sig:
            bPrinter(f"[Header Check] SOF main header mismatch at 0x{off:02X}.", console_colour="yellow")
            ok = False
    for off, sig in _SOF_HDR1_CONSTS:
        if len(data) < off + len(sig) or data[off:off+len(sig)] != sig:
            bPrinter(f"[Header Check] SOF second header mismatch at 0x{off:02X}.", console_colour="yellow")
            ok = False
    if ok:
        bPrinter("[Header Check] Required SOF headers present (both).", console_colour="green")
    else:
        bPrinter("[Header Check] One or more required headers missing; continuing defensively.", console_colour="red")
    return ok

def _iter_all_occurrences(data: bytes, needle: bytes) -> Generator[int, Any, None]:
    """
    Generator that yields all start offsets of 'needle' within 'data'.
    """
    start = 0
    nlen = len(needle)
    while True:
        idx = data.find(needle, start)
        if idx == -1:
            return
        yield idx
        start = idx + nlen

def _extract_ascii_from(data: bytes, start_off: int, max_len: int) -> str | None:
    """
    Attempts to extract an ASCII string from 'data' starting at 'start_off'.
    Returns the string if it meets minimum length requirements, else None.
    """
    dlen = len(data)
    if start_off >= dlen:
        return None
    out = bytearray()
    end = min(dlen, start_off + max_len)
    for i in range(start_off, end):
        b = data[i]
        if b in _ALLOWED_CHARS_BYTES:
            out.append(b)
        else:
            break
    if len(out) >= MIN_EXTRACTED_STRING_LENGTH:
        try:
            return out.decode("ascii")
        except Exception:
            return None
    return None

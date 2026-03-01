# SPDX-License-Identifier: MIT
"""
Parser module for The Simpsons Game binary files.
Contains logic for signature scanning, string extraction, and mesh-texture linking.
"""
import re
import string
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
_TEX_HDR_VARIANTS = [
    bytes.fromhex("02 11 01 00 02 00 00 00 14 00 00 00 2D 00 02 1C"),
    bytes.fromhex("02 11 01 00 02 00 00 00 18 00 00 00 2D 00 02 1C"),
    bytes.fromhex("02 11 01 00 02 00 00 00 10 00 00 00 2D 00 02 1C"),
]
_REL_STRING_OFFSET_FROM_TEX_HDR = 16
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


def build_texture_mesh_links(data: bytes, preinstanced_filepath: str | None = None) -> tuple[dict[int, list[str]], dict[str, str], set[str]]:
    """
    Scans binary data for texture names and established links between meshes and textures.
    Returns a mapping of mesh offsets to texture names, resolved paths, and a set of all textures found.
    """
    links: dict[int, list[str]] = {}
    resolved_paths: dict[str, str] = {}
    all_texture_names_found: set[str] = set()
    events = []

    _check_required_headers(data)

    tex_hits = 0
    for hdr in _TEX_HDR_VARIANTS:
        for off in _iter_all_occurrences(data, hdr):
            name = _extract_ascii_from(data, off + _REL_STRING_OFFSET_FROM_TEX_HDR, MAX_POTENTIAL_STRING_LENGTH)
            if name:
                tex_hits += 1
                events.append((off, "tex_name", name))
                all_texture_names_found.add(name)
                _maybe_cache_texture_path(name, resolved_paths, preinstanced_filepath)

    if tex_hits == 0:
        bPrinter("[TexScan] No texture strings found via header variants.", console_colour="yellow")
    else:
        bPrinter(f"[TexScan] Collected {tex_hits} texture name(s).", console_colour="green")

    tlfd_hits = 0
    for off in _iter_all_occurrences(data, _TLFD_MARKER):
        tlfd_hits += 1
        events.append((off, "tlfd", None))
    bPrinter(f"[TLFD] Found {tlfd_hits} TLFD marker(s).", console_colour="green" if tlfd_hits > 0 else "yellow")

    mesh_hits = 0
    for m in MESH_REGEX.finditer(data):
        events.append((m.start(), "mesh", None))
        mesh_hits += 1
    bPrinter(f"[MeshScan] Found {mesh_hits} mesh chunk header(s).", console_colour="green" if mesh_hits > 0 else "yellow")

    eof_off = data.find(_EOF_MARKER)
    if eof_off != -1:
        events.append((eof_off, "eof", None))
        bPrinter(f"[EOF] EOF marker detected at {eof_off:08X}.", console_colour="green")
    else:
        bPrinter("[EOF] EOF marker not detected; file may still be valid.", console_colour="yellow")

    events.sort(key=lambda x: x[0])

    # --- FIXED ASSOCIATION LOGIC ---
    active_textures: list[str] = []
    has_seen_tex_since_mesh = False

    for off, etype, payload in events:
        if etype == "tex_name":
            if not has_seen_tex_since_mesh:
                active_textures.clear()
                has_seen_tex_since_mesh = True
            active_textures.append(payload)
        elif etype == "mesh":
            has_seen_tex_since_mesh = False
            if active_textures:
                links[off] = active_textures.copy()
        elif etype == "eof":
            break

    bPrinter("\n--- Texture ↔ Mesh Links ---", to_blender_editor=True)
    if links:
        for moff, names in links.items():
            line = f"[Link] MeshChunk@{moff:08X} -> {', '.join(names) if names else '(no textures)'}"
            bPrinter(line, to_blender_editor=True)
    else:
        bPrinter("[Link] No mesh↔texture associations could be established.", to_blender_editor=True)
    return links, resolved_paths, all_texture_names_found



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


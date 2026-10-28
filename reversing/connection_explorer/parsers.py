"""Documented ID fields. Internal pointers and arbitrary integers are not file IDs.

All offsets are payload-relative unless the caller explicitly supplies another
coordinate space. Structural links describe stored fields, not observed gameplay.
"""
from __future__ import annotations

from dataclasses import dataclass
import re
import struct

from audio_subtitles import parse_alb, parse_lh2, parse_smb


@dataclass(frozen=True)
class Identifier:
    namespace: str
    value: str
    role: str
    offset: int
    width: int
    endian: str
    label: str
    confidence: str = "structural"
    doc: str = ""
    region: str = "payload"


DOC = "PS3_GAME/FormatAnalysis/STR/imbedded-formats/"
INVALID_GUIDS = {"0" * 32, "F" * 32, "BADBADBABEEFBEEFEAC15A5591100911"}


def u32(data: bytes, offset: int, order: str = ">") -> int:
    if offset < 0 or offset + 4 > len(data):
        raise ValueError(f"u32 outside payload at {offset:#x}")
    return struct.unpack_from(order + "I", data, offset)[0]


def cstring(data: bytes, offset: int, end: int | None = None) -> str:
    end = len(data) if end is None else end
    if not 0 <= offset < end <= len(data):
        raise ValueError(f"string outside payload at {offset:#x}")
    stop = data.find(b"\0", offset, end)
    if stop < 0:
        raise ValueError(f"unterminated string at {offset:#x}")
    return data[offset:stop].decode("cp1252", errors="replace")


def guid(data: bytes, offset: int, order: str = ">") -> str:
    if offset < 0 or offset + 16 > len(data):
        raise ValueError(f"GUID outside payload at {offset:#x}")
    return "".join(f"{v:08X}" for v in struct.unpack_from(order + "4I", data, offset))


def integer(namespace: str, value: int, role: str, offset: int, label: str,
            doc: str, order: str = "BE", confidence: str = "structural") -> Identifier:
    return Identifier(namespace, f"{value:08X}", role, offset, 4, order, label, confidence, DOC + doc)


def parse_simgroup(data: bytes) -> list[Identifier]:
    if len(data) < 48 or data[8:12] != b"SimG":
        raise ValueError("expected complete SimGroup body (SimG at +8); legacy dumps need base correction")
    result = [integer("simgroup.id", u32(data, 16), "definition", 16, "SimGroup ID", "simgroup.dat.html#header")]
    count, indirect = u32(data, 24), u32(data, 40)
    cursor = u32(data, indirect)
    if count > len(data) // 32:
        raise ValueError("SimGroup entity count exceeds payload")
    for index in range(count):
        if cursor + 32 > len(data):
            raise ValueError("truncated SimGroup entity packet")
        attached, attributes = data[cursor + 18], data[cursor + 19]
        pointer = cursor + 24
        target = pointer + struct.unpack_from(">i", data, pointer)[0]
        value = guid(data, target)
        if value not in INVALID_GUIDS:
            result.append(Identifier("entity.guid", value, "definition", target, 16, "BE words",
                                     f"Entity {index}", doc=DOC + "simgroup.dat.html#entity-entry"))
        result.append(integer("entity.behavior", u32(data, cursor + 28), "value", cursor + 28,
                              f"Entity {index} behavior; no proven file target", "simgroup.dat.html#entity-entry"))
        table = cursor + 32
        if table + 4 * (attached + attributes) > len(data):
            raise ValueError("SimGroup entity pointer tables outside payload")
        for slot in range(attached):
            pointer = table + slot * 4
            target = pointer + struct.unpack_from(">i", data, pointer)[0]
            value = guid(data, target)
            if value not in INVALID_GUIDS:
                result.append(Identifier("asset.guid", value, "reference", target, 16, "BE words",
                                         f"Entity {index}, attached resource {slot}", doc=DOC + "simgroup.dat.html#entity-entry"))
        for slot in range(attributes):
            pointer = table + 4 * (attached + slot)
            target = pointer + struct.unpack_from(">i", data, pointer)[0]
            result.append(integer("attribute.handler", u32(data, target), "value", target,
                                  f"Entity {index}, attribute handler {slot}; semantics unresolved",
                                  "simgroup.dat.html#attribute-packets"))
        cursor = table + 4 * (attached + attributes)
    return result


def parse_uie(data: bytes) -> list[Identifier]:
    if len(data) % 20:
        raise ValueError("UIE payload is not a whole number of observed 20-byte entries")
    result = []
    previous = -1
    for offset in range(0, len(data), 20):
        key = u32(data, offset, "<")
        if key <= previous:
            raise ValueError("UIE keys do not match the documented ascending unique layout")
        previous = key
        result.append(integer("uie.key", key, "definition", offset, "UIE label key", "simgroup.dat.html#uie", "LE"))
        result.append(Identifier("entity.guid", guid(data, offset + 4, "<"), "reference", offset + 4,
                                 16, "LE words → BE canonical", "UIE entity GUID", doc=DOC + "simgroup.dat.html#uie"))
    return result


def parse_bbn(data: bytes) -> list[Identifier]:
    if len(data) < 40:
        raise ValueError("BBN too short for the documented table layout")
    alias_count, rig_count, rig_start, alias_start = struct.unpack_from(">4I", data, 24)
    if rig_start < 40 or alias_start < 40 or rig_start + rig_count * 8 > len(data) or alias_start + alias_count * 16 > len(data):
        raise ValueError("BBN does not match the documented bounded rig/alias tables")
    result, rigs = [], []
    for index in range(rig_count):
        offset = rig_start + index * 8
        name, value = cstring(data, u32(data, offset)), u32(data, offset + 4)
        rigs.append((name, value))
        result.extend([integer("bone.rig", value, "definition", offset + 4, name, "bbn.PS3.html#bunny-binding-join"),
                       integer("bone.hanim", value, "reference", offset + 4, f"Rig {name} → HAnim node ID (pose unresolved)", "bbn.PS3.html#bunny-binding-join")])
    for index in range(alias_count):
        offset = alias_start + index * 16
        name, value, rig = cstring(data, u32(data, offset)), u32(data, offset + 4), u32(data, offset + 8)
        if rig >= len(rigs):
            raise ValueError("BBN alias rig index outside rig table")
        result.append(integer("bone.alias", value, "definition", offset + 4,
                              f"{name} → rig[{rig}] {rigs[rig][0]} / {rigs[rig][1]:08X}", "bbn.PS3.html#bunny-binding-join"))
    return result


def parse_acs(data: bytes) -> list[Identifier]:
    if len(data) < 4 or data[0] != 1 or data[2:4] != b"\0\0":
        raise ValueError("not the documented ACS version-1 header")
    cursor, result = 4, []
    for index in range(data[1]):
        size = u32(data, cursor)
        if size < 76 or size % 4 or cursor + size > len(data):
            raise ValueError("ACS record size outside payload")
        result.append(integer("bone.binding", u32(data, cursor + 8), "reference", cursor + 8,
                              f"Primitive {index} binding (alias or direct rig ID)", "acs.PS3.html#bunny"))
        for relative in (4, 20):
            result.append(integer("acs.unresolved", u32(data, cursor + relative), "value", cursor + relative,
                                  f"Primitive {index} unidentified field +{relative:#x}", "acs.PS3.html"))
        cursor += size
    if cursor != len(data):
        raise ValueError("ACS trailing bytes are not covered by declared records")
    return result


def parse_rw(data: bytes, is_txd: bool) -> list[Identifier]:
    """Follow LE RenderWare chunk boundaries; do not scan blindly for HAnim magic."""
    result: list[Identifier] = []
    containers = {3, 6, 7, 8, 14, 15, 16, 21, 22, 26}

    def walk(start: int, end: int, parent: int, depth: int) -> None:
        if depth > 20:
            raise ValueError("RenderWare nesting limit")
        offset = start
        while offset + 12 <= end:
            kind, size, _ = struct.unpack_from("<3I", data, offset)
            body, stop = offset + 12, offset + 12 + size
            if stop > end or stop <= offset:
                return  # Opaque native geometry is not a nested RW stream.
            if kind == 0x11E and size >= 12:
                count = u32(data, body + 8, "<")
                if count and size >= 20 + count * 12:
                    for index in range(count):
                        pos = body + 20 + index * 12
                        result.append(integer("bone.hanim", u32(data, pos, "<"), "definition", pos,
                                              f"HAnim node index {u32(data, pos + 4, '<')}",
                                              "preinstanced.html#collision-hanim-join", "LE"))
            elif is_txd and kind == 1 and parent == 21 and size >= 40:
                name = data[body + 8:body + 40].split(b"\0")[0].decode("utf-8", errors="replace")
                if name:
                    result.append(Identifier("texture.name", name.lower(), "definition", body + 8, len(name),
                                             "UTF-8", name, doc=DOC + "txd.html"))
            elif not is_txd and kind == 2 and parent == 6:
                name = cstring(data, body, stop) if size else ""
                if name:
                    result.append(Identifier("texture.name", name.lower(), "reference", body, size, "UTF-8",
                                             name, "association", DOC + "preinstanced.html"))
            if kind in containers:
                walk(body, stop, kind, depth + 1)
            offset = stop

    walk(0, len(data), 0, 0)
    return result


def parse_meta(data: bytes) -> list[Identifier]:
    if len(data) < 88:
        raise ValueError("short MetaModel header")
    start, count = u32(data, 44), struct.unpack_from(">H", data, 76)[0]
    if start < 88 and count or start + count * 32 > len(data):
        raise ValueError("MetaModel asset table outside payload")
    result = [Identifier("metamodel.guid", guid(data, 16), "definition", 16, 16, "BE words",
                         "MetaModel header GUID", doc=DOC + "meta.xml.html")]
    for index in range(count):
        pos = start + index * 32
        result.append(Identifier("asset.guid", guid(data, pos + 12), "reference", pos + 12, 16,
                                 "BE words", f"MetaModel asset {index}", doc=DOC + "meta.xml.html"))
    return result


def parse_identifiers(data: bytes, kind: str) -> tuple[list[Identifier], str]:
    """Strict known fields plus observed literal filenames. Unknown formats stay raw."""
    result: list[Identifier] = []
    doc = ""
    if kind == ".lh2":
        doc = "lh2.html"
        for sid, columns, loc in parse_lh2(data):
            label = columns[-1] + " · " + columns[0] if len(columns) > 1 else columns[0]
            result.append(integer("localization.string", sid, "definition", loc["id_offset"], label[:240], doc))
    elif kind == ".alb":
        doc = "alb.html"
        for offset, alias, bank, stream, sid in parse_alb(data):
            result.extend([integer("audio.alias", alias, "definition", offset, "Audio alias ID", doc),
                           Identifier("audio.stream", f"{bank:08X}{stream:08X}", "reference", offset + 4, 8,
                                      "BE pair", "Bank / stream → SMB", doc=DOC + doc),
                           integer("localization.string", sid, "reference", offset + 20, "Dialogue StringID → LH2", doc)])
            for relative in (8, 12, 16):
                result.append(integer("audio.stream_word", stream, "value", offset + relative,
                                      "Stream slot; use bank/stream pair for resolution", doc))
    elif kind == ".smb":
        doc = "smb.html"
        for offset, bank, stream, name in parse_smb(data):
            result.extend([Identifier("audio.stream", f"{bank:08X}{stream:08X}", "definition", offset + 4, 8,
                                      "BE pair", name, doc=DOC + doc),
                           Identifier("file.name", (name + ".snu").lower(), "reference", offset + 52, len(name),
                                      "ASCII (.snu wrapper on disc)", name + ".snu", doc=DOC + doc)])
    elif kind == ".tox.ps3":
        doc = "tox.PS3.html"
        if data[:4] != b"1BOT" or len(data) < 16 or u32(data, 4) != len(data) or len(data) != 16 + 16 * u32(data, 12):
            raise ValueError("invalid TOX header or record bounds")
        for pos in range(16, len(data), 16):
            result.append(integer("localization.string", u32(data, pos), "reference", pos,
                                  f"Movie cue, start {u32(data, pos + 4)} ms, duration {u32(data, pos + 8)} ms", doc))
    elif kind == ".dat.simgroup" or data[8:12] == b"SimG":
        doc, result = "simgroup.dat.html", parse_simgroup(data)
    elif kind == ".dat.uie":
        doc, result = "simgroup.dat.html#uie", parse_uie(data)
    elif kind == ".bbn.ps3":
        doc, result = "bbn.PS3.html", parse_bbn(data)
    elif kind == ".acs.ps3":
        doc, result = "acs.PS3.html", parse_acs(data)
    elif kind == ".preinstanced" or kind == ".txd":
        doc, result = "preinstanced.html" if kind == ".preinstanced" else "txd.html", parse_rw(data, kind == ".txd")
    elif kind == ".meta.xml":
        doc, result = "meta.xml.html", parse_meta(data)
    elif kind == ".graph" and len(data) >= 128:
        doc = "graph.html"
        result.append(Identifier("graph.guid", guid(data, 16), "definition", 16, 16, "BE words", "Graph GUID", doc=DOC + doc))
    elif kind == ".cec.ps3":
        doc = "cec.ps3.html"
        if len(data) < 192:
            raise ValueError("short CEC")
        count = struct.unpack_from(">H", data, 2)[0]
        if 192 + count * 128 > len(data):
            raise ValueError("CEC event table outside payload")
        result.append(integer("controller.config", u32(data, 4), "definition", 4,
                              cstring(data, 9, 42), doc))
        for index in range(count):
            pos = 192 + index * 128
            result.append(integer("controller.event", u32(data, pos), "definition", pos,
                                  cstring(data, pos + 5, pos + 31), doc))
    # Filename literals are observations, not a recovered event/selection algorithm.
    if kind in {".msb", ".uix", ".xml.ps3", ".rcb.ps3", ".txt", ".lua"}:
        for match in re.finditer(rb"[A-Za-z0-9_./\\-]{2,180}\.(?:mus|txd|inf|sbk|smb|bnk\.PS3|vp6|exa)(?=\x00|[\s\"'])", data, re.I):
            name = match.group().decode("ascii").replace("\\", "/").split("/")[-1].lower()
            if name.endswith(".exa"):
                name += ".snu"
            result.append(Identifier("file.name", name, "reference", match.start(), len(match.group()),
                                     "ASCII", "Observed filename: " + name, "association", DOC + ("msb.html" if kind == ".msb" else "../relationships.html")))
    return result, ("documented fields; original runtime semantics may remain unresolved" if doc else
                    "no verified ID layout adapter; raw words and candidate matches available")

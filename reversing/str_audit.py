"""Audit source STR bytes independently of QuickBMS; never write input files.

Usage: python -B reversing/str_audit.py <STR-file-or-root> <report.json>
Validated on the inspected PS3 US full release, 2026-10-19. This is a bounded
structural audit, not a complete asset decoder. Keep Python assertions enabled.
The JSON retains source SHA-256, section positions, record boundaries, original
metadata paths, body/payload hashes and SimGroup pointer checks. Original paths
can contain drive letters; QuickBMS cleans those when writing extracted files.
"""
from pathlib import Path
import collections
import hashlib
import json
import struct
import sys


def u32(data, pos, order=">"):
    return struct.unpack_from(order + "I", data, pos)[0]


def refpack(data, expected):
    assert data[:2] == b"\x10\xfb"
    assert int.from_bytes(data[2:5], "big") == expected
    out = bytearray()
    pos = 5
    while True:
        c = data[pos]
        pos += 1
        stop = False
        if c < 0x80:
            c1 = data[pos]
            pos += 1
            literal, count, distance = c & 3, ((c >> 2) & 7) + 3, ((c & 0x60) << 3) + c1 + 1
        elif c < 0xC0:
            c1, c2 = data[pos:pos + 2]
            pos += 2
            literal, count, distance = c1 >> 6, (c & 0x3F) + 4, ((c1 & 0x3F) << 8) + c2 + 1
        elif c < 0xE0:
            c1, c2, c3 = data[pos:pos + 3]
            pos += 3
            literal, count, distance = c & 3, ((c & 0x0C) << 6) + c3 + 5, ((c & 0x10) << 12) + (c1 << 8) + c2 + 1
        elif c < 0xFC:
            literal, count, distance = ((c & 0x1F) * 4) + 4, 0, 0
        else:
            literal, count, distance, stop = c & 3, 0, 0, True
        assert pos + literal <= len(data)
        out.extend(data[pos:pos + literal])
        pos += literal
        assert count == 0 or 0 < distance <= len(out)
        for _ in range(count):
            out.append(out[-distance])
        assert len(out) <= expected
        if stop:
            break
    assert len(out) == expected
    return bytes(out), pos


def inspect(path, root):
    source = path.read_bytes()
    assert source[:4] == b"SToc"
    n, info = source[8], u32(source, 16)
    base = (info + n * 24 + 0x7FF) & ~0x7FF
    result = {"archive": path.relative_to(root).as_posix(), "sha256": hashlib.sha256(source).hexdigest(), "size": len(source), "sections": []}
    for section in range(n):
        desc = struct.unpack_from(">6I", source, info + section * 24)
        policy, compression, size, allocation, stored, extra = desc
        raw = source[base:base + stored]
        assert len(raw) == stored
        compressed = raw[:2] == b"\x10\xfb"
        data, used = refpack(raw, size) if compressed else (raw[:size], size)
        s = {"index": section, "source_offset": base, "data_size": size, "stored_size": stored, "descriptor_last_word": extra, "compressed": compressed, "stream_bytes_used": used, "records": []}
        offset = 0
        while offset < len(data):
            assert len(data) - offset >= 12, (path, section, offset, "short record")
            kind = int.from_bytes(data[offset:offset + 2], "big")
            body_size = u32(data, offset + 4, "<")
            end = offset + 12 + body_size
            assert body_size > 0 and end <= len(data), (path, section, hex(offset), hex(kind), body_size, len(data))
            body = data[offset + 12:end]
            record = {"offset": offset, "type": f"{kind:04x}", "body_size": body_size, "body_prefix": body[:48].hex(), "body_sha256": hashlib.sha256(body).hexdigest()}
            if kind == 0x1607:
                header = u32(body, 0)
                assert header > 0
                cursor = 4
                fields = []
                for field in range(4):
                    if field == 1:
                        cursor += 16
                    length = u32(body, cursor)
                    cursor += 4
                    assert cursor + length <= 4 + header
                    fields.append(body[cursor:cursor + length].split(b"\0")[0].decode("ascii"))
                    cursor += length
                payload_size = u32(body, cursor + 4)
                payload_start = 4 + header
                assert cursor + 8 <= payload_start
                assert payload_start + ((payload_size + 3) & ~3) == body_size, (path, section, offset, body_size, payload_start, payload_size)
                payload = body[payload_start:payload_start + payload_size]
                record.update(path=fields[2], resource_type=fields[1], header_size=header, payload_size=payload_size, payload_sha256=hashlib.sha256(payload).hexdigest())
            else:
                # Legacy extraction stopped walking here and swallowed the tail.
                record["legacy_sha256"] = hashlib.sha256(data[offset + 16:]).hexdigest()
                record["legacy_size"] = len(data) - offset - 16
                record["simg_at_8"] = body[8:12] == b"SimG"
                if body[8:12] == b"SimG":
                    record.update(version=u32(body, 12), guid=f"{u32(body, 16):08x}", flags=u32(body, 20), entities=u32(body, 24), dispatched=u32(body, 28), shared_data_size=u32(body, 32), dictionary_size=u32(body, 36), pp_ent_packets=u32(body, 40))
                    pointer = u32(body, 40)
                    assert pointer + 4 <= len(body)
                    entities_start = u32(body, pointer)
                    assert entities_start < len(body) or record["entities"] == 0
                    record["entity_array"] = entities_start
            s["records"].append(record)
            offset = end
        result["sections"].append(s)
        base += stored
    assert base == len(source), (path, base, len(source))
    return result


if __name__ == "__main__":
    root = Path(sys.argv[1])
    paths = sorted(root.rglob("*.str")) if root.is_dir() else [root]
    relative_root = root if root.is_dir() else root.parent
    archives, errors = [], []
    for path in paths:
        try:
            archives.append(inspect(path, relative_root))
        except Exception as exc:
            errors.append({"path": str(path), "error": repr(exc)})
    records = [r for a in archives for s in a["sections"] for r in s["records"]]
    counts = dict(collections.Counter(r["type"] for r in records))
    report = {"archives": archives, "errors": errors, "record_counts": counts}
    Path(sys.argv[2]).write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"archives": len(archives), "record_counts": counts, "errors": errors}, indent=2))
    sys.exit(bool(errors))

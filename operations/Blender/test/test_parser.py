import sys
import unittest
from pathlib import Path


ADDON_PARENT = Path(__file__).resolve().parents[1] / "blender_addon"
sys.path.insert(0, str(ADDON_PARENT.parent))

from blender_addon.parser import _iter_texture_names, build_texture_mesh_links


VERSION = bytes.fromhex("2D 00 02 1C")
RW_STRUCT = bytes.fromhex("01 00 00 00")
RW_STRING = bytes.fromhex("02 00 00 00")
TEXTURE_MARKER = bytes.fromhex("2D 00 02 1C 00 00 00 0A")
MESH_MARKER = bytes.fromhex("33 EA 00 00 10 00 00 00 2D 00 02 1C")
EOF_MARKER = bytes.fromhex("16 EA 00 00 05 00 00 00 2D 00 02 1C 01 00 00 00 00")


def make_texture_name_chunk(name: str, filter_bytes: bytes, length_override: int | None = None) -> bytes:
    encoded_name = name.encode("ascii")
    payload = encoded_name + b"\x00"
    payload += b"\xBF" * ((-len(payload)) % 4)
    string_size = len(payload) if length_override is None else length_override
    return (
        RW_STRUCT
        + (4).to_bytes(4, "little")
        + VERSION
        + filter_bytes
        + RW_STRING
        + string_size.to_bytes(4, "little")
        + VERSION
        + payload
    )


def make_preinstanced(data: bytes) -> bytes:
    header = bytearray(0x40)
    header[0:4] = bytes.fromhex("10 00 00 00")
    header[8:12] = VERSION
    header[0x38:0x3C] = VERSION
    return bytes(header) + data


class TextureNameParserTests(unittest.TestCase):
    def test_reads_variable_lengths_and_filter_bytes(self):
        chunks = [
            make_texture_name_chunk("abcd", bytes.fromhex("02 11 01 00")),
            make_texture_name_chunk("play_sound", bytes.fromhex("03 22 04 01")),
            make_texture_name_chunk("a_longer_texture_name", bytes.fromhex("00 00 00 00")),
            make_texture_name_chunk("apu", bytes.fromhex("02 11 01 00")),
        ]
        data = b"".join(chunks)

        parsed = list(_iter_texture_names(data))

        expected_offsets = []
        offset = 0
        for chunk in chunks:
            expected_offsets.append(offset + 12)
            offset += len(chunk)
        self.assertEqual([
            (expected_offsets[0], "abcd"),
            (expected_offsets[1], "play_sound"),
            (expected_offsets[2], "a_longer_texture_name"),
            (expected_offsets[3], "apu"),
        ], parsed)

    def test_rejects_bad_version_oversized_and_truncated_chunks(self):
        bad_version = bytearray(make_texture_name_chunk("valid_name", bytes(4)))
        bad_version[8:12] = b"\x00\x00\x00\x00"
        oversized = make_texture_name_chunk("oversized", bytes(4), length_override=0x81)
        truncated = make_texture_name_chunk("truncated", bytes(4))[:-2]

        parsed = list(_iter_texture_names(bytes(bad_version) + oversized + truncated))

        self.assertEqual([], parsed)

    def test_build_texture_mesh_links_associates_names_before_mesh_marker(self):
        name_chunk = make_texture_name_chunk("play_sound", bytes.fromhex("01 09 04 00"))
        payload = bytearray(make_preinstanced(name_chunk + b"TLFD" + MESH_MARKER + EOF_MARKER))
        expected_mesh_offset = 0x40 + len(name_chunk) + 4
        payload.extend(bytes(4))

        links, _, found_names = build_texture_mesh_links(bytes(payload))

        self.assertEqual({expected_mesh_offset: ["play_sound"]}, links)
        self.assertEqual({"play_sound"}, found_names)


if __name__ == "__main__":
    unittest.main()
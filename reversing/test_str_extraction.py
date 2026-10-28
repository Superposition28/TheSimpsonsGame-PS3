"""Exercise the STR BMS with generated archives, without proprietary game data.

python -B reversing/test_str_extraction.py --quickbms <exe> --scratch <directory>
Leaves fixtures/logs beneath a new scratch subdirectory for inspection.
"""
import argparse
from pathlib import Path
import struct
import subprocess
import uuid


def word(value):
    return struct.pack(">I", value)


def record(kind, body):
    return struct.pack(">H", kind) + b"\0\0" + struct.pack("<I", len(body)) + bytes.fromhex("ffff0218") + body


def string(value):
    data = value.encode("ascii") + b"\0"
    data += b"\xbf" * (-len(data) % 4)
    return word(len(data)) + data


def asset(name, payload, resource="TEST"):
    header = string("Object") + bytes(16) + string(resource) + string(name) + word(0) + word(0) + word(len(payload))
    return record(0x1607, word(len(header)) + header + payload + bytes(-len(payload) % 4))


def archive(data, compressed=False):
    stored = data
    if compressed:
        # Literal-only valid RefPack stream, independent of its decoder.
        stored = b"\x10\xfb" + len(data).to_bytes(3, "big")
        pos = 0
        while len(data) - pos >= 4:
            count = min(112, ((len(data) - pos) // 4) * 4)
            stored += bytes([0xE0 + count // 4 - 1]) + data[pos:pos + count]
            pos += count
        stored += bytes([0xFC + len(data) - pos]) + data[pos:]
    read_size = (len(stored) + 0x7FF) & ~0x7FF
    header = b"SToc" + word(7) + bytes.fromhex("01060000") + word(0) + word(20)
    descriptor = word(0) + word(0xB9F0B9EC if compressed else 0x0EAC15C8) + word(len(data)) + word(read_size) + word(read_size) + word(0)
    return (header + descriptor).ljust(0x800, b"\0") + stored.ljust(read_size, b"\0")


def run(executable, script, scratch, name, data, expected, compressed=False, error=None):
    source = scratch / (name + ".str")
    output = scratch / name
    output.mkdir()
    source.write_bytes(archive(data, compressed))
    result = subprocess.run([str(executable), "-o", str(script), str(source), str(output)], capture_output=True)
    transcript = result.stdout + result.stderr
    (scratch / (name + ".log")).write_bytes(transcript)
    actual = {p.relative_to(output).as_posix(): p.read_bytes() for p in output.rglob("*") if p.is_file()}
    assert actual == expected, (name, list(actual), list(expected), transcript.decode(errors="replace"))
    if error:
        # QuickBMS CleanExit does not guarantee a nonzero exit code.
        assert error.encode() in transcript, (name, transcript)
    else:
        assert result.returncode == 0 and b"ERROR:" not in transcript, (name, transcript)
        # A second identical extraction must produce exactly the same files/bytes.
        rerun = subprocess.run([str(executable), "-o", str(script), str(source), str(output)], capture_output=True)
        assert rerun.returncode == 0 and b"ERROR:" not in rerun.stdout + rerun.stderr
        assert actual == {p.relative_to(output).as_posix(): p.read_bytes() for p in output.rglob("*") if p.is_file()}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--quickbms", type=Path, required=True)
    parser.add_argument("--scratch", type=Path, required=True)
    args = parser.parse_args()
    args.scratch.mkdir(parents=True, exist_ok=True)
    scratch = args.scratch.resolve() / ("run-" + uuid.uuid4().hex[:12])
    scratch.mkdir()
    script = Path(__file__).resolve().parents[1] / "operations/simpsons_str.bms"
    sim = bytes(8) + b"SimG" + word(1) + bytes(32)
    middle = asset("middle.bin", b"mid")
    data = record(0x2207, sim) + middle + record(0x2207, sim)
    expected = {"simgroup_s000_o00000000.dat.simgroup": sim, "middle.bin": b"mid", f"simgroup_s000_o{len(record(0x2207, sim) + middle):08x}.dat.simgroup": sim}
    run(args.quickbms, script, scratch, "multiple-raw", data, expected)
    run(args.quickbms, script, scratch, "multiple-refpack", data, expected, compressed=True)
    unknown = word(0x12345678) + b"unknown"
    no_header = word(0) + b"raw-body"
    data = record(0x2307, unknown) + record(0x1607, no_header) + record(0x2207, b"not-simg")
    run(args.quickbms, script, scratch, "unknown-records", data, {"chunk_2307_s000_o00000000.dat": unknown, f"chunk_1607_s000_o{12 + len(unknown):08x}.dat": no_header, f"chunk_2207_s000_o{24 + len(unknown) + len(no_header):08x}.dat": b"not-simg"})
    uie = asset("", bytes(range(20)), "UIE")
    run(args.quickbms, script, scratch, "unnamed-assets", uie + asset("", b"other"), {"uie_s000_o00000000.dat.uie": bytes(range(20)), f"unnamed_asset_s000_o{len(uie):08x}.dat": b"other"})
    named_uie = asset("ui.dat", bytes(range(20)), "UIE")
    named_data = named_uie + asset("UI.DAT", b"second", "UIE") + asset("unknown.dat", b"opaque") + asset("ui.uie", b"typed", "UIE") + asset("ready.dat.uie", b"categorized", "UIE")
    run(args.quickbms, script, scratch, "named-dat-categories", named_data, {
        "ui.dat.uie": bytes(range(20)),
        f"__str_duplicates__/s000_o{len(named_uie):08x}/UI.DAT.uie": b"second",
        "unknown.dat": b"opaque", "ui.uie": b"typed", "ready.dat.uie": b"categorized",
    })
    # SimG-like bytes in an undocumented outer type do not identify SimGroup.
    run(args.quickbms, script, scratch, "unknown-simg-signature", record(0x2307, sim), {"chunk_2307_s000_o00000000.dat": sim})
    first = asset("StreamSetConfig", b"first")
    run(args.quickbms, script, scratch, "repeated-path", first + asset("StreamSetConfig", b"second"), {"StreamSetConfig": b"first", f"__str_duplicates__/s000_o{len(first):08x}/StreamSetConfig": b"second"})
    oversized = record(0x2207, sim)[:4] + struct.pack("<I", 0x7FFFFFFF) + bytes(4)
    run(args.quickbms, script, scratch, "bad-record-size", oversized, {}, error="ERROR: STR record exceeds section")
    run(args.quickbms, script, scratch, "short-envelope", b"abc", {}, error="ERROR: truncated STR record envelope")
    print(f"Passed 9 STR extraction cases, including reruns. Fixtures/logs: {scratch}")


if __name__ == "__main__":
    main()

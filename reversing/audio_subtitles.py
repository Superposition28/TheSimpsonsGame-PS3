"""Recover ALB -> SMB -> SNU / LH2 links directly from original PS3 EU STRs.

No AudioMap, normalized files, CSVs, or previously converted audio are inputs.
Run with Python 3.11+ (without -O; the shared RefPack decoder uses assertions).
See audio_subtitles.md for commands, evidence scope, and timing limitations.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from dataclasses import dataclass, field
import hashlib
import json
from pathlib import Path
import struct
import subprocess
import wave

from str_audit import refpack


LANGUAGES = {"EN": 0, "FR": 1, "IT": 2, "ES": 3}
MODULE = Path(__file__).resolve().parents[1]


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def word(data: bytes, offset: int, order: str = ">") -> int:
    require(0 <= offset <= len(data) - 4, f"word outside payload: {offset:#x}")
    return struct.unpack_from(order + "I", data, offset)[0]


def string(data: bytes, offset: int, end: int | None = None) -> str:
    end = len(data) if end is None else end
    require(0 <= offset < end <= len(data), "string outside payload")
    stop = data.find(b"\0", offset, end)
    require(stop >= 0, f"unterminated string: {offset:#x}")
    # Preserve every source byte, including undefined CP1252 control positions.
    return data[offset:stop].decode("cp1252", errors="surrogateescape")


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sdbm(label: str) -> int:
    result = 0
    for byte in label.lower().encode("cp1252", errors="surrogateescape"):
        result = (result * 65599 + byte) & 0xFFFFFFFF
    return result


@dataclass
class Asset:
    suffix: str
    data: bytes
    sha256: str
    sources: list[dict] = field(default_factory=list)


def original_assets(source: Path) -> tuple[list[Asset], list[dict]]:
    """Walk bounded original STR records; preserve archive/member coordinates."""
    assets: dict[tuple[str, str], Asset] = {}
    archives = []
    paths = sorted(source.rglob("*.str"))
    require(bool(paths), "no original STR archives found")
    for index, path in enumerate(paths):
        raw = path.read_bytes()
        require(raw[:4] == b"SToc" and len(raw) >= 20, f"invalid STR: {path}")
        archive = path.relative_to(source).as_posix()
        archive_hash = digest(raw)
        archives.append({"path": archive, "sha256": archive_hash, "size": len(raw)})
        count, info = raw[8], word(raw, 16)
        require(info + count * 24 <= len(raw), f"truncated section table: {archive}")
        base = (info + count * 24 + 2047) & ~2047
        for section in range(count):
            _, _, size, _, stored, _ = struct.unpack_from(">6I", raw, info + section * 24)
            require(base + stored <= len(raw) and size <= 256 * 1024 * 1024,
                    f"invalid section bounds: {archive}")
            compressed = raw[base:base + stored]
            data = refpack(compressed, size)[0] if compressed[:2] == b"\x10\xfb" else compressed[:size]
            require(len(data) == size, f"short section: {archive}")
            base += stored
            offset = 0
            while offset < len(data):
                require(offset + 12 <= len(data), f"short record: {archive}")
                end = offset + 12 + word(data, offset + 4, "<")
                require(offset + 12 < end <= len(data), f"record outside section: {archive}")
                if data[offset:offset + 2] == b"\x16\x07":
                    body = data[offset + 12:end]
                    header = word(body, 0)
                    if header:
                        require(4 + header <= len(body), "asset header outside record")
                        cursor, fields = 4, []
                        for part in range(4):
                            if part == 1:
                                cursor += 16
                            length = word(body, cursor)
                            cursor += 4
                            require(cursor + length <= 4 + header, "asset field outside header")
                            fields.append(body[cursor:cursor + length].split(b"\0")[0].decode("ascii"))
                            cursor += length
                        require(cursor + 8 <= 4 + header, "short asset size fields")
                        payload_size = word(body, cursor + 4)
                        require(4 + header + ((payload_size + 3) & ~3) == len(body), "asset size mismatch")
                        member = fields[2]
                        suffix = Path(member.replace("\\", "/")).suffix.lower()
                        if suffix in {".lh2", ".alb", ".smb"}:
                            payload = body[4 + header:4 + header + payload_size]
                            sha = digest(payload)
                            asset = assets.setdefault((suffix, sha), Asset(suffix, payload, sha))
                            asset.sources.append({"archive": archive, "section": section,
                                                  "record_offset": offset, "member": member,
                                                  "resource_type": fields[1], "payload_offset": 4 + header})
                offset = end
        require(base == len(raw), f"unaccounted STR bytes: {archive}")
        if index % 25 == 0:
            print(f"Read {index + 1}/{len(paths)} original STRs", flush=True)
    return list(assets.values()), archives


def parse_lh2(data: bytes) -> list[tuple[int, tuple[str, ...], dict]]:
    require(len(data) >= 32 and data[:4] == b"2HCL", "invalid LH2 header")
    require(word(data, 4) == len(data), "LH2 declared size mismatch")
    count, columns = word(data, 16), word(data, 20)
    require(columns > 0 and 32 + 4 * count * (1 + columns) <= len(data), "truncated LH2 matrix")
    result = []
    for index in range(count):
        pointers = [word(data, 32 + 4 * count + 4 * (column * count + index)) for column in range(columns)]
        result.append((word(data, 32 + 4 * index), tuple(string(data, p) for p in pointers),
                       {"row": index, "id_offset": 32 + 4 * index, "text_offsets": pointers}))
    return result


def parse_alb(data: bytes) -> list[tuple[int, int, int, int, int]]:
    require(len(data) >= 8, "short ALB")
    version, count, start = struct.unpack_from(">HHI", data)
    require(version == 6 and start == 8 and len(data) == start + 24 * count,
            "unrecognized ALB layout (expected version 6, 24-byte records)")
    result = []
    for index in range(count):
        offset = start + index * 24
        alias, bank, stream, second, third, subtitle = struct.unpack_from(">6I", data, offset)
        require(stream == second == third, "ALB stream slots differ; language/slot selection unresolved")
        result.append((offset, alias, bank, stream, subtitle))
    return result


def parse_smb(data: bytes) -> list[tuple[int, int, int, str]]:
    require(len(data) >= 24, "short SMB")
    count, table = word(data, 16), word(data, 20)
    require(table == 24 and table + count * 4 <= len(data), "invalid SMB pointer table")
    offsets = [word(data, table + index * 4) for index in range(count)]
    require(not offsets or offsets[0] == table + count * 4, "unexpected SMB records start")
    result = []
    for index, offset in enumerate(offsets):
        end = offsets[index + 1] if index + 1 < count else len(data)
        require(offset >= table + count * 4 and end - offset == 96 and end <= len(data),
                "unrecognized SMB record bounds (expected 96-byte records)")
        bank, stream, second, third = struct.unpack_from(">4I", data, offset + 4)
        require(stream == second == third, "SMB stream slots differ; selection unresolved")
        name = string(data, offset + 52, end)
        require(name.lower().endswith(".exa") and "/" not in name and "\\" not in name, "invalid SMB stream name")
        result.append((offset, bank, stream, name))
    return result


def build_report(source: Path, assets: list[Asset], archives: list[dict]) -> dict:
    texts, streams = defaultdict(list), defaultdict(list)
    aliases, catalog = [], {}
    counts = Counter()
    for asset in assets:
        key = asset.suffix[1:] + ":" + asset.sha256
        catalog[key] = {"sha256": asset.sha256, "size": len(asset.data), "sources": asset.sources}
        counts[asset.suffix[1:] + "_unique_payloads"] += 1
        counts[asset.suffix[1:] + "_occurrences"] += len(asset.sources)
        if asset.suffix == ".lh2":
            rows = parse_lh2(asset.data)
            if word(asset.data, 20) == 5:
                counts["lh2_five_column_payloads"] += 1
                for sid, columns, location in rows:
                    require(sdbm(columns[4]) == sid, f"LH2 label hash mismatch: {sid:08x}")
                    texts[sid].append({"asset": key, **location, "columns": columns})
        elif asset.suffix == ".smb":
            for offset, bank, stream, name in parse_smb(asset.data):
                streams[bank, stream].append({"asset": key, "offset": offset, "name": name})
                counts["smb_records"] += 1
        else:
            for offset, alias, bank, stream, sid in parse_alb(asset.data):
                aliases.append((key, offset, alias, bank, stream, sid))
                counts["alb_records_with_duplicate_payloads"] += len(asset.sources)
    links, unresolved, linked_names = [], [], set()
    for key, offset, alias, bank, stream, sid in aliases:
        sounds, localized = streams.get((bank, stream), []), texts.get(sid, [])
        names = {r["name"].lower() for r in sounds}
        values = {tuple(r["columns"]) for r in localized}
        if len(names) != 1 or len(values) != 1:
            unresolved.append({"alb_asset": key, "offset": offset, "string_id": f"{sid:08X}",
                               "stream_names": sorted(names), "text_variants": len(values)})
            continue
        columns = next(iter(values))
        name = next(iter(names))
        # A check on the recovered numeric join; never used to select the clip.
        require(name == "d_" + columns[4].lower() + ".exa", "numeric join and label filename disagree")
        linked_names.add(name)
        links.append({"alb_asset": key, "alb_offset": offset, "alias_id": f"{alias:08X}",
                      "bank_id": f"{bank:08X}", "stream_id": f"{stream:08X}",
                      "string_id": f"{sid:08X}", "label": columns[4], "stream_name": name,
                      "text": {language: columns[column] for language, column in LANGUAGES.items()},
                      "smb_records": sounds,
                      "lh2_rows": [{k: v for k, v in row.items() if k != "columns"} for row in localized]})
    physical = defaultdict(list)
    for path in sorted((source / "audiostreams").rglob("*.snu")):
        physical[path.name.lower()].append(path.relative_to(source).as_posix())
    all_names = {row["name"].lower() for rows in streams.values() for row in rows}
    unlinked = sorted(all_names - linked_names)
    counts.update({"archives": len(archives), "alb_records": len(aliases), "resolved_alb_records": len(links),
                   "unresolved_alb_records": len(unresolved), "dialogue_string_ids": len(texts),
                   "linked_dialogue_stream_names": len(linked_names), "smb_stream_names": len(all_names),
                   "original_snu_files": sum(map(len, physical.values())), "original_snu_names": len(physical),
                   "streams_without_alb_subtitle_link": len(unlinked)})
    return {"source_root": str(source), "method": "ALB(bank, stream) -> SMB filename; ALB StringID -> LH2 ID",
            "language_columns": LANGUAGES, "counts": dict(counts), "archives": archives, "assets": catalog,
            "links": links, "unresolved_alb_records": unresolved,
            "streams_without_alb_subtitle_link": unlinked,
            "smb_names_without_snu": sorted(name for name in all_names if name + ".snu" not in physical),
            "snu_names_without_smb": sorted(set(physical) - {name + ".snu" for name in all_names}),
            "physical_snu_paths": dict(physical),
            "limitations": ["Static original-file joins; no original runtime execution observed.",
                            "ALB subtitle links cover individual dialogue, not composite IGC, ambience or music.",
                            "The demonstration displays a cue for the decoded clip duration; original subtitle dwell timing is unknown.",
                            "SBK subsongs, MUS/SNR/SNS and VP6 audio are not resolved by this ALB/SMB audit."]}


def executable(root: Path, tool: str, version: str, relative: str) -> Path:
    path = root / f"{tool}-{version}-win-x64" / relative
    require(path.is_file(), f"missing declared tool: {path}")
    return path


def command(args: list[str], cwd: Path, log: Path) -> None:
    result = subprocess.run(args, cwd=cwd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    log.write_bytes(result.stdout)
    require(result.returncode == 0, f"command failed; see {log}")


def make_video(source: Path, output: Path, relative: str, report: dict, tools_root: Path) -> dict:
    snu = (source / relative).resolve()
    require(snu.is_relative_to((source / "audiostreams").resolve()) and snu.is_file(),
            "--snu must select an original file beneath source/audiostreams")
    require(snu.name.lower().endswith(".exa.snu"), "expected an original EXA.SNU")
    relative = snu.relative_to(source).as_posix()
    parts = snu.relative_to(source / "audiostreams").parts
    language = parts[0].upper() if parts[0].upper() in {"FR", "IT", "ES"} else "EN"
    links = [r for r in report["links"] if r["stream_name"] + ".snu" == snu.name.lower()]
    require(bool(links), f"no recovered ALB/SMB/LH2 link for {relative}; refusing a guessed subtitle")
    texts = {r["text"][language] for r in links}
    require(len(texts) == 1, f"ambiguous localized subtitle for {relative}")
    text = next(iter(texts))
    require(bool(text.strip()), "empty source subtitle")
    demo = output / (snu.name[:-8] + "-" + language)
    demo.mkdir(parents=True, exist_ok=True)
    vgm = executable(tools_root, "vgmstream-cli", "r2117", "vgmstream-cli.exe")
    ffmpeg = executable(tools_root, "ffmpeg", "8.0", "bin/ffmpeg.exe")
    original_hash = digest(snu.read_bytes())
    command([str(vgm), "-i", "-o", "audio.wav", str(snu)], demo, demo / "vgmstream.log")
    with wave.open(str(demo / "audio.wav"), "rb") as wav:
        frames, rate, channels = wav.getnframes(), wav.getframerate(), wav.getnchannels()
    duration = frames / rate
    end_ms = round(duration * 1000)
    hours, rem = divmod(end_ms, 3600000)
    minutes, rem = divmod(rem, 60000)
    seconds, millis = divmod(rem, 1000)
    (demo / "subtitle.srt").write_text(
        f"1\n00:00:00,000 --> {hours:02}:{minutes:02}:{seconds:02},{millis:03}\n{text}\n", encoding="utf-8")
    # This fixed relative filter path avoids Windows drive-letter filter escaping.
    command([str(ffmpeg), "-y", "-hide_banner", "-loglevel", "warning", "-f", "lavfi", "-i",
             "color=c=black:s=1280x720:r=25", "-i", "audio.wav", "-vf",
             "subtitles=subtitle.srt:force_style='FontName=Arial,FontSize=26,MarginV=55'",
             "-map", "0:v:0", "-map", "1:a:0", "-t", f"{duration:.9f}",
             "-c:v", "libx264", "-preset", "fast", "-crf", "20", "-pix_fmt", "yuv420p",
             "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", "test.mp4"], demo, demo / "ffmpeg.log")
    require(digest(snu.read_bytes()) == original_hash, "source SNU changed during demonstration")
    evidence = {"original_snu": relative, "snu_sha256": original_hash, "language": language,
                "subtitle": text, "sample_frames": frames, "sample_rate": rate, "channels": channels,
                "duration_seconds": duration, "wav_sha256": digest((demo / "audio.wav").read_bytes()),
                "vgmstream": str(vgm), "ffmpeg": str(ffmpeg),
                "timing": "Demonstration cue spans decoded sample duration; not recovered original-game cue timing.",
                "links": links, "video": str(demo / "test.mp4")}
    (demo / "evidence.json").write_text(json.dumps(evidence, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")
    return {"snu": relative, "video": str(demo / "test.mp4"), "duration_seconds": duration}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=MODULE / "Source/PS3/EU/1/PS3_GAME/USRDIR")
    parser.add_argument("--output", type=Path, default=MODULE / "GameFiles/original-audio-subtitles")
    parser.add_argument("--tools-root", type=Path, default=MODULE.parents[1] / "Tools")
    parser.add_argument("--snu", action="append", default=[], help="Original SNU path relative to USRDIR; repeat for several videos")
    args = parser.parse_args()
    source, output = args.source.resolve(), args.output.resolve()
    # Prevent selecting a derivative dataset or placing generated files in Source.
    require(source.is_relative_to((MODULE / "Source").resolve()) and source.name.upper() == "USRDIR",
            "--source must be an original USRDIR beneath this module's Source directory")
    require(output.is_relative_to((MODULE / "GameFiles").resolve()), "--output must be beneath GameFiles")
    require(not output.is_relative_to(source), "output cannot be inside the source tree")
    output.mkdir(parents=True, exist_ok=True)
    assets, archives = original_assets(source)
    report = build_report(source, assets, archives)
    # Save audit evidence even when a requested clip has no recovered subtitle.
    report_path = output / "report.json"
    report_path.write_text(json.dumps(report, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")
    print(json.dumps(report["counts"], indent=2), flush=True)
    for relative in args.snu:
        print(json.dumps(make_video(source, output, relative, report, args.tools_root.resolve())), flush=True)
    require(not report["unresolved_alb_records"], "some ALB rows did not resolve; see report.json")


if __name__ == "__main__":
    main()

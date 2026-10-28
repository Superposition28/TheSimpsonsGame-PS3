"""Original archive inventory, extracted-copy provenance and scoped ID resolution."""
from __future__ import annotations

from collections import OrderedDict
from dataclasses import asdict
import hashlib
import json
import os
from pathlib import Path
import re
import sqlite3
import struct
import time

from str_audit import refpack
from .parsers import Identifier, INVALID_GUIDS, guid, parse_identifiers, u32, DOC


MODULE = Path(__file__).resolve().parents[2]
SKIP = {".history", ".backup", ".git", ".godot", "__pycache__", ".vscodecounter"}
MEDIA = {".snu", ".exa.snu", ".mus", ".vp6", ".wav", ".ogg", ".ogv", ".png", ".dds", ".blend", ".glb", ".mp4", ".elf", ".bin"}
COMPOUND = (".dat.simgroup", ".dat.uie", ".tox.ps3", ".bbn.ps3", ".acs.ps3", ".cec.ps3", ".rcb.ps3", ".xml.ps3", ".meta.xml", ".preinstanced", ".exa.snu")
SCHEMA = """
CREATE TABLE files(id INTEGER PRIMARY KEY, view TEXT, root TEXT, path TEXT, level TEXT,
 format TEXT, size INTEGER, sha256 TEXT, archive INTEGER, member TEXT, locator TEXT,
 status TEXT, language TEXT);
CREATE TABLE ids(id INTEGER PRIMARY KEY, file INTEGER, namespace TEXT, value TEXT,
 role TEXT, offset INTEGER, width INTEGER, endian TEXT, label TEXT, confidence TEXT,
 doc TEXT, region TEXT);
CREATE TABLE edges(id INTEGER PRIMARY KEY, source INTEGER, target INTEGER, kind TEXT,
 label TEXT, confidence TEXT);
CREATE TABLE meta(key TEXT PRIMARY KEY, value TEXT);
CREATE INDEX file_hash ON files(sha256);
CREATE INDEX file_level ON files(level,view);
CREATE INDEX file_archive ON files(archive);
CREATE INDEX id_file ON ids(file,role);
CREATE INDEX id_key ON ids(namespace,value,role);
CREATE INDEX id_value ON ids(value,role);
CREATE INDEX edge_source ON edges(source);
CREATE INDEX edge_target ON edges(target);
"""


def kind_of(path: str) -> str:
    name = path.lower()
    return next((suffix for suffix in COMPOUND if name.endswith(suffix)), Path(name).suffix or "(no suffix)")


def walk_files(root: Path) -> list[Path]:
    paths = []
    for base, directories, names in os.walk(root, followlinks=False):
        directories[:] = sorted(d for d in directories if d.lower() not in SKIP and not (Path(base) / d).is_symlink())
        for name in sorted(names):
            path = Path(base) / name
            if not path.is_symlink() and path.is_file():
                paths.append(path)
    return paths


def hash_file(path: Path) -> str:
    with path.open("rb") as handle:
        return hashlib.file_digest(handle, "sha256").hexdigest()


def language_of(path: str, kind: str) -> str:
    lower = path.lower().replace("\\", "/")
    for code in ("fr", "it", "es", "en"):
        if re.search(rf"(?:^|/){code}(?:/|$)", lower) or re.search(rf"\.{code}\.lh2$", lower) or f"dialog_{code}/" in lower:
            return code.upper()
    if kind == ".lh2" and not re.search(r"\.(?:en|fr|it|es|ss)\.lh2$", lower):
        return "MULTI"
    return "EN" if "pal_en" in lower or "audiostreams/" in lower else "ANY"


def semantic_path(node: dict) -> str:
    return (node.get("member") or node["path"]).replace("\\", "/").lower()


def path_distance(left: str, right: str) -> int:
    a, b = left.split("/")[:-1], right.split("/")[:-1]
    common = 0
    for x, y in zip(a, b):
        if x != y:
            break
        common += 1
    return len(a) + len(b) - 2 * common


class Builder:
    def __init__(self, database: Path, source: Path, extracted: list[Path], max_parse: int = 32 * 1024 * 1024) -> None:
        self.database, self.source, self.extracted, self.max_parse = database, source, extracted, max_parse
        self.db = sqlite3.connect(database)
        self.db.executescript(SCHEMA)
        self.db.execute("PRAGMA journal_mode=OFF")
        self.db.execute("PRAGMA synchronous=OFF")
        registry = json.loads((MODULE / "reversing/docs/reference/naming.json").read_text(encoding="utf-8"))
        self.levels = {}
        self.level_labels = {"Shared": "Shared / global / frontend"}
        for item in registry["folders"]:
            if item["extracted"].startswith(("L0", "L1", "LHub")):
                self.levels[item["original"].lower()] = item["original"]
                self.levels[item["extracted"].lower()] = item["original"]
                self.level_labels[item["original"]] = item["extracted"] + " · " + item["display_name"]
        self.cache: OrderedDict[tuple[str, str], tuple[list[Identifier], str]] = OrderedDict()

    def level_of(self, path: str) -> str:
        return self.levels.get(path.replace("\\", "/").split("/")[0].lower(), "Shared")

    def node(self, view: str, root: str, path: str, level: str, size: int, sha: str = "",
             archive: int | None = None, member: str = "", locator: dict | None = None,
             kind: str | None = None, status: str = "indexed; raw words available") -> int:
        kind = kind or kind_of(path)
        cursor = self.db.execute("INSERT INTO files VALUES(NULL,?,?,?,?,?,?,?,?,?,?,?,?)",
                                 (view, root, path, level, kind, size, sha, archive, member,
                                  json.dumps(locator or {}), status, language_of(member or path, kind)))
        file = cursor.lastrowid
        if view != "member":
            self.identifiers(file, [Identifier("file.name", Path(path).name.lower(), "definition", 0, 0,
                                               "filename", Path(path).name, "provenance", region="filename")])
        return file

    def identifiers(self, file: int, values: list[Identifier]) -> None:
        self.db.executemany("INSERT INTO ids VALUES(NULL,?,?,?,?,?,?,?,?,?,?,?)", [
            (file, value.namespace, value.value, value.role, value.offset, value.width, value.endian,
             value.label, value.confidence, value.doc, value.region) for value in values
        ])

    def edge(self, source: int, target: int, kind: str, label: str, confidence: str = "provenance") -> None:
        self.db.execute("INSERT INTO edges VALUES(NULL,?,?,?,?,?)", (source, target, kind, label, confidence))

    def parse(self, file: int, payload: bytes, kind: str, sha: str) -> None:
        key = (sha, kind)
        if key not in self.cache:
            try:
                values, status = parse_identifiers(payload, kind)
            except (ValueError, IndexError, struct.error, UnicodeError) as exc:
                values, status = [], "Adapter rejected layout: " + str(exc)
            self.cache[key] = values, status
            if len(self.cache) > 512:
                self.cache.popitem(last=False)
        values, status = self.cache[key]
        self.identifiers(file, values)
        self.db.execute("UPDATE files SET status=? WHERE id=?", (status, file))

    def archive(self, path: Path, archive_id: int) -> None:
        raw = path.read_bytes()
        if raw[:4] != b"SToc" or len(raw) < 20:
            raise ValueError("invalid STR header")
        count, info = raw[8], u32(raw, 16)
        if info + count * 24 > len(raw):
            raise ValueError("STR section table outside file")
        level = self.level_of(path.relative_to(self.source).as_posix())
        # Optional StreamFile ID is its own namespace; the filename hash rule is unknown.
        stream = u32(raw, 12)
        if stream:
            value = u32(raw, stream)
            self.identifiers(archive_id, [Identifier("str.stream", f"{value:08X}", "definition", stream,
                                                    4, "BE", "Optional StreamFile GUID32", doc="PS3_GAME/FormatAnalysis/STR/index.html", region="file")])
        base = (info + count * 24 + 2047) & ~2047
        for section in range(count):
            _, _, size, _, stored, _ = struct.unpack_from(">6I", raw, info + section * 24)
            if base + stored > len(raw) or size > 256 * 1024 * 1024:
                raise ValueError("STR section bounds exceed supported range")
            packed = raw[base:base + stored]
            compressed = packed[:2] == b"\x10\xfb"
            data = refpack(packed, size)[0] if compressed else packed[:size]
            if len(data) != size:
                raise ValueError("STR decoded length mismatch")
            offset = 0
            while offset < len(data):
                if offset + 12 > len(data):
                    raise ValueError("short STR record")
                outer, body_size = int.from_bytes(data[offset:offset + 2], "big"), u32(data, offset + 4, "<")
                end, start = offset + 12 + body_size, offset + 12
                if body_size == 0 or end > len(data):
                    raise ValueError("STR record outside section")
                member, resource, asset_guid, guid_pos = "", "", "", 0
                payload_start, payload_size = start, body_size
                body = data[start:end]
                if outer == 0x1607 and body_size >= 4 and u32(body, 0):
                    header = u32(body, 0)
                    cursor, fields = 4, []
                    for part in range(4):
                        if part == 1:
                            guid_pos = start + cursor
                            asset_guid = guid(body, cursor)
                            cursor += 16
                        length = u32(body, cursor)
                        cursor += 4
                        if cursor + length > 4 + header or 4 + header > len(body):
                            raise ValueError("STR asset field outside header")
                        fields.append(body[cursor:cursor + length].split(b"\0")[0].decode("ascii", errors="replace"))
                        cursor += length
                    member, resource = fields[2], fields[1]
                    payload_size, payload_start = u32(body, cursor + 4), start + 4 + header
                    if 4 + header + ((payload_size + 3) & ~3) != body_size:
                        raise ValueError("STR asset/record size disagreement")
                suffix = f"s{section:03d}_o{offset:08x}"
                if not member:
                    if outer == 0x2207 and body[8:12] == b"SimG":
                        member = "simgroup_" + suffix + ".dat.simgroup"
                    elif resource == "UIE":
                        member = "uie_" + suffix + ".dat.uie"
                    elif outer == 0x1607 and resource:
                        member = "unnamed_asset_" + suffix + ".dat"
                    else:
                        member = f"chunk_{outer:04x}_" + suffix + ".dat"
                elif resource == "UIE" and member.lower().endswith(".dat"):
                    member += ".uie"
                payload = data[payload_start:payload_start + payload_size]
                sha = hashlib.sha256(payload).hexdigest()
                locator = {"archive": str(path), "section": section, "section_file_offset": base,
                           "stored_size": stored, "decoded_size": size, "compressed": compressed,
                           "payload_start": payload_start, "payload_size": payload_size,
                           "record_offset": offset, "outer_type": f"{outer:04X}", "resource_type": resource}
                display = path.relative_to(self.source).as_posix() + f" :: {suffix}/" + member.replace("\\", "/")
                kind = ".dat.uie" if resource == "UIE" and kind_of(member) == ".dat.uie" else kind_of(member)
                child = self.node("member", str(self.source), display, level, len(payload), sha,
                                  archive_id, member, locator, kind)
                self.edge(archive_id, child, "contains", f"STR section {section}, record +0x{offset:X}")
                self.identifiers(child, [Identifier("file.name", member.replace("\\", "/").split("/")[-1].lower(),
                                                   "definition", 0, 0, "member filename", member, "provenance", region="filename")])
                if asset_guid and asset_guid not in INVALID_GUIDS:
                    self.identifiers(child, [Identifier("asset.guid", asset_guid, "definition", guid_pos, 16,
                                                       "BE words", "STR asset metadata GUID", "structural",
                                                       "PS3_GAME/FormatAnalysis/STR/index.html#embedded-asset-chunk-0x1607", "decompressed section")])
                if len(payload) <= self.max_parse and kind not in MEDIA:
                    self.parse(child, payload, kind, sha)
                else:
                    self.db.execute("UPDATE files SET status=? WHERE id=?", ("opaque media or over parse limit; raw words available on demand", child))
                offset = end
            base += stored
        if base != len(raw):
            raise ValueError("STR trailing bytes outside declared sections")
        self.db.execute("UPDATE files SET status=? WHERE id=?", ("bounded original STR record walk; children carry exact source coordinates", archive_id))

    def build(self) -> dict:
        started = time.time()
        source_paths, archives = walk_files(self.source), []
        print(f"Inventory {len(source_paths)} original physical files", flush=True)
        for index, path in enumerate(source_paths):
            rel, size = path.relative_to(self.source).as_posix(), path.stat().st_size
            kind = kind_of(rel)
            sha = hash_file(path)
            file = self.node("source", str(self.source), rel, self.level_of(rel), size, sha)
            if kind == ".str":
                archives.append((path, file))
            elif size <= self.max_parse and kind not in MEDIA:
                self.parse(file, path.read_bytes(), kind, sha)
            if index % 2000 == 0:
                print(f"Original files {index + 1}/{len(source_paths)}", flush=True)
        for index, (path, file) in enumerate(archives):
            try:
                self.archive(path, file)
            except (AssertionError, ValueError, IndexError, struct.error) as exc:
                self.db.execute("UPDATE files SET status=? WHERE id=?", ("STR parse failed/partial: " + str(exc), file))
            if index % 25 == 0:
                self.db.commit()
                print(f"STR archives {index + 1}/{len(archives)}", flush=True)
        self.db.commit()
        source_sizes = {row[0] for row in self.db.execute("SELECT DISTINCT size FROM files")}
        self.db.row_factory = sqlite3.Row
        for root in self.extracted:
            paths = walk_files(root)
            print(f"Inventory extracted root {root.name}: {len(paths)} files", flush=True)
            for index, path in enumerate(paths):
                rel, size = path.relative_to(root).as_posix(), path.stat().st_size
                kind, level = kind_of(rel), self.level_of(rel)
                # Media exports and Blender projects can be enormous. Hash candidates
                # only when their length can equal a known original/member payload.
                sha = hash_file(path) if size in source_sizes else ""
                file = self.node("extracted", str(root), rel, level, size, sha)
                matches = [dict(r) for r in self.db.execute(
                    "SELECT * FROM files WHERE sha256=? AND view IN ('member','source')", (sha,))] if sha else []
                if matches:
                    current = dict(self.db.execute("SELECT * FROM files WHERE id=?", (file,)).fetchone())
                    same_level = [r for r in matches if r["level"] == level]
                    matches = same_level or [r for r in matches if r["level"] == "Shared"]
                    # A source archive's extraction folder is usually NAME_str.
                    def origin_score(item: dict) -> tuple:
                        archive = dict(self.db.execute("SELECT * FROM files WHERE id=?", (item["archive"],)).fetchone()) if item["archive"] else item
                        stem = Path(archive["path"]).stem.lower() + "_str"
                        return (0 if stem in rel.lower().split("/") else 1,
                                -os.path.commonprefix([semantic_path(current)[::-1], semantic_path(item)[::-1]]).__len__())
                    if matches:
                        best = min(map(origin_score, matches))
                        nearest = [m for m in matches if origin_score(m) == best]
                        for original in nearest:
                            self.edge(original["id"], file, "extracted copy", "SHA-256 identical original payload")
                        # Preserve all tied origins as edges, not a guessed single origin.
                        if len(nearest) == 1:
                            original = nearest[0]
                            self.db.execute("UPDATE files SET archive=?,member=?,language=? WHERE id=?",
                                            (original["archive"], original["member"], original["language"], file))
                        ids = {}
                        for original in nearest:
                            for row in self.db.execute("SELECT * FROM ids WHERE file=?", (original["id"],)):
                                if row["region"] == "decompressed section":
                                    continue  # It is not an embedded ID in the output bytes.
                                key = (row["namespace"], row["value"], row["role"], row["offset"])
                                ids[key] = tuple(row[k] for k in ("namespace", "value", "role", "offset", "width", "endian", "label", "confidence", "doc", "region"))
                            # Metadata GUID identifies the extracted file via verified
                            # provenance; keep its region explicitly outside the output.
                            for row in self.db.execute("SELECT * FROM ids WHERE file=? AND namespace='asset.guid'", (original["id"],)):
                                key = ("asset.guid", row["value"], "definition", 0)
                                ids[key] = (row["namespace"], row["value"], "definition", row["offset"], row["width"], row["endian"],
                                            "Origin STR metadata GUID (not stored in output payload)", "provenance", row["doc"], "origin STR metadata")
                        self.db.executemany("INSERT INTO ids VALUES(NULL,?,?,?,?,?,?,?,?,?,?,?)", [(file, *values) for values in ids.values()])
                        self.db.execute("UPDATE files SET status=? WHERE id=?", ("byte-identical original copy; " + nearest[0]["status"], file))
                else:
                    self.db.execute("UPDATE files SET status=? WHERE id=?", ("no byte-identical original origin established; raw words available", file))
                    if size <= self.max_parse and kind not in MEDIA:
                        self.parse(file, path.read_bytes(), kind, sha or hash_file(path))
                if index % 2000 == 0:
                    self.db.commit()
                    print(f"Extracted files {index + 1}/{len(paths)}", flush=True)
        summary = {"built_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "source": str(self.source),
                   "extracted": list(map(str, self.extracted)), "seconds": round(time.time() - started, 2),
                   "files": self.db.execute("SELECT COUNT(*) FROM files").fetchone()[0],
                   "identifiers": self.db.execute("SELECT COUNT(*) FROM ids").fetchone()[0],
                   "provenance_edges": self.db.execute("SELECT COUNT(*) FROM edges").fetchone()[0],
                   "level_labels": self.level_labels, "max_parse_bytes": self.max_parse,
                   "resolution": "same archive, same level, compatible language, nearest semantic path; shared fallback; cross-level disabled by default",
                   "limitations": "Raw matches are numeric coincidences until their namespace/field meaning is verified. Nearest-copy ranking is an inspection policy, not observed game loading behavior."}
        self.db.execute("INSERT INTO meta VALUES('summary',?)", (json.dumps(summary),))
        self.db.execute("ANALYZE")
        self.db.commit()
        self.db.close()
        return summary


class Explorer:
    def __init__(self, database: Path) -> None:
        self.database = database
        self.db = sqlite3.connect(f"file:{database.as_posix()}?mode=ro", uri=True, check_same_thread=False)
        self.db.row_factory = sqlite3.Row
        self.sections: OrderedDict[tuple, bytes] = OrderedDict()

    def summary(self) -> dict:
        return json.loads(self.db.execute("SELECT value FROM meta WHERE key='summary'").fetchone()[0])

    def file(self, identifier: int) -> dict:
        row = self.db.execute("SELECT * FROM files WHERE id=?", (identifier,)).fetchone()
        if row is None:
            raise ValueError("file not found")
        return dict(row)

    def read(self, file: dict, start: int = 0, length: int | None = None) -> bytes:
        if file["view"] != "member":
            path = Path(file["root"]) / file["path"]
            with path.open("rb") as stream:
                stream.seek(start)
                return stream.read(length) if length is not None else stream.read()
        loc = json.loads(file["locator"])
        key = (loc["archive"], loc["section_file_offset"], loc["stored_size"])
        if key not in self.sections:
            with Path(loc["archive"]).open("rb") as stream:
                stream.seek(loc["section_file_offset"])
                raw = stream.read(loc["stored_size"])
            self.sections[key] = refpack(raw, loc["decoded_size"])[0] if loc["compressed"] else raw[:loc["decoded_size"]]
            if len(self.sections) > 2:
                self.sections.popitem(last=False)
        offset = loc["payload_start"] + start
        stop = loc["payload_start"] + loc["payload_size"] if length is None else offset + length
        return self.sections[key][offset:stop]

    def resolve(self, observation: dict, source: dict, view: str = "member", cross: bool = False,
                language: str = "auto", limit: int = 8) -> dict:
        namespace = observation["namespace"]
        spaces = ("bone.alias", "bone.rig") if namespace == "bone.binding" else (namespace,)
        marks = ",".join("?" for _ in spaces)
        rows = self.db.execute(f"SELECT f.*,i.id AS definition,i.offset AS target_offset,i.region AS target_region,i.label AS target_label,i.namespace AS target_namespace FROM ids i JOIN files f ON f.id=i.file WHERE i.role='definition' AND i.namespace IN ({marks}) AND i.value=? LIMIT 5001", (*spaces, observation["value"])).fetchall()
        options, excluded = {}, 0
        wanted_language = source["language"] if language == "auto" else language
        for row in rows[:5000]:
            target = dict(row)
            if target["level"] not in {source["level"], "Shared"} and not cross:
                excluded += 1
                continue
            if wanted_language not in {"ANY", "MULTI"} and target["language"] not in {wanted_language, "MULTI", "ANY"}:
                continue
            representation = source["view"] if view == "both" else view
            same_archive = source["archive"] is not None and source["archive"] == target["archive"]
            rank = (0 if same_archive else 1,
                    0 if target["level"] == source["level"] else 1 if target["level"] == "Shared" else 2,
                    0 if target["view"] == representation else 1,
                    path_distance(semantic_path(source), semantic_path(target)),
                    0 if target["target_namespace"] == "bone.alias" else 1)
            if target["id"] not in options or rank < options[target["id"]][0]:
                options[target["id"]] = (rank, target)
        ordered = sorted(options.values(), key=lambda item: (item[0], item[1]["path"], item[1]["id"]))
        if not ordered:
            return {"status": "unresolved", "targets": [], "alternatives": [], "candidate_files": 0,
                    "excluded_cross_level": excluded, "catalog_truncated": len(rows) > 5000}
        best = [target for rank, target in ordered if rank == ordered[0][0]]
        same_bytes = len({t["sha256"] for t in best}) == 1 and bool(best[0]["sha256"])
        status = "resolved" if len(best) == 1 else "equivalent copies" if same_bytes else "ambiguous"
        selected = best[:1] if same_bytes else best[:limit]
        selected_ids = {t["id"] for t in selected}
        return {"status": status, "targets": selected, "alternatives": [t for _, t in ordered if t["id"] not in selected_ids][:limit],
                "candidate_files": len(options), "best_ties": len(best), "excluded_cross_level": excluded,
                "catalog_truncated": len(rows) > 5000, "policy": "archive → level → view → path distance; shared fallback"}

    def search(self, level: str = "", query: str = "", view: str = "member", kind: str = "",
               offset: int = 0, limit: int = 80, shared: bool = False) -> dict:
        clauses, args = [], []
        if level:
            clauses.append("f.level IN (?, 'Shared')" if shared else "f.level=?")
            args.append(level)
        if view != "both":
            clauses.append("f.view=?")
            args.append(view)
        if kind:
            clauses.append("f.format=?")
            args.append(kind)
        if query:
            clauses.append("(f.path LIKE ? OR EXISTS(SELECT 1 FROM ids i WHERE i.file=f.id AND (i.value=? OR i.label LIKE ?)))")
            args.extend(("%" + query + "%", query.upper().removeprefix("0X").replace("-", ""), "%" + query + "%"))
        where = " WHERE " + " AND ".join(clauses) if clauses else ""
        total = self.db.execute("SELECT COUNT(*) FROM files f" + where, args).fetchone()[0]
        rows = self.db.execute("SELECT f.* FROM files f" + where + " ORDER BY f.path,f.id LIMIT ? OFFSET ?", (*args, limit, offset)).fetchall()
        return {"files": [dict(r) for r in rows], "total": total, "offset": offset, "limit": limit}

    def identifiers(self, file_id: int, offset: int, limit: int, **options: object) -> dict:
        source = self.file(file_id)
        total = self.db.execute("SELECT COUNT(*) FROM ids WHERE file=?", (file_id,)).fetchone()[0]
        rows = [dict(r) for r in self.db.execute("SELECT * FROM ids WHERE file=? ORDER BY offset,id LIMIT ? OFFSET ?", (file_id, limit, offset))]
        for row in rows:
            if row["role"] == "reference":
                row["resolution"] = self.resolve(row, source, **options)
        return {"file": source, "identifiers": rows, "total": total, "offset": offset}

    def words(self, file_id: int, offset: int, limit: int, step: int = 4, **options: object) -> dict:
        source = self.file(file_id)
        data = self.read(source, offset, limit * step + 15)
        values = []
        for index in range(limit):
            pos = index * step
            if pos + 4 > len(data):
                break
            raw = data[pos:pos + 4]
            row = {"offset": offset + pos, "raw": raw.hex().upper(), "be": int.from_bytes(raw, "big"),
                   "le": int.from_bytes(raw, "little"), "matches": []}
            for order, value in (("BE", row["be"]), ("LE", row["le"])):
                if value in (0, 0xFFFFFFFF):
                    continue
                key = f"{value:08X}"
                spaces = [r[0] for r in self.db.execute("SELECT DISTINCT namespace FROM ids WHERE role='definition' AND value=? LIMIT 20", (key,))]
                for namespace in spaces:
                    resolution = self.resolve({"namespace": namespace, "value": key}, source, **options)
                    if resolution["targets"]:
                        row["matches"].append({"namespace": namespace, "value": key, "endian": order,
                                               "confidence": "raw candidate (not a verified reference)", "resolution": resolution})
            if pos + 16 <= len(data):
                for order in (">", "<"):
                    key = guid(data, pos, order)
                    if key in INVALID_GUIDS:
                        continue
                    for namespace in ("asset.guid", "entity.guid", "graph.guid", "metamodel.guid"):
                        if self.db.execute("SELECT 1 FROM ids WHERE role='definition' AND namespace=? AND value=? LIMIT 1", (namespace, key)).fetchone():
                            resolution = self.resolve({"namespace": namespace, "value": key}, source, **options)
                            if resolution["targets"]:
                                row["matches"].append({"namespace": namespace, "value": key, "endian": "BE words" if order == ">" else "LE words",
                                                       "confidence": "raw GUID candidate", "resolution": resolution})
            values.append(row)
        return {"file": source, "words": values, "offset": offset, "step": step,
                "next_offset": offset + len(values) * step, "size": source["size"],
                "notice": "Numbers include floats, flags and pointers. A raw equality is a candidate, not proof of a file reference."}

    def graph(self, file_id: int, depth: int = 1, maximum: int = 160, incoming: bool = False, **options: object) -> dict:
        files, ids, edges, queue, seen = {}, {}, [], [(file_id, 0)], set()
        truncated = False
        while queue:
            current, distance = queue.pop(0)
            if current in seen:
                continue
            seen.add(current)
            source = self.file(current)
            files[current] = source
            if distance >= depth:
                continue
            references = self.db.execute("SELECT * FROM ids WHERE file=? AND role='reference' ORDER BY offset,id LIMIT 1001", (current,)).fetchall()
            if len(references) > 1000:
                truncated = True
            for observation in references[:1000]:
                if len(files) + len(ids) >= maximum:
                    truncated = True
                    break
                obs = dict(observation)
                resolution = self.resolve(obs, source, **options)
                ids[obs["id"]] = {**obs, "resolution": resolution}
                edges.append({"source": "f" + str(current), "target": "i" + str(obs["id"]), "kind": obs["confidence"], "label": obs["namespace"]})
                for target in resolution["targets"]:
                    if len(files) + len(ids) >= maximum:
                        truncated = True
                        break
                    files[target["id"]] = self.file(target["id"])
                    edges.append({"source": "i" + str(obs["id"]), "target": "f" + str(target["id"]),
                                  "kind": "ambiguous" if resolution["status"] == "ambiguous" else obs["confidence"], "label": resolution["status"]})
                    queue.append((target["id"], distance + 1))
            for relation in self.db.execute("SELECT * FROM edges WHERE source=? OR target=? LIMIT 81", (current, current)):
                other = relation["target"] if relation["source"] == current else relation["source"]
                if relation["kind"] == "contains" and relation["source"] == current and source["view"] != "source":
                    continue
                if len(files) + len(ids) >= maximum:
                    truncated = True
                    break
                files[other] = self.file(other)
                edges.append({"source": "f" + str(relation["source"]), "target": "f" + str(relation["target"]),
                              "kind": "provenance", "label": relation["kind"]})
                # Do not expand every archive sibling just because provenance is shown.
            if incoming:
                for definition in self.db.execute("SELECT DISTINCT namespace,value FROM ids WHERE file=? AND role='definition' LIMIT 100", (current,)):
                    refs = self.db.execute("SELECT * FROM ids WHERE namespace=? AND value=? AND role='reference' LIMIT 100", tuple(definition)).fetchall()
                    for row in refs:
                        other = self.file(row["file"])
                        resolution = self.resolve(dict(row), other, **options)
                        if current not in {r["id"] for r in resolution["targets"]}:
                            continue
                        if len(files) + len(ids) + 2 > maximum:
                            truncated = True
                            break
                        files[other["id"]] = other
                        ids[row["id"]] = {**dict(row), "resolution": resolution}
                        edges.extend([{"source": "f" + str(other["id"]), "target": "i" + str(row["id"]), "kind": "structural", "label": row["namespace"]},
                                      {"source": "i" + str(row["id"]), "target": "f" + str(current), "kind": "structural", "label": "incoming"}])
        return {"files": list(files.values()), "identifiers": list(ids.values()), "edges": edges,
                "focus": file_id, "truncated": truncated, "maximum": maximum,
                "notice": "Graph shows a bounded neighborhood. All observations remain pageable in the ID inspector. Nearest-copy choice is an inspection policy."}

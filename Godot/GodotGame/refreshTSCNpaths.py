"""Refresh scene asset paths from the maps copied into this Godot project's assets.

Run after operations/copyassets.ps1. No game region or external GameFiles map is
assumed. Historical UID migrations are deliberately outside this normal updater.
"""

from __future__ import annotations

import argparse
import json
import re
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Callable, Iterable

ASSET_PREFIX = "res://assets/"
ASSET_PATH_RE = re.compile(r'(?<=")res://assets/[^"\r\n]+(?=")')
FILENAME_UID_RE = re.compile(r"_([0-9a-fA-F]{6,})$")
GODOT_UID_RE = re.compile(r'\s+uid="uid://[^"\r\n]+"')
CONVERTED_EXTENSIONS = {
    ".preinstanced": {".glb", ".fbx", ".blend"},
    ".inf": {".fnt"},
    ".vp6": {".ogv"},
}


@dataclass(frozen=True)
class AssetEntry:
    uid: str
    original_path: str
    new_path: str


def extract_uid(asset_path: str) -> str | None:
    """Read the asset UID before the first extension, including .rws.PS3.glb."""
    filename = asset_path.replace("\\", "/").rsplit("/", 1)[-1]
    match = FILENAME_UID_RE.search(filename.split(".", 1)[0])
    return match.group(1).lower() if match else None


def relative_asset_path(value: object, context: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{context}: expected a nonempty relative path")
    path = value.replace("\\", "/")
    if path.startswith("/") or ":" in path or ".." in path.split("/"):
        raise ValueError(f"{context}: unsafe relative path: {value!r}")
    return str(PurePosixPath(path))


def discover_maps(assets_root: Path) -> list[Path]:
    if not assets_root.is_dir():
        raise ValueError(f"Assets directory not found: {assets_root}. Run operations/copyassets.ps1 first.")
    full_map = assets_root / "normalized_map.json"
    maps = [full_map] if full_map.is_file() else sorted(assets_root.glob("map_*.json"))
    maps = [path for path in maps if path.is_file()]
    if not maps:
        raise ValueError(f"No normalized_map.json or map_*.json found in {assets_root}. Copy the asset maps with the assets.")
    return maps


def load_asset_maps(map_paths: Iterable[Path]) -> list[AssetEntry]:
    entries: dict[AssetEntry, None] = {}
    for map_path in map_paths:
        try:
            data = json.loads(map_path.read_text(encoding="utf-8-sig"))
        except (OSError, ValueError) as exc:
            raise ValueError(f"Cannot read asset map {map_path}: {exc}") from exc
        if not isinstance(data, list):
            raise ValueError(f"{map_path}: expected an array of asset mappings")
        for index, row in enumerate(data):
            context = f"{map_path}, entry {index + 1}"
            if not isinstance(row, dict) or not isinstance(row.get("uid"), str) or not re.fullmatch(r"[0-9a-fA-F]{6,}", row["uid"]):
                raise ValueError(f"{context}: missing or invalid asset UID")
            entry = AssetEntry(
                row["uid"].lower(),
                relative_asset_path(row.get("original_path"), context),
                relative_asset_path(row.get("new_path"), context),
            )
            entries[entry] = None
    if not entries:
        raise ValueError("Asset maps contain no mappings; no scenes were changed.")
    return list(entries)


def target_path(entry: AssetEntry, reference: str) -> str | None:
    """Preserve the requested export format when the map indexes its source."""
    source = PurePosixPath(entry.new_path)
    extension = PurePosixPath(reference).suffix.lower()
    if source.suffix.lower() == extension:
        return entry.new_path
    if extension in CONVERTED_EXTENSIONS.get(source.suffix.lower(), set()):
        return str(source.with_suffix(extension))
    return None


class AssetResolver:
    def __init__(self, entries: Iterable[AssetEntry], assets_root: Path):
        self.assets_root = assets_root.resolve()
        self.by_uid: dict[str, list[AssetEntry]] = defaultdict(list)
        for entry in entries:
            self.by_uid[entry.uid].append(entry)

    def __call__(self, reference: str) -> tuple[str | None, str]:
        uid = extract_uid(reference)
        if not uid:
            return None, "no_uid"
        targets = {path for entry in self.by_uid.get(uid, []) if (path := target_path(entry, reference))}
        if not targets:
            return None, "missing_uid_or_format"
        if len(targets) > 1:
            current = reference.removeprefix(ASSET_PREFIX)
            if current not in targets:
                return None, "ambiguous_uid"
            targets = {current}
        target = targets.pop()
        asset_file = (self.assets_root / target).resolve()
        if not asset_file.is_relative_to(self.assets_root) or not asset_file.is_file():
            return None, "missing_asset_file"
        return ASSET_PREFIX + target, "resolved"


def refresh_scenes(
    project_root: Path,
    resolver: Callable[[str], tuple[str | None, str]],
    dry_run: bool = False,
) -> tuple[Counter, dict[str, set[str]]]:
    if not project_root.is_dir():
        raise ValueError(f"Godot project directory not found: {project_root}")
    stats: Counter = Counter()
    unresolved: dict[str, set[str]] = defaultdict(set)
    scenes = sorted(path for path in project_root.rglob("*.tscn")
                    if not {".godot", "assets"}.intersection(path.relative_to(project_root).parts))
    if not scenes:
        print(f"[WARNING] No .tscn files found in {project_root}")
    for scene in scenes:
        stats["scanned_files"] += 1
        content = scene.read_bytes().decode("utf-8")  # Preserve BOM and line endings.
        changes: list[tuple[str, str]] = []

        def replace_path(match: re.Match) -> str:
            old = match.group(0)
            new, reason = resolver(old)
            if new is None:
                stats[reason] += 1
                unresolved[reason].add(f"{scene}: {old}")
                return old
            if new == old:
                stats["already_correct"] += 1
                return old
            changes.append((old, new))
            stats["updated_references"] += 1
            return new

        lines = []
        for line in content.splitlines(keepends=True):
            updated = ASSET_PATH_RE.sub(replace_path, line)
            if updated != line and line.lstrip().startswith("[ext_resource "):
                # The imported Godot UID is independent of the six-character asset UID.
                # Let Godot import the corrected path instead of following a stale hint.
                updated, removed = GODOT_UID_RE.subn("", updated)
                stats["cleared_godot_uid_hints"] += removed
            lines.append(updated)
        if changes:
            stats["modified_files"] += 1
            print(f"[{'PREVIEW' if dry_run else 'UPDATED'}] {scene} ({len(changes)} references)")
            if not dry_run:
                scene.write_bytes("".join(lines).encode("utf-8"))
    return stats, unresolved


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project", type=Path, default=Path(__file__).resolve().parent / "PreBuilt",
                        help="Godot project directory (default: PreBuilt beside this script)")
    parser.add_argument("--dry-run", action="store_true", help="Preview changes without writing scenes")
    args = parser.parse_args()
    try:
        if not args.project.is_dir():
            raise ValueError(f"Godot project directory not found: {args.project}")
        assets_root = args.project / "assets"
        maps = discover_maps(assets_root)
        entries = load_asset_maps(maps)
        print(f"Loaded {len(entries):,} mappings from: {', '.join(str(path) for path in maps)}")
        stats, unresolved = refresh_scenes(args.project, AssetResolver(entries, assets_root), args.dry_run)
    except (OSError, UnicodeError, ValueError) as exc:
        print(f"[ERROR] {exc}")
        return 1
    for reason, references in sorted(unresolved.items()):
        print(f"[WARNING] {reason}: {len(references)} unique unresolved references (left unchanged)")
        for reference in sorted(references):
            print(f"  {reference}")
    print("Summary: " + ", ".join(f"{key}={value}" for key, value in sorted(stats.items())))
    if args.dry_run:
        print("Dry run: no scenes were modified.")
    return 1 if unresolved else 0


if __name__ == "__main__":
    raise SystemExit(main())

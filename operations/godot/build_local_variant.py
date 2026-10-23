"""Build an isolated, disposable Godot project from the canonical EU scenes.

No input is ever rewritten. All generated content (including game geometry and
Godot imports) lives in ignored LocalVariant/ or .local_variant_work/ directories.
Requires Python 3.11+ and Godot 4.6+. See local_variant.md beside this file.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import stat
import subprocess
import sys
import tomllib
from typing import Any

from refreshTSCNpaths import AssetEntry, discover_maps, extract_uid, load_asset_maps, target_path

MODULE = Path(__file__).resolve().parents[2]
CANONICAL = MODULE / 'Godot/GodotGame/PreBuilt'
OUTPUT = CANONICAL.parent / 'LocalVariant'
WORK = CANONICAL.parent / '.local_variant_work'
MARKER = '.local_variant_owned.json'
HEADER = re.compile(r'^\[(?:gd_scene|gd_resource|resource|ext_resource|sub_resource|node|connection|editable)\b[^\n]*\]\s*$', re.M)
ATTR = re.compile(r'(\w+)="((?:\\.|[^"\\])*)"')
RESOURCE = re.compile(r'\b(ExtResource|SubResource)\("([^"\n]+)"\)')
RES_PATH = re.compile(r'"(res://[^"\r\n]+)"')
TEXT_TYPES = {'.tscn', '.tres', '.gd', '.godot', '.gdshader', '.gdshaderinc', '.cfg', '.fnt'}
SKIP_DIRS = {'assets', '.godot', '.git', '.history', '.backup', '__pycache__'}


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')


def checked_path(root: Path, relative: str) -> Path:
    path = (root / relative).resolve()
    if not path.is_relative_to(root.resolve()):
        raise ValueError(f'Path escapes input root: {relative}')
    return path


def owned_remove(path: Path, expected_parent: Path) -> None:
    """Only delete this tool's fixed, marked output; never follow directory links."""
    if path.is_symlink() or path.resolve().parent != expected_parent.resolve():
        raise ValueError(f'Refusing to remove unsafe output: {path}')
    if path.exists():
        marker = path / MARKER
        if not marker.is_file() or json.loads(marker.read_text(encoding='utf-8')).get('tool') != 'local_variant':
            raise ValueError(f'Refusing to remove an unowned directory: {path}')
        def retry_readonly(function: Any, failed: str, error: Any) -> None:
            target = Path(failed)
            if not target.resolve().is_relative_to(path.resolve()):
                raise ValueError(f'Refusing to change permissions outside output: {target}')
            target.chmod(stat.S_IWRITE | stat.S_IREAD)
            function(failed)
        shutil.rmtree(path, onerror=retry_readonly)


@dataclass
class Block:
    header: str
    body: str

    @property
    def kind(self) -> str:
        return self.header[1:].split()[0].rstrip(']')

    @property
    def attrs(self) -> dict[str, str]:
        return dict(ATTR.findall(self.header))

    def text(self) -> str:
        return self.header.rstrip() + '\n' + self.body.strip('\n') + '\n\n'


def parse_blocks(text: str) -> list[Block]:
    matches = list(HEADER.finditer(text))
    return [Block(m.group().rstrip(), text[m.end():matches[i + 1].start() if i + 1 < len(matches) else len(text)])
            for i, m in enumerate(matches)]


def node_path(block: Block) -> str:
    attrs = block.attrs
    if 'parent' not in attrs:
        return '.'
    return attrs['name'] if attrs['parent'] == '.' else attrs['parent'] + '/' + attrs['name']


def descendants(path: str, roots: set[str]) -> bool:
    return any(root == '.' or path == root or path.startswith(root + '/') for root in roots)


def prune_resources(blocks: list[Block]) -> list[Block]:
    """Keep only resources reachable from nodes/connections (or a .tres root)."""
    resources = {(('ExtResource' if b.kind == 'ext_resource' else 'SubResource'), b.attrs['id']): b
                 for b in blocks if b.kind in {'ext_resource', 'sub_resource'}}
    required = set()
    pending = [ref for b in blocks if b.kind not in {'ext_resource', 'sub_resource'} for ref in RESOURCE.findall(b.text())]
    while pending:
        key = pending.pop()
        if key in required:
            continue
        required.add(key)
        if key in resources:
            pending.extend(RESOURCE.findall(resources[key].text()))
    return [b for b in blocks if b.kind not in {'ext_resource', 'sub_resource'} or
            ('ExtResource' if b.kind == 'ext_resource' else 'SubResource', b.attrs['id']) in required]


class VariantBuilder:
    def __init__(self, project: Path, assets: Path, source: Path | None, collision: bool = True, logos: Path | None = None):
        self.project = project.resolve()
        self.assets = assets.resolve()
        self.source = source.resolve() if source else None
        self.logos = (logos or self.assets.parent / 'logos').resolve()
        self.collision = collision
        self.entries = load_asset_maps(discover_maps(self.assets))
        self.by_uid: dict[str, list[AssetEntry]] = defaultdict(list)
        self.collision_by_directory: dict[str, list[AssetEntry]] = defaultdict(list)
        for entry in self.entries:
            self.by_uid[entry.uid].append(entry)
            if re.search(r'\.(hkt|hko)\.[^.]+$', entry.new_path, re.I):
                self.collision_by_directory[str(PurePosixPath(entry.original_path).parent)].append(entry)
        self.report: dict[str, Any] = {'schema_version': 1, 'canonical_project': str(self.project),
                                     'assets': str(self.assets), 'source': str(self.source),
                                     'logos': str(self.logos),
                                     'collision_enabled': collision, 'disabled': [], 'collisions': [], 'warnings': []}
        self.materialized: set[str] = set()
        self.jobs: dict[str, dict[str, Any]] = {}
        self.attachments: list[dict[str, str]] = []
        self.scene_instances: list[dict[str, str]] = []
        self._source_entries: dict[str, list[AssetEntry]] | None = None
        self.preview = False

    def auxiliary(self, reference: str, stage: Path) -> bool:
        if not reference.startswith('res://logos/'):
            return False
        original = checked_path(self.logos, reference.removeprefix('res://logos/'))
        if not original.is_file():
            return False
        if not self.preview:
            target = stage / reference[6:]
            target.parent.mkdir(parents=True, exist_ok=True)
            if not target.exists():
                shutil.copy2(original, target)
        return True

    def resolve(self, reference: str) -> tuple[str | None, str]:
        uid = extract_uid(reference)
        if not uid:
            return None, 'no_normalization_uid'
        targets = {p for e in self.by_uid.get(uid, []) if (p := target_path(e, reference))}
        if len(targets) != 1:
            return None, 'ambiguous_uid' if targets else 'missing_uid_or_format'
        target = targets.pop()
        if not checked_path(self.assets, target).is_file():
            return None, 'missing_asset_file'
        return 'res://assets/' + target, 'resolved'

    def materialize(self, reference: str, stage: Path) -> None:
        """Copy referenced files, never link mutable imports to supplied assets."""
        if reference in self.materialized:
            return
        self.materialized.add(reference)
        relative = reference.removeprefix('res://assets/')
        original = checked_path(self.assets, relative)
        target = stage / 'assets' / relative
        if not self.preview:
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(original, target)
        # BMFont pages and glTF external buffers/images use file-relative paths.
        dependencies: list[str] = []
        if original.suffix.lower() == '.fnt':
            dependencies = re.findall(r'\bfile="([^"]+)"', original.read_text(encoding='utf-8-sig'))
        elif original.suffix.lower() == '.gltf':
            data = json.loads(original.read_text(encoding='utf-8-sig'))
            dependencies = [item['uri'] for group in ('buffers', 'images') for item in data.get(group, [])
                            if 'uri' in item and not item['uri'].startswith('data:')]
        for dependency in dependencies:
            dep = checked_path(self.assets, str(PurePosixPath(relative).parent / dependency))
            if not dep.is_file():
                raise ValueError(f'Missing asset dependency: {original}: {dependency}')
            self.materialize('res://assets/' + dep.relative_to(self.assets).as_posix(), stage)

    def collision_job(self, reference: str) -> tuple[str | None, str]:
        uid = extract_uid(reference)
        records = self.by_uid.get(uid or '', [])
        models = [e for e in records if target_path(e, reference) == reference.removeprefix('res://assets/')]
        if len(models) != 1:
            return None, 'ambiguous_model_mapping'
        model = models[0]
        if model.original_path.casefold().startswith('a2_characters/'):
            return None, 'character_collision_excluded'
        # Work in canonical map paths, never normalized directory spellings.
        path = PurePosixPath(model.original_path)
        directory = path.parent.parent if path.parent.name.casefold() == 'terrain' else path.parent
        candidates = self.collision_by_directory.get(str(directory / 'collision'), []) + self.collision_by_directory.get(str(directory), [])
        if len(candidates) != 1:
            return None, 'ambiguous_collision' if candidates else 'no_original_collision_match'
        if not self.source:
            return None, 'no_collision_source_selected'
        if self._source_entries is None:
            self._source_entries = defaultdict(list)
            for entry in load_asset_maps(discover_maps(self.source)):
                self._source_entries[entry.uid].append(entry)
        entry = candidates[0]
        for expected in (model, entry):
            if self._source_entries.get(expected.uid) != [expected]:
                raise ValueError(f'Selected source maps disagree with asset dataset for UID {expected.uid}')
        # If the selected source contains the converted model, require the same bytes.
        exported = checked_path(self.source, reference.removeprefix('res://assets/'))
        if exported.is_file() and digest(exported) != digest(checked_path(self.assets, reference.removeprefix('res://assets/'))):
            raise ValueError(f'Selected source GLB differs from asset dataset for UID {model.uid}')
        raw = checked_path(self.source, entry.new_path)
        if not raw.is_file():
            return None, 'missing_collision_file'
        key = entry.uid
        self.jobs[key] = {'uid': key, 'source': str(raw), 'source_hash': digest(raw),
                          'canonical_path': entry.original_path,
                          'output': f'res://generated_collision/{key}.tscn'}
        return key, 'pending'

    def adapt_scene(self, text: str, relative: str, stage: Path) -> str:
        blocks = prune_resources(parse_blocks(text))
        # Imported cache filenames are machine-specific. Recover the normalized
        # source UID rather than copying anyone's .godot import artifacts.
        for b in blocks:
            if b.kind != 'sub_resource' or b.attrs.get('type') != 'CompressedTexture2D':
                continue
            cached = re.search(r'load_path\s*=\s*"res://\.godot/imported/(.+)-[0-9a-f]{32}\.ctex"', b.body)
            if cached:
                rid = b.attrs['id']
                resolved, reason = self.resolve('res://assets/' + cached[1])
                for other in blocks:
                    other.body = other.body.replace(f'SubResource("{rid}")', f'ExtResource("Recovered_{rid}")' if resolved else 'null')
                if resolved:
                    b.header = f'[ext_resource type="Texture2D" path="{resolved}" id="Recovered_{rid}"]'
                    b.body = ''
                else:
                    self.report['disabled'].append({'scene': relative, 'resource': cached[0], 'reason': reason})
        blocks = prune_resources(blocks)
        resources: dict[str, tuple[str | None, str, str]] = {}
        for b in blocks:
            if b.kind != 'ext_resource':
                continue
            attrs = b.attrs
            b.header = re.sub(r'\s+uid="[^"]+"', '', b.header)
            path = attrs.get('path', '')
            if path.startswith('res://logos/'):
                self.auxiliary(path, stage)
            if path.startswith('res://assets/'):
                resolved, reason = self.resolve(path)
                resources[attrs['id']] = resolved, reason, path
                if resolved:
                    self.materialize(resolved, stage)
                    b.header = re.sub(r'\s+uid="[^"]+"', '', b.header).replace('path="' + path + '"', 'path="' + resolved + '"')
            elif path.startswith('res://') and not (stage / path[6:]).is_file():
                if attrs.get('type') in {'Script', 'Shader', 'PackedScene'}:
                    raise ValueError(f'Missing required resource in {relative}: {path}')
                resources[attrs['id']] = None, 'missing_optional_resource', path

        removed_roots: set[str] = set()
        missing_instances: dict[str, tuple[str, str]] = {}
        glb_roots = set()
        for b in blocks:
            if b.kind != 'node':
                continue
            instance = re.search(r'instance=ExtResource\("([^"]+)"\)', b.header)
            if not instance or instance[1] not in resources:
                continue
            resolved, reason, original = resources[instance[1]]
            path = node_path(b)
            if not resolved:
                missing_instances[path] = original, reason
            elif original.lower().endswith(('.glb', '.gltf')):
                glb_roots.add(path)
                self.scene_instances.append({'scene': relative, 'node': path, 'asset': resolved})
                key, status = self.collision_job(resolved) if self.collision else (None, 'collision_disabled')
                self.report['collisions'].append({'scene': relative, 'node': path, 'asset': resolved, 'uid': key, 'status': status})
                if key:
                    self.attachments.append({'scene': relative, 'node': path, 'uid': key})

        # Only legacy static blockers inside GLB instances are suppressed; player
        # capsules and deliberately authored physics elsewhere remain untouched.
        for b in blocks:
            if b.kind == 'node' and b.attrs.get('type') == 'StaticBody3D' and descendants(node_path(b), glb_roots):
                removed_roots.add(node_path(b))

        output = []
        for b in blocks:
            if b.kind == 'node':
                path = node_path(b)
                if descendants(path, removed_roots) or any(path != root and descendants(path, {root}) for root in missing_instances):
                    continue
                if path in missing_instances:
                    original, reason = missing_instances[path]
                    attrs = b.attrs
                    header = '[node name=' + json.dumps(attrs['name']) + ' type="Node3D"'
                    if 'parent' in attrs:
                        header += ' parent=' + json.dumps(attrs['parent'])
                    if 'unique_id' in b.header:
                        unique = re.search(r'\bunique_id=\d+', b.header)
                        if unique:
                            header += ' ' + unique[0]
                    b.header = header + ']'
                    # Preserve placement, but never active scripts/physics on a stub.
                    b.body = '\n'.join(line for line in b.body.splitlines() if re.match(r'^(transform|position|rotation|scale)\s*=', line))
                    b.body += '\nvisible = false\nprocess_mode = 4\n'
                    b.body += 'metadata/variant_disabled = true\nmetadata/canonical_uid = ' + json.dumps(extract_uid(original) or '') + '\n'
                    b.body += 'metadata/canonical_path = ' + json.dumps(original) + '\nmetadata/disabled_reason = ' + json.dumps(reason) + '\n'
                    self.report['disabled'].append({'scene': relative, 'node': path, 'canonical_path': original, 'reason': reason})
            elif b.kind == 'editable':
                if descendants(b.attrs['path'], removed_roots | set(missing_instances)):
                    continue
            elif b.kind == 'connection':
                if any(descendants(b.attrs.get(k, ''), removed_roots | set(missing_instances)) for k in ('from', 'to')):
                    continue
            if b.kind == 'ext_resource' and b.attrs.get('id') in resources and resources[b.attrs['id']][0] is None:
                continue
            for rid, (resolved, reason, original) in resources.items():
                if resolved is None and f'ExtResource("{rid}")' in b.body:
                    b.body = b.body.replace(f'ExtResource("{rid}")', 'null')
                    self.report['disabled'].append({'scene': relative, 'resource': original, 'reason': reason})
            output.append(b)
        output = prune_resources(output)
        # load_steps is a hint, but stale counts make reviewing output confusing.
        if output:
            output[0].header = re.sub(r'\s+load_steps=\d+', '', output[0].header)
        return ''.join(b.text() for b in output)

    def preview_inputs(self) -> None:
        self.preview = True
        for directory, dirs, filenames in os.walk(self.project):
            dirs[:] = [d for d in dirs if d not in SKIP_DIRS - {'assets'} and not (d in {'assets', 'logos'} and Path(directory) == self.project)]
            for filename in sorted(filenames):
                path = Path(directory) / filename
                if path.suffix in {'.tscn', '.tres'}:
                    self.adapt_scene(path.read_text(encoding='utf-8-sig'), path.relative_to(self.project).as_posix(), self.project)
        print(f'Would copy {len(self.materialized)} referenced assets, bake {len(self.jobs)} collision files, '
              f'and disable {len(self.report["disabled"])} missing references.')
        print('Collision coverage:', dict(Counter(row['status'] for row in self.report['collisions'])))

    def adapt_text(self, text: str, relative: str, stage: Path) -> str:
        if relative.endswith('.gd'):
            def optional_load(match: re.Match[str]) -> str:
                reference = match[2]
                resolved, reason = self.resolve(reference)
                if resolved:
                    self.materialize(resolved, stage)
                    return match[1] + '(' + json.dumps(resolved) + ')'
                self.report['disabled'].append({'file': relative, 'canonical_path': reference, 'reason': reason})
                return 'null'
            text = re.sub(r'\b(preload|load)\(\s*"(res://assets/[^"\r\n]+)"\s*\)', optional_load, text)
        def replace(match: re.Match[str]) -> str:
            path = match[1]
            if path.startswith('res://logos/'):
                return match[0] if self.auxiliary(path, stage) else ('""' if relative.endswith('.gd') else 'null')
            if not path.startswith('res://assets/'):
                return match[0]
            if path.endswith('/'):
                return match[0]
            if path in {'res://assets/normalized_map.json'}:
                return match[0]
            resolved, reason = self.resolve(path)
            if resolved:
                self.materialize(resolved, stage)
                return json.dumps(resolved)
            self.report['disabled'].append({'file': relative, 'canonical_path': path, 'reason': reason})
            # Keep GDScript string types intact; resource-valued text fields use null.
            return '""' if relative.endswith('.gd') else 'null'
        return RES_PATH.sub(replace, text)

    def suppress_nested_overrides(self, stage: Path) -> None:
        scenes = {p.relative_to(stage).as_posix(): parse_blocks(p.read_text(encoding='utf-8-sig'))
                  for p in stage.rglob('*.tscn') if p.relative_to(stage).parts[0] != 'assets'}
        cache: dict[str, set[str]] = {}

        def disabled_in(relative: str, visiting: set[str]) -> set[str]:
            if relative in cache:
                return cache[relative]
            if relative in visiting:
                raise ValueError(f'Cyclic scene dependencies: {relative}')
            blocks = scenes.get(relative, [])
            result = {node_path(b) for b in blocks if b.kind == 'node' and 'metadata/variant_disabled = true' in b.body}
            refs = {b.attrs['id']: b.attrs.get('path', '') for b in blocks if b.kind == 'ext_resource'}
            for b in blocks:
                instance = re.search(r'instance=ExtResource\("([^"]+)"\)', b.header) if b.kind == 'node' else None
                if not instance:
                    continue
                child = refs.get(instance[1], '').removeprefix('res://')
                for path in disabled_in(child, visiting | {relative}):
                    prefix = node_path(b)
                    result.add(prefix if path == '.' else (path if prefix == '.' else prefix + '/' + path))
            cache[relative] = result
            return result

        for relative, blocks in scenes.items():
            disabled = disabled_in(relative, set())
            output = []
            for b in blocks:
                if b.kind == 'node' and node_path(b) not in disabled and descendants(node_path(b), disabled):
                    self.report['disabled'].append({'scene': relative, 'node': node_path(b), 'reason': 'override_below_unavailable_instance'})
                    continue
                if b.kind == 'editable' and descendants(b.attrs['path'], disabled):
                    continue
                if b.kind == 'connection' and any(descendants(b.attrs.get(k, ''), disabled) for k in ('from', 'to')):
                    continue
                output.append(b)
            (stage / relative).write_text(''.join(b.text() for b in prune_resources(output)), encoding='utf-8')

    def prepare(self, stage: Path) -> None:
        shutil.copytree(self.project, stage, dirs_exist_ok=True,
                        ignore=lambda directory, names: [n for n in names if
                            n in SKIP_DIRS - {'assets'} or (n in {'assets', 'logos'} and Path(directory) == self.project) or n.endswith('.import')])
        # The authoring editor must not recursively build from a generated project.
        config = stage / 'project.godot'
        text = config.read_text(encoding='utf-8-sig')
        text = re.sub(r',?\s*"res://addons/local_variant/plugin.cfg"', '', text)
        # A missing optional shader texture must not retain a broken dependency.
        for path in RES_PATH.findall(text):
            self.auxiliary(path, stage)
            if not path.startswith('res://assets/') and not (stage / path[6:]).exists():
                if path.endswith(('.gd', '.tscn')):
                    raise ValueError(f'Missing core project resource: {path}')
                text = text.replace(json.dumps(path), 'null' if '/shader' in path or path.endswith('.tres') else '""')
                self.report['warnings'].append('Missing optional project resource: ' + path)
        config.write_text(text, encoding='utf-8')
        for path in sorted(stage.rglob('*')):
            if not path.is_file() or path.relative_to(stage).parts[0] == 'assets' or path.suffix not in TEXT_TYPES:
                continue
            relative = path.relative_to(stage).as_posix()
            text = path.read_text(encoding='utf-8-sig')
            adapted = self.adapt_scene(text, relative, stage) if path.suffix in {'.tscn', '.tres'} else self.adapt_text(text, relative, stage)
            if adapted != text:
                path.write_text(adapted, encoding='utf-8')
        for mapping in discover_maps(self.assets):
            target = stage / 'assets' / mapping.name
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(mapping, target)
        self.suppress_nested_overrides(stage)
        runtime = stage / '.variant_tools'
        shutil.copytree(Path(__file__).parent / 'variant_runtime', runtime)
        shutil.copy2(MODULE / 'Godot/GodotGame/collisionTest/scripts/tsg_havok_reader.gd', runtime / 'tsg_havok_reader.gd')
        write_json(stage / 'variant_jobs.json', {'jobs': list(self.jobs.values()), 'instances': self.scene_instances})

    def attach(self, stage: Path, results: dict[str, Any]) -> None:
        successful = {row['uid'] for row in results['jobs'] if row.get('ok')}
        for uid in sorted(successful):
            path = stage / 'generated_collision' / f'{uid}.tscn'
            text = path.read_text(encoding='utf-8')
            # Godot assigns random editor IDs on serialization. No external
            # overrides target generated children, so omit those hints and use
            # stable subresource IDs for identical repeated bakes.
            text = re.sub(r'\s+unique_id=\d+', '', text)
            identifiers = re.findall(r'^\[sub_resource[^\n]+\bid="([^"]+)"', text, re.M)
            for index, old in enumerate(identifiers):
                new = f'VariantShape_{index:06d}'
                text = text.replace('id="' + old + '"', 'id="' + new + '"').replace(f'SubResource("{old}")', f'SubResource("{new}")')
            path.write_text(text, encoding='utf-8')
        by_scene: dict[str, list[dict[str, str]]] = defaultdict(list)
        for attachment in self.attachments:
            if attachment['uid'] in successful:
                by_scene[attachment['scene']].append(attachment)
        for relative, attachments in by_scene.items():
            path = stage / relative
            blocks = parse_blocks(path.read_text(encoding='utf-8'))
            insert = next((i for i, b in enumerate(blocks) if b.kind == 'node'), len(blocks))
            resources = []
            for uid in sorted({item['uid'] for item in attachments}):
                resources.append(Block(f'[ext_resource type="PackedScene" path="res://generated_collision/{uid}.tscn" id="VariantCollision_{uid}"]', ''))
            blocks[insert:insert] = resources
            for item in attachments:
                # One owner instance per GLB placement; shapes are shared resources.
                blocks.append(Block('[node name="OriginalGameCollision" parent=' + json.dumps(item['node']) +
                                    f' instance=ExtResource("VariantCollision_{item["uid"]}")]', ''))
            path.write_text(''.join(b.text() for b in blocks), encoding='utf-8')
        self.report['bake_results'] = results
        self.report['asset_files_copied'] = len(self.materialized)
        statuses = {row['uid']: row for row in results['jobs']}
        for row in self.report['collisions']:
            if row['uid'] in statuses:
                result = statuses[row['uid']]
                row['status'] = 'baked' if result.get('ok') else result.get('error', 'unsupported_or_malformed')


def find_godot(explicit: Path | None) -> Path:
    candidates = [explicit] if explicit else [
        Path('B:/Installed_Apps/Program_Files_x86/Steam/steamapps/common/Godot Engine/godot.windows.opt.tools.64.exe'),
        MODULE.parents[1] / 'Tools/Godot-4.6-stable-win-x64/Godot_v4.6-stable_win64_console.exe',
        Path(shutil.which('godot') or shutil.which('godot4') or '__missing_godot__')]
    for candidate in candidates:
        if candidate and candidate.is_file():
            return candidate.resolve()
    raise ValueError('Godot executable not found. Supply --godot PATH.')


def isolated_godot(original: Path, work: Path) -> Path:
    """Portable Godot otherwise writes editor settings beside its installation.

    Run an isolated copy with its own self-contained profile, never changing the
    installed engine or a user's editor configuration. The copy is game-free.
    """
    directory = work / 'engine'
    directory.mkdir(parents=True, exist_ok=True)
    executable = directory / original.name
    if not executable.exists() or executable.stat().st_size != original.stat().st_size or digest(executable) != digest(original):
        shutil.copy2(original, executable)
    for library in original.parent.glob('*.dll'):
        target = directory / library.name
        if not target.exists() or digest(target) != digest(library):
            shutil.copy2(library, target)
    if 'mono' in original.name.lower() and (original.parent / 'GodotSharp').is_dir():
        shutil.copytree(original.parent / 'GodotSharp', directory / 'GodotSharp', dirs_exist_ok=True)
    (directory / '_sc_').touch()
    return executable


def run_godot(godot: Path, stage: Path, arguments: list[str], work: Path) -> None:
    environment = os.environ.copy()
    for name in ('APPDATA', 'LOCALAPPDATA'):
        target = work / name.lower()
        target.mkdir(parents=True, exist_ok=True)
        environment[name] = str(target)
    command = [str(godot), '--headless', '--path', str(stage), '--log-file', str(work / 'godot.log'), *arguments]
    print('Godot:', ' '.join(arguments), flush=True)
    with (work / 'process.log').open('a', encoding='utf-8') as output:
        start = output.tell()
        output.write('\nCOMMAND ' + ' '.join(arguments) + '\n')
        output.flush()
        result = subprocess.run(command, stdout=output, stderr=subprocess.STDOUT, env=environment, timeout=1200)
    if result.returncode:
        raise ValueError(f'Godot exited {result.returncode}; see {work / "process.log"}')
    with (work / 'process.log').open('rb') as log:
        log.seek(start)
        lines = log.read().decode('utf-8', errors='replace').splitlines()
    errors = [line for line in lines if ('ERROR:' in line or 'Parse Error:' in line) and
              'Failed to read the root certificate store' not in line]
    if errors:
        raise ValueError(f'Godot reported {errors[0]}; see {work / "process.log"}')


def default_source() -> Path | None:
    config = MODULE / 'config.toml'
    if not config.is_file():
        return None
    values = tomllib.loads(config.read_text(encoding='utf-8-sig')).get('placeholders', [])
    if not values:
        return None
    row = values[0]
    return MODULE / 'GameFiles' / '-'.join(str(row[key]) for key in ('Platform', 'Region', 'Type', 'audio_state', 'isRenamed'))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--assets', type=Path, default=CANONICAL / 'assets')
    parser.add_argument('--source', type=Path, help='Raw collision dataset with its matching normalization maps')
    parser.add_argument('--logos', type=Path, help='Optional logos from this dataset; defaults to a logos/ sibling of --assets')
    parser.add_argument('--godot', type=Path)
    parser.add_argument('--no-collision', action='store_true')
    parser.add_argument('--dry-run', action='store_true')
    parser.add_argument('--clean', action='store_true')
    args = parser.parse_args()
    WORK.mkdir(parents=True, exist_ok=True)
    lock = WORK / 'build.lock'
    stage, previous = WORK / 'staging', WORK / 'previous'
    try:
        # Serialize editor and CLI builds; never clean a project during a bake.
        try:
            fd = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        except FileExistsError:
            raise ValueError(f'Another build is active. If interrupted, remove stale lock {lock}')
        os.close(fd)
        try:
            if args.clean:
                if not args.dry_run:
                    owned_remove(OUTPUT, OUTPUT.parent)
                    owned_remove(stage, WORK)
                    owned_remove(previous, WORK)
                print('Local variant removed.' if not args.dry_run else f'Would remove {OUTPUT}')
                return 0
            source = args.source or (default_source() if not args.no_collision else None)
            for supplied in (args.assets, source):
                if supplied and any(supplied.resolve().is_relative_to(root.resolve()) for root in (OUTPUT, WORK)):
                    raise ValueError(f'Inputs must live outside disposable local output: {supplied}')
            builder = VariantBuilder(CANONICAL, args.assets, source, not args.no_collision, args.logos)
            if args.dry_run:
                builder.preview_inputs()
                print('No project changed.')
                return 0
            godot = isolated_godot(find_godot(args.godot), WORK)
            (WORK / 'process.log').write_text('', encoding='utf-8')
            owned_remove(stage, WORK)
            owned_remove(previous, WORK)
            stage.mkdir()
            write_json(stage / MARKER, {'tool': 'local_variant'})
            print('Preparing isolated project...', flush=True)
            builder.prepare(stage)
            print(f'Copied {len(builder.materialized)} referenced assets; {len(builder.jobs)} original collision files.', flush=True)
            run_godot(godot, stage, ['--script', 'res://.variant_tools/bake.gd'], WORK)
            results = json.loads((stage / 'variant_bake_results.json').read_text(encoding='utf-8'))
            builder.attach(stage, results)
            write_json(stage / 'variant_report.json', builder.report)
            run_godot(godot, stage, ['--editor', '--import'], WORK)
            run_godot(godot, stage, ['--script', 'res://addons/local_variant/plugin.gd', '--check-only'], WORK)
            run_godot(godot, stage, ['--script', 'res://.variant_tools/validate.gd'], WORK)
            validation = json.loads((stage / 'variant_validation.json').read_text(encoding='utf-8'))
            if validation['failures']:
                raise ValueError('Scene validation failed: ' + '; '.join(validation['failures'][:8]))
            run_godot(godot, stage, ['--quit-after', '5'], WORK)
            # Publish by directory rename. If active files are locked, retain the
            # previous project rather than deleting or partially overwriting it.
            if OUTPUT.exists():
                if (OUTPUT.is_symlink() or OUTPUT.resolve().parent != OUTPUT.parent.resolve() or
                        not (OUTPUT / MARKER).is_file() or
                        json.loads((OUTPUT / MARKER).read_text(encoding='utf-8')).get('tool') != 'local_variant'):
                    raise ValueError(f'Output is not an owned local variant: {OUTPUT}')
                OUTPUT.rename(previous)
            try:
                stage.rename(OUTPUT)
            except OSError:
                if previous.exists():
                    previous.rename(OUTPUT)
                raise
            owned_remove(previous, WORK)
            write_json(WORK / 'status.json', {'ok': True, 'output': str(OUTPUT)})
            print(f'Built {OUTPUT}\nReport: {OUTPUT / "variant_report.json"}', flush=True)
            return 0
        finally:
            lock.unlink(missing_ok=True)
    except (OSError, ValueError, subprocess.TimeoutExpired) as exc:
        write_json(WORK / 'status.json', {'ok': False, 'error': str(exc)})
        print(f'ERROR: {exc}', file=sys.stderr, flush=True)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())

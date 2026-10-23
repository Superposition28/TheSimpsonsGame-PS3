"""Synthetic fixtures only: no original game geometry or proprietary payloads."""
from __future__ import annotations

import json
import contextlib
import io
import stat
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import build_local_variant as variant


class LocalVariantTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.project = self.root / 'PreBuilt'
        self.assets = self.root / 'input_assets'
        self.source = self.root / 'source'
        for directory in (self.project, self.assets, self.source):
            directory.mkdir()
        self.model = variant.AssetEntry('abc123', 'level/zone/export/terrain/model.rws.PS3.preinstanced',
                                        'level/terrain/model_abc123.rws.PS3.preinstanced')
        self.collision = variant.AssetEntry('def456', 'level/zone/export/collision/model.hkt.PS3',
                                            'level/collision/model_def456.hkt.PS3')
        self.write_maps([self.model, self.collision])
        self.put(self.assets / 'level/terrain/model_abc123.rws.PS3.glb', b'authored-test-placeholder')
        self.put(self.source / self.collision.new_path, b'authored-invalid-collision')
        self.scene = '''[gd_scene load_steps=4 format=3 uid="uid://baseline"]

[ext_resource type="PackedScene" uid="uid://oldimport" path="res://assets/level/terrain/model_abc123.rws.PS3.glb" id="1"]
[sub_resource type="BoxShape3D" id="old"]
size = Vector3(1, 2, 3)
[node name="World" type="Node3D"]
[node name="Model" parent="." instance=ExtResource("1")]
transform = Transform3D(1, 0, 0, 0, 1, 0, 0, 0, 1, 7, 8, 9)
[node name="Mesh" parent="Model" index="0"]
[node name="OldBlocker" type="StaticBody3D" parent="Model/Mesh"]
[node name="Shape" type="CollisionShape3D" parent="Model/Mesh/OldBlocker"]
shape = SubResource("old")
[node name="Player" type="CharacterBody3D" parent="."]
[node name="PlayerShape" type="CollisionShape3D" parent="Player"]
shape = SubResource("old")
[editable path="Model/Mesh"]
'''
        self.put(self.project / 'World.tscn', self.scene)
        self.put(self.project / 'project.godot', 'config_version=5\n[application]\nrun/main_scene="res://World.tscn"\n')

    def tearDown(self) -> None:
        self.temp.cleanup()

    @staticmethod
    def put(path: Path, data: str | bytes) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data.encode() if isinstance(data, str) else data)

    def write_maps(self, entries: list[variant.AssetEntry]) -> None:
        data = [vars(e) for e in entries]
        for root in (self.assets, self.source):
            variant.write_json(root / 'normalized_map.json', data)

    def build(self, stage_name: str = 'stage', collision: bool = True) -> tuple[variant.VariantBuilder, Path]:
        stage = self.root / stage_name
        stage.mkdir()
        builder = variant.VariantBuilder(self.project, self.assets, self.source, collision)
        builder.prepare(stage)
        return builder, stage

    def test_bake_attachment_and_source_preservation(self) -> None:
        before = {p: p.read_bytes() for directory in (self.project, self.assets, self.source) for p in directory.rglob('*') if p.is_file()}
        builder, stage = self.build()
        self.assertEqual(list(builder.jobs), ['def456'])
        self.put(stage / 'generated_collision/def456.tscn', '[gd_scene format=3]\n[node name="Collision" type="Node3D" unique_id=1234]\n')
        builder.attach(stage, {'jobs': [{'uid': 'def456', 'ok': True, 'physics_shapes': 1}]})
        text = (stage / 'World.tscn').read_text()
        self.assertIn('OriginalGameCollision', text)
        self.assertIn('parent="Model"', text)
        self.assertNotIn('OldBlocker', text)
        self.assertIn('PlayerShape', text)
        self.assertIn('7, 8, 9', text)
        self.assertNotIn('uid://oldimport', text)
        self.assertTrue(all(p.read_bytes() == data for p, data in before.items()))

    def test_repeat_build_is_deterministic(self) -> None:
        _, first = self.build('first')
        _, second = self.build('second')
        self.assertEqual((first / 'World.tscn').read_bytes(), (second / 'World.tscn').read_bytes())

    def test_variant_switch_and_restore(self) -> None:
        _, eu = self.build('eu')
        model_file = self.assets / 'level/terrain/model_abc123.rws.PS3.glb'
        model_file.unlink()
        builder, reduced = self.build('reduced')
        text = (reduced / 'World.tscn').read_text()
        self.assertIn('metadata/variant_disabled = true', text)
        self.assertIn('res://assets/level/terrain/model_abc123.rws.PS3.glb', text)
        self.assertIn('7, 8, 9', text)
        self.assertNotIn('ExtResource("1")', text)
        self.assertNotIn('parent="Model/Mesh"', text)
        self.assertEqual(builder.jobs, {})
        self.put(model_file, b'authored-test-placeholder')
        _, restored = self.build('restored')
        self.assertEqual((eu / 'World.tscn').read_bytes(), (restored / 'World.tscn').read_bytes())

    def test_platform_suffix_and_renamed_path(self) -> None:
        xen = variant.AssetEntry('abc123', 'level/zone/export/terrain/model.rws.XEN.preinstanced', 'different/model_abc123.rws.XEN.preinstanced')
        self.write_maps([xen])
        self.put(self.assets / 'different/model_abc123.rws.XEN.glb', b'authored-xen-placeholder')
        _, stage = self.build(collision=False)
        text = (stage / 'World.tscn').read_text()
        self.assertIn('res://assets/different/model_abc123.rws.XEN.glb', text)
        self.assertNotIn('rws.PS3.glb', text)

    def test_collision_disabled_removes_legacy_blockers(self) -> None:
        builder, stage = self.build(collision=False)
        self.assertFalse(builder.jobs)
        text = (stage / 'World.tscn').read_text()
        self.assertNotIn('OldBlocker', text)
        self.assertNotIn('OriginalGameCollision', text)
        self.assertIn('PlayerShape', text)

    def test_missing_collision_is_reported(self) -> None:
        (self.source / self.collision.new_path).unlink()
        builder, _ = self.build()
        self.assertFalse(builder.jobs)
        self.assertEqual(builder.report['collisions'][0]['status'], 'missing_collision_file')

    def test_conflicting_source_maps_fail(self) -> None:
        variant.write_json(self.source / 'normalized_map.json', [vars(self.model)])
        with self.assertRaisesRegex(ValueError, 'disagree'):
            self.build()

    def test_different_export_in_source_fails(self) -> None:
        self.put(self.source / 'level/terrain/model_abc123.rws.PS3.glb', b'another-dataset')
        with self.assertRaisesRegex(ValueError, 'differs'):
            self.build()

    def test_ambiguous_uid_never_chooses_by_file_order(self) -> None:
        second = variant.AssetEntry('abc123', 'another/export/model.preinstanced', 'another/model_abc123.preinstanced')
        self.write_maps([self.model, second, self.collision])
        builder, stage = self.build()
        self.assertEqual(builder.report['disabled'][0]['reason'], 'ambiguous_uid')
        self.assertIn('variant_disabled', (stage / 'World.tscn').read_text())

    def test_unsafe_mapping_rejected(self) -> None:
        variant.write_json(self.assets / 'normalized_map.json', [{'uid': 'abc123', 'new_path': '../escape.glb', 'original_path': 'x'}])
        with self.assertRaisesRegex(ValueError, 'unsafe'):
            self.build()

    def test_broken_core_script_fails(self) -> None:
        self.put(self.project / 'World.tscn', '[gd_scene format=3]\n[ext_resource type="Script" path="res://missing.gd" id="1"]\n[node name="World" type="Node3D"]\nscript = ExtResource("1")\n')
        with self.assertRaisesRegex(ValueError, 'required resource'):
            self.build()

    def test_optional_texture_is_disabled(self) -> None:
        self.put(self.project / 'UI.tscn', '[gd_scene format=3]\n[ext_resource type="Texture2D" path="res://assets/ui/missing_ffffff.png" id="1"]\n[node name="UI" type="Sprite2D"]\ntexture = ExtResource("1")\n')
        builder, stage = self.build()
        self.assertIn('texture = null', (stage / 'UI.tscn').read_text())
        self.assertTrue(any(d.get('resource', '').endswith('missing_ffffff.png') for d in builder.report['disabled']))

    def test_unused_stale_cache_is_pruned(self) -> None:
        self.put(self.project / 'Unused.tscn', '[gd_scene format=3]\n[sub_resource type="CompressedTexture2D" id="stale"]\nload_path = "res://.godot/imported/stale.ctex"\n[node name="Root" type="Node3D"]\n')
        _, stage = self.build()
        self.assertNotIn('stale.ctex', (stage / 'Unused.tscn').read_text())

    def test_tres_resource_dependencies_survive(self) -> None:
        self.put(self.project / 'material.tres', '[gd_resource type="StandardMaterial3D" format=3]\n[ext_resource type="Texture2D" path="res://assets/texture_123456.png" id="1"]\n[resource]\nalbedo_texture = ExtResource("1")\n')
        texture = variant.AssetEntry('123456', 'texture.png', 'texture_123456.png')
        self.write_maps([self.model, self.collision, texture])
        self.put(self.assets / texture.new_path, b'authored-placeholder')
        _, stage = self.build()
        self.assertIn('[resource]', (stage / 'material.tres').read_text())
        self.assertTrue((stage / 'assets' / texture.new_path).exists())

    def test_font_page_dependency_is_copied(self) -> None:
        font = variant.AssetEntry('123456', 'font.inf', 'fonts/font_123456.inf')
        self.write_maps([self.model, self.collision, font])
        self.put(self.assets / 'fonts/font_123456.fnt', 'page id=0 file="page.png"\n')
        self.put(self.assets / 'fonts/page.png', b'authored-placeholder')
        self.put(self.project / 'Font.tres', '[gd_resource type="FontFile" format=3]\n[ext_resource type="FontFile" path="res://assets/fonts/font_123456.fnt" id="1"]\n[resource]\nfallbacks = Array[Font]([ExtResource("1")])\n')
        _, stage = self.build()
        self.assertTrue((stage / 'assets/fonts/page.png').is_file())

    def test_addon_assets_directory_is_preserved(self) -> None:
        self.put(self.project / 'addons/controller/assets/player.gd', 'extends Node\n')
        _, stage = self.build()
        self.assertTrue((stage / 'addons/controller/assets/player.gd').is_file())

    def test_unsupported_bake_never_attaches(self) -> None:
        builder, stage = self.build()
        builder.attach(stage, {'jobs': [{'uid': 'def456', 'ok': False, 'error': 'Unsupported header'}]})
        self.assertNotIn('OriginalGameCollision', (stage / 'World.tscn').read_text())
        self.assertEqual(builder.report['collisions'][0]['status'], 'Unsupported header')

    def test_nested_overrides_of_missing_glb_are_suppressed(self) -> None:
        (self.assets / 'level/terrain/model_abc123.rws.PS3.glb').unlink()
        self.put(self.project / 'Parent.tscn', '[gd_scene format=3]\n[ext_resource type="PackedScene" path="res://World.tscn" id="1"]\n[node name="Parent" type="Node3D"]\n[node name="World" parent="." instance=ExtResource("1")]\n[node name="Mesh" parent="World/Model" index="0"]\nvisible = false\n[editable path="World/Model"]\n')
        _, stage = self.build()
        text = (stage / 'Parent.tscn').read_text()
        self.assertNotIn('parent="World/Model"', text)
        self.assertNotIn('[editable', text)
        self.assertIn('name="World"', text)

    def test_another_dataset_never_uses_canonical_logos(self) -> None:
        self.put(self.project / 'logos/eu.png', b'eu-only')
        self.put(self.project / 'Logo.tscn', '[gd_scene format=3]\n[ext_resource type="Texture2D" path="res://logos/eu.png" id="1"]\n[node name="Logo" type="Sprite2D"]\ntexture = ExtResource("1")\n')
        _, stage = self.build()
        self.assertFalse((stage / 'logos/eu.png').exists())
        self.assertIn('texture = null', (stage / 'Logo.tscn').read_text())

    def test_shared_readonly_logo_is_copied_once(self) -> None:
        logo = self.assets.parent / 'logos/boot.png'
        self.put(logo, b'authored-placeholder')
        logo.chmod(stat.S_IREAD)
        self.put(self.project / 'Logo.tscn', '[gd_scene format=3]\n[ext_resource type="Texture2D" path="res://logos/boot.png" id="1"]\n[node name="Logo" type="Sprite2D"]\ntexture = ExtResource("1")\n')
        self.put(self.project / 'project.godot', 'config_version=5\n[application]\nrun/main_scene="res://World.tscn"\nboot_splash/image="res://logos/boot.png"\n')
        try:
            _, stage = self.build()
            self.assertEqual((stage / 'logos/boot.png').read_bytes(), b'authored-placeholder')
            (stage / 'logos/boot.png').chmod(stat.S_IWRITE | stat.S_IREAD)
        finally:
            logo.chmod(stat.S_IWRITE | stat.S_IREAD)

    def test_missing_preload_becomes_null(self) -> None:
        self.put(self.project / 'optional.gd', 'extends Node\nconst Optional = preload("res://assets/missing_ffffff.png")\n')
        _, stage = self.build()
        self.assertIn('const Optional = null', (stage / 'optional.gd').read_text())

    def test_recover_cached_texture_through_uid(self) -> None:
        texture = variant.AssetEntry('123456', 'texture.png', 'new/texture_123456.png')
        self.write_maps([self.model, self.collision, texture])
        self.put(self.assets / texture.new_path, b'authored-placeholder')
        self.put(self.project / 'Cache.tscn', '[gd_scene format=3]\n[sub_resource type="CompressedTexture2D" id="cached"]\nload_path = "res://.godot/imported/texture_123456.png-' + 'a' * 32 + '.ctex"\n[node name="Image" type="Sprite2D"]\ntexture = SubResource("cached")\n')
        _, stage = self.build()
        text = (stage / 'Cache.tscn').read_text()
        self.assertNotIn('.ctex', text)
        self.assertIn('path="res://assets/new/texture_123456.png"', text)
        self.assertIn('texture = ExtResource("Recovered_cached")', text)

    def test_clean_requires_ownership_and_stays_in_parent(self) -> None:
        output = self.root / 'output'
        output.mkdir()
        self.put(output / 'important.txt', 'keep')
        with self.assertRaisesRegex(ValueError, 'unowned'):
            variant.owned_remove(output, self.root)
        variant.write_json(output / variant.MARKER, {'tool': 'local_variant'})
        with self.assertRaisesRegex(ValueError, 'unsafe'):
            variant.owned_remove(output, self.project)
        variant.owned_remove(output, self.root)
        self.assertFalse(output.exists())
        self.assertTrue(self.project.exists())

    def test_invalid_build_preserves_active_project(self) -> None:
        work, output = self.root / 'work', self.root / 'active'
        output.mkdir()
        self.put(output / 'sentinel', 'previous-valid-project')
        with patch.multiple(variant, WORK=work, OUTPUT=output, CANONICAL=self.project), patch('sys.argv', ['builder', '--assets', str(self.root / 'missing')]), contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(variant.main(), 1)
        self.assertEqual((output / 'sentinel').read_text(), 'previous-valid-project')
        self.assertFalse((work / 'build.lock').exists())

    def test_failed_engine_validation_keeps_previous_project(self) -> None:
        work, output = self.root / 'work', self.root / 'active'
        output.mkdir()
        variant.write_json(output / variant.MARKER, {'tool': 'local_variant'})
        self.put(output / 'sentinel', 'previous-valid-project')

        def engine(_godot: Path, stage: Path, arguments: list[str], _work: Path) -> None:
            if arguments == ['--script', 'res://.variant_tools/bake.gd']:
                variant.write_json(stage / 'variant_bake_results.json', {'jobs': []})
            else:
                raise ValueError('Synthetic engine validation failure')

        with patch.multiple(variant, WORK=work, OUTPUT=output, CANONICAL=self.project), \
                patch('sys.argv', ['builder', '--assets', str(self.assets), '--no-collision']), \
                patch.object(variant, 'find_godot', return_value=Path('test-engine')), \
                patch.object(variant, 'isolated_godot', return_value=Path('test-engine')), \
                patch.object(variant, 'run_godot', side_effect=engine), \
                contextlib.redirect_stderr(io.StringIO()), contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(variant.main(), 1)
        self.assertEqual((output / 'sentinel').read_text(), 'previous-valid-project')
        self.assertFalse((work / 'build.lock').exists())


if __name__ == '__main__':
    unittest.main()

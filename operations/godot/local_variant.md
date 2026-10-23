# Local Godot variants and original collision

`Godot/GodotGame/PreBuilt` is the complete EU authoring source. Never run path
refreshers or collision baking against its public scenes to adapt a user's game.
The local variant builder reads those scenes and the user's selected dataset,
then publishes a separate, disposable Godot project. The canonical scenes and
supplied files are never rewritten.

## Using the editor

Enable **Local Game Variant** in PreBuilt's editor plugins (enabled by default).
The **Project → Tools → Variant** commands provide:

- **Build/Refresh Local Variant**: choose converted assets and their matching raw
  collision dataset. Blank raw source uses the module's `config.toml` selection.
- **Open Local Variant**: open the validated local project in another editor.
- **Build Without Collision**: regenerate the variant without original or legacy
  render-mesh blockers. The player controller's own capsule remains available.
- **Remove Local Variant**: remove this tool's generated project and pending
  staging/previous projects. Canonical source and input assets remain intact.

Python 3.11+ must be available as `python`; Godot 4.6+ is required. Builds run
outside the editor thread. Their output appears in the editor console when
finished; detailed progress is available in the ignored work directory's
`process.log`. Close the local variant editor/game before rebuilding or removing
it, because Windows may lock its files. A failed replacement preserves the
previous valid project.

## Headless commands

Run from the game module root:

```powershell
python -B operations/godot/build_local_variant.py --dry-run
python -B operations/godot/build_local_variant.py
python -B operations/godot/build_local_variant.py --assets "D:/MyGame/converted" --source "D:/MyGame/flattened" --godot "D:/Godot/Godot.exe"
python -B operations/godot/build_local_variant.py --no-collision
python -B operations/godot/build_local_variant.py --clean
```

The default assets are `PreBuilt/assets`; the default raw collision dataset is
the flattened `GameFiles` directory selected by module configuration. On a fresh
clone, first use the game module to extract/convert the user's game, then supply
the resulting directories. Both inputs need `normalized_map.json` or matching
`map_*.json` files. Original game files are never downloaded by this tool.

`--logos` optionally selects that dataset's logo directory. Its default is a
`logos/` sibling of `--assets`; another dataset never falls back to PreBuilt's EU
logos. Missing optional logos/textures are disabled locally.

Only referenced converted assets and their dependencies are copied, including
BMFont pages and external glTF buffers/images. Godot imports write into the local
copy. A separate copy of the engine keeps build-time portable editor settings and
caches inside the work directory instead of the installed editor directory.

## Repeatability, variants, and undo

Every build starts again from the complete EU source, resolves normalization
UIDs using the selected maps, and checks actual file availability. Directory
names, region strings, platform extensions, and Godot import UIDs are not asset
identities. Multiple candidate paths for one UID are reported as ambiguous.
Missing asset instances become disabled placeholders with their original name,
placement, EU path, and UID. Other missing optional resources become null
references. Dependent overrides are suppressed only in the local copy.

The adaptation report records disabled components and collision coverage.
Original scene content remains in PreBuilt; it is never reconstructed from the
adapted output. Switching back to EU automatically restores available components
from that source. Building without collision undoes collision baking; `--clean`
undoes the entire local adaptation. No inverse patch or saved pre-bake snapshot
is required. Do not author changes in LocalVariant that need to survive a rebuild.

Known legacy static bodies under GLB instances are suppressed in the generated
copy, including when original collision is unavailable. Collision resources are
baked once per source collision UID and instanced once per GLB placement. Their
owner transforms preserve scene offsets and rotations. No Havok parsing runs
during gameplay.

The current PS3 EU dataset has 51 matched environment GLBs and 3,061 source bodies.
These numbers are a regression baseline, not requirements for another dataset.
The reader supports the collision lab's inspected Havok layout and converts its
mesh, convex, box, and sphere geometry into Godot static physics. ACS character
collision, original material response, dynamics, and destructibility are not
implemented. An Xbox/other variant with stable UIDs may still use an unsupported
binary layout; those collision assets are reported and skipped, never interpreted
as PS3 data simply because their UIDs match. Partially supported collision files
are skipped as a whole rather than silently baking incomplete blockers.

## Output ownership and failures

All local projects, copied assets, collision geometry, reports, and caches live
under these Git-ignored directories:

```text
Godot/GodotGame/LocalVariant/
Godot/GodotGame/.local_variant_work/
```

Never force-add their contents. Public commits contain authored code and scene
references, never generated original collision payloads. The builder retains the
previous project until imports, scene reloads, collision counts, and physics
checks pass. Invalid maps, mismatched source datasets, missing core scripts, or
engine errors fail the build. Missing optional assets are compatibility results
in the report. Failed staging output stays ignored for diagnosis and is removed
by the next build or clean command. Cleanup accepts only fixed, tool-owned paths
with the ownership marker; it never cleans the selected inputs.

A lock prevents concurrent builds/cleanup. After an interrupted process, confirm
it has stopped, then remove `.local_variant_work/build.lock` before retrying.

## Verification

```powershell
python -B -m unittest discover -s operations/godot -p test_local_variant.py -v
```

These tests use authored synthetic fixtures. A normal build additionally imports
and reloads the local scenes, compares baked body counts to decoded source,
tests transformed collision rays and a known EU falling-body fixture, and saves
`variant_validation.json`. The Havok reader is copied directly from collisionTest
at build time, so both projects use the same decoder implementation.

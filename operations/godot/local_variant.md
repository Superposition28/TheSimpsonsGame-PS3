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

The Lua operation is **18 — Build Isolated Local Godot Variant**. From the engine
root, run:

```powershell
dotnet run -c Debug --project .\EngineNet\ -- --game_module TheSimpsonsGame-PS3 --run_op 18
```

For direct Lua calls, use `--script_type lua --script` with
`{{Game_Root}}/operations/godot/BuildLocalVariant.lua` and pass the same options
listed below through the engine's `--args` JSON array. The operation is excluded
from run-all and depends on asset copying, rather than in-place scene refresh.
`--clean` only removes marked, fixed local output/staging directories; it does
not remove canonical scenes or the selected input datasets.

The Lua builder imports `RefreshGodotTSCNPaths.lua` as global functions with
`GodotRefreshImportOnly=true`, restoring the previous flag after loading.
Its own `GodotVariantImportOnly=true` flag permits global library imports without
starting a build. Shared classes live in `local_variant/VariantTypes.lua`; the
other files separate scene adaptation, dataset handling, and build orchestration.

Lua processes must use a registered Godot 4.6+ executable (`--godot` can select
one). The builder prefers registered Godot 4.6, checks the executable's version,
and redirects APPDATA, LOCALAPPDATA, and XDG profile directories into the work
directory. Portable `_sc_`/`._sc_` installations are rejected because their
settings would be written beside the executable. This uses the SDK's registered
tool policy without launching an unregistered copied binary. Native Godot helper
scripts batch the SHA-256 job hashes and publish with directory renames and
rollback; the SDK's move helper can fall back to copy/delete and is unsuitable
for publication.

The copy, path-refresh, and local-variant Lua operations all show overall script
stages and a separate current-activity bar. Counts cover discovered entries,
copied files, map rows, scene adaptation, collision attachment, and owned-output
cleanup. Scans discover their totals as they traverse the tree. Activity updates
are throttled, with periodic text output for terminal users. Godot runs are polled
so output appears immediately and their active job stays visible; hashing,
baking, and validation also send item counts to the activity bar. Both progress
handles close on success or failure. Importing the Lua libraries starts no bars.

The editor plugin currently invokes the Python entry point. Its commands remain:

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
# From the engine root; omit --args for the Lua-only synthetic checks.
dotnet run -c Debug --project .\EngineNet\ -- --game_module TheSimpsonsGame-PS3 --script_type lua --script "{{Game_Root}}/operations/godot/tests/LocalVariantTests.lua" --args '["--integration"]'
```

These tests use authored synthetic fixtures. A normal build additionally imports
and reloads the local scenes, compares baked body counts to decoded source,
tests transformed collision rays and a known EU falling-body fixture, and saves
`variant_validation.json`. The Havok reader is copied directly from collisionTest
at build time, so both projects use the same decoder implementation.

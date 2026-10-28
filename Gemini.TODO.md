# Gemini Strategic Roadmap & Technical Backlog (`Gemini.TODO.md`)

**Generated:** 2026-10-28  
**Baseline:** `TheSimpsonsGame-PS3` `v0.6.7-A` · `reversing/docs` `v0.3.5`

This file translates the project evaluation of `TheSimpsonsGame-PS3` and `reversing/docs` into an actionable, prioritized engineering roadmap—organized from immediate pipeline housekeeping and converter fixes to medium- and long-term reverse-engineering and gameplay milestones.

---

## Tier 1: Pipeline Architecture, Cleanup & Housekeeping (Immediate)

### 1.1 Decouple Folder-Rename State from `GameFiles/` Path Placeholders
- [ ] **Audit placeholder suffixes in `operations.toml` and `config.toml`:**
  - Currently, Operations `2`, `3`, `4`, and `6` rename the active `GameFiles/{{Platform}}-{{Region}}-{{Type}}-{{audio_state}}-{{isRenamed}}` folder on disk (`audio_none` → `audio_og` → `audio_reorg`, `notRenamed` → `isRenamed`, `Full` → `FullFlattened`).
  - Encoding transient step states (`audio_state`, `isRenamed`) into the directory name forces artificial serial dependencies in `operations.toml` (e.g., Operation `5` TXD extraction waiting on Operation `4` audio reorganization) solely to prevent concurrent folder-rename race conditions.
- [ ] **Migrate step completion tracking to `config.toml` or state markers:**
  - Keep meaningful dataset roots (`{{Platform}}-{{Region}}-Full` and `{{Platform}}-{{Region}}-FullFlattened`) while tracking `audio_state` and `isRenamed` in config metadata or lock/marker files.
  - Coordinate any canonical dataset path naming updates with `reversing/docs/reference/sources.json` and `check_docs.py --module-checks`.

### 1.2 Add a Post-Pipeline Cleanup Operation
- [ ] **Create a dedicated cleanup operation in `operations/` (modeled on `operations/resetThisBih.lua`):**
  - Provide `--mode backup` (moves to `.backup/<dateTime>`) and `--mode delete` options to remove intermediate build artifacts after a successful pipeline + Godot setup run without wiping the final game or `Source/`:
    - `TMP_TSG_LNKS-{{Platform}}-{{Region}}-{{Type}}-{{audio_state}}-{{isRenamed}}/` (Blender symlink batching directory)
    - `TMP/blender_temp/` and `operations/Blender/blend.log`
    - Intermediate unflattened tree `GameFiles/{{Platform}}-{{Region}}-Full-{{audio_state}}-{{isRenamed}}/` (once `FullFlattened`, Operation `17` asset copy, and Operation `18` variant build are complete)
    - `Godot/GodotGame/.local_variant_work/` temporary isolated profile folders

### 1.3 Unify Godot Launch Manifest (`Operation 15`) & Local Variant (`Operation 18`)
- [ ] **Reconcile `generate-game-toml.lua` (`Operation 15`) with `BuildLocalVariant.lua` (`Operation 18`):**
  - `operations/generate-game-toml.lua` writes `exe = "{{Game_Root}}/Godot/GodotGame/LocalVariant/project.godot"`, but Operation `18` is currently `run-all = false` and not in Operation `15`'s `depends-on` list.
  - Either make Operation `15` point to `PreBuilt/project.godot` when `LocalVariant` is absent, or add an option/dependency so `LocalVariant` is built before generating `game.toml`.

### 1.4 Repository Hygiene in `reversing/`
- [ ] **Clean up legacy/vendored trees in `reversing/`:**
  - Remove tracked OS artifacts such as `reversing/TheSimpsonsGameFileExtractor-main/.DS_Store`.
  - Document or consolidate the relationship between the `reversing/fileviewer` submodule, `reversing/TSGFileViewer/`, and `reversing/TheSimpsonsGameFileExtractor-main/`.

---

## Tier 2: Converter Fidelity & Asset Pipeline Completion (Short-Term)

### 2.1 Fix High-LOD Model Material & Texture Assignment (`Operation 7`)
- [ ] **Resolve `TLFD` material group semantics in `operations/Blender/blender_addon/PreinstancedImportExtension.py`:**
  - Use `reversing/preinstanced_viewer.py` and `reversing/file_connections.py` on known broken high-LOD vs. working low-LOD pairs (e.g., `exportBldgDuffBrewery` `lodmodel1` vs. `lodmodel2`) to verify how `TLFD` chunks delimit material texture groups and how submesh material IDs index into those groups.
  - Replace the current pair heuristic only after regression-testing against validated assets across multiple levels.

### 2.2 Upgrade `.lh2` -> `.csv` Localization Converter (`Operation 8`)
- [ ] **Modernize `operations/Converters/lh2_to_csv.lua`:**
  - Replace raw `string.byte` / raw byte concatenation with the validated Windows-1252 → UTF-8 decoding and host-safe binary reading utilities used in `operations/Converters/inf_to_fnt.Fonts.lua` (`Operation 9`) and `operations/Converters/tox_to_srt.Subtitles.lua` (`Operation 10`).
  - Verify CSV output against all 654 EU `.LH2` tables audited in `reversing/audio_subtitles.py` and update `reversing/docs/reference/coverage.json` once the Lua converter validation gap is closed.

### 2.3 Exhaustive `.sbk` Sound Bank Subsong Extraction (`Operation 11`)
- [ ] **Export all subsongs from `.sbk` banks:**
  - Currently, Operation `11` (`format-convert` with `vgmstream`) decodes a single default `.wav` per `.sbk` bank without enumerating all embedded subsongs.
  - Add subsong enumeration/splitting so every embedded sound effect in each `.sbk` bank is exported with a deterministic name/index.

---

## Tier 3: Scene Assembly, World Placement & Dialogue Integration (Medium-Term)

### 3.1 Automated Level Entity & Transform Placement (`.dat.simgroup`, `.dat.uie`, `.meta.xml`)
- [ ] **Decode `SimGroup` and `UIE` payload structures:**
  - Operation `1` (`operations/simpsons_str.bms`) now tags `.dat.simgroup` and `.dat.uie` outputs (`v0.6.6-A`), and `reversing/file_connections.py` (`v0.6.7-A`) indexes their cross-file links.
  - Analyze the record layouts of `.dat.simgroup`, `.meta.xml`, and `.xml.PS3` to extract 3D transforms, entity archetypes, trigger volumes, and prop instance references.
- [ ] **Integrate placement data into `Godot/GodotGame/PreBuilt` / `BuildLocalVariant.lua`:**
  - Automatically instantiate and position level props, collectibles, spawn points, and triggers in Godot `.tscn` scenes using resolved asset UIDs from `normalized_map.json`.

### 3.2 In-Game Dialogue, Stream Lookup & Subtitle Playback (`.alb` + `.smb` + `.lh2` + `.snu`)
- [ ] **Export a runtime dialogue catalog for Godot:**
  - Build on `reversing/audio_subtitles.py` (which validated all 14,283 `.alb` records, 99 `.smb` banks, 7,413 `.snu` streams, and 7,314 `.lh2` dialogue links) to emit a compact JSON or SQLite lookup table into `Godot/GodotGame/PreBuilt/assets/`.
  - Create a Godot runtime dialogue manager node that resolves an event/dialogue ID to its converted `.wav` stream(s) and localized `.lh2` subtitle string.

### 3.3 Navigation Graph Runtime Integration (`.graph`)
- [ ] **Promote `tsg_graph_importer` from debug visualization to playable AI navigation:**
  - Validate the heuristic edge boundaries in `.graph` files against level geometry and Havok `.hkt.PS3` collision meshes.
  - Generate native Godot `AStar3D` or `NavigationRegion3D` resources for NPC and companion pathfinding.

### 3.4 Complete Character/Prop Auxiliary Collision (`.acs.PS3` & `.bbn.PS3`)
- [ ] **Finish coordinate/pose reconstruction in `tsg_character_reader.gd`:**
  - All 267 canonical `.acs.PS3` files walk to EOF and join against `.bbn.PS3` SDBM bone hashes and `.preinstanced` `HAnim` nodes, but shape pose/coordinate reconstruction remains partial.
  - Attach reconstructed capsules, boxes, and spheres directly to `Skeleton3D` bone attachments in Godot character scenes.

---

## Tier 4: Documentation Subproject (`reversing/docs`) Backlog

### 4.1 Populate Per-Level `USRDIR` Inventories & Analyses
- [ ] **Expand the 16 level and 2 hub pages under `reversing/docs/PS3_GAME/USRDIR/`:**
  - Replace the `v0.1.14` scaffold pages (`L02_BartmanBegins` through `L16_MeetThyPlayer`, `LHub-00_GameHub`, `LHub-00_SprHub`) with verified canonical path inventories, `.STR` archive breakdowns, zone/sub-archive lists, and level-specific asset relationships (following the `L01_LandOfChocolate` pilot).

### 4.2 Reconcile Legacy Mixed Inventories
- [ ] **Finish migrating historical mixed-path tables to `PS3-EU-Full-audio_reorg-isRenamed`:**
  - Use `normalized_map.json` and `reversing/file_connections.py` to reconcile remaining labeled legacy inventories across format pages while preserving historical provenance notes.

### 4.3 Cross-Platform (`Xbox 360` / `US` / `DEMO`) Verification
- [ ] **Expand non-EU PS3 and Xbox 360 format verification in `reference/coverage.json`:**
  - Systematically verify `.itxd`, `.tox.XEN`, `.acs.XEN`, and regional `.LH2`/`.STR` differences against the `Source/XBOX360/` and `Source/PS3/US` / `DEMO` datasets.

---

## Tier 5: Full Game Reconstruction ("Hard Wall" Long-Term Milestones)

### 5.1 Character Animation & Rigging Pipeline (`.bnk.PS3`, `.rcb.PS3`, `.cec.ps3`)
- [ ] **Reverse-engineer `.bnk.PS3` animation banks and `.rcb.PS3` rig controllers:**
  - Decode keyframe/curve compression in `.bnk.PS3` and bone/event bindings in `.rcb.PS3` / `.cec.ps3`.
  - Build a converter to export animations into Blender / `.glb` or Godot `AnimationLibrary` resources for playable characters and enemies.

### 5.2 Adaptive Music State Machine (`.mus` + `.msb`)
- [ ] **Implement `.msb` transition logic for `.mus` segments:**
  - Operation `13` decodes `.mus` sub-streams (`.snr`/`.sns` → `.wav`), but adaptive layering and cue transitions in `.msb` remain `Blue (Analysis only)`.
  - Decode `.msb` state/transition tables to drive interactive music playback in Godot.

### 5.3 Original Game Logic & Scripting Runtime (`.lua`, `.shk`, `EBOOT.BIN`)
- [ ] **Map the C++ engine API surface called by disc `.lua` scripts:**
  - Catalog all native engine functions, event hooks, and Shock (`.shk`) state machine commands referenced by the readable `.lua` scripts across levels and missions.
  - Implement a Godot GDScript/C# compatibility layer (or Lua runtime bridge) capable of executing level logic, mission objectives, cutscenes, and boss behaviors.

### 5.4 UI, Frontend & HUD Reconstruction (`.uix` / `.dat.uie`)
- [ ] **Complete Frontend and HUD scenes in `Godot/GodotGame/PreBuilt/Node4D/Node2D/`:**
  - Either decode `.uix` (EA APT / ActionScript-like UI containers) and `.dat.uie` layout records into Godot `Control` trees, or finish authoring the menus, HUD, and cliché overlays in `PreBuilt` using the converted `.fnt` fonts (`Operation 9`) and `.txd` PNG atlases (`Operation 5`).


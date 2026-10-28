# TODO — TheSimpsonsGame-PS3 (`v0.6.7-A`)

## Pipeline & Configuration
- [ ] **Simplify `GameFiles` folder state placeholders:** Evaluate the placeholders encoded into the working directory name (`{{Platform}}-{{Region}}-{{Type}}-{{audio_state}}-{{isRenamed}}`). State suffixes like `audio_state` and `isRenamed` currently require sequential folder-rename `onsuccess` hooks across Operations `2`, `3`, `4`, and `6`, forcing artificial serial dependencies to avoid filesystem conflicts; keep `Platform`, `Region`, and `Type` (`Full` vs `FullFlattened`) while tracking step completion in config or manifest state instead of renaming the directory.
- [ ] **Add a Post-Pipeline Cleanup Operation (or self-cleaning steps):** Similar to Operation `6677` (`operations/resetThisBih.lua`), add an operation (or per-step cleanup) that deletes or moves temporary build artifacts to `.backup/<timestamp>` without wiping the final converted outputs or Godot project:
  - `TMP_TSG_LNKS-{{Platform}}-{{Region}}-{{Type}}-{{audio_state}}-{{isRenamed}}/` (Blender symlink farm)
  - `TMP/blender_temp/` and `operations/Blender/blend.log`
  - Unflattened intermediate directory `GameFiles/{{Platform}}-{{Region}}-Full-{{audio_state}}-{{isRenamed}}/` once `FullFlattened` (Operation `6`) and Godot asset copy/variant steps (`17`, `16`, `18`) have succeeded
  - `Godot/GodotGame/.local_variant_work/` temporary profile directories
- [ ] **Align `generate-game-toml.lua` (Operation `15`) and `BuildLocalVariant.lua` (Operation `18`):** `game.toml` points to `Godot/GodotGame/LocalVariant/project.godot`, while Operation `18` has `run-all = false`. Decide whether Operation `15` should depend on Operation `18` (or default to `PreBuilt` when `LocalVariant` has not been built).

## Asset Converters & Format Fidelity
- [ ] **Fix High-LOD Material / Texture Pairing (`.preinstanced` -> `.blend`/`.glb`, Operation `7`):** Validate how `TLFD` events delimit material texture groups and how submesh material IDs index those groups in `operations/Blender/blender_addon/PreinstancedImportExtension.py`, replacing the current pair heuristic after checking known-good high-LOD assets.
- [ ] **Upgrade `.lh2` -> `.csv` Converter (`operations/Converters/lh2_to_csv.lua`, Operation `8`):** Align binary reading and Windows-1252 -> UTF-8 string decoding with the validated host-safe conventions used in `inf_to_fnt.Fonts.lua` and `tox_to_srt.Subtitles.lua`.
- [ ] **Exhaustive `.sbk` Subsong Extraction (Operation `11`):** Update `.sbk` audio conversion so all embedded subsongs in multi-stream sound banks are exported rather than only the default stream.

## Godot Integration & Reversing Next Steps
- [ ] **Scene Entity & Placement Reconstruction (`.dat.simgroup`, `.dat.uie`, `.meta.xml`):** Use the newly tagged `.dat.simgroup` / `.dat.uie` payloads and `reversing/file_connections.py` index to decode world placement and entity links for automated Godot scene population.
- [ ] **In-Game Dialogue & Subtitle Playback (`.alb` + `.smb` + `.lh2` + `.snu`):** Integrate the validated dialogue link tables from `reversing/audio_subtitles.py` into the Godot runtime so character voice streams play with synchronized localized subtitles.
- [ ] **Character Animation & Rigging (`.bnk.PS3`, `.rcb.PS3`, `.cec.ps3`):** Decode `.bnk.PS3` animation clip compression and `.rcb.PS3` bindings to export skeletal animations alongside `.preinstanced` rigs.

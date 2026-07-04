# Remake Engine Game Module: The Simpsons Game (2007, PS3 Edition)

![](.github\assets\cpy\4_medal_of_homer_1baaa2.png)
![](.github\assets\cpy\32_simpsons_start_371d9a.png)


This module re-implements *The Simpsons Game* (2007, PS3 edition) using the [RemakeEngine](https://github.com/yggdrasil-au/RemakeEngine). It converts user-provided assets into formats compatible with the [Godot Engine](https://godotengine.org/) and generates a playable project. **You must own an original copy of the game to use this module.**


## What is This?
well an over engineered remake of the original game
i wanted to remake it but i had to reuse the original assets, because i dont have the time to remake all the assets (or skill)
so i had to reverse engineer the original game files, using the few existing scripts online and alot of AI guesses
then i relised its a waste of time to remake the game if i cant share it
so i make the remake engine, basically a autmation tool, that lets me share the instructions to remake the game, but not the assets themselves, so people can remake the game if they own it, but not share it, because that would be illegal
but now that means i not only need to reverse engineer the game, but also make the remake engine, and the instructions on building the game and actually building the Entire Game
luckily godot takes care of the engine aspect, and it doesnt need to be a perfect remake, just a playable one, so i can focus on the game world and eventually logic

current remake progress, it creates like some of the maps, terrain only with super broken textures
current reverse engineering progress, i dont even remember, theres so many formats, and so little skill (me),
ive made some docs on the formats, [here](https://github.com/Superposition28/TheSimpsonsGame-PS3-Docs), by me i do mostly mean the AI
mostly just all textures are being extracted correctly now, the models are i think almost all extracted correctly however assigning textures to the models is a nightmare, because idk how to read the format at the texture mapping point, for now it just reads texture string names listed above each submesh and uses the first one, surprisingly it works for some simple models, but for more complex models it just randomly assigns textures to submeshes, and the textures are all over the place, so it looks like a mess, but its repeatable, so the same model will always have the same random texture applied to it
all video and most audio files are converted fine
but the .MUS music files are currently unknown format, we only have the 128ish ambient audo, and the 14,698 dialogue audio files (for each language if using EU version), still missing the 17 music .mus
i have been mapping the dialogue audio files to the characters in docs repo \PS3_GAME\USRDIR\A1_Audio\AudioMap.yaml

## Features

- Converts your legally obtained game assets into Godot-ready formats.
- Generates a Godot project using Python and GDScript.
- Requires possession of the original PlayStation 3 game.

## Goals

- Re-implement the original game logic in GDScript and C#.

## Module Platform Support

- **Current Support:** Windows only
- **Planned Support:** Linux support is expected as toolchain and script compatibility improves

## depends on
remake engine (and naturally its dependencies), docs repo (must be in 'reversing/docs' folder under repo root, for scripts to work)
tools like blender, quickbms, godot, are handled by remake engine, so you dont need to install them yourself, remake engine will download and install them for you


## File Breakdown

- `config/`
  - `config/RenameMap.db` - Maps original folder names to human-readable names used by the module.

- `Godot/`
  - `Game/` - Godot project files and scripts for remake logic.
    - `addons/` - Third-party and custom Godot addons.
    - `rootfiles/Scripts/` - Scene Builder GDScript for generating game nodes and worlds.
      - `import-V*.gd` - Main scene builder script.
    - `godot-init-V*.lua` - Godot project initializer.
    - `rootfiles/json/**.json` - Asset locations and node/script mapping.

- `operations/` - Core operation scripts (Lua, BMS, Blender, etc.).
  - `Blender/` - Blender conversion scripts and handlers.
- `reversing/` - Reverse engineering notes and format analyses.
  - `Source/` - Main format documentation and notes.
  - `Source/Format-Analysis/` - Detailed format-specific analyses.

- `Source/` - Local copy of user-provided game files (if copied/moved).
- `.gitignore` - Ignore rules for assets and outputs.
- `blank.blend` - Blank Blender file for model conversion.
- `config.toml` - Module-local configuration (stores `SourcePath`).
- `operations_cli.md` - CLI documentation for operations.
- `operations.toml` / `operations.json` - Defines the sequence of asset-processing operations.
- `Readme.md` - This file.
- `Tools.toml` / `Tools.json` - Configuration for external tools managed by RemakeEngine.

### Path Placeholders

RemakeEngine operations use built-in placeholders for paths and configuration. These are provided by the engine and some are set by the module's `init.lua` or changed after successful operations using `config.lua` and resolved automatically in `operations.toml` for scripts.

**Built-in placeholders for `operations.toml`:**
- `{{Game_Root}}` — Path to this module's root directory.
- `{{Project_Root}}` — Path to the RemakeEngine root project directory.

**Custom placeholders defined in `config.toml`:**
- `{{SourcePath}}` — Path to your validated original game files (set by `init.lua` and stored in `config.toml`).
- `{{Region}}` — Game region, e.g. `US` or `EU`.
- `{{Type}}` — Extraction/structure type for validation. Set to `FullFlattened` after normalization.
- `{{audio_state}}` — Audio layout state; set to `audio_reorg` after running the audio setup step.
- `{{isRenamed}}` — Flag indicating base folder rename status; set to `isRenamed` after the rename step.
- `{{STROUT}}` — Output root for extracted STR content; updated to `STROUT_Normalized` after normalization.

**Usage:**
- Placeholders are referenced in TOML and scripts as `{{PlaceholderName}}`.
- They are resolved by the engine before running each operation.
- Example: `args = ["{{SourcePath}}", "--map-db-file", "{{Game_Root}}/config/RenameMap.db"]`
- The validation operations select the correct index DB based on `Region`, `Type`, `audio_state`, and `isRenamed`.

**Note:** The placeholder format is always double curly braces, e.g. `{{SourcePath}}`.

This module is fully automated and designed to be executed by [The Remake Engine](https://github.com/yggdrasil-au/RemakeEngine). All direct dependencies (Godot, Blender, QuickBMS, etc.) are defined by `Tools.toml`/`Tools.json` and handled by RemakeEngine. **This module is in beta.**

### Operations Overview
- Init and config: creates/updates `config.toml`, ensures placeholders exist.
- Validate source: engine `validate-files` using `config/GameFilesIndex_{...}.db`.
- Download required tools: engine `download-tools` reading `Tools.toml`.
- Rename base folders: engine `rename-folders` using `config/RenameMap.db` (sets `isRenamed`).
- Reorganize audio: `operations/SetupAudioDir.lua` (sets `audio_state`, applies `Dialogue` and `EN-CUTSCENE` folder rename rules from `reversing/docs/PS3_GAME/USRDIR/A1_Audio/AudioMap.yaml` across `EN/ES/FR/IT`, applies `Global-Sound` folder rename rules inside `A1_Audio/Global`, supports nested destination folders like `Enemies/Bosses`, and places mapped dialogue voice-line files inside `NEW_DIR_NAME/<CharacterName>/` while moving unmatched files to `NEW_DIR_NAME` root).
- Normalize folder structure: `operations/DirectoryNormalizer.lua` using `config/DirectoryNormalizer.rules.json` (sets `Type=FullFlattened` and updates `STROUT` to `STROUT_Normalized`).
- Extract/convert: STR extract, TXD -> DDS, DDS -> PNG, with optional video/audio conversions.
- Blender conversion: converts `.preinstanced` → `.blend` (and optionally `glb`/`fbx`), using the main index DB.
- Final validation and Godot project generation (experimental).

---

## Reverse Engineering & Format Documentation

For technical details and reverse-engineering notes on the file formats used in The Simpsons Game (PS3), see:

- [reversing/Source/README.md](./reversing/Source/README.md) -- Overview of main formats in USRDIR and STR output.
- [reversing/Source/Format-Analysis/README.md](./reversing/Source/Format-Analysis/README.md) -- Index of all format-specific analyses, including audio, RenderWare assets, and miscellaneous formats.

These resources provide:

- Format breakdowns for `.snu`, `.mus`, `.str`, `.vp6`, and more.
- Links to detailed reverse-engineering notes for each format.
- Guidance for contributing new format analyses or deduplicating documentation.

---

## Obligatory Legal Disclaimer

This project automates extraction of assets (3D models, sounds, videos) from *The Simpsons Game* 2007 (PS3 edition) for personal use only--hobby projects, learning, research, etc.--not for commercial distribution.

**Key Points:**

- **Requires Ownership of the Game:** You must possess your own legally obtained ISO copy of the game for PlayStation 3. This tool does not provide game files.
- **Respect Copyright:** Extracted assets are copyrighted by Electronic Arts (EA) and Disney. Use is limited to personal exploration and modification of assets from a game you legally own. You are responsible for compliance with copyright laws and the game's EULA/Terms of Service where applicable.
- **No Distribution of Assets:** This project does not distribute copyrighted game assets. It only provides code to automate extraction from your own files and should not be used to share or distribute game content.

**By using this project, you acknowledge that you have read and understood this disclaimer and agree to use it responsibly and in accordance with all applicable laws and terms of service.**

---
---

A:\RemakeEngine\Main\EngineApps\Games\TheSimpsonsGame-PS3\GameFiles\EU-FullFlattened-audio_reorg-isRenamed\LHub-00_SprHub\sprHub\zone08str\assets\environs\sprIndustrialBldgDuffBreweryGeo\exportBldgDuffBrewery\
High LOD model with broken textures
![](.github/assets/blendersnip/lodmodel1_3f18fc.rws.PS3.blend.png)
low LOD model with working textures
![](.github/assets/blendersnip/lodmodel2_4f599b.rws.PS3.blend.png)

gotta love that, especially since the textures are applied mostly randomly, but repeatably it will always be the same random texture applied to the same model.
i assume low lod models have less layers and less overall textures so my script is more likely to apply the correct textures to the low lod models?

---
---

![](.github/assets/OperationsMenu2.png)
---
Extract Archives (.STR)

![](.github/assets/ExtractingSTR-DEBUG.png)
---
![](.github/assets/ExtractingSTR.png)
![](.github/assets/ExtractedSTR.png)
---
---


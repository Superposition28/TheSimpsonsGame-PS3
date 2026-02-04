# Operations CLI Reference

All operations available through the Remake Engine for The Simpsons Game PS3 module.

## Placeholders
- `{{Game_Root}}` - Game module root directory
- `{{Project_Root}}` - Engine root directory
- `{{SourcePath}}` - Source files location
- `{{Region}}` - EU or US
- `{{STROUT}}` - STROUT or STROUT_Normalized
- `{{Type}}` - Full or FullFlattened
- `{{audio_state}}` - audio_og or audio_reorg
- `{{isRenamed}}` - notRenamed or isRenamed
- `{{PostSourcePath}}` - PS3_GAME\USRDIR

---

## Operation 0: Initialize Configuration (Auto-run)
**Description:** Creates config.toml, ensures placeholders exist, verifies source path.  
**Dependencies:** None  
**Run-all:** false

```pwsh
dotnet run -c Release --project EngineNet --framework net10.0 -- --game_module ".\EngineApps\Games\TheSimpsonsGame-PS3\" --script_type lua --script "{{Game_Root}}/operations/init.lua"
```

---

## Operation -4: Change Region to US (Dev Test)
**Description:** Updates configuration to use US region source files.  
**Dependencies:** None

```pwsh
dotnet run -c Release --project EngineNet --framework net10.0 -- --game_module ".\EngineApps\Games\TheSimpsonsGame-PS3\" --script_type lua --script "{{Game_Root}}/config.lua" --args '["--group","placeholders","--set","Region=US:string","--set","MainSourcePath={{Game_Root}}\\Source\\US\\PS3_GAME\\USRDIR:string"]'
```

---

## Operation -2: Change Region to EU (Dev Test)
**Description:** Updates configuration to use EU region source files.  
**Dependencies:** None

```pwsh
dotnet run -c Release --project EngineNet --framework net10.0 -- --game_module ".\EngineApps\Games\TheSimpsonsGame-PS3\" --script_type lua --script "{{Game_Root}}/config.lua" --args '["--group","placeholders","--set","Region=EU:string","--set","MainSourcePath={{Game_Root}}\\Source\\EU\\PS3_GAME\\USRDIR:string"]'
```

---

## Operation 1: Validate Source Game Files and Folders
**Description:** Validates original source files and directory structure.  
**Dependencies:** Op 0  
**Run-all:** false

```pwsh
dotnet run -c Release --project EngineNet --framework net10.0 -- --game_module ".\EngineApps\Games\TheSimpsonsGame-PS3\" --script_type engine --script "validate-files" --args '["{{Game_Root}}/config/GameFilesIndex_{{Region}}_{{Type}}-{{audio_state}}-{{isRenamed}}.db","{{SourcePath}}/{{Region}}/{{PostSourcePath}}","--tables","str_index:source_path,video_index:source_path,mus_index:source_path,snu_index:source_path","--required-dirs","audiostreams,movies,frontend,simpsons_chars,spr_hub,loc,brt,eighty_bites,tree_hugger,mob_rules,cheater,dayofthedolphins,colossaldonut,dayspringfieldstoodstill,bargainbin,gamehub,neverquest,grand_theft_scratchy,medal_of_homer,bigsuperhappy,rhymes,meetthyplayer"]'
```

---

## Operation 2: Download Required Tools
**Description:** Downloads QuickBMS, Blender, ffmpeg, vgmstream, ImageMagick from Tools.toml.  
**Dependencies:** Op 0  
**Run-all:** false

```pwsh
dotnet run -c Release --project EngineNet --framework net10.0 -- --game_module ".\EngineApps\Games\TheSimpsonsGame-PS3\" --script_type engine --script "download-tools" --tools_manifest "{{Game_Root}}/Tools.toml"
```

---

## Operation 3: Rename Base Folders
**Description:** Renames base directories using RenameMap.db for clarity.  
**Dependencies:** Op 0, 6, 12, 13  
**Run-all:** false  
**On Success:** Updates `isRenamed` placeholder to "isRenamed" and renames output folder.

```pwsh
dotnet run -c Release --project EngineNet --framework net10.0 -- --game_module ".\EngineApps\Games\TheSimpsonsGame-PS3\" --script_type engine --script "rename-folders" --args '["{{Game_Root}}/GameFiles/STROUT-{{Region}}_{{Type}}-{{audio_state}}-{{isRenamed}}","--map-db-file","{{Game_Root}}/config/RenameMap.db"]'
```

---

## Operation 4: Reorganize Audio Files
**Description:** Creates EN and Global folders for audio organization.  
**Dependencies:** Op 0, 6, 13  
**Run-all:** false  
**On Success:** Updates `audio_state` placeholder to "audio_reorg" and renames output folder.

```pwsh
dotnet run -c Release --project EngineNet --framework net10.0 -- --game_module ".\EngineApps\Games\TheSimpsonsGame-PS3\" --script_type lua --script "{{Game_Root}}/operations/SetupAudioDir.lua" --args '["{{Game_Root}}/GameFiles/STROUT-{{Region}}_{{Type}}-{{audio_state}}-{{isRenamed}}"]'
```

---

## Operation 6: Extract Archives (.STR)
**Description:** Extracts .preinstanced, .txd, and other game files from .str archives.  
**Dependencies:** Op 0, 2  
**Run-all:** true

```pwsh
dotnet run -c Release --project EngineNet --framework net10.0 -- --game_module ".\EngineApps\Games\TheSimpsonsGame-PS3\" --script_type bms --script "{{Game_Root}}/operations/simpsons_str.bms" --set "input={{SourcePath}}/{{Region}}/{{PostSourcePath}}" --set "output={{Game_Root}}/GameFiles/STROUT-{{Region}}_{{Type}}-{{audio_state}}-{{isRenamed}}" --set "extension=.str"
```

---

## Operation 7: Normalize Folder Structure
**Description:** Flattens redundant directory structures to avoid path length limits.  
**Dependencies:** Op 0  
**Run-all:** false  
**On Success:** Updates `STROUT` to "STROUT_Normalized" and `Type` to "FullFlattened".

```pwsh
dotnet run -c Release --project EngineNet --framework net10.0 -- --game_module ".\EngineApps\Games\TheSimpsonsGame-PS3\" --script_type lua --script "{{Game_Root}}/operations/DirectoryNormalizer.lua" --args '["{{Game_Root}}/GameFiles/STROUT-{{Region}}_{{Type}}-{{audio_state}}-{{isRenamed}}","{{Game_Root}}/GameFiles/STROUT_Normalized-{{Region}}_{{Type}}-{{audio_state}}-{{isRenamed}}","--action","copy","--ignore","A1_Audio","--ignore","audiostreams","--ignore","A1_Video","--ignore","movies"]'
```

With dry-run option:
```pwsh
dotnet run -c Release --project EngineNet --framework net10.0 -- --game_module ".\EngineApps\Games\TheSimpsonsGame-PS3\" --script_type lua --script "{{Game_Root}}/operations/DirectoryNormalizer.lua" --args '["{{Game_Root}}/GameFiles/STROUT-{{Region}}_{{Type}}-{{audio_state}}-{{isRenamed}}","{{Game_Root}}/GameFiles/STROUT_Normalized-{{Region}}_{{Type}}-{{audio_state}}-{{isRenamed}}","--action","copy","--ignore","A1_Audio","--ignore","audiostreams","--ignore","A1_Video","--ignore","movies","--dry-run"]'
```

---

## Operation 8: Extract Textures (.txd -> .dds)
**Description:** Extracts DDS textures from TXD texture dictionaries.  
**Dependencies:** Op 0, 7  
**Run-all:** true

```pwsh
dotnet run -c Release --project EngineNet --framework net10.0 -- --game_module ".\EngineApps\Games\TheSimpsonsGame-PS3\" --script_type engine --script "format-extract" --format txd --args '["{{Game_Root}}/GameFiles/{{STROUT}}-{{Region}}_{{Type}}-{{audio_state}}-{{isRenamed}}"]'
```

---

## Operation 9: Convert Textures (.dds -> .png)
**Description:** Converts DDS textures to PNG using ImageMagick.  
**Dependencies:** Op 0, 7, 8, 2  
**Run-all:** true

```pwsh
dotnet run -c Release --project EngineNet --framework net10.0 -- --game_module ".\EngineApps\Games\TheSimpsonsGame-PS3\" --script_type engine --script "format-convert" --tool "ImageMagick" --args '["--source","{{Game_Root}}/GameFiles/{{STROUT}}-{{Region}}_{{Type}}-{{audio_state}}-{{isRenamed}}","--target","{{Game_Root}}/GameFiles/{{STROUT}}-{{Region}}_{{Type}}-{{audio_state}}-{{isRenamed}}","--input-ext",".dds","--output-ext",".png"]'
```

---

## Operation 10: Validate Extracted Game Files
**Description:** Validates extracted .preinstanced, .txd, .dds, .png files.  
**Dependencies:** Op 0  
**Run-all:** false

```pwsh
dotnet run -c Release --project EngineNet --framework net10.0 -- --game_module ".\EngineApps\Games\TheSimpsonsGame-PS3\" --script_type engine --script "validate-files" --args '["{{Game_Root}}/config/GameFilesIndex_{{Region}}_{{Type}}-{{audio_state}}-{{isRenamed}}.db","{{Game_Root}}/GameFiles/{{STROUT}}-{{Region}}_{{Type}}-{{audio_state}}-{{isRenamed}}","--tables","preinstanced_index:source_path,txd_index:source_path,dds_index:source_path,png_index:source_path","--required-dirs","audiostreams||A1_Audio,movies||A1_Video,frontend||A2_Frontend,simpsons_chars||A2_Characters_Simpsons,spr_hub||L00_SprHub,loc||L01_LandOfChocolate,brt||L02_BartmanBegins,eighty_bites||L03_HungryHungryHomer,tree_hugger||L04_TreeHugger,mob_rules||L05_MobRules,cheater||L06_EnterTheCheatrix,dayofthedolphins||L07_DayOfTheDolphin,colossaldonut||L08_TheColossalDonut,dayspringfieldstoodstill||L09_Invasion,bargainbin||L10_BargainBin,gamehub||L00_GameHub,neverquest||L11_NeverQuest,grand_theft_scratchy||L12_GrandTheftScratchy,medal_of_homer||L13_MedalOfHomer,bigsuperhappy||L14_BigSuperHappy,rhymes||L15_Rhymes,meetthyplayer||L16_MeetThyPlayer"]'
```

---

## Operation 11: Convert Models (.preinstanced -> .blend)
**Description:** Converts 3D models to Blender format and exports to GLB/FBX with textures.  
**Dependencies:** Op 0, 2, 6, 8, 9  
**Run-all:** true

```pwsh
dotnet run -c Release --project EngineNet --framework net10.0 -- --game_module ".\EngineApps\Games\TheSimpsonsGame-PS3\" --script_type lua --script "{{Game_Root}}/operations/Blender/run.lua" --args '["--game-root","{{Game_Root}}","--base-dir","{{Game_Root}}","--operations-dir","{{Game_Root}}/operations","--blender-dir","{{Game_Root}}/operations/Blender","--preinstanced-dir","{{Game_Root}}/GameFiles/{{STROUT}}-{{Region}}_{{Type}}-{{audio_state}}-{{isRenamed}}","--blend-dir","{{Game_Root}}/GameFiles/{{STROUT}}-{{Region}}_{{Type}}-{{audio_state}}-{{isRenamed}}","--blank-blend","{{Game_Root}}/blank.blend","--root-drive","{{Game_Root}}/TMP_TSG_LNKS-{{Region}}_{{Type}}-{{audio_state}}-{{isRenamed}}","--main-db","{{Game_Root}}/config/GameFilesIndex_{{Region}}_{{Type}}-{{audio_state}}-{{isRenamed}}.db","--asset-map-db","{{Game_Root}}/GameFiles/config/{{Region}}_{{Type}}-{{audio_state}}-{{isRenamed}}/AssetMap.sqlite"]'
```

With verbose and debug options:
```pwsh
dotnet run -c Release --project EngineNet --framework net10.0 -- --game_module ".\EngineApps\Games\TheSimpsonsGame-PS3\" --script_type lua --script "{{Game_Root}}/operations/Blender/run.lua" --args '["--game-root","{{Game_Root}}","--base-dir","{{Game_Root}}","--operations-dir","{{Game_Root}}/operations","--blender-dir","{{Game_Root}}/operations/Blender","--preinstanced-dir","{{Game_Root}}/GameFiles/{{STROUT}}-{{Region}}_{{Type}}-{{audio_state}}-{{isRenamed}}","--blend-dir","{{Game_Root}}/GameFiles/{{STROUT}}-{{Region}}_{{Type}}-{{audio_state}}-{{isRenamed}}","--blank-blend","{{Game_Root}}/blank.blend","--root-drive","{{Game_Root}}/TMP_TSG_LNKS-{{Region}}_{{Type}}-{{audio_state}}-{{isRenamed}}","--main-db","{{Game_Root}}/config/GameFilesIndex_{{Region}}_{{Type}}-{{audio_state}}-{{isRenamed}}.db","--asset-map-db","{{Game_Root}}/GameFiles/config/{{Region}}_{{Type}}-{{audio_state}}-{{isRenamed}}/AssetMap.sqlite","--verbose","--debug-sleep","--export","glb","fbx"]'
```

---

## Operation 12: Convert Videos (.vp6 -> .ogv)
**Description:** Converts VP6 videos to OGV format for Godot using ffmpeg.  
**Dependencies:** Op 0, 2  
**Run-all:** true

```pwsh
dotnet run -c Release --project EngineNet --framework net10.0 -- --game_module ".\EngineApps\Games\TheSimpsonsGame-PS3\" --script_type engine --script "format-convert" --tool "ffmpeg" --args '["-m","ffmpeg","--type","video","-s","{{SourcePath}}/{{Region}}/{{PostSourcePath}}","-t","{{Game_Root}}/GameFiles/{{STROUT}}-{{Region}}_{{Type}}-{{audio_state}}-{{isRenamed}}","-i",".vp6","-o",".ogv"]'
```

---

## Operation 13: Convert Audio (.snu -> .wav)
**Description:** Converts SNU audio to WAV format using vgmstream-cli.  
**Dependencies:** Op 0, 2  
**Run-all:** true

```pwsh
dotnet run -c Release --project EngineNet --framework net10.0 -- --game_module ".\EngineApps\Games\TheSimpsonsGame-PS3\" --script_type engine --script "format-convert" --tool "vgmstream" --args '["-m","vgmstream","--type","audio","-s","{{SourcePath}}/{{Region}}/{{PostSourcePath}}","-t","{{Game_Root}}/GameFiles/{{STROUT}}-{{Region}}_{{Type}}-{{audio_state}}-{{isRenamed}}","-i",".snu","-o",".wav","--godot-compatible"]'
```

---

## Operation 14: Validate All Game Files
**Description:** Final validation of all converted assets before Godot generation.  
**Dependencies:** Op 0  
**Run-all:** false

```pwsh
dotnet run -c Release --project EngineNet --framework net10.0 -- --game_module ".\EngineApps\Games\TheSimpsonsGame-PS3\" --script_type engine --script "validate-files" --args '["{{Game_Root}}/config/GameFilesIndex_{{Region}}_{{Type}}-{{audio_state}}-{{isRenamed}}.db","{{Game_Root}}/GameFiles/{{STROUT}}-{{Region}}_{{Type}}-{{audio_state}}-{{isRenamed}}","--tables","preinstanced_index:source_path,glb_index:source_path,txd_index:source_path,dds_index:source_path,png_index:source_path,audio_wav_index:source_path,video_ogv_index:source_path"]'
```

---

## Operation 15: Generate Godot Game (EXPERIMENTAL)
**Description:** Generates complete Godot project from converted assets.  
**Dependencies:** Op 0, 6, 8, 9, 11, 12, 13, 14  
**Run-all:** false

```pwsh
dotnet run -c Release --project EngineNet --framework net10.0 -- --game_module ".\EngineApps\Games\TheSimpsonsGame-PS3\" --script_type lua --script "{{Game_Root}}/Godot/Game/godot-init-V0.4.2.lua" --args '["--project-name","SimpsonsGamePS3","--repo-root","{{Project_Root}}","--sourcePath","{{Game_Root}}/GameFiles/{{STROUT}}-{{Region}}_{{Type}}-{{audio_state}}-{{isRenamed}}"]'
```

---

## Operation 16: Generate Godot Menu (EXPERIMENTAL)
**Description:** Generates menu and UI systems for Godot project.  
**Dependencies:** Op 0, 6, 8, 9, 11, 12, 13, 14  
**Run-all:** false

```pwsh
dotnet run -c Release --project EngineNet --framework net10.0 -- --game_module ".\EngineApps\Games\TheSimpsonsGame-PS3\" --script_type lua --script "{{Project_Root}}/EngineApps/Games/TheSimpsonsGame-PS3/Godot/Game.Menu/godot-init-V0.4.2.lua" --args '["--project-name","SimpsonsGamePS3","--repo-root","{{Project_Root}}","--sourcePath","{{Game_Root}}/GameFiles/{{STROUT}}-{{Region}}_{{Type}}-{{audio_state}}-{{isRenamed}}"]'
```

---

## Operation 17: Extract Dialogue/Subtitles (.lh2 -> .csv)
**Description:** Extracts dialogue and subtitle data from LH2 files to CSV format.  
**Dependencies:** Op 0  
**Run-all:** false

```pwsh
dotnet run -c Release --project EngineNet --framework net10.0 -- --game_module ".\EngineApps\Games\TheSimpsonsGame-PS3\" --script_type lua --script "{{Game_Root}}/operations/lh2_to_csv.lua" --args '["--input-dir","{{Game_Root}}/GameFiles/{{STROUT}}-{{Region}}_{{Type}}-{{audio_state}}-{{isRenamed}}"]'
```

---

## Operation -1: Godot Dev Tests (Dev)
**Description:** Development testing for Godot integration.  
**Dependencies:** None  
**Run-all:** false

```pwsh
dotnet run -c Debug --project EngineNet --framework net10.0 -- --game_module ".\EngineApps\Games\TheSimpsonsGame-PS3\" --script_type lua --script "{{Project_Root}}/EngineApps/Games/TheSimpsonsGame-PS3/Godot/Game.Dev/godot-init-V0.4.2.lua" --args '["--project-name","Test","--repo-root","{{Project_Root}}","--sourcePath","{{Game_Root}}/GameFiles/{{STROUT}}-{{Region}}_{{Type}}-{{audio_state}}-{{isRenamed}}"]'
```

---

## Advanced: Manual Blender Python Execution
For debugging or manual processing of individual assets:

```pwsh
Tools/Blender/blender-4.0.2-windows-x64/blender.exe -b path/to/your_asset.blend --python EngineApps/Games/TheSimpsonsGame-PS3/operations/Blender/MainPreinstancedConvert.py -- path/to/your_asset.blend path/to/your_asset.preinstanced path/to/your_asset.glb EngineApps/Games/TheSimpsonsGame-PS3/operations/Blender/PreinstancedImportExtension.py true false EngineApps/Games/TheSimpsonsGame-PS3/operations/Blender path/to/your_asset.fbx asset_identifier path/to/temp_addon_dir glb,fbx
```

---

## Typical Processing Pipeline

### Full Build (from source to Godot-ready):
1. **Op 0** - Initialize (auto)
2. **Op 2** - Download Tools
3. **Op 1** - Validate Source
4. **Op 6** - Extract Archives (.str)
5. **Op 12** - Convert Videos
6. **Op 13** - Convert Audio
7. **Op 3** - Rename Folders (optional)
8. **Op 4** - Reorganize Audio (optional)
9. **Op 7** - Normalize Structure (optional, recommended)
10. **Op 8** - Extract Textures
11. **Op 9** - Convert Textures
12. **Op 11** - Convert Models
13. **Op 14** - Validate All
14. **Op 15** - Generate Godot Game

### Quick Build (run-all operations only):
Operations 6, 8, 9, 11, 12, 13 are marked as `run-all = true` and can be executed together.


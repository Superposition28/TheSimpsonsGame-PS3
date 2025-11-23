# Module TODO List


godot::
## TODO: the current scene_config.json expects very specific asset paths that are nolonger correct
## TODO: instead auto export the full asset map sqlite db to json and use the asset_id in the scene config
## TODO: or somehow auto generate the scene config based on the db file
## last version does technically work, but only with the correct asset paths

The materials applied to the models within godot will need to be adjustable via the godot editor scene builder script and the json configs


Blender::
## blender cannot handle paths that exeed windows path limits
## blender refused to accept my solutions to this so i did two things to ensure it works for -
## blender and any other application that needs to handle the files
## the second solution within the blender init is to create symbolic links to the long paths, this had a noticable impact on reliability
## but the two solutions significantly impact time to complete second only to godot



Init Lua:
the Init Lua script needs to be updated to handle multiple possible source paths for the game files
Possible source paths provided by user:
G:\PS3_GAME\USRDIR -- containing game files
G:\PS3_GAME -- containing USRDIR folder, and .png files, this is where the path will resolve to, regardless of which of the three paths is provided
G:\ -- containing PS3_GAME folder

ensure the order of prompts in the init is Path, Region, etc, currently the region prompt comes before the path prompt which is not ideal
when 'how to use source files' prompt appears ensure the path is writable and not a read only location like iso mount point, especially when user selects 'use source files directly' or move source files to game root (delete source files after move), not necessary for copy source files to game root (keep source files in original location)
run the validation before accepting source path after user input instead
```
Validating final source location: 'A:\RemakeEngine\EngineApps\Games\TheSimpsonsGame-PS3\Source\USRDIR'
All 23 required 'USRDIR_DIRS_ORIGINAL' subdirectories found in 'A:\RemakeEngine\EngineApps\Games\TheSimpsonsGame-PS3\Source\USRDIR'.
Success: Source validated and saved: A:\RemakeEngine\EngineApps\Games\TheSimpsonsGame-PS3\Source\USRDIR
```


Indexer:
will likly require a number of possible db outputs to handle different scenarios
the folder structure may or maynot be flattened
the stray audio files may or maynot be reorganized into en and global folders
the main folder names may or may not be renamed based on the rename map to be more descriptive
resulting in all these outputs together:
GameFilesIndex_EU_SourceOnly-audio_og-notRenamed.db -- notRenamed means no rename, source only means it only scans the original source structure as it would be in the iso
GameFilesIndex_EU_SourceOnly-audio_og-isRenamed.db -- isRenamed means with rename, source only means it only scans the original source structure as it would be in the iso after renaming the base folders
GameFilesIndex_EU_SourceOnly-audio_reorg-notRenamed.db -- as before but with audio files reorganized into en and global folders.
GameFilesIndex_EU_SourceOnly-audio_reorg-isRenamed.db -- as before but with audio files reorganized into en and global folders.
// source could also be flattened but its better to flatten after extraction, thats when all the files are deeply nested
GameFilesIndex_EU_Full-audio_og-notRenamed.db -- full means it scans the full structure both source and extracted files
GameFilesIndex_EU_Full-audio_og-isRenamed.db -- full means it scans the full structure both source and extracted files
GameFilesIndex_EU_Full-audio_reorg-notRenamed.db -- as before but audio_reorg means audio files reorganized into en and global folders.
GameFilesIndex_EU_Full-audio_reorg-isRenamed.db -- as before but audio_reorg means audio files reorganized into en and global folders.
GameFilesIndex_EU_FullFlattened-audio_og-notRenamed.db -- full means it scans the full structure both source and extracted files flattened means the folder structure is flattened
GameFilesIndex_EU_FullFlattened-audio_og-isRenamed.db -- full means it scans the full structure both source and extracted files flattened means the folder structure is flattened
GameFilesIndex_EU_FullFlattened-audio_reorg-notRenamed.db -- as before but audio_reorg means audio files reorganized into en and global folders.
GameFilesIndex_EU_FullFlattened-audio_reorg-isRenamed.db -- as before but audio_reorg means audio files reorganized into en and global folders.

the init script will set a var for en or us and the ops will use that to determine which db to use
the scripts that change the folder structure (flatten, reorganize audio files) will also set vars to indicate what changes were made so the correct db can be used

```
current
db = "{{Game_Root}}/config/GameFilesIndex_{{Region}}_Full-{{isRenamed}}.db"
```
```
better
db = "{{Game_Root}}/config/GameFilesIndex_{{Region}}_Full-{{audio_state}}-{{isRenamed}}.db"
the conf file will contains string values for audio_state and int for isRenamed
and
db = "{{Game_Root}}/config/GameFilesIndex_{{Region}}_SourceOnly-{{audio_state}}-{{isRenamed}}.db"
the conf file will contains string values for audio_state and int for isRenamed
```


finish indexing all files EN|US both un-processed and processed
the index needs to handle the case where audio files are moved into en and global folders after (Reorganize Audio Files) operation

TMP::

## Universal Permutation Indexer V7
The indexer automatically builds and indexes multiple permutations of the game files by:
1. Configuring the engine with placeholders (Region, Type, audio_state, isRenamed, STROUT)
2. Running the required operations in sequence
3. Indexing the resulting files into UniversalIndex.db

Run with: `python EngineApps\Games\TheSimpsonsGame-PS3\indexer\indexv7.py`

### Permutations Built and Indexed:

#### 1. EU_Full_audio_og_notRenamed
Config: Region=EU, Type=Full, audio_state=audio_og, isRenamed=notRenamed, STROUT=STROUT
Operations Run (in order):
> Op 6  -- Extract Archives (.STR)
> Op 12 -- Convert Videos (.vp6 -> .ogv)
> Op 13 -- Convert Audio (.snu -> .wav)
> Op 8  -- Extract Textures (.txd -> .dds)
> Op 9  -- Convert Textures (.dds -> .png)
> Op 11 -- Convert Models (.preinstanced -> .blend)

dotnet commands:
```pwsh
# Op 6: Extract Archives
dotnet run -c Release --project EngineNet --framework net9.0 -- --game_module "A:\RemakeEngine\EngineApps\Games\TheSimpsonsGame-PS3" --script_type bms --script "{{Game_Root}}/operations/simpsons_str.bms" --set "input={{SourcePath}}/{{Region}}/{{PostSourcePath}}" --set "output={{Game_Root}}/GameFiles/STROUT-{{Region}}_{{Type}}-{{audio_state}}-{{isRenamed}}" --set "extension=.str"

# Op 12: Convert Videos
dotnet run -c Release --project EngineNet --framework net9.0 -- --game_module "A:\RemakeEngine\EngineApps\Games\TheSimpsonsGame-PS3" --script_type engine --script "format-convert" --args '["-m","ffmpeg","--type","video","-s","{{SourcePath}}/{{Region}}/{{PostSourcePath}}","-t","{{Game_Root}}/GameFiles/{{STROUT}}-{{Region}}_{{Type}}-{{audio_state}}-{{isRenamed}}","-i",".vp6","-o",".ogv"]'

# Op 13: Convert Audio
dotnet run -c Release --project EngineNet --framework net9.0 -- --game_module "A:\RemakeEngine\EngineApps\Games\TheSimpsonsGame-PS3" --script_type engine --script "format-convert" --args '["-m","vgmstream","--type","audio","-s","{{SourcePath}}/{{Region}}/{{PostSourcePath}}","-t","{{Game_Root}}/GameFiles/{{STROUT}}-{{Region}}_{{Type}}-{{audio_state}}-{{isRenamed}}","-i",".snu","-o",".wav","--godot-compatible"]'

# Op 8: Extract Textures
dotnet run -c Release --project EngineNet --framework net9.0 -- --game_module "A:\RemakeEngine\EngineApps\Games\TheSimpsonsGame-PS3" --script_type engine --script "format-extract" --args '["{{Game_Root}}/GameFiles/{{STROUT}}-{{Region}}_{{Type}}-{{audio_state}}-{{isRenamed}}"]'

# Op 9: Convert Textures
dotnet run -c Release --project EngineNet --framework net9.0 -- --game_module "A:\RemakeEngine\EngineApps\Games\TheSimpsonsGame-PS3" --script_type engine --script "format-convert" --args '["--source","{{Game_Root}}/GameFiles/{{STROUT}}-{{Region}}_{{Type}}-{{audio_state}}-{{isRenamed}}","--target","{{Game_Root}}/GameFiles/{{STROUT}}-{{Region}}_{{Type}}-{{audio_state}}-{{isRenamed}}","--input-ext",".dds","--output-ext",".png"]'

# Op 11: Convert Models
dotnet run -c Release --project EngineNet --framework net9.0 -- --game_module "A:\RemakeEngine\EngineApps\Games\TheSimpsonsGame-PS3" --script_type lua --script "{{Game_Root}}/operations/Blender/run.lua" --args '["--game-root","{{Game_Root}}","--base-dir","{{Game_Root}}","--operations-dir","{{Game_Root}}/operations","--blender-dir","{{Game_Root}}/operations/Blender","--preinstanced-dir","{{Game_Root}}/GameFiles/{{STROUT}}-{{Region}}_{{Type}}-{{audio_state}}-{{isRenamed}}","--blend-dir","{{Game_Root}}/GameFiles/{{STROUT}}-{{Region}}_{{Type}}-{{audio_state}}-{{isRenamed}}","--blank-blend","{{Game_Root}}/blank.blend","--root-drive","{{Game_Root}}/TMP_TSG_LNKS-{{Region}}_{{Type}}-{{audio_state}}-{{isRenamed}}","--main-db","{{Game_Root}}/config/GameFilesIndex_{{Region}}_{{Type}}-{{audio_state}}-{{isRenamed}}.db","--asset-map-db","{{Game_Root}}/GameFiles/config/{{Region}}_{{Type}}-{{audio_state}}-{{isRenamed}}/AssetMap.sqlite"]'
```

#### 2. EU_Full_audio_og_isRenamed
Config: Region=EU, Type=Full, audio_state=audio_og, isRenamed=isRenamed, STROUT=STROUT
Operations Run (in order):
> Op 6  -- Extract Archives (.STR)
> Op 12 -- Convert Videos (.vp6 -> .ogv)
> Op 13 -- Convert Audio (.snu -> .wav)
> Op 8  -- Extract Textures (.txd -> .dds)
> Op 9  -- Convert Textures (.dds -> .png)
> Op 11 -- Convert Models (.preinstanced -> .blend)
> Op 3  -- Rename base folders

#### 3. EU_Full_audio_reorg_isRenamed
Config: Region=EU, Type=Full, audio_state=audio_reorg, isRenamed=isRenamed, STROUT=STROUT
Operations Run (in order):
> Op 6  -- Extract Archives (.STR)
> Op 12 -- Convert Videos (.vp6 -> .ogv)
> Op 13 -- Convert Audio (.snu -> .wav)
> Op 8  -- Extract Textures (.txd -> .dds)
> Op 9  -- Convert Textures (.dds -> .png)
> Op 11 -- Convert Models (.preinstanced -> .blend)
> Op 3  -- Rename base folders
> Op 4  -- Reorganize Audio Files

#### 4. EU_FullFlattened_audio_reorg_isRenamed
Config: Region=EU, Type=FullFlattened, audio_state=audio_reorg, isRenamed=isRenamed, STROUT=STROUT_Normalized
Operations Run (in order):
> Op 6  -- Extract Archives (.STR)
> Op 12 -- Convert Videos (.vp6 -> .ogv)
> Op 13 -- Convert Audio (.snu -> .wav)
> Op 8  -- Extract Textures (.txd -> .dds)
> Op 9  -- Convert Textures (.dds -> .png)
> Op 11 -- Convert Models (.preinstanced -> .blend)
> Op 3  -- Rename base folders
> Op 4  -- Reorganize Audio Files
> Op 7  -- Normalize folder structure

### Database Output:
All permutations are indexed into a single UniversalIndex.db containing:
- `permutations` table: Tracks each build variant with config parameters
- `assets` table: Unique assets identified by UID (MD5 hash of canonical path)
- `instances` table: Links assets to specific permutations with file paths






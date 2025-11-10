






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


engine:

add parallel execution support for operations, based on operation dependencies
eg
these three operations can run in parallel after extract archives is complete, as the audio and video conversions have no requirements or dependencies on any previous operations including extract archives as they are not stored in archives
> -- Convert Models (.preinstanced -> .blend)
> -- Convert Videos (.vp6 -> .ogv)
> -- Convert Audio (.snu -> .wav)
blender convert is dependent on extract and txd operations completing first, txd is also dependent on extract completing first

add operation ID's to the operation config to uniquely identify each operation



add placeholder resolution for operation Names

engine git module downloader: tui issue:
when downloading TheSimpsonsGame-PS3 module, the tui does not correctly handle the print event from the git tool resulting in this output:
Select a module to download:
  SimpsonsHitAndRun
  TheSimpsonsGame-PS2
> TheSimpsonsGame-PS3
  TheSimpsonsRoadRage-PS2
  Back
@@REMAKE@@ {"event":"print","message":"[ENGINE-GitTools] ","color":null,"newline":false}
@@REMAKE@@ {"event":"print","message":"Downloading \u0027TheSimpsonsGame-PS3\u0027 from \u0027https://github.com/Superposition28/TheSimpsonsGame-PS3.git\u0027...","color":null,"newline":true}
@@REMAKE@@ {"event":"print","message":"[ENGINE-GitTools] ","color":null,"newline":false}
@@REMAKE@@ {"event":"print","message":"Target directory: \u0027A:\\RemakeEngine\\EngineApps\\Games\\TheSimpsonsGame-PS3\u0027","color":null,"newline":true}
@@REMAKE@@ {"event":"print","message":"[ENGINE-GitTools] ","color":null,"newline":false}
@@REMAKE@@ {"event":"print","message":"Cloning into \u0027A:\\RemakeEngine\\EngineApps\\Games\\TheSimpsonsGame-PS3\u0027...","color":null,"newline":true}

:: engine tui displays the uninstalled modules in the main menu list only after entering and exiting the git module downloader menu:
Select a game:
> demo  [registered, installed, unbuilt]
  TheSimpsonsGame-PS3  [registered, installed, unbuilt]
  TheSimpsonsGame-PS2  [registered, uninstalled]
  SimpsonsHitAndRun  [registered, uninstalled]
  TheSimpsonsRoadRage-PS2  [registered, uninstalled]
  TheSimpsonsGame-PS3-Dev  [installed, unverified, unbuilt]
  ---------------
  Download module...
  Exit

progress bar issue
 if console window is too tall it will print many progress bars that all actually work, but are partial repeats of the same bar

Tools-Downloader:

vgmstream-cli has no checksum
when re-runing the downloader with no force redownload, it always redownloads despite the file existing already in both the tools and tmp downloads, but then stops when it find the exe in the tools folder, its checking the exe path after it determines what the file is named, which it can only know after downloading it first, so it always downloads again even if its already there


the Loading bar does not render correctly, often showing many empty lines and/or printing the bar on multiple lines
this may also occur in other tools, and is likly connected to console size W and/or H, like in vs code terminal



flatten:
the flatten structure script (C#) needs to be updated to be more like this py script 'reversing\Source\Format-Analysis\preinstanced\scripts\flatten.py' or maybe it was 'reversing\Format-Analysis\preinstanced\flatten2.py'


Texture Extraction:
the texture extraction script needs to be updated to correctly write dds header data, some don't have the file size written correctly
add support for exporting to png format directly from dds files to not require an external tool to convert dds to png



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

operations to run in order to produce each of the different index db's

 ## COMPLETED the Following for EU region
 using PS A:\RemakeEngine> python EngineApps\Games\TheSimpsonsGame-PS3\dev-tools\indexer\main.py --Type Full --region EU --AudioReorg audio_og --renamedBaseDirs notRenamed
  to make this db:EngineApps\Games\TheSimpsonsGame-PS3\config\GameFilesIndex_EU_Full-audio_og-notRenamed.db
 GameFilesIndex_EU_Full-audio_og-notRenamed.db:: -- full means it scans the full structure both source and extracted files
  (Skipped) -- Validate Source Game Files and Folders
> (ran)     -- Download Required Tools
  (Skipped) -- Rename base folders
  (Skipped) -- Reorganize Audio Files
  (Skipped) -- re-Validate Source Game Files and Folders
> (ran)     -- Extract Archives (.STR)
  (Skipped) -- flatten folder structure
> (ran)     -- Extract Textures (.txd -> .dds)
> (ran)     -- Convert Textures (.dds -> .png)
  (Skipped) -- validate extracted game files
> (ran)     -- Convert Models (.preinstanced -> .blend)
> (ran)     -- Convert Videos (.vp6 -> .ogv)
> (ran)     -- Convert Audio (.snu -> .wav)
  (Skipped) -- Validate all game files
  (Skipped) -- generate Godot Game (EXPERIMENTAL)
  (Skipped) -- GODOT - Generate Menu's (EXPERIMENTAL)

 using PS A:\RemakeEngine> python EngineApps\Games\TheSimpsonsGame-PS3\dev-tools\indexer\main.py --Type Full --region EU --AudioReorg audio_og --renamedBaseDirs isRenamed
  to make this db:EngineApps\Games\TheSimpsonsGame-PS3\config\GameFilesIndex_EU_Full-audio_og-isRenamed.db
 GameFilesIndex_EU_Full-audio_og-isRenamed.db: -- full means it scans the full structure both source and extracted files
  (Skipped) -- Validate Source Game Files and Folders
> (ran)     -- Download Required Tools
> (ran)     -- Rename base folders
  (Skipped) -- Reorganize Audio Files
  (Skipped) -- re-Validate Source Game Files and Folders
> (ran)     -- Extract Archives (.STR)
  (Skipped) -- flatten folder structure
> (ran)     -- Extract Textures (.txd -> .dds)
> (ran)     -- Convert Textures (.dds -> .png)
  (Skipped) -- validate extracted game files
> (ran)     -- Convert Models (.preinstanced -> .blend)
> (ran)     -- Convert Videos (.vp6 -> .ogv)
> (ran)     -- Convert Audio (.snu -> .wav)
  (Skipped) -- Validate all game files
  (Skipped) -- generate Godot Game (EXPERIMENTAL)
  (Skipped) -- GODOT - Generate Menu's (EXPERIMENTAL)


  ## this will be the main run-all sequence

  using PS A:\RemakeEngine> python EngineApps\Games\TheSimpsonsGame-PS3\dev-tools\indexer\main.py --Type Full --region EU --AudioReorg audio_reorg --renamedBaseDirs isRenamed
  to make this db:EngineApps\Games\TheSimpsonsGame-PS3\config\GameFilesIndex_EU_Full-audio_reorg-isRenamed.db
 GameFilesIndex_EU_Full-audio_reorg-isRenamed.db -- as before but audio_reorg means audio files reorganized into en and global folders.
  (Skipped) -- Validate Source Game Files and Folders
> (ran)     -- Download Required Tools
> (ran)     -- Rename base folders
> (ran)     -- Reorganize Audio Files
  (Skipped) -- re-Validate Source Game Files and Folders
> (ran)     -- Extract Archives (.STR)
  (Skipped) -- flatten folder structure
> (ran)     -- Extract Textures (.txd -> .dds)
> (ran)     -- Convert Textures (.dds -> .png)
  (Skipped) -- validate extracted game files
> (ran)     -- Convert Models (.preinstanced -> .blend)
> (ran)     -- Convert Videos (.vp6 -> .ogv)
> (ran)     -- Convert Audio (.snu -> .wav)
  (Skipped) -- Validate all game files
  (Skipped) -- generate Godot Game (EXPERIMENTAL)
  (Skipped) -- GODOT - Generate Menu's (EXPERIMENTAL)

 ## TODO the Following for EU region

 using PS A:\RemakeEngine> python EngineApps\Games\TheSimpsonsGame-PS3\dev-tools\indexer\main.py --Type Full --region EU --AudioReorg audio_reorg --renamedBaseDirs notRenamed
  to make this db:EngineApps\Games\TheSimpsonsGame-PS3\config\GameFilesIndex_EU_Full-audio_reorg-notRenamed.db
 GameFilesIndex_EU_Full-audio_reorg-notRenamed.db -- as before but audio_reorg means audio files reorganized into en and global folders.
  (Skipped) -- Validate Source Game Files and Folders
> (ran)     -- Download Required Tools
  (Skipped) -- Rename base folders
> (ran)     -- Reorganize Audio Files
  (Skipped) -- re-Validate Source Game Files and Folders
> (ran)     -- Extract Archives (.STR)
  (Skipped) -- flatten folder structure
> (ran)     -- Extract Textures (.txd -> .dds)
> (ran)     -- Convert Textures (.dds -> .png)
  (Skipped) -- validate extracted game files
> (ran)     -- Convert Models (.preinstanced -> .blend)
> (ran)     -- Convert Videos (.vp6 -> .ogv)
> (ran)     -- Convert Audio (.snu -> .wav)
  (Skipped) -- Validate all game files
  (Skipped) -- generate Godot Game (EXPERIMENTAL)
  (Skipped) -- GODOT - Generate Menu's (EXPERIMENTAL)


  using PS A:\RemakeEngine> python EngineApps\Games\TheSimpsonsGame-PS3\dev-tools\indexer\main.py --Type FullFlattened --region EU --AudioReorg audio_og --renamedBaseDirs notRenamed
  to make this db:EngineApps\Games\TheSimpsonsGame-PS3\config\GameFilesIndex_EU_FullFlattened-audio_og-notRenamed.db
 GameFilesIndex_EU_FullFlattened-audio_og-notRenamed.db -- full means it scans the full structure both source and extracted files flattened means the folder structure is flattened
  (Skipped) -- Validate Source Game Files and Folders
> (ran)     -- Download Required Tools
  (Skipped) -- Rename base folders
  (Skipped) -- Reorganize Audio Files
  (Skipped) -- re-Validate Source Game Files and Folders
> (ran)     -- Extract Archives (.STR)
> (ran)     -- flatten folder structure
> (ran)     -- Extract Textures (.txd -> .dds)
> (ran)     -- Convert Textures (.dds -> .png)
  (Skipped) -- validate extracted game files
> (ran)     -- Convert Models (.preinstanced -> .blend)
> (ran)     -- Convert Videos (.vp6 -> .ogv)
> (ran)     -- Convert Audio (.snu -> .wav)
  (Skipped) -- Validate all game files
  (Skipped) -- generate Godot Game (EXPERIMENTAL)
  (Skipped) -- GODOT - Generate Menu's (EXPERIMENTAL)

  using PS A:\RemakeEngine> python EngineApps\Games\TheSimpsonsGame-PS3\dev-tools\indexer\main.py --Type FullFlattened --region EU --AudioReorg audio_og --renamedBaseDirs isRenamed
  to make this db:EngineApps\Games\TheSimpsonsGame-PS3\config\GameFilesIndex_EU_FullFlattened-audio_og-isRenamed.db
 GameFilesIndex_EU_FullFlattened-audio_og-isRenamed.db -- full means it scans the full structure both source and extracted files flattened means the folder structure is flattened
  (Skipped) -- Validate Source Game Files and Folders
> (ran)     -- Download Required Tools
> (ran)     -- Rename base folders
  (Skipped) -- Reorganize Audio Files
  (Skipped) -- re-Validate Source Game Files and Folders
> (ran)     -- Extract Archives (.STR)
> (ran)     -- flatten folder structure
> (ran)     -- Extract Textures (.txd -> .dds)
> (ran)     -- Convert Textures (.dds -> .png)
  (Skipped) -- validate extracted game files
> (ran)     -- Convert Models (.preinstanced -> .blend)
> (ran)     -- Convert Videos (.vp6 -> .ogv)
> (ran)     -- Convert Audio (.snu -> .wav)
  (Skipped) -- Validate all game files
  (Skipped) -- generate Godot Game (EXPERIMENTAL)
  (Skipped) -- GODOT - Generate Menu's (EXPERIMENTAL)

  using PS A:\RemakeEngine> python EngineApps\Games\TheSimpsonsGame-PS3\dev-tools\indexer\main.py --Type FullFlattened --region EU --AudioReorg audio_reorg --renamedBaseDirs notRenamed
  to make this db:EngineApps\Games\TheSimpsonsGame-PS3\config\GameFilesIndex_EU_FullFlattened-audio_reorg-notRenamed.db
 GameFilesIndex_EU_FullFlattened-audio_reorg-notRenamed.db -- as before but audio_reorg means audio files reorganized into en and global folders.
  (Skipped) -- Validate Source Game Files and Folders
> (ran)     -- Download Required Tools
  (Skipped) -- Rename base folders
> (ran)     -- Reorganize Audio Files
  (Skipped) -- re-Validate Source Game Files and Folders
> (ran)     -- Extract Archives (.STR)
  (Skipped) -- flatten folder structure
> (ran)     -- Extract Textures (.txd -> .dds)
> (ran)     -- Convert Textures (.dds -> .png)
  (Skipped) -- validate extracted game files
> (ran)     -- Convert Models (.preinstanced -> .blend)
> (ran)     -- Convert Videos (.vp6 -> .ogv)
> (ran)     -- Convert Audio (.snu -> .wav)
  (Skipped) -- Validate all game files
  (Skipped) -- generate Godot Game (EXPERIMENTAL)
  (Skipped) -- GODOT - Generate Menu's (EXPERIMENTAL)

  using PS A:\RemakeEngine> python EngineApps\Games\TheSimpsonsGame-PS3\dev-tools\indexer\main.py --Type FullFlattened --region EU --AudioReorg audio_reorg --renamedBaseDirs isRenamed
  to make this db:EngineApps\Games\TheSimpsonsGame-PS3\config\GameFilesIndex_EU_FullFlattened-audio_reorg-isRenamed.db
 GameFilesIndex_EU_FullFlattened-audio_reorg-isRenamed.db -- as before but audio_reorg means audio files reorganized into en and global folders.
  (Skipped) -- Validate Source Game Files and Folders
> (ran)     -- Download Required Tools
> (ran)     -- Rename base folders
> (ran)     -- Reorganize Audio Files
  (Skipped) -- re-Validate Source Game Files and Folders
> (ran)     -- Extract Archives (.STR)
> (ran)     -- flatten folder structure
> (ran)     -- Extract Textures (.txd -> .dds)
> (ran)     -- Convert Textures (.dds -> .png)
  (Skipped) -- validate extracted game files
> (ran)     -- Convert Models (.preinstanced -> .blend)
> (ran)     -- Convert Videos (.vp6 -> .ogv)
> (ran)     -- Convert Audio (.snu -> .wav)
  (Skipped) -- Validate all game files
  (Skipped) -- generate Godot Game (EXPERIMENTAL)
  (Skipped) -- GODOT - Generate Menu's (EXPERIMENTAL)






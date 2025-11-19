
init:
```pwsh
dotnet run -c Release
 --project EngineNet
 --framework net9.0
 --
 --game_module ".\EngineApps\Games\TheSimpsonsGame-PS3\"
 --script_type lua
 --script "{{Game_Root}}/operations/init.lua"
``

ops:
-   Name: "Download Tools"
```pwsh
 dotnet run -c Release
 --project EngineNet
 --framework net9.0
 --
 --game_module ".\EngineApps\Games\TheSimpsonsGame-PS3\"
 --script_type engine
 --script download_tools
 --tools_manifest "{{Game_Root}}/Tools.toml"
```


-   Name: "validate source game files1"
```pwsh
dotnet run -c Release --project EngineNet --framework net9.0 -- --game_module ".\EngineApps\Games\TheSimpsonsGame-PS3\" --script_type "engine" --script "validate-files" --args '["{{Game_Root}}/config/SourceFiles.db","F:/PS3_GAME/USRDIR","--tables", "str_index:source_path,video_index:source_path,mus_index:source_path,snu_index:source_path,other_files_index:source_path","--required-dirs", "audiostreams,movies,simpsons_chars,frontend,gamehub,spr_hub,loc,brt,eighty_bites,tree_hugger,mob_rules,cheater,dayofthedolphins,colossaldonut,dayspringfieldstoodstill,bargainbin,neverquest,grand_theft_scratchy,medal_of_homer,bigsuperhappy,rhymes,meetthyplayer"]'
```


-   Name: "Rename base folders"
```pwsh
 dotnet run -c Release
 --project EngineNet
 --framework net9.0
 --
 --game_module ".\EngineApps\Games\TheSimpsonsGame-PS3\"
 --script_type engine
 --script rename-folders
 --args '["{{SourcePath}}", "--map-db-file", "{{Game_Root}}/config/RenameMap.db"]'
```

-   Name: "Reorganize Audio Files"
```pwsh
 dotnet run -c Release
 --project EngineNet
 --framework net9.0
 --
 --game_module ".\EngineApps\Games\TheSimpsonsGame-PS3\"
 --script_type "lua"
 --script "{{Game_Root}}/operations/SetupAudioDir.lua"
 --args '["{{SourcePath}}/Assets_1_Audio_Streams"]'
```



-   Name: "validate source game files2"
```pwsh
dotnet run -c Release
 --project EngineNet
 --framework net9.0
 --
 --game_module ".\EngineApps\Games\TheSimpsonsGame-PS3\"
 --script_type "engine"
 --script "validate-files"
 --args '[
	"{{Game_Root}}/config/SourceFiles.db",
	"{{SourcePath}}",
	"--tables", "str_index:source_path,video_index:source_path,mus_index:source_path,snu_index:source_path",
	"--required-dirs", "Assets_1_Audio_Streams,Assets_1_Video_Movies,Assets_2_Characters_Simpsons,Assets_2_Frontend,Map_3-00_GameHub,Map_3-00_SprHub,Map_3-01_LandOfChocolate,Map_3-02_BartmanBegins,Map_3-03_HungryHungryHomer,Map_3-04_TreeHugger,Map_3-05_MobRules,Map_3-06_EnterTheCheatrix,Map_3-07_DayOfTheDolphin,Map_3-08_TheColossalDonut,Map_3-09_Invasion,Map_3-10_BargainBin,Map_3-11_NeverQuest,Map_3-12_GrandTheftScratchy,Map_3-13_MedalOfHomer,Map_3-14_BigSuperHappy,Map_3-15_Rhymes,Map_3-16_MeetThyPlayer"
]'
```

-   Name: "flatten folder structure"
```pwsh
dotnet run -c Release
 --project EngineNet
 --framework net9.0
 --
 --game_module ".\EngineApps\Games\TheSimpsonsGame-PS3\"
 --script_type lua
 --script "{{Game_Root}}/operations/DirectoryNormalizer.lua"
 --args '[
  "{{Game_Root}}/GameFiles/{{STROUT}}",
  "{{Game_Root}}/GameFiles/{{STROUT}}_Normalized",
  "--rules", "{{Game_Root}}/config/DirectoryNormalizer.rules.json",
  "--action", "copy",
  "--ignore", "Assets_1_Audio_Streams",
  "--ignore", "audiostreams",
  "--ignore", "Assets_1_Video_Movies",
  "--ignore", "movies"
]'
```

dotnet run -c Release --project EngineNet --framework net9.0 -- --game_module ".\EngineApps\Games\TheSimpsonsGame-PS3\" --script_type lua --script "{{Game_Root}}/operations/DirectoryNormalizer.lua" --args '["{{Game_Root}}/GameFiles/STROUT", "{{Game_Root}}/GameFiles/STROUT_Normalized", "--action", "copy", "--ignore", "Assets_1_Audio_Streams", "--ignore", "audiostreams", "--ignore", "Assets_1_Video_Movies", "--ignore", "movies", "--ignore", "Map_3-02_BartmanBegins", "--ignore", "Map_3-03_HungryHungryHomer", "--ignore", "Map_3-04_TreeHugger", "--ignore", "Map_3-05_MobRules", "--ignore", "Map_3-06_EnterTheCheatrix", "--ignore", "Map_3-07_DayOfTheDolphin", "--ignore", "Map_3-08_TheColossalDonut", "--ignore", "Map_3-09_Invasion", "--ignore", "Map_3-10_BargainBin", "--ignore", "Map_3-11_NeverQuest", "--ignore", "Map_3-12_GrandTheftScratchy", "--ignore", "Map_3-13_MedalOfHomer", "--ignore", "Map_3-14_BigSuperHappy", "--ignore", "Map_3-15_Rhymes", "--ignore", "Map_3-16_MeetThyPlayer", "--ignore", "Assets_2_Characters_Simpsons", "--ignore", "Assets_2_Frontend", "--ignore", "Map_3-00_GameHub", "--ignore", "Map_3-00_SprHub"]'



-   Name: "validate flattened source game files"
```pwsh
dotnet run -c Release
 --project EngineNet
 --framework net9.0
 --
 --game_module ".\EngineApps\Games\TheSimpsonsGame-PS3\"
 --script_type "engine"
 --script "validate-files"
 --args '[
	"{{Game_Root}}/config/full-index-noflat-test.db",
	"{{SourcePath}}",
	"--tables", "str_index:source_path,video_index:source_path,mus_index:source_path,snu_index:source_path",
	"--required-dirs", "Assets_1_Audio_Streams,Assets_1_Video_Movies,Assets_2_Characters_Simpsons,Assets_2_Frontend,Map_3-00_GameHub,Map_3-00_SprHub,Map_3-01_LandOfChocolate,Map_3-02_BartmanBegins,Map_3-03_HungryHungryHomer,Map_3-04_TreeHugger,Map_3-05_MobRules,Map_3-06_EnterTheCheatrix,Map_3-07_DayOfTheDolphin,Map_3-08_TheColossalDonut,Map_3-09_Invasion,Map_3-10_BargainBin,Map_3-11_NeverQuest,Map_3-12_GrandTheftScratchy,Map_3-13_MedalOfHomer,Map_3-14_BigSuperHappy,Map_3-15_Rhymes,Map_3-16_MeetThyPlayer"
]'
```

-   Name: "Extract Archives (.STR)"
```pwsh
dotnet run -c Release --project EngineNet --framework net9.0 -- --game_module ".\EngineApps\Games\TheSimpsonsGame-PS3\" --script_type "bms" --script "./EngineApps/Games/TheSimpsonsGame-PS3/operations/simpsons_str.bms" --input "{{Game_Root}}/Source" --output "{{Game_Root}}/GameFiles/STROUT" --extension ".str" 
```

-   Name: "Extract Textures (.txd -> .dds)"
```pwsh
 dotnet run -c Release
 --project EngineNet
 --framework net9.0
 --
 --game_module ".\EngineApps\Games\TheSimpsonsGame-PS3\"
 --script_type "engine"
 --script "format-extract"
 --format txd
 --args '["{{Game_Root}}/GameFiles/STROUT"]'
```

-   Name: "validate extracted game files"
```pwsh
 dotnet run -c Release
 --project EngineNet
 --framework net9.0
 --
 --game_module ".\EngineApps\Games\TheSimpsonsGame-PS3\"
 --script_type "engine"
 --script "validate-files"
 --args '[
  "{{Game_Root}}/config/PrimaryIndex.db",
  "{{Game_Root}}/GameFiles/STROUT",
  "--tables", "preinstanced_index:source_path,txd_index:source_path,dds_index:source_path,unknown_files_index:source_path",
  "--required-dirs", "Assets_2_Characters_Simpsons,Assets_2_Frontend,Map_3-00_GameHub,Map_3-00_SprHub,Map_3-01_LandOfChocolate,Map_3-02_BartmanBegins,Map_3-03_HungryHungryHomer,Map_3-04_TreeHugger,Map_3-05_MobRules,Map_3-06_EnterTheCheatrix,Map_3-07_DayOfTheDolphin,Map_3-08_TheColossalDonut,Map_3-09_Invasion,Map_3-10_BargainBin,Map_3-11_NeverQuest,Map_3-12_GrandTheftScratchy,Map_3-13_MedalOfHomer,Map_3-14_BigSuperHappy,Map_3-15_Rhymes,Map_3-16_MeetThyPlayer",
  "--debug"
 ]'
```

-   Name: "Convert Models (.preinstanced -> .blend)"
```pwsh
dotnet run -c Release --project EngineNet --framework net9.0 -- --game_module ".\EngineApps\Games\TheSimpsonsGame-PS3\" --script_type "lua" --script "{{Game_Root}}/operations/Blender/run.lua" --args '["--game-root","{{Game_Root}}","--verbose","--debug-sleep","--export","glb","fbx"]'
```
```pwsh
dotnet run -c Release --project EngineNet --framework net9.0 -- --game_module ".\EngineApps\Games\TheSimpsonsGame-PS3\" --script_type "lua"
--script "{{Game_Root}}/operations/Blender/run.lua" --args '[
	"--game-root", "{{Game_Root}}",
	"--base-dir", "{{Game_Root}}",
	"--operations-dir", "{{Game_Root}}/operations",
	"--blender-dir", "{{Game_Root}}/operations/Blender",
	"--preinstanced-dir", "{{Game_Root}}/GameFiles/STROUT",
	"--blend-dir", "{{Game_Root}}/GameFiles/STROUT",
	"--blank-blend", "{{Game_Root}}/blank.blend",
	"--root-drive", "{{Game_Root}}/TMP_TSG_LNKS"
]'
```




manual python run
# Replace the paths and values below with your actual test files and asset info
```pwsh
Tools/Blender/blender-4.0.2-windows-x64/blender.exe \
  -b path/to/your_asset.blend \
  --python EngineApps/Games/TheSimpsonsGame-PS3/operations/Blender/MainPreinstancedConvert.py \
  -- \
  path/to/your_asset.blend \
  path/to/your_asset.preinstanced \
  path/to/your_asset.glb \
  EngineApps/Games/TheSimpsonsGame-PS3/operations/Blender/PreinstancedImportExtension.py \
  true \
  false \
  EngineApps/Games/TheSimpsonsGame-PS3/operations/Blender \
  path/to/your_asset.fbx \
  asset_identifier \
  path/to/temp_addon_dir \
  glb,fbx
```

-   Name: "Convert Videos (.vp6 -> .ogv)"
```pwsh
 dotnet run -c Release
 --project EngineNet
 --framework net9.0
 --
 --game_module ".\EngineApps\Games\TheSimpsonsGame-PS3\"
 --script_type "engine"
 --script "format-convert"
 --tool "ffmpeg"
 --args '["-m", "ffmpeg", "--type", "video", "-s", "{{Game_Root}}/SourceFlat/Assets_1_Video_Movies", "-t", "{{Game_Root}}/GameFiles/STROUT/Assets_1_Video_Movies", "-f", "ffmpeg.exe", "-i", ".vp6", "-o", ".ogv"]'
```


-   Name: "Convert Audio (.snu -> .wav)"
```pwsh
 dotnet run -c Release
 --project EngineNet
 --framework net9.0
 --
 --game_module ".\EngineApps\Games\TheSimpsonsGame-PS3\"
 --script_type "engine"
 --script "format-convert"
 --tool "vgmstream"
 --args '["-m", "vgmstream", "--type", "audio", "-s", "{{Game_Root}}/SourceFlat/Assets_1_Audio_Streams", "-t", "{{Game_Root}}/GameFiles/STROUT/Assets_1_Audio_Streams", "--vgmstream-cli", "vgmstream-cli.exe", "-i", ".snu", "-o", ".wav", "--godot-compatible"]'
```



-   Name: "generate Godot Game (EXPERIMENTAL)"
```pwsh
 dotnet run -c Release
 --project EngineNet
 --framework net9.0
 --
 --game_module ".\EngineApps\Games\TheSimpsonsGame-PS3\"
 --script_type "lua"
 --script "{{Game_Root}}/Game/init.lua"
 --args '["--project-name", "SimpsonsGamePS3",
	"--repo-root", "{{Project_Root}}",
	"--sourcePath", "{{Game_Root}}/GameFiles/{{STROUT}}"]'
```

```pwsh
dotnet run -c Debug
 --project EngineNet
 --framework net9.0
 --
 --game_module "EngineApps\Games\TheSimpsonsGame-PS3\"
 --script_type "lua"
 --script "{{Project_Root}}\EngineApps\Games\TheSimpsonsGame-PS3\Game.Menu\init.lua"
 --args '["--project-name", "SimpsonsGamePS3", "--repo-root", "{{Project_Root}}", "--sourcePath", "{{Game_Root}}/EngineApps/GameFiles/STROUT"]'
```

```pwsh
dotnet run -c Debug
 --project EngineNet
 --framework net9.0
 --
 --game_module "EngineApps\Games\TheSimpsonsGame-PS3\"
 --script_type "lua"
 --script "{{Project_Root}}/EngineApps/Games/TheSimpsonsGame-PS3/Godot/Game.Dev/godot-init-V0.4.2.lua"
 --args '["--project-name", "Test", "--repo-root", "{{Project_Root}}", "--sourcePath", "{{Game_Root}}/GameFiles/{{STROUT}}"]'
```


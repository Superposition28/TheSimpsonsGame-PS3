

# Placeholders: Game_Root, Project_Root are built into the engine


## creates config.toml and ensures placeholders exist
## operations marked with init = true are not displayed in interactive UI or GUI lists to ensure they are always run every time
##  - ensure placeholders exist: SourcePath, Region
##  - create ./config.toml on first run if missing
##  - verify {{SourcePath}}/{{Region}}/{{PostSourcePath}} exists and is readable
## get user input for values like region and path if needed
[[operation]]
id = 0
init = true
run-all = true # rerun when using run-all to ensure config is valid
depends-on = []
script_type = "lua"
script = "{{Game_Root}}/operations/init.lua"


##
[[operation]]
id = -1
Name = "Download Required Tools"
run-all = true
depends-on = [0]
script_type = "engine"
script = "download-tools"
tools_manifest = "{{Game_Root}}/Tools.toml"
[[operation.prompts]]
type = "confirm"
Name = "force download"
message = "Force override existing downloads?"
default = false


[[operation]]
id = 1
Name = "Extract Archives (.STR)"
run-all = true
depends-on = [-1] # depends on qbms tool
script_type = "bms"
script = "{{Game_Root}}/operations/simpsons_str.bms"
input = "{{SourcePath}}/{{Region}}/{{PostSourcePath}}"
output = "{{Game_Root}}/GameFiles/{{Region}}-{{Type}}-{{audio_state}}-{{isRenamed}}" # always output to STROUT not {{STROUT}}
extension = ".str"


[[operation]]
id = 2
Name = "Copy Source Audio/Video Files"
run-all = true
depends-on = [1]
script_type = "lua"
script = "{{Game_Root}}/operations/CopySourceAudioVideo.lua"
args = [
    "--source", "{{SourcePath}}/{{Region}}/{{PostSourcePath}}",
    "--target", "{{Game_Root}}/GameFiles/{{Region}}-{{Type}}-{{audio_state}}-{{isRenamed}}"
]
[[operation.onsuccess]] # when successful, update {{isRenamed}} placeholder to "isRenamed"
Name = "set audio_state placeholder"
script_type = "engine"
script = "config"
args = ["--group", "placeholders", "--key", "audio_state", "--value", "audio_og", "--type", "string"]
[[operation.onsuccess]]
Name = "rename folder STROUT-{{Region}}-{{Type}}-{{audio_state}}-{{isRenamed}} to STROUT-{{Region}}-{{Type}}-{{audio_state}}-isRenamed"
script_type = "lua"
script = "{{Game_Root}}/rename.lua"
args = [
    "--old_path", "{{Game_Root}}/GameFiles/{{Region}}-{{Type}}-audio_none-{{isRenamed}}",
    "--new_path", "{{Game_Root}}/GameFiles/{{Region}}-{{Type}}-audio_og-{{isRenamed}}"
]

[[operation]]
id = 3
Name = "Extract Textures (.txd -> .dds)"
run-all = true
depends-on = [2] # depends on STR extraction
script_type = "engine"
script = "format-extract"
format = "txd"
args = ["{{Game_Root}}/GameFiles/{{Region}}-{{Type}}-{{audio_state}}-{{isRenamed}}"]

[[operation]]
id = 4
Name = "Rename base folders"
run-all = true
depends-on = [3]
script_type = "engine"
script = "rename-folders"
args = ["{{Game_Root}}/GameFiles/{{Region}}-{{Type}}-{{audio_state}}-{{isRenamed}}", "--map-db-file", "{{Game_Root}}/config/RenameMap.db"]
[[operation.onsuccess]] # when successful, update {{isRenamed}} placeholder to "isRenamed"
Name = "set isRenamed placeholder"
script_type = "engine"
script = "config"
args = ["--group", "placeholders", "--key", "isRenamed", "--value", "isRenamed", "--type", "string"]
[[operation.onsuccess]]
Name = "rename folder STROUT-{{Region}}-{{Type}}-{{audio_state}}-{{isRenamed}} to STROUT-{{Region}}-{{Type}}-{{audio_state}}-isRenamed"
script_type = "lua"
script = "{{Game_Root}}/rename.lua"
args = [
    "--old_path", "{{Game_Root}}/GameFiles/{{Region}}-{{Type}}-{{audio_state}}-notRenamed",
    "--new_path", "{{Game_Root}}/GameFiles/{{Region}}-{{Type}}-{{audio_state}}-isRenamed"
]

[[operation]]
id = 5
Name = "Reorganize Audio Files"
run-all = true
depends-on = [4]
script_type = "lua"
script = "{{Game_Root}}/operations/SetupAudioDir.lua"
args = ["{{Game_Root}}/GameFiles/{{Region}}-{{Type}}-{{audio_state}}-{{isRenamed}}"]
[[operation.onsuccess]] # when successful, update isRenamed placeholder to "isRenamed"
Name = "set audio_state placeholder"
script_type = "engine"
script = "config"
args = ["--group", "placeholders", "--key", "audio_state", "--value", "audio_reorg", "--type", "string"]
[[operation.onsuccess]]
Name = "rename folder STROUT-{{Region}}-{{Type}}-{{audio_state}}-{{isRenamed}} to STROUT-{{Region}}-{{Type}}-audio_reorg-{{isRenamed}}"
script_type = "lua"
script = "{{Game_Root}}/rename.lua"
args = [
    "--old_path", "{{Game_Root}}/GameFiles/{{Region}}-{{Type}}-audio_og-{{isRenamed}}",
    "--new_path", "{{Game_Root}}/GameFiles/{{Region}}-{{Type}}-audio_reorg-{{isRenamed}}"
]

[[operation]]
id = 6
Name = "Normalize folder structure"
run-all = true
depends-on = [5]
script_type = "lua"
script = "{{Game_Root}}/operations/DirectoryNormalizer/run.lua"
args = [
    "{{Game_Root}}/GameFiles/{{Region}}-{{Type}}-{{audio_state}}-{{isRenamed}}",
    "{{Game_Root}}/GameFiles/{{Region}}-{{Type}}Flattened-{{audio_state}}-{{isRenamed}}",
    "--copyonly", "A1_Audio",
    #"--copyonly", "A1_Video",
    "--copyonly", "audiostreams",
    #"--copyonly", "movies",
]
[[operation.onsuccess]]
Name = "update normalized placeholders"
script_type = "engine"
script = "config"
args = [
    "--group", "placeholders",
    "--set", "Type=FullFlattened:string"
]

[[operation]]
id = 7
Name = "Convert Textures (.dds -> .png)"
run-all = true
depends-on = [6]
script_type = "engine"
script = "format-convert"
tool = "ImageMagick"
args = [
    "--source", "{{Game_Root}}/GameFiles/{{Region}}-{{Type}}-{{audio_state}}-{{isRenamed}}",
    "--target", "{{Game_Root}}/GameFiles/{{Region}}-{{Type}}-{{audio_state}}-{{isRenamed}}",
    "--input-ext", ".dds",
    "--output-ext", ".png",
    "--replace"
]

## convert 3d models into .blend files, and export to glb for godot use
## auto apply textures within blender as well, however materials will need to be manually adjusted within godot
[[operation]]
id = 8
Name = "Convert Models (.preinstanced -> .blend)"
run-all = true
depends-on = [7] # depends on blender, str extraction for assets, and texture extraction and conversion for materials
script_type = "lua"
script = "{{Game_Root}}/operations/Blender/run.lua"
args = [
    "--game-root", "{{Game_Root}}",
    "--base-dir", "{{Game_Root}}",
    "--operations-dir", "{{Game_Root}}/operations",
    "--blender-dir", "{{Game_Root}}/operations/Blender",
    "--GameFiles", "{{Game_Root}}/GameFiles/{{Region}}-{{Type}}-{{audio_state}}-{{isRenamed}}",
    "--blank-blend", "{{Game_Root}}/blank.blend",
    "--symlink-path", "{{Game_Root}}/TMP_TSG_LNKS-{{Region}}-{{Type}}-{{audio_state}}-{{isRenamed}}", # symbolic link root to avoid path length issues
    "--asset-map-db", "{{Game_Root}}/GameFiles/config/{{Region}}-{{Type}}-{{audio_state}}-{{isRenamed}}/AssetMap.sqlite",
]
# for debugging
#[[operation.prompts]]
#type = "confirm"
#Name = "verbose"
#message = "Model Conversion: Enable verbose output?"
#default = false
#cli_arg = "--verbose"
# for debugging
#[[operation.prompts]]
#type = "confirm"
#Name = "debug mode"
#message = "Model Conversion: Enable debug mode?"
#default = false
#cli_arg = "--debug-sleep"
## for direct export to glb or fbx instead of just creating .blend files
[[operation.prompts]]
type = "confirm"
Name = "enable_export"
message = "Model Conversion: Export additional formats (FBX/GLTF)?"
default = true
## for direct export to glb or fbx instead of just creating .blend files
[[operation.prompts]]
type = "checkbox"
Name = "export_formats"
message = "Select export formats:"
default = ["glb"]
choices = ["fbx", "glb"]
cli_prefix = "--export"
condition = "enable_export"
validation = { required = true, message = "You must select at least one format." }


# convert all lh2 dialogue/subtitles to csv
[[operation]]
id = 9
Name = "Extract Dialogue/Subtitles (.lh2 -> .csv)"
run-all = true
depends-on = [6]
script_type = "lua"
script = "{{Game_Root}}/operations/lh2_to_csv.lua"
args = [
    "--input-dir", "{{Game_Root}}/GameFiles/{{Region}}-{{Type}}-{{audio_state}}-{{isRenamed}}"
    # auto output to same location as input files
]

## convert Audio into a usable format for godot
[[operation]]
id = 10
Name = "Convert Audio (.snu -> .wav)"
run-all = true
depends-on = [6] # depends on vgmstream being downloaded, could depend on audio reorg but that is technically optional
script_type = "engine"
script = "format-convert"
tool = "vgmstream"
args = [
    "-m", "vgmstream",
    "--type", "audio",
    ## doesnt need to specify the location of the audiostreams folder as its within the source path and {{STROUT}} and the only location snu files exist
    "-s", "{{Game_Root}}/GameFiles/{{Region}}-{{Type}}-{{audio_state}}-{{isRenamed}}",
    "-t", "{{Game_Root}}/GameFiles/{{Region}}-{{Type}}-{{audio_state}}-{{isRenamed}}",
    "-i", ".snu",
    "-o", ".wav",
    "--godot-compatible"
]


[[operation]]
id = 11
Name = "Convert Videos (.vp6 -> .ogv)"
run-all = true
depends-on = [6] # depends on ffmpeg being downloaded
script_type = "engine"
script = "format-convert"
tool = "ffmpeg"
args = [
    "-m", "ffmpeg",
    "--type", "video",
    "-s", "{{Game_Root}}/GameFiles/{{Region}}-{{Type}}-{{audio_state}}-{{isRenamed}}",
    "-t", "{{Game_Root}}/GameFiles/{{Region}}-{{Type}}-{{audio_state}}-{{isRenamed}}",
    "-i", ".vp6",
    "-o", ".ogv"
]


[[operation]]
id = 12
Name = "generate Godot Game (EXPERIMENTAL)"
run-all = false
depends-on = [8,9,10,11]
script_type = "lua"
script = "{{Game_Root}}/Godot/Game/godot-init-V0.5.1.lua"
args = [
    "--project-name", "SimpsonsGamePS3",
    "--repo-root", "{{Project_Root}}",
    "--sourcePath", "{{Game_Root}}/GameFiles/{{Region}}-{{Type}}-{{audio_state}}-{{isRenamed}}",
    "--iconPath", "{{SourcePath}}/{{Region}}/{{PostSourcePath}}",
    "--no-exit"
]

```pwsh
dotnet run -c Debug --project EngineNet --framework net10.0 --
 --game_module ".\EngineApps\Games\TheSimpsonsGame-PS3"
 --script_type lua
 --script "{{Game_Root}}/Godot/Game/godot-init-V0.5.1.lua"
 --args '
"--project-name", "SimpsonsGamePS311",
 "--repo-root", "{{Project_Root}}",
 "--sourcePath", "{{Game_Root}}/GameFiles/{{Region}}-{{Type}}-{{audio_state}}-{{isRenamed}}",
 "--iconPath", "{{SourcePath}}/{{Region}}/{{PostSourcePath}}",
 "--no-exit"
'
```
